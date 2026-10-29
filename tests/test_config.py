# -*- coding: utf-8 -*-
"""配置层的单元测试：解析、归一化、校验

    pytest tests/
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.config import (ALL, DEGREE_BOTH, DEGREE_DOCTOR, DEGREE_MASTER,  # noqa: E402
                         EXCEL_ALWAYS, EXCEL_AUTO, EXCEL_NEVER, ConfigError,
                         build_config, load_config, resolve_config_path)


# ----------------------------------------------------------------------
# 归一化
# ----------------------------------------------------------------------
def test_degree_defaults_to_master():
    config = build_config({})
    assert config.degrees == [DEGREE_MASTER]
    assert config.wants_master() is True
    assert config.wants_doctor() is False


def test_degree_both_expands_to_two_levels():
    config = build_config({'degree': 'both'})
    assert config.degrees == [DEGREE_MASTER, DEGREE_DOCTOR]
    assert config.wants_master() and config.wants_doctor()


def test_degree_accepts_list():
    config = build_config({'degree': ['doctor', 'master']})
    assert config.degrees == [DEGREE_DOCTOR, DEGREE_MASTER]


def test_degree_rejects_unknown_value():
    with pytest.raises(ConfigError) as error:
        build_config({'degree': 'xyz'})
    assert 'master' in str(error.value)


def test_schools_all_string():
    config = build_config({'schools': 'all'})
    assert config.all_schools() is True
    assert config.school_names() == []


def test_schools_all_in_list():
    """列表里写 - all 也算全量"""
    config = build_config({'schools': ['all']})
    assert config.all_schools() is True


def test_schools_comma_separated_string():
    """命令行覆盖只能传字符串，用逗号分隔"""
    config = build_config({'schools': '南京大学,南开大学'})
    assert config.all_schools() is False
    assert config.school_names() == ['南京大学', '南开大学']


def test_schools_chinese_comma_separated():
    config = build_config({'schools': '南京大学，南开大学'})
    assert config.school_names() == ['南京大学', '南开大学']


def test_schools_string_with_all_becomes_all():
    config = build_config({'schools': '南京大学, all'})
    assert config.all_schools() is True


def test_majors_comma_separated_string():
    config = build_config({'majors': '经济学,应用经济学'})
    assert config.all_majors() is False
    assert config.major_names() == ['经济学', '应用经济学']


def test_majors_all_in_list():
    config = build_config({'majors': ['all']})
    assert config.all_majors() is True


def test_extra_schools_comma_separated_string():
    config = build_config({'schools': ['南京大学'], 'extra_schools': '某某大学,某某理工'})
    assert config.school_names() == ['南京大学', '某某大学', '某某理工']


def test_schools_list_normalised():
    config = build_config({'schools': ['南京大学', '  ', '10284']})
    assert config.all_schools() is False
    assert config.school_names() == ['南京大学', '10284']


def test_extra_schools_are_always_appended():
    config = build_config({'schools': ['南京大学'], 'extra_schools': ['某某大学']})
    assert config.school_names() == ['南京大学', '某某大学']

    config = build_config({'schools': 'all', 'extra_schools': ['某某大学']})
    assert config.all_schools() is True
    assert config.school_names() == ['某某大学']


def test_majors_all_and_names():
    assert build_config({'majors': 'all'}).all_majors() is True
    assert build_config({'majors': 'all'}).major_names() == []

    config = build_config({'majors': ['应用经济学']})
    assert config.all_majors() is False
    assert config.major_names() == ['应用经济学']


def test_unknown_key_is_rejected():
    with pytest.raises(ConfigError) as error:
        build_config({'disciplines': ['经济学']})
    assert 'disciplines' in str(error.value)


# ----------------------------------------------------------------------
# 输出 / 请求
# ----------------------------------------------------------------------
def test_output_defaults():
    config = build_config({})
    assert config.output_directory() == './result'
    assert config.excel_mode() == EXCEL_AUTO
    assert config.excel_max_schools() == 100


def test_output_excel_modes():
    assert build_config({'output': {'excel': 'always'}}).excel_mode() == EXCEL_ALWAYS
    assert build_config({'output': {'excel': 'never'}}).excel_mode() == EXCEL_NEVER
    with pytest.raises(ConfigError):
        build_config({'output': {'excel': 'sometimes'}})


def test_request_defaults_and_validation():
    config = build_config({})
    assert config.delay() == 3
    assert config.concurrency() == 1
    assert config.max_schools() == 0

    with pytest.raises(ConfigError):
        build_config({'request': {'concurrency': 0}})
    with pytest.raises(ConfigError):
        build_config({'request': {'delay': 'abc'}})


# ----------------------------------------------------------------------
# 覆盖 / 读取
# ----------------------------------------------------------------------
def test_override_replaces_values():
    config = build_config({'degree': 'master', 'schools': ['南京大学']})
    updated = config.override({'degree': 'doctor', 'schools': 'all'})
    assert updated.degrees == [DEGREE_DOCTOR]
    assert updated.all_schools() is True


def test_override_keeps_other_fields():
    config = build_config({'output': {'excel': 'never'}, 'schools': ['南京大学']})
    updated = config.override({'degree': 'doctor'})
    assert updated.excel_mode() == EXCEL_NEVER
    assert updated.school_names() == ['南京大学']


def test_load_config_from_file(tmp_path):
    path = tmp_path / 'cfg.yaml'
    path.write_text(
        'degree: both\n'
        'schools: all\n'
        'majors: [应用经济学]\n'
        'request:\n'
        '  delay: 0.5\n',
        encoding='utf-8')

    config = load_config(str(path))
    assert config.degrees == [DEGREE_MASTER, DEGREE_DOCTOR]
    assert config.all_schools() is True
    assert config.major_names() == ['应用经济学']
    assert config.delay() == 0.5


def test_load_config_missing_explicit_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / 'nope.yaml'))


def test_load_config_without_file_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv('YZW_CONFIG', str(tmp_path / 'nope.yaml'))
    # 文件不存在且没显式指定路径时，返回内置默认配置
    config = load_config(None)
    assert config.degrees == [DEGREE_MASTER]
    assert config.majors == ALL


def test_resolve_config_path_prefers_argument(tmp_path, monkeypatch):
    monkeypatch.setenv('YZW_CONFIG', str(tmp_path / 'env.yaml'))
    assert resolve_config_path(str(tmp_path / 'arg.yaml')).endswith('arg.yaml')
    assert resolve_config_path(None).endswith('env.yaml')


# ----------------------------------------------------------------------
# 命令行覆盖：-a 传进来的参数怎么落到配置上
# ----------------------------------------------------------------------
def test_override_supports_dotted_paths():
    """-a output.directory=xxx 这种点号路径要真的生效"""
    config = build_config({'output': {'directory': './result'}})
    updated = config.override({
        'output.directory': '/app/result',
        'output.excel': 'never',
        'output.excel_max_schools': '20',
        'request.delay': '0.5',
        'request.concurrency': '4',
        'request.max_schools': '3',
    })
    assert updated.output_directory() == '/app/result'
    assert updated.excel_mode() == 'never'
    assert updated.excel_max_schools() == 20
    assert updated.delay() == 0.5
    assert updated.concurrency() == 4
    assert updated.max_schools() == 3


def test_override_does_not_mutate_the_original():
    """覆盖出来的应该是新对象，原配置不受影响"""
    config = build_config({'output': {'directory': './result'}})
    updated = config.override({'output.directory': '/tmp/out'})
    assert updated.output_directory() == '/tmp/out'
    assert config.output_directory() == './result'


def test_override_rejects_unknown_key():
    """写错的参数名要报错，不能静默忽略"""
    config = build_config({})
    with pytest.raises(ConfigError) as error:
        config.override({'output.dir': '/tmp/out'})
    assert 'output.dir' in str(error.value)
    assert 'output.directory' in str(error.value)


def test_override_rejects_unknown_top_level_key():
    config = build_config({})
    with pytest.raises(ConfigError):
        config.override({'schoolss': '南京大学'})


def test_override_ignores_none_values():
    config = build_config({'degree': 'master'})
    assert config.override({'degree': None}).degrees == ['master']


def test_env_cookie_overrides_file(monkeypatch, tmp_path):
    """YZW_COOKIE 环境变量优先于配置文件里的 cookie（Docker 里用它传登录态）"""
    path = tmp_path / 'cfg.yaml'
    path.write_text('cookie: "JSESSIONID=from-file"\n', encoding='utf-8')
    monkeypatch.setenv('YZW_COOKIE', 'JSESSIONID=from-env')
    assert load_config(str(path)).cookie == 'JSESSIONID=from-env'

    monkeypatch.delenv('YZW_COOKIE')
    assert load_config(str(path)).cookie == 'JSESSIONID=from-file'


# ----------------------------------------------------------------------
# 省份
# ----------------------------------------------------------------------
def test_province_defaults_to_all():
    """不限省份 —— 逐省枚举时 31 个省都要跑"""
    config = build_config({})
    assert config.province == ALL
    assert config.provinces() == []


def test_province_accepts_code_list():
    config = build_config({'province': ['32', '33']})
    assert config.provinces() == ['32', '33']


def test_province_all_means_unlimited():
    """写 all 和不写一样 —— 都要跑全国"""
    config = build_config({'province': 'all'})
    assert config.province == ALL
    assert config.provinces() == []


def test_province_empty_list_means_unlimited():
    config = build_config({'province': []})
    assert config.province == ALL
    assert config.provinces() == []


def test_province_rejects_unknown_code():
    """省份码写错要报错 —— 静默跳过的结果是一个省都不抓"""
    with pytest.raises(ConfigError) as error:
        build_config({'province': ['99']})
    assert '99' in str(error.value)


def test_override_keeps_province():
    """回归测试：用 -a 覆盖别的项时，省份限制不能被悄悄丢掉

    override() 是从零重建 data 再调 build_config() 的，
    这里漏掉 province 的话，-a degree=doctor 就会让省份限制失效、变成全国全量。
    """
    config = build_config({'province': ['32']})
    updated = config.override({'degree': 'doctor'})
    assert updated.provinces() == ['32']
    assert updated.degrees == [DEGREE_DOCTOR]


def test_override_can_replace_province():
    """province 也能用 -a 直接覆盖"""
    config = build_config({'province': ['32']})
    updated = config.override({'province': '31,32'})
    assert updated.provinces() == ['31', '32']
