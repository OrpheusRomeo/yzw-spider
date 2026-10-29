# -*- coding: utf-8 -*-
"""执行器的单元测试：起任务、读日志、停任务

这里用的是假命令，不会真的去抓研招网 ——
要验证的是"任务怎么被拉起来、状态怎么落盘、日志怎么读、怎么停"。

    pytest tests/
"""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import jobs  # noqa: E402


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / 'data'
    path.mkdir()
    monkeypatch.setenv('YZW_DATA_DIR', str(path))
    monkeypatch.setenv('YZW_RESULT_DIR', str(tmp_path / 'result'))
    return path


@pytest.fixture
def runner(data_dir, monkeypatch):
    """一个执行器实例，命令换成假命令"""
    import web.runner as runner_module

    def fake_command(spider, config, log_level='INFO'):
        # 假爬虫：打两行进度标记，然后退出
        return [sys.executable, '-c',
                'import sys\n'
                'print("YZW_PROGRESS {\\"kind\\": \\"school\\", \\"index\\": 1}")\n'
                'print("普通日志一行")\n'
                'print("YZW_PROGRESS {\\"kind\\": \\"item\\", \\"count\\": 7, '
                '\\"degree\\": \\"master\\"}")\n'
                'sys.exit(0)\n']

    monkeypatch.setattr(runner_module, 'build_command', fake_command)
    runner_module._running.clear()
    return runner_module


def make_job(data_dir):
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    jobs.write_job_config(job_id, {'degree': 'master'})
    jobs.write_status(job_id, jobs.default_status(job_id))
    return job_id


# ----------------------------------------------------------------------
# 进度标记 -> 状态
# ----------------------------------------------------------------------
def test_apply_progress_counts_schools_and_items():
    from web.runner import apply_progress

    status = jobs.default_status('x')
    apply_progress(status, {'kind': 'school', 'index': 3, 'name': '南京大学'})
    apply_progress(status, {'kind': 'item', 'count': 120, 'degree': 'master'})
    apply_progress(status, {'kind': 'item', 'count': 40, 'degree': 'doctor'})

    assert status['schools_done'] == 3
    assert status['current_school'] == '南京大学'
    assert status['items_by_degree'] == {'master': 120, 'doctor': 40}
    assert status['items'] == 160


def test_apply_progress_keeps_the_largest_count():
    """done 标记里的条数比 item 标记小的时候不能把计数改小"""
    from web.runner import apply_progress

    status = jobs.default_status('x')
    apply_progress(status, {'kind': 'item', 'count': 120, 'degree': 'master'})
    apply_progress(status, {'kind': 'done', 'items': 100, 'degree': 'master'})
    assert status['items'] == 120


# ----------------------------------------------------------------------
# 起任务
# ----------------------------------------------------------------------
def test_run_writes_log_and_finishes(runner, data_dir):
    """假爬虫跑完之后：日志落盘、状态变成 done、条数对得上"""
    from fastapi.testclient import TestClient

    job_id = make_job(data_dir)

    # 用上下文管理器，portal 的事件循环才会一直活着 ——
    # 后台任务是在起任务的那个循环里跑的
    with TestClient(runner.app) as client:
        response = client.post('/run', json={
            'job_id': job_id, 'spider': 'master',
            'config': jobs.config_path(job_id),
        })
        assert response.status_code == 200

        # 等子进程跑完
        for _ in range(100):
            status = jobs.read_status(job_id)
            if status['status'] in (jobs.STATUS_DONE, jobs.STATUS_FAILED):
                break
            time.sleep(0.05)

    status = jobs.read_status(job_id)
    assert status['status'] == jobs.STATUS_DONE
    assert status['exit_code'] == 0
    assert status['items'] == 7
    assert status['schools_done'] == 1
    assert status['finished_at']

    chunk = jobs.read_log(job_id)
    text = '\n'.join(chunk['lines'])
    assert '普通日志一行' in text


def test_run_rejects_a_missing_config(runner, data_dir):
    from fastapi.testclient import TestClient

    client = TestClient(runner.app)
    response = client.post('/run', json={
        'job_id': 'nope', 'spider': 'master',
        'config': str(data_dir / 'missing.yaml'),
    })
    assert response.status_code == 400


def test_run_rejects_a_duplicate_job(runner, data_dir):
    from fastapi.testclient import TestClient

    job_id = make_job(data_dir)
    client = TestClient(runner.app)

    def slow_command(spider, config, log_level='INFO'):
        return [sys.executable, '-c', 'import time; time.sleep(30)\n']

    runner.build_command = slow_command
    assert client.post('/run', json={
        'job_id': job_id, 'spider': 'master',
        'config': jobs.config_path(job_id)}).status_code == 200

    second = client.post('/run', json={
        'job_id': job_id, 'spider': 'master',
        'config': jobs.config_path(job_id)})
    assert second.status_code == 409

    client.post('/stop/%s' % job_id)


# ----------------------------------------------------------------------
# 停任务
# ----------------------------------------------------------------------
def test_stop_ends_the_task(runner, data_dir):
    """停掉之后状态是 stopped，进程真的退出了"""
    from fastapi.testclient import TestClient

    job_id = make_job(data_dir)

    def slow_command(spider, config, log_level='INFO'):
        return [sys.executable, '-c',
                'import sys, time\n'
                'print("YZW_PROGRESS {\\"kind\\": \\"school\\", \\"index\\": 1}")\n'
                'sys.stdout.flush()\n'
                'time.sleep(60)\n']

    runner.build_command = slow_command

    with TestClient(runner.app) as client:
        assert client.post('/run', json={
            'job_id': job_id, 'spider': 'master',
            'config': jobs.config_path(job_id)}).status_code == 200

        # 等它真的起来了
        for _ in range(100):
            if jobs.read_status(job_id)['status'] == jobs.STATUS_RUNNING:
                break
            time.sleep(0.05)

        assert client.post('/stop/%s' % job_id).status_code == 200

        for _ in range(100):
            status = jobs.read_status(job_id)
            if status['status'] in (jobs.STATUS_STOPPED, jobs.STATUS_FAILED):
                break
            time.sleep(0.05)

    status = jobs.read_status(job_id)
    assert status['status'] == jobs.STATUS_STOPPED
    assert status['stop_requested'] is True


def test_stop_rejects_an_unknown_job(runner, data_dir):
    from fastapi.testclient import TestClient

    client = TestClient(runner.app)
    assert client.post('/stop/没有这个任务').status_code == 404


# ----------------------------------------------------------------------
# 残留状态
# ----------------------------------------------------------------------
def test_interrupted_jobs_are_marked_on_startup(runner, data_dir):
    """执行器重启之后，残留的 running 要改成 interrupted

    不改的话页面会一直显示"运行中"，但进程早没了。
    """
    job_id = make_job(data_dir)
    jobs.write_status(job_id, jobs.default_status(job_id,
                                                  status=jobs.STATUS_RUNNING))

    runner.mark_interrupted_jobs()

    status = jobs.read_status(job_id)
    assert status['status'] == jobs.STATUS_INTERRUPTED
    assert status['finished_at']
