# -*- coding: utf-8 -*-
"""Web 控制台的后端

干四件事：

1. 给前端提供选项（省份、院校、专业代码表、某校专业）
2. 把前端的选单翻译成爬虫配置，写进共享卷，起一个任务
3. 把任务状态和日志从共享卷里读出来给前端
4. 把结果文件列出来、下载

跟执行器（web.runner）之间只走几个 HTTP 接口，
状态、日志、结果都靠共享卷传 —— 少一份要同步的状态。

**这个服务没有认证**，只能放在内网或者本机用。
"""
import os
import threading
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web import jobs, options
from web.schemas import JobCreate, JobOut

# 执行器的地址（compose 里是 http://runner:8001）
RUNNER_URL = os.environ.get('YZW_RUNNER_URL') or 'http://127.0.0.1:8001'

# 前端打包产物
FRONTEND_DIR = os.environ.get('YZW_FRONTEND_DIR') or os.path.join(
    jobs.PROJECT_ROOT, 'frontend', 'dist')

# 同时只允许一个任务 —— 见 jobs.active_job
_create_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    app.state.client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.client.aclose()


app = FastAPI(title='研招网爬虫控制台', lifespan=lifespan)


# ----------------------------------------------------------------------
# 选项
# ----------------------------------------------------------------------
@app.get('/api/options/provinces')
def get_provinces():
    """31 个省 + 各省院校数"""
    return options.provinces()


@app.get('/api/options/schools')
def get_schools(province: str = '', kw: str = ''):
    """院校列表，可按省份和校名关键词筛"""
    return options.schools(province=province, keyword=kw)


@app.get('/api/options/majors')
async def get_majors():
    """门类 / 一级学科代码表（转发给执行器，那边才有网）"""
    groups = await _runner_get('/codes')
    return [{'code': group.get('code') or '',
             'name': group.get('name') or '',
             'children': group.get('children') or []}
            for group in groups]


@app.get('/api/majors-of-school')
async def get_majors_of_school(dwdm: str = ''):
    """实时查某所学校开设的专业（转发给执行器）"""
    if not dwdm.strip():
        raise HTTPException(400, '缺少 dwdm')
    return await _runner_get('/majors-of-school', {'dwdm': dwdm.strip()})


# ----------------------------------------------------------------------
# 任务
# ----------------------------------------------------------------------
@app.post('/api/jobs', response_model=JobOut, status_code=201)
async def create_job(payload: JobCreate):
    """新建一个抓取任务

    同时只允许一个任务在跑 —— 研招网限流很硬，
    而且两个爬虫同时写 data/schools.json 会互相覆盖。
    """
    with _create_lock:
        active = jobs.active_job()
        if active:
            raise HTTPException(
                409, '已经有任务在跑（{}，{}），先停掉它'.format(
                    active.get('id'), active.get('status')))

        try:
            config = jobs.build_job_config(payload)
            spider = jobs.spider_for(payload.degree)
        except ValueError as error:
            raise HTTPException(400, str(error))

        job_id = jobs.new_job_id()
        os.makedirs(jobs.job_dir(job_id), exist_ok=True)
        jobs.write_job_config(job_id, config)

        status = jobs.default_status(
            job_id,
            degree=payload.degree,
            spider=spider,
            province=list(payload.province),
            schools=list(payload.schools),
            majors=list(payload.majors),
        )
        jobs.write_status(job_id, status)

        try:
            await _runner_post('/run', {
                'job_id': job_id,
                'spider': spider,
                'config': jobs.config_path(job_id),
            })
        except httpx.HTTPError as error:
            # 起不来就把半成品收拾掉，别留个永远 running 的任务
            status['status'] = jobs.STATUS_FAILED
            status['message'] = '执行器起不来：%s' % error
            status['finished_at'] = jobs.now()
            jobs.write_status(job_id, status)
            raise HTTPException(502, '执行器起不来：%s' % error)

    return jobs.read_status(job_id)


@app.get('/api/jobs')
def get_jobs():
    """任务列表，最新的在前"""
    return jobs.list_jobs()


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    """任务状态"""
    if not os.path.isdir(jobs.job_dir(job_id)):
        raise HTTPException(404, '任务 %s 不存在' % job_id)
    return jobs.read_status(job_id)


@app.get('/api/jobs/{job_id}/logs')
def get_job_logs(job_id: str, offset: int = 0, limit: int = 400):
    """增量日志

    offset 是字节偏移 —— 前端每次拿 next_offset 接着往下读。
    """
    if not os.path.isdir(jobs.job_dir(job_id)):
        raise HTTPException(404, '任务 %s 不存在' % job_id)
    return jobs.read_log(job_id, offset=offset, limit=limit)


@app.post('/api/jobs/{job_id}/stop')
async def stop_job(job_id: str):
    """停任务"""
    if not os.path.isdir(jobs.job_dir(job_id)):
        raise HTTPException(404, '任务 %s 不存在' % job_id)
    try:
        return await _runner_post('/stop/%s' % job_id, {})
    except httpx.HTTPStatusError as error:
        raise HTTPException(error.response.status_code, error.response.text)
    except httpx.HTTPError as error:
        raise HTTPException(502, '执行器联系不上：%s' % error)


# ----------------------------------------------------------------------
# 结果
# ----------------------------------------------------------------------
@app.get('/api/results')
def get_results():
    """结果文件列表"""
    return jobs.list_result_files()


@app.get('/api/results/download')
def download_result(path: str = ''):
    """下载结果文件

    path 是相对于结果目录的路径 —— 目录外面的一律拒绝。
    """
    if not path:
        raise HTTPException(400, '缺少 path')
    try:
        target = jobs.safe_join(jobs.result_dir(), path)
    except ValueError as error:
        raise HTTPException(400, str(error))
    if not os.path.isfile(target):
        raise HTTPException(404, '文件不存在')
    return FileResponse(target, filename=os.path.basename(target))


# ----------------------------------------------------------------------
# 跟执行器说话
# ----------------------------------------------------------------------
async def _runner_get(path, params=None):
    try:
        response = await app.state.client.get(
            RUNNER_URL + path, params=params or {})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        raise HTTPException(error.response.status_code, error.response.text)
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(502, '执行器联系不上：%s' % error)


async def _runner_post(path, payload):
    try:
        response = await app.state.client.post(RUNNER_URL + path, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        raise HTTPException(error.response.status_code, error.response.text)
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(502, '执行器联系不上：%s' % error)


# ----------------------------------------------------------------------
# 前端页面
# ----------------------------------------------------------------------
if os.path.isdir(FRONTEND_DIR):
    # 挂在最后 —— 挂早了会把 /api 下的接口也吃掉
    app.mount('/', StaticFiles(directory=FRONTEND_DIR, html=True), name='frontend')
else:
    @app.get('/')
    def index():
        return {
            'message': '前端还没打包。开发时用 cd frontend && npm run dev，'
                       '或者先 npm run build 再重启这个服务。',
            'api': '/docs',
        }
