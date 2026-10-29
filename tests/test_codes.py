# -*- coding: utf-8 -*-
"""学科代码表 / 院校库解析的单元测试

    pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.codes import (LEVEL_ML, LEVEL_YJXK, LEVEL_ZY, CodeTable,  # noqa: E402
                        match_major, parse_autozy, parse_code_list)
from yzw.discovery import (SchoolCatalog, base_name, merge_catalog,  # noqa: E402
                           parse_school_list)

ML_JSON = '{"rad":"","dms":[{"mc":"哲学","dm":"01"},{"mc":"经济学","dm":"02"}]}'
YJXK_JSON = ('{"dms":[{"mc":"理论经济学","dm":"0201"},'
             '{"mc":"应用经济学","dm":"0202"}]}')
AUTOZY_JSON = '[{"mc":"西方经济学","dm":"020104"}]'


def make_table():
    table = CodeTable()
    table.load_ml(ML_JSON)
    table.load_yjxk('02', YJXK_JSON)
    return table


# ----------------------------------------------------------------------
# 代码表
# ----------------------------------------------------------------------
def test_parse_code_list():
    items = parse_code_list(ML_JSON)
    assert [(i['mc'], i['dm']) for i in items] == [('哲学', '01'), ('经济学', '02')]
    assert parse_code_list('not json') == []


def test_parse_autozy():
    items = parse_autozy(AUTOZY_JSON)
    assert items[0]['dm'] == '020104'
    assert parse_autozy('{}') == []


def test_resolve_numeric_code_uses_length():
    table = make_table()
    assert table.resolve('02') == (LEVEL_ML, '02')
    assert table.resolve('0202') == (LEVEL_YJXK, '0202')
    assert table.resolve('020104') == (LEVEL_ZY, '020104')
    assert table.resolve('0201041') is None


def test_resolve_name_falls_through_tables():
    table = make_table()
    assert table.resolve('经济学') == (LEVEL_ML, '02')
    assert table.resolve('应用经济学') == (LEVEL_YJXK, '0202')
    # 两张表里都没有 -> 属于专业（6 位码），交给 autozy.do
    assert table.resolve('西方经济学') is None


def test_resolve_all_returns_every_level():
    """同名专业横跨多个层级时全都返回"""
    table = CodeTable()
    table.load_ml(ML_JSON)
    table.load_yjxk('10', '{"dms":[{"mc":"临床医学","dm":"1002"},'
                            '{"mc":"临床医学","dm":"1051"}]}')
    assert table.resolve_all('临床医学') == [
        (LEVEL_YJXK, '1002'), (LEVEL_YJXK, '1051')]


def test_match_major():
    assert match_major(LEVEL_ML, '02', '020200') is True
    assert match_major(LEVEL_ML, '02', '010100') is False
    assert match_major(LEVEL_YJXK, '0202', '020200') is True
    assert match_major(LEVEL_YJXK, '0202', '020300') is False
    assert match_major(LEVEL_ZY, '020200', '020200') is True
    assert match_major(LEVEL_ZY, '020200', '020201') is False
    assert match_major(LEVEL_ZY, '020200', '') is False


# ----------------------------------------------------------------------
# 院校库
# ----------------------------------------------------------------------
SCHOOL_HTML = '''
<div class="sch-item">
  <img src="https://t1.chei.com.cn/common/xh/10284.jpg">
  <a class="schoolInfo--schId-368194.dhtml" href="#"> 南京大学 </a>
  <i class="iconfont">&#xe6a4;</i> 江苏
</div>
<div class="sch-item">
  <img src="https://t1.chei.com.cn/common/xh/10055.jpg">
  <a class="schoolInfo--schId-367949.dhtml" href="#"> 南开大学 </a>
  <i class="iconfont">&#xe6a4;</i> 天津
</div>
'''


def test_parse_school_list():
    units = parse_school_list(SCHOOL_HTML, '32')
    assert len(units) == 2
    assert units[0]['dwdm'] == '10284'
    assert units[0]['dwmc'] == '南京大学'
    assert units[0]['szss'] == '江苏'
    assert units[1]['szssm'] == '32'


def test_parse_school_list_ignores_garbage():
    assert parse_school_list('<html>nothing</html>', '32') == []


def test_catalog_dedups_by_code():
    catalog = SchoolCatalog()
    catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})
    catalog.add({'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'})
    assert catalog.count() == 1
    assert catalog.find_by_name('南京大学')['dwdm'] == '10284'
    assert catalog.find_by_code('10284') is not None
    assert catalog.find_by_name('不存在') is None


def test_catalog_province_counts_and_lookup():
    catalog = SchoolCatalog([
        {'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'},
        {'dwdm': '10055', 'dwmc': '南开大学', 'szssm': '12'},
    ])
    assert catalog.province_counts() == {'32': 1, '12': 1}
    assert [u['dwmc'] for u in catalog.schools_of('32')] == ['南京大学']


# ----------------------------------------------------------------------
# 多校区：去掉括号后本体名相同 = 同一所大学
# ----------------------------------------------------------------------
def test_base_name_strips_campus_suffix():
    assert base_name('中国石油大学(华东)') == '中国石油大学'
    assert base_name('中国石油大学（华东）') == '中国石油大学'
    assert base_name('中国石油大学') == '中国石油大学'
    assert base_name('上海交通大学') == '上海交通大学'
    # 用顿号把几个研究所连在一起的校名，取第一个再剥括号
    assert base_name('中国兵器科学研究院(西安近代化学研究所)、中国兵器科学研究院(内蒙古金属材料研究所)') \
        == '中国兵器科学研究院'
    assert base_name('') == ''


def test_catalog_finds_all_campuses_of_one_university():
    catalog = SchoolCatalog([
        {'dwdm': '10425', 'dwmc': '中国石油大学(华东)', 'szssm': '32'},
        {'dwdm': '11414', 'dwmc': '中国石油大学(北京)', 'szssm': '11'},
        {'dwdm': '10004', 'dwmc': '北京交通大学', 'szssm': '11'},
        {'dwdm': '10248', 'dwmc': '上海交通大学', 'szssm': '31'},
    ])
    camps = catalog.find_by_base_name('中国石油大学')
    assert [u['dwdm'] for u in camps] == ['10425', '11414']
    # 带括号写也一样能找到同一组
    assert [u['dwdm'] for u in catalog.find_by_base_name('中国石油大学(华东)')] \
        == ['10425', '11414']


def test_catalog_does_not_confuse_different_universities():
    """本体名对不上就不是多校区 —— "交通大学"匹配不到任何一所"""
    catalog = SchoolCatalog([
        {'dwdm': '10004', 'dwmc': '北京交通大学', 'szssm': '11'},
        {'dwdm': '10248', 'dwmc': '上海交通大学', 'szssm': '31'},
        {'dwdm': '10404', 'dwmc': '华东交通大学', 'szssm': '36'},
    ])
    assert catalog.find_by_base_name('交通大学') == []
    assert catalog.find_by_base_name('大学') == []
    assert len(catalog.find_by_base_name('北京交通大学')) == 1


def test_catalog_save_and_load(tmp_path):
    path = str(tmp_path / 'schools.json')
    catalog = SchoolCatalog([{'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'}])
    catalog.save(path)

    loaded = SchoolCatalog.load(path)
    assert loaded.count() == 1
    assert loaded.all()[0]['dwmc'] == '南京大学'
    assert SchoolCatalog.load(str(tmp_path / 'nope.json')).count() == 0


def test_merge_catalog_does_not_truncate_existing(tmp_path):
    """定向抓取只枚举到一所院校时，不能把已有的全国清单覆盖掉"""
    path = str(tmp_path / 'schools.json')
    SchoolCatalog([
        {'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32'},
        {'dwdm': '10055', 'dwmc': '南开大学', 'szssm': '12'},
    ]).save(path)

    # 只抓到南开大学 -> 合并后仍然应该是 2 所
    total, added = merge_catalog(path, [
        {'dwdm': '10055', 'dwmc': '南开大学', 'szssm': '12'},
    ])
    assert total == 2
    assert added == 0

    # 抓到一个清单里没有的 -> 追加而不是替换
    total, added = merge_catalog(path, [
        {'dwdm': '10001', 'dwmc': '北京大学', 'szssm': '11'},
    ])
    assert total == 3
    assert added == 1
    assert SchoolCatalog.load(path).find_by_name('北京大学') is not None


def test_merge_catalog_keeps_existing_record_fields(tmp_path):
    """已存在的记录以文件里的为准（院校库解析出来的字段更全）"""
    path = str(tmp_path / 'schools.json')
    SchoolCatalog([{'dwdm': '10284', 'dwmc': '南京大学', 'szssm': '32',
                     'szss': '江苏', 'schId': '368194'}]).save(path)

    merge_catalog(path, [{'dwdm': '10284', 'dwmc': '南京大学'}])

    unit = SchoolCatalog.load(path).find_by_code('10284')
    assert unit['szss'] == '江苏'
    assert unit['schId'] == '368194'


def test_merge_catalog_on_missing_file(tmp_path):
    """文件不存在时，合并等价于新建"""
    path = str(tmp_path / 'nope.json')
    total, added = merge_catalog(path, [{'dwdm': '10284', 'dwmc': '南京大学'}])
    assert total == 1
    assert added == 1
    assert SchoolCatalog.load(path).count() == 1
