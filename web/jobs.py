# -*- coding: utf-8 -*-
"""任务的生成、落盘和状态管理

任务在共享卷上的布局：

    data/jobs/<job_id>/
        config.yaml   本次任务的配置（不含 cookie）
        log           爬虫的输出
        status.json   状态 + 计数

web 和 runner 两个容器都读写这个目录：
web 负责建任务、读状态和日志；runner 负责跑爬虫、往 status.json 里写计数。
"""
import json
import os
import time
import uuid

import yaml

from yzw.config import ConfigError, build_config

# 仓库根目录（web/jobs.py -> web/ -> 仓库根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 状态机
STATUS_PENDING = 'pending'
STATUS_RUNNING = 'running'
STATUS_DONE = 'done'
STATUS_STOPPED = 'stopped'
STATUS_FAILED = 'failed'
STATUS_INTERRUPTED = 'interrupted'

# 还在跑的状态 —— 用来判断"能不能再起一个任务"
ACTIVE_STATUSES = (STATUS_PENDING, STATUS_RUNNING)

# 一次最多读多少日志
LOG_CHUNK_SIZE = 1024 * 1024


# ----------------------------------------------------------------------
# 目录
# ----------------------------------------------------------------------
def data_dir():
    """共享卷里的数据目录（容器里是 /app/data）"""
    return os.environ.get('YZW_DATA_DIR') or os.path.join(PROJECT_ROOT, 'data')


def result_dir():
    """共享卷里的结果目录（容器里是 /app/result）"""
    return os.environ.get('YZW_RESULT_DIR') or os.path.join(PROJECT_ROOT, 'result')


def jobs_dir():
    return os.path.join(data_dir(), 'jobs')


def job_dir(job_id):
    return os.path.join(jobs_dir(), job_id)


def config_path(job_id):
    return os.path.join(job_dir(job_id), 'config.yaml')


def log_path(job_id):
    return os.path.join(job_dir(job_id), 'log')


def status_path(job_id):
    return os.path.join(job_dir(job_id), 'status.json')


def new_job_id():
    """任务号：时间戳 + 随机后缀，按时间排序也好看"""
    return '{}-{}'.format(time.strftime('%Y%m%d-%H%M%S'), uuid.uuid4().hex[:6])


# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------
def spider_for(degree):
    """学位层次 -> spider 名字

    both 必须起 all：master spider 遇到 degree=both 只打一条 WARNING
    就零请求退出，退出码还是 0，看着像"成功但没数据"。
    """
    degree = (degree or '').strip().lower()
    if degree in ('master', 'doctor'):
        return degree
    if degree == 'both':
        return 'all'
    raise ValueError('学位层次只能是 master / doctor / both，实际是 %s' % degree)


def build_job_config(payload, output_directory=None):
    """把前端的选择翻译成爬虫的配置字典

    空的省份 / 学校 / 专业都表示"全部"。
    登录态不写在这里 —— 它只走子进程的 YZW_COOKIE 环境变量，
    落盘的 YAML 里不留 cookie。

    生成之后立刻用爬虫自己的 build_config() 校验一遍：
    省份码写错之类的问题当场就报错，不用等子进程起来才发现。
    """
    options = payload.options
    degree = (payload.degree or 'master').strip().lower()
    if degree not in ('master', 'doctor', 'both'):
        raise ValueError('学位层次只能是 master / doctor / both，实际是 %s' % degree)

    directory = output_directory or result_dir()
    config = {
        'degree': degree,
        'province': list(payload.province) or 'all',
        'schools': list(payload.schools) or 'all',
        'majors': list(payload.majors) or 'all',
        'output': {
            # 必须是绝对路径：相对路径是按子进程的 CWD 解析的，
            # 子进程的 CWD 跟 web 容器不一定一样
            'directory': os.path.abspath(directory),
            'excel': options.excel,
            'excel_max_schools': options.excel_max_schools,
        },
        'request': {
            'delay': options.delay,
            'concurrency': options.concurrency,
            'max_schools': options.max_schools,
        },
    }

    try:
        build_config(config)
    except ConfigError as error:
        raise ValueError(str(error))
    return config


