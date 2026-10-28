# -*- coding: utf-8 -*-
"""爬虫调度逻辑的单元测试：院校枚举的分支与去重

    pytest tests/
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.config import build_config  # noqa: E402
from yzw.spiders.base import BaseSpider  # noqa: E402


class FakeResponse(object):
    """够用的假响应"""

    def __init__(self, text, meta=None, url='https://yz.chsi.com.cn/fake'):
        self.text = text
        self.meta = meta or {}
        self.url = url


class DummySpider(BaseSpider):
    """把 school_requests 换成记录，不发请求"""

    name = 'dummy'

    def __init__(self, **config):
        super().__init__()
        self.config = build_config(config)
        self.captured = []

    def school_requests(self, unit):
        self.captured.append(unit)
        return iter(())


SCHOOL_HTML = (
    '<div class="sch-item">'
    '<img src="https://t1.chei.com.cn/common/xh/10284.jpg">'
    '<a class="schoolInfo--schId-368194.dhtml" href="#"> 南京大学 </a>'
    '<i class="iconfont">&#xe6a4;</i> 江苏'
    '</div>'
)


# ----------------------------------------------------------------------
# schools 参数的三种写法
# ----------------------------------------------------------------------
def test_single_school_as_plain_string():
    """schools: 南京大学（裸字符串）"""
    config = build_config({'schools': '南京大学'})
    assert config.all_schools() is False
    assert config.school_names() == ['南京大学']


def test_several_schools_as_list():
    """schools: [南京大学, 南开大学]"""
    config = build_config({'schools': ['南京大学', '南开大学']})
    assert config.all_schools() is False
    assert config.school_names() == ['南京大学', '南开大学']


def test_all_schools():
    """schools: all"""
    config = build_config({'schools': 'all'})
    assert config.all_schools() is True
    assert config.school_names() == []


def test_list_containing_all_means_all():
    """列表里混进 all 也算全量"""
    config = build_config({'schools': ['南京大学', 'all']})
    assert config.all_schools() is True


def test_extra_schools_never_turns_on_all():
    """extra_schools 不能把指定模式变成全量"""
    config = build_config({'schools': ['南京大学'], 'extra_schools': ['某某大学']})
    assert config.all_schools() is False
    assert config.school_names() == ['南京大学', '某某大学']


# ----------------------------------------------------------------------
# 枚举分支
# ----------------------------------------------------------------------
def test_empty_school_list_yields_no_request():
    """schools 写空 / 漏写时不该悄悄空跑"""
    spider = DummySpider(schools=[])
    assert list(spider.begin_school_phase()) == []


def test_all_schools_starts_from_first_province():
    """全量模式从第一个省份开始"""
    spider = DummySpider(schools='all')
    requests = list(spider.begin_school_phase())
    assert len(requests) == 1
    assert 'ssdm=11' in requests[0].url
    assert 'start=0' in requests[0].url


def test_named_school_uses_resolve_request():
    """指定院校走 dws.do 精确查"""
    spider = DummySpider(schools=['南京大学'])
    requests = list(spider.begin_school_phase())
    assert len(requests) == 1
    assert requests[0].url.endswith('/zsml/rs/dws.do')
    assert requests[0].method == 'POST'
    assert b'dwmc=%E5%8D%97%E4%BA%AC%E5%A4%A7%E5%AD%A6' in requests[0].body


def test_school_code_is_sent_as_dwdm():
    """填代码时按 dwdm 查，不按校名"""
    spider = DummySpider(schools=['10284'])
    requests = list(spider.begin_school_phase())
    assert b'dwdm=10284' in requests[0].body
    assert b'dwmc=' in requests[0].body


# ----------------------------------------------------------------------
# extra_schools 在全量模式下也要被抓
# ----------------------------------------------------------------------
def test_extra_schools_are_crawled_in_all_mode():
    """全量模式下 extra_schools 也要被补上（枚举漏掉的院校）"""
    spider = DummySpider(schools='all', extra_schools=['某某大学'])
    spider._pending_provinces = []          # 假装省份已经枚举完
    spider.catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})

    response = FakeResponse(SCHOOL_HTML, {'ssdm': '32', 'start': 0})
    requests = list(spider.parse_school_page(response))

    # 省份枚举抓到南京大学，另外排一个 extra_schools 的精确查
    assert [unit['dwmc'] for unit in spider.captured] == ['南京大学']
    assert len(requests) == 1
    assert requests[0].url.endswith('/zsml/rs/dws.do')
    assert b'dwmc=%E6%9F%90%E6%9F%90%E5%A4%A7%E5%AD%A6' in requests[0].body


def test_extra_school_already_crawled_is_skipped():
    """extra_schools 里的院校已经被省份枚举抓到过就不再抓一遍"""
    spider = DummySpider(schools='all', extra_schools=['南京大学'])
    spider._pending_provinces = []
    spider.catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})

    response = FakeResponse(SCHOOL_HTML, {'ssdm': '32', 'start': 0})
    list(spider.parse_school_page(response))
    assert spider._crawled_codes == {'10284'}

    # 再把南京大学当作 extra 精确查一次 —— 不应该重复抓
    spider.catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})
    payload = json.dumps({'flag': True, 'msg': {
        'list': [{'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'}]}})
    extra = FakeResponse(payload, {'school': '南京大学'})
    assert list(spider.parse_resolved_school(extra)) == []
    assert [unit['dwmc'] for unit in spider.captured] == ['南京大学']


def test_extra_schools_not_processed_twice():
    """extra_schools 只补一次"""
    spider = DummySpider(schools='all', extra_schools=['某某大学'])
    spider._pending_provinces = []
    spider.catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})

    response = FakeResponse(SCHOOL_HTML, {'ssdm': '32', 'start': 0})
    list(spider.parse_school_page(response))
    assert spider._extras_done is True

    # 再翻一页（该省已枚举完）不应该重复排 extra 的请求
    again = FakeResponse(SCHOOL_HTML, {'ssdm': '32', 'start': 20})
    assert list(spider.parse_school_page(again)) == []


def test_school_is_not_crawled_twice():
    """同一所院校不会被抓两遍"""
    spider = DummySpider(schools='all')
    spider._pending_provinces = []
    spider.catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})

    response = FakeResponse(SCHOOL_HTML, {'ssdm': '32', 'start': 0})
    list(spider.parse_school_page(response))
    list(spider.parse_school_page(response))

    assert [unit['dwmc'] for unit in spider.captured] == ['南京大学']
    assert spider._crawled_schools == 1
