# -*- coding: utf-8 -*-
"""执行器：真正跑爬虫的那个容器

爬虫必须跑在子进程里 —— Twisted 的 reactor 是进程级单例且不可重启，
同一个进程里跑完第一个任务，第二个任务必然 ReactorNotRestartable。
子进程顺带解决崩溃隔离、内存隔离、日志流式输出三个问题。

对外只有几个接口，web 那边通过它们驱动：

    POST /run              起一个爬虫
    POST /stop/{job_id}    停一个爬虫
    GET  /codes            门类 / 一级学科代码表
    GET  /majors-of-school 某所学校开设的专业
    GET  /health           活着没
"""
import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from yzw.progress import parse_progress_line

from web import jobs
from web.majors import code_table, majors_of_school

# 爬虫进程的工作目录 —— 仓库根（有 scrapy.cfg）
PROJECT_ROOT = jobs.PROJECT_ROOT

# 停止之后等多久还没退就 SIGKILL
KILL_AFTER = 15

# 正在跑的任务：job_id -> {'proc': ..., 'stop_requested': bool}
_running = {}


class RunRequest(BaseModel):
    """起一个爬虫"""

    job_id: str
    spider: str = 'master'
    config: str = ''          # 生成的 YAML 的绝对路径
    log_level: str = 'INFO'


@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    mark_interrupted_jobs()
    yield
    await app.state.client.aclose()


app = FastAPI(title='研招网爬虫执行器', lifespan=lifespan)


# ----------------------------------------------------------------------
# 状态
# ----------------------------------------------------------------------
def mark_interrupted_jobs():
    """把残留的"运行中"改成"已中断"

    容器重启之后原来那个爬虫进程早就没了，
    状态还停在 running 的话页面会一直转圈。
    """
    for status in jobs.list_jobs():
        if status.get('status') in jobs.ACTIVE_STATUSES:
            status['status'] = jobs.STATUS_INTERRUPTED
            status['finished_at'] = jobs.now()
            status['message'] = '执行器重启，任务已中断'
            jobs.write_status(status['id'], status)


def apply_progress(status, progress):
    """把一条进度标记并进任务状态"""
    kind = progress.get('kind')
    by_degree = status.setdefault('items_by_degree', {})

    if kind == 'school':
        index = progress.get('index') or 0
        status['schools_done'] = max(status.get('schools_done') or 0, index)
        if progress.get('name'):
            status['current_school'] = progress['name']

    elif kind == 'item':
        degree = progress.get('degree') or ''
        count = progress.get('count') or 0
        if degree:
            by_degree[degree] = max(by_degree.get(degree, 0), count)
        status['items'] = sum(by_degree.values())

    elif kind == 'done':
        if 'schools' in progress:
            status['schools_done'] = max(status.get('schools_done') or 0,
                                         progress.get('schools') or 0)
        if 'items' in progress:
            degree = progress.get('degree') or ''
            count = progress.get('items') or 0
            if degree:
                by_degree[degree] = max(by_degree.get(degree, 0), count)
            status['items'] = sum(by_degree.values())

    return status


# ----------------------------------------------------------------------
# 起 / 停
# ----------------------------------------------------------------------
def build_command(spider, config, log_level='INFO'):
    """爬虫的命令行

    单独抽出来是为了能测：测试里换成一个假命令，
    不用真的去抓研招网也能验证起任务、读日志、停任务这一套。
    """
    return [
        sys.executable, '-m', 'scrapy', 'crawl', spider,
        '-a', 'config=%s' % config,
        '-s', 'LOG_LEVEL=%s' % log_level,
    ]


def build_env(config):
    """子进程的环境变量"""
    env = dict(os.environ)
    # 管道下 stdout 是块缓冲的，不设这个日志和进度标记会晚几十秒才出现
    env['PYTHONUNBUFFERED'] = '1'
    # all spider 的子 spider 是另起实例读配置的，
    # 环境变量不指过去的话它们会读到仓库根目录那份 config.yaml
    env['YZW_CONFIG'] = config
    return env


