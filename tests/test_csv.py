# -*- coding: utf-8 -*-
"""CSV 输出的单元测试

重点是那个 BOM —— 没有它，Excel（Windows 中文版）打开就是满屏乱码。

    pytest tests/
"""
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.utils.csv_handler import CsvHandler  # noqa: E402

BOM = b'\xef\xbb\xbf'

HEAD = ['University', 'Major', 'ResearchInterests']
ITEM = {'University': '南京大学', 'Major': '世界史', 'ResearchInterests': '国际关系史'}


def read_rows(path):
    """按 utf-8-sig 读回来（跟 Excel 的行为一致）"""
    with open(path, 'r', encoding='utf-8-sig', newline='') as file:
        return list(csv.reader(file))


# ----------------------------------------------------------------------
# BOM
# ----------------------------------------------------------------------
def test_csv_starts_with_utf8_bom(tmp_path):
    """文件开头要有 BOM —— Excel 靠它认出 UTF-8"""
    path = str(tmp_path / 'out.csv')
    handler = CsvHandler()
    handler.init_file(path, HEAD)

    with open(path, 'rb') as file:
        assert file.read(3) == BOM


def test_csv_without_bom_is_garbled_in_excel(tmp_path):
    """反证：没有 BOM 的话，Excel 按 GBK 解码就是乱码

    这里模拟 Excel 的做法 —— 按 GBK 解码 UTF-8 的字节。
    """
    path = str(tmp_path / 'plain.csv')
    with open(path, 'w', encoding='utf-8', newline='') as file:
        csv.writer(file).writerow(['南京大学'])

    with open(path, 'rb') as file:
        raw = file.read()
    assert b'\xef\xbb\xbf' not in raw
    assert '南京大学' != raw.decode('gbk', errors='replace')


def test_append_does_not_add_bom_in_the_middle(tmp_path):
    """追加的时候不能在中间夹 BOM

    夹在中间会把那一行弄乱，Excel 之后也认不出这个文件了。
    """
    path = str(tmp_path / 'out.csv')
    handler = CsvHandler()
    handler.init_file(path, HEAD)
    handler.import_data(ITEM, path, HEAD)
    handler.import_data(ITEM, path, HEAD)

    with open(path, 'rb') as file:
        raw = file.read()
    assert raw.count(BOM) == 1
    assert raw.startswith(BOM)


def test_import_data_creates_file_with_bom(tmp_path):
    """不先 init_file、直接写数据，也要带 BOM"""
    path = str(tmp_path / 'out.csv')
    CsvHandler().import_data(ITEM, path, HEAD)

    with open(path, 'rb') as file:
        assert file.read(3) == BOM


# ----------------------------------------------------------------------
# 内容
# ----------------------------------------------------------------------
def test_chinese_survives_the_round_trip(tmp_path):
    """中文不能被写坏"""
    path = str(tmp_path / 'out.csv')
    handler = CsvHandler()
    handler.init_file(path, HEAD)
    handler.import_data(ITEM, path, HEAD)

    rows = read_rows(path)
    assert rows[0] == HEAD
    assert rows[1] == ['南京大学', '世界史', '国际关系史']


def test_missing_fields_become_empty_strings(tmp_path):
    """缺字段补空串，不能写 None"""
    path = str(tmp_path / 'out.csv')
    CsvHandler().import_data({'University': '南开大学'}, path, HEAD)

    rows = read_rows(path)
    assert rows[1] == ['南开大学', '', '']


def test_excel_can_read_it(tmp_path):
    """Excel 读的时候：带 BOM 的 UTF-8，中文正常

    utf-8-sig 读进来就是没有 BOM 的干净文本，pandas 的
    read_csv(encoding='utf-8-sig') 也是这么读的。
    """
    path = str(tmp_path / 'out.csv')
    handler = CsvHandler()
    handler.init_file(path, HEAD)
    handler.import_data(ITEM, path, HEAD)

    with open(path, 'r', encoding='utf-8-sig', newline='') as file:
        rows = list(csv.reader(file))
    assert rows[1][0] == '南京大学'


def test_append_to_existing_file_keeps_one_bom(tmp_path):
    """同一分钟重复跑会往同一个文件追加 —— BOM 仍然只有一个"""
    path = str(tmp_path / 'out.csv')
    handler = CsvHandler()
    handler.init_file(path, HEAD)
    handler.import_data(ITEM, path, HEAD)

    # 模拟另一次运行接着写
    with open(path, 'a', encoding='utf-8', newline='') as file:
        csv.writer(file).writerow(['南开大学', '经济学', '西方经济学'])

    with open(path, 'rb') as file:
        assert file.read().count(BOM) == 1
    assert len(read_rows(path)) == 3