def write_job_config(job_id, config):
    """把配置写成 YAML

    allow_unicode 让中文专业名保持可读；
    PyYAML 会自动给 '32'、'10284' 加引号，正好是配置层期望的字符串。
    """
    path = config_path(job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        yaml.safe_dump(config, file, allow_unicode=True, sort_keys=False)
    return path


def safe_join(root, relative):
    """把相对路径拼到根目录下，并挡住路径穿越

    realpath 之后再比对前缀，'../' 和符号链接都挡得住。
    """
    root_real = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root_real, relative))
    if target != root_real and not target.startswith(root_real + os.sep):
        raise ValueError('路径越界：%s' % relative)
    return target


# ----------------------------------------------------------------------
# 状态
# ----------------------------------------------------------------------
def default_status(job_id, **fields):
    """一个任务的初始状态"""
    status = {
        'id': job_id,
        'status': STATUS_PENDING,
        'degree': 'master',
        'spider': 'master',
        'province': [],
        'schools': [],
        'majors': [],
        'created_at': now(),
        'started_at': '',
        'finished_at': '',
        'items': 0,
        'items_by_degree': {},
        'schools_done': 0,
        'stop_requested': False,
        'exit_code': None,
        'message': '',
    }
    status.update(fields)
    return status


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def read_status(job_id):
    """读任务状态；文件还没有就返回空状态"""
    path = status_path(job_id)
    if not os.path.exists(path):
        return default_status(job_id)
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, ValueError):
        return default_status(job_id)
    if not isinstance(data, dict):
        return default_status(job_id)
    merged = default_status(job_id)
    merged.update(data)
    return merged


def write_status(job_id, status):
    """写任务状态

    先写临时文件再改名 —— 读到一半的 JSON 会让前端直接崩。
    """
    path = status_path(job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as file:
        json.dump(status, file, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return status


def list_job_ids():
    """所有任务号，按时间倒序"""
    root = jobs_dir()
    if not os.path.isdir(root):
        return []
    ids = []
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root, name)):
            ids.append(name)
    return sorted(ids, reverse=True)


def list_jobs():
    """所有任务的状态，倒序"""
    return [read_status(job_id) for job_id in list_job_ids()]


def active_job():
    """正在跑的任务；没有就返回 None

    研招网限流很硬，而且两个爬虫同时写 data/schools.json
    （merge_catalog 是"读-改-写"）会互相覆盖 —— 所以同时只跑一个。
    """
    for status in list_jobs():
        if status.get('status') in ACTIVE_STATUSES:
            return status
    return None


# ----------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------
def read_log(job_id, offset=0, limit=400):
    """读一段日志

    按字节偏移往后读 —— 一次全量能出几百 MB 的日志，
    用行号定位会越读越慢。

    最后一行没写完（还缺换行）就留在原地等下次，
    否则页面会看到半截日志。
    """
    path = log_path(job_id)
    if not os.path.exists(path):
        return {'offset': offset, 'next_offset': offset, 'lines': [], 'eof': True}

    size = os.path.getsize(path)
    if offset > size:
        # 日志被重建过，从头再来
        offset = 0

    with open(path, 'rb') as file:
        file.seek(offset)
        chunk = file.read(LOG_CHUNK_SIZE)

    if not chunk:
        return {'offset': offset, 'next_offset': offset, 'lines': [], 'eof': True}

    end = chunk.rfind(b'\n')
    if end < 0:
        # 一行都还没写完
        return {'offset': offset, 'next_offset': offset, 'lines': [], 'eof': False}

    raw_lines = chunk[:end + 1].split(b'\n')
    if raw_lines and raw_lines[-1] == b'':
        raw_lines.pop()

    lines = []
    consumed = 0
    for raw in raw_lines:
        lines.append(raw.decode('utf-8', errors='replace'))
        consumed += len(raw) + 1
        if limit and len(lines) >= limit:
            break

    next_offset = offset + consumed
    return {
        'offset': offset,
        'next_offset': next_offset,
        'lines': lines,
        'eof': next_offset >= size,
    }


# ----------------------------------------------------------------------
# 结果文件
# ----------------------------------------------------------------------
def list_result_files(limit=200):
    """结果目录下的文件，最新的排在前面"""
    root = result_dir()
    if not os.path.isdir(root):
        return []

    files = []
    for base, _, names in os.walk(root):
        for name in names:
            path = os.path.join(base, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            files.append({
                'name': name,
                'path': os.path.relpath(path, root),
                'size': stat.st_size,
                'modified': time.strftime('%Y-%m-%d %H:%M:%S',
                                         time.localtime(stat.st_mtime)),
            })

    files.sort(key=lambda item: (item['modified'], item['path']), reverse=True)
    return files[:limit]
