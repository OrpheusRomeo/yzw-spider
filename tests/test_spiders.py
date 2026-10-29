# -*- coding: utf-8 -*-
"""爬虫调度逻辑的单元测试：院校枚举的分支与去重

    pytest tests/
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.config import build_config  # noqa: E402
from yzw.discovery import SchoolCatalog  # noqa: E402
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
        # 测试不依赖磁盘上的 data/schools.json，需要院校清单的用例自己塞
        self.catalog_index = SchoolCatalog()

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


def test_named_school_is_resolved_to_code():
    """校名先从院校清单里换成招生单位代码再查

    dws.do 的 dwmc 是子串匹配，"大学"能匹配 485 所却只返回 10 条，
    直接拿校名查并不可靠 —— 院校清单里能查到就换成 dwdm 精确查。
    """
    spider = DummySpider(schools=['南京大学'])
    spider.catalog_index.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})
    requests = list(spider.begin_school_phase())
    assert len(requests) == 1
    assert requests[0].url.endswith('/zsml/rs/dws.do')
    assert requests[0].method == 'POST'
    assert b'dwdm=10284' in requests[0].body
    assert b'dwmc=&' in requests[0].body


def test_unknown_school_name_falls_back_to_name_query():
    """院校清单里没有的校名，退回按 dwmc 查"""
    spider = DummySpider(schools=['某某野鸡大学'])
    requests = list(spider.begin_school_phase())
    assert b'dwmc=%E6%9F%90%E6%9F%90%E9%87%8E%E9%B8%A1%E5%A4%A7%E5%AD%A6' in requests[0].body
    assert b'dwdm=&' in requests[0].body


def test_school_code_is_sent_as_dwdm():
    """填代码时按 dwdm 查，不按校名"""
    spider = DummySpider(schools=['10284'])
    requests = list(spider.begin_school_phase())
    assert b'dwdm=10284' in requests[0].body
    assert b'dwmc=' in requests[0].body


def test_ambiguous_name_is_not_silently_guessed():
    """校名匹配到多所时报错，不瞎猜第一条

    dws.do 用子串匹配，"交通大学"会命中 8 所（没有一所叫"交通大学"），
    猜第一条就等于抓错学校。
    """
    spider = DummySpider(schools=['交通大学'])
    payload = json.dumps({'flag': True, 'msg': {
        'totalCount': 8,
        'list': [{'dwdm': '10004', 'dwmc': '北京交通大学'},
                 {'dwdm': '10150', 'dwmc': '大连交通大学'}]}})
    response = FakeResponse(payload, {'school': '交通大学', 'by_code': False})

    assert list(spider.parse_resolved_school(response)) == []
    assert spider.captured == []
    assert spider._crawled_schools == 0


def test_exact_match_among_many_is_still_skipped():
    """即使候选里有一所同名，匹配到多所也不抓

    接口返回的是子串匹配的结果集，"同名"的那一所在不在结果集里都不算数。
    """
    spider = DummySpider(schools=['某某大学'])
    payload = json.dumps({'flag': True, 'msg': {
        'totalCount': 3,
        'list': [{'dwdm': '10001', 'dwmc': '某某大学'},
                 {'dwdm': '10002', 'dwmc': '某某大学(北京)'}]}})
    response = FakeResponse(payload, {'school': '某某大学', 'by_code': False})

    assert list(spider.parse_resolved_school(response)) == []
    assert spider.captured == []


def test_unique_exact_match_is_crawled():
    """全站就这一所、校名一模一样 —— 抓"""
    spider = DummySpider(schools=['某某大学'])
    payload = json.dumps({'flag': True, 'msg': {
        'totalCount': 1,
        'list': [{'dwdm': '90001', 'dwmc': '某某大学', 'szssm': '32'}]}})
    response = FakeResponse(payload, {'school': '某某大学', 'by_code': False})

    list(spider.parse_resolved_school(response))
    assert [unit['dwdm'] for unit in spider.captured] == ['90001']
    assert spider._crawled_schools == 1


def test_unique_but_different_name_is_skipped():
    """只匹配到一所但校名不一样 —— 也不抓（那不是你要的学校）"""
    spider = DummySpider(schools=['某某大学'])
    payload = json.dumps({'flag': True, 'msg': {
        'totalCount': 1,
        'list': [{'dwdm': '90001', 'dwmc': '某某大学(北京)', 'szssm': '32'}]}})
    response = FakeResponse(payload, {'school': '某某大学', 'by_code': False})

    assert list(spider.parse_resolved_school(response)) == []
    assert spider.captured == []


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
        'totalCount': 1,
        'list': [{'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'}]}})
    extra = FakeResponse(payload, {'school': '南京大学', 'by_code': False})
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
