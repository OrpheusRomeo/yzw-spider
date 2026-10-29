# -*- coding: utf-8 -*-
"""Web 控制台的单元测试：配置生成、路径安全、任务调度

    pytest tests/
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import jobs  # noqa: E402
from web.schemas import JobCreate, JobOptions  # noqa: E402


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """把共享卷指到临时目录，别动仓库里的 data/"""
    path = tmp_path / 'data'
    path.mkdir()
    monkeypatch.setenv('YZW_DATA_DIR', str(path))
    monkeypatch.setenv('YZW_RESULT_DIR', str(tmp_path / 'result'))
    return path


# ----------------------------------------------------------------------
# 学位层次 -> spider
# ----------------------------------------------------------------------
def test_spider_for_master_and_doctor():
    assert jobs.spider_for('master') == 'master'
    assert jobs.spider_for('doctor') == 'doctor'


def test_spider_for_both_is_all():
    """both 必须起 all spider

    master spider 遇到 degree=both 只打一条 WARNING 就零请求退出，
    退出码还是 0 —— 看着像"成功但没数据"。
    """
    assert jobs.spider_for('both') == 'all'


def test_spider_for_rejects_unknown_degree():
    with pytest.raises(ValueError):
        jobs.spider_for('xyz')


# ----------------------------------------------------------------------
# 配置生成
# ----------------------------------------------------------------------
def test_build_job_config_maps_the_choices():
    payload = JobCreate(degree='master', province=['32'], schools=['10284'],
                        majors=['应用经济学'])
    config = jobs.build_job_config(payload, output_directory='/tmp/out')

    assert config['degree'] == 'master'
    assert config['province'] == ['32']
    assert config['schools'] == ['10284']
    assert config['majors'] == ['应用经济学']
    assert config['output']['directory'] == '/tmp/out'


def test_build_job_config_empty_choices_mean_all():
    """空数组要归一化成 all —— schools: [] 会让爬虫直接报错退出"""
    config = jobs.build_job_config(JobCreate(), output_directory='/tmp/out')

    assert config['province'] == 'all'
    assert config['schools'] == 'all'
    assert config['majors'] == 'all'


def test_build_job_config_output_directory_is_absolute():
    """相对路径是按子进程的 CWD 解析的，必须给绝对路径"""
    config = jobs.build_job_config(JobCreate(), output_directory='result')
    assert os.path.isabs(config['output']['directory'])


def test_build_job_config_never_writes_the_cookie():
    """登录态只走环境变量，落盘的 YAML 里不能有 cookie"""
    payload = JobCreate()
    config = jobs.build_job_config(payload, output_directory='/tmp/out')
    assert 'cookie' not in config

    text = json.dumps(config, ensure_ascii=False)
    assert 'cookie' not in text.lower()


def test_build_job_config_rejects_unknown_province():
    """省份码写错要当场报错，不能等爬虫起来才发现"""
    payload = JobCreate(province=['99'])
    with pytest.raises(ValueError) as error:
        jobs.build_job_config(payload, output_directory='/tmp/out')
    assert '99' in str(error.value)


def test_build_job_config_carries_the_options():
    payload = JobCreate(options=JobOptions(delay=0.5, concurrency=2,
                                           max_schools=3, excel='never'))
    config = jobs.build_job_config(payload, output_directory='/tmp/out')

    assert config['request']['delay'] == 0.5
    assert config['request']['concurrency'] == 2
    assert config['request']['max_schools'] == 3
    assert config['output']['excel'] == 'never'


# ----------------------------------------------------------------------
# 路径安全
# ----------------------------------------------------------------------
def test_safe_join_allows_paths_inside(tmp_path):
    target = jobs.safe_join(str(tmp_path), 'master/a.csv')
    assert target.startswith(str(tmp_path))


def test_safe_join_blocks_traversal(tmp_path):
    """结果下载不能让人读到目录外面的文件"""
    with pytest.raises(ValueError):
        jobs.safe_join(str(tmp_path), '../../etc/passwd')


# ----------------------------------------------------------------------
# 状态与日志
# ----------------------------------------------------------------------
def test_status_round_trip(data_dir):
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)

    status = jobs.default_status(job_id, degree='doctor')
    jobs.write_status(job_id, status)

    loaded = jobs.read_status(job_id)
    assert loaded['id'] == job_id
    assert loaded['degree'] == 'doctor'


def test_read_log_returns_lines(data_dir):
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    with open(jobs.log_path(job_id), 'w', encoding='utf-8') as file:
        file.write('第一行\n第二行\n')

    chunk = jobs.read_log(job_id)
    assert chunk['lines'] == ['第一行', '第二行']
    assert chunk['next_offset'] > 0


def test_read_log_resumes_from_offset(data_dir):
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    with open(jobs.log_path(job_id), 'w', encoding='utf-8') as file:
        file.write('第一行\n第二行\n')

    first = jobs.read_log(job_id)
    second = jobs.read_log(job_id, offset=first['next_offset'])
    assert second['lines'] == []


def test_read_log_keeps_incomplete_last_line(data_dir):
    """最后一行还没写完就留着等下次，不能显示半截日志"""
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    with open(jobs.log_path(job_id), 'w', encoding='utf-8') as file:
        file.write('完整的一行\n还没写完')

    chunk = jobs.read_log(job_id)
    assert chunk['lines'] == ['完整的一行']
    assert chunk['next_offset'] == len('完整的一行\n'.encode('utf-8'))


def test_active_job_finds_the_running_one(data_dir):
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    jobs.write_status(job_id, jobs.default_status(job_id,
                                                  status=jobs.STATUS_RUNNING))

    active = jobs.active_job()
    assert active and active['id'] == job_id


# ----------------------------------------------------------------------
# 接口
# ----------------------------------------------------------------------
@pytest.fixture
def client(data_dir):
    from fastapi.testclient import TestClient

    from web.app import app
    return TestClient(app)


def test_options_provinces(client):
    response = client.get('/api/options/provinces')
    assert response.status_code == 200

    provinces = response.json()
    assert len(provinces) == 31
    assert any(item['code'] == '32' and item['name'] == '江苏'
               for item in provinces)


def test_options_schools(client, data_dir):
    """院校清单在共享卷上，写一份进去就能查出来"""
    catalog = data_dir / 'schools.json'
    catalog.write_text(json.dumps({
        'schools': [{'dwdm': '10284', 'dwmc': '南京大学',
                     'szss': '江苏', 'szssm': '32'}],
    }), encoding='utf-8')

    response = client.get('/api/options/schools', params={'province': '32'})
    assert response.status_code == 200

    schools = response.json()
    assert schools[0]['name'] == '南京大学'
    assert schools[0]['dwdm'] == '10284'


def test_create_job_rejects_a_bad_province(client):
    response = client.post('/api/jobs', json={'province': ['99']})
    assert response.status_code == 400


def test_second_job_is_rejected(client, data_dir):
    """已经在跑一个了就不让再起一个 —— 研招网扛不住并发"""
    job_id = jobs.new_job_id()
    os.makedirs(jobs.job_dir(job_id), exist_ok=True)
    jobs.write_status(job_id, jobs.default_status(job_id,
                                                  status=jobs.STATUS_RUNNING))

    response = client.post('/api/jobs', json={'degree': 'master'})
    assert response.status_code == 409


def test_create_job_writes_the_config(client, data_dir, monkeypatch):
    """起任务时会把配置写到共享卷上"""
    import web.app as app_module

    async def fake_post(path, payload):
        return {'id': payload.get('job_id')}

    monkeypatch.setattr(app_module, '_runner_post', fake_post)

    response = client.post('/api/jobs', json={
        'degree': 'master', 'province': ['32'], 'schools': ['10284'],
    })
    assert response.status_code == 201

    job = response.json()
    config_file = jobs.config_path(job['id'])
    assert os.path.exists(config_file)

    import yaml
    config = yaml.safe_load(open(config_file, encoding='utf-8'))
    assert config['schools'] == ['10284']
    assert config['province'] == ['32']
    assert 'cookie' not in config


def test_download_result_blocks_traversal(client):
    response = client.get('/api/results/download',
                          params={'path': '../../etc/passwd'})
    assert response.status_code == 400


def test_download_result_serves_the_file(client, tmp_path):
    result = tmp_path / 'result' / 'master'
    result.mkdir(parents=True)
    (result / 'a.csv').write_text('列1,列2\n', encoding='utf-8')

    response = client.get('/api/results/download',
                          params={'path': 'master/a.csv'})
    assert response.status_code == 200
    assert '列1' in response.text