@app.post('/run')
async def run(payload: RunRequest):
    """起一个爬虫子进程"""
    if payload.job_id in _running:
        raise HTTPException(409, '任务 %s 已经在跑了' % payload.job_id)

    config = payload.config or jobs.config_path(payload.job_id)
    if not os.path.exists(config):
        raise HTTPException(400, '配置文件不存在：%s' % config)

    command = build_command(payload.spider, config, payload.log_level)
    env = build_env(config)

    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=PROJECT_ROOT,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        # 单独一个进程组 —— 停止时 killpg 不会误伤执行器自己
        start_new_session=True,
    )

    _running[payload.job_id] = {'proc': proc, 'stop_requested': False}

    status = jobs.read_status(payload.job_id)
    status['status'] = jobs.STATUS_RUNNING
    status['started_at'] = jobs.now()
    jobs.write_status(payload.job_id, status)

    asyncio.create_task(_watch(payload.job_id, proc))
    return {'id': payload.job_id, 'status': jobs.STATUS_RUNNING, 'pid': proc.pid}


async def _watch(job_id, proc):
    """读子进程的输出，写日志、解析进度，等它退出"""
    path = jobs.log_path(job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    status = jobs.read_status(job_id)
    try:
        with open(path, 'ab') as log_file:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode('utf-8', errors='replace')
                log_file.write(text.encode('utf-8'))
                log_file.flush()

                progress = parse_progress_line(text)
                if progress:
                    status = apply_progress(status, progress)
                    jobs.write_status(job_id, status)
    except asyncio.CancelledError:  # pragma: no cover - 服务关停时才会走到
        raise
    except Exception as error:  # pragma: no cover - 兜底，别让读日志失败把任务带崩
        status['message'] = '读日志出错：%s' % error

    code = await proc.wait()
    entry = _running.pop(job_id, {}) or {}
    stop_requested = entry.get('stop_requested', False)

    status = jobs.read_status(job_id)
    status['exit_code'] = code
    status['finished_at'] = jobs.now()
    if stop_requested:
        status['status'] = jobs.STATUS_STOPPED
    elif code == 0:
        status['status'] = jobs.STATUS_DONE
    else:
        status['status'] = jobs.STATUS_FAILED
        status['message'] = status.get('message') or '爬虫退出码 %s' % code
    jobs.write_status(job_id, status)


@app.post('/stop/{job_id}')
async def stop(job_id: str):
    """停一个正在跑的爬虫

    发 SIGTERM —— Scrapy 收到之后会走优雅停机，
    close_spider 照常执行（文件句柄关掉、Excel 落盘），数据不丢。
    """
    entry = _running.get(job_id)
    if entry is None:
        raise HTTPException(404, '任务 %s 不在运行' % job_id)

    proc = entry['proc']
    if proc.returncode is not None:
        raise HTTPException(409, '任务 %s 已经结束了' % job_id)

    entry['stop_requested'] = True

    status = jobs.read_status(job_id)
    status['stop_requested'] = True
    jobs.write_status(job_id, status)

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()

    asyncio.create_task(_kill_if_stuck(job_id, proc))
    return {'id': job_id, 'status': 'stopping'}


async def _kill_if_stuck(job_id, proc):
    """15 秒还没退就强杀

    用轮询 returncode 而不是再调一次 proc.wait() ——
    两个任务等同一个进程退出容易踩到 asyncio 的坑。
    """
    for _ in range(KILL_AFTER * 10):
        if proc.returncode is not None:
            return
        await asyncio.sleep(0.1)

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass

    status = jobs.read_status(job_id)
    status['message'] = '停止超时，已强制结束'
    jobs.write_status(job_id, status)


# ----------------------------------------------------------------------
# 选项
# ----------------------------------------------------------------------
@app.get('/codes')
async def codes():
    """门类 / 一级学科代码表（带 7 天缓存）"""
    try:
        groups = await code_table(app.state.client)
    except Exception as error:
        raise HTTPException(502, '取代码表失败：%s' % error)
    return groups


@app.get('/majors-of-school')
async def majors_of_school_endpoint(dwdm: str):
    """某所学校开设的专业"""
    if not dwdm.strip():
        raise HTTPException(400, '缺少 dwdm')
    try:
        majors, truncated = await majors_of_school(app.state.client, dwdm.strip())
    except Exception as error:
        raise HTTPException(502, '取专业失败：%s' % error)
    return {'dwdm': dwdm.strip(), 'total': len(majors),
            'majors': majors, 'truncated': truncated}


@app.get('/health')
async def health():
    return {'ok': True, 'running': sorted(_running.keys())}
