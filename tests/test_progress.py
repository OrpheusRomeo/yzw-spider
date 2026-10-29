# -*- coding: utf-8 -*-
"""进度标记的单元测试：爬虫往外报进度，后端靠它统计

    pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.progress import (PROGRESS_TAG, emit_progress,  # noqa: E402
                           parse_progress_line)


# ----------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------
def test_parse_progress_line():
    line = '2026-10-29 14:33:12 [yzw.progress] INFO: %s {"kind": "item", "count": 1200}' % PROGRESS_TAG
    data = parse_progress_line(line)
    assert data == {'kind': 'item', 'count': 1200}


def test_parse_progress_line_ignores_ordinary_log():
    assert parse_progress_line('2026-10-29 14:33:12 [yzw.spiders.base] INFO: 抓完了') is None


def test_parse_progress_line_ignores_empty():
    assert parse_progress_line('') is None
    assert parse_progress_line(None) is None


def test_parse_progress_line_ignores_broken_json():
    line = '2026-10-29 [yzw.progress] INFO: %s {"kind": ' % PROGRESS_TAG
    assert parse_progress_line(line) is None


def test_parse_progress_line_needs_kind():
    line = '2026-10-29 [yzw.progress] INFO: %s {"count": 12}' % PROGRESS_TAG
    assert parse_progress_line(line) is None


def test_parse_progress_line_ignores_trailing_noise():
    """后面跟着别的内容也不该整行报废"""
    line = '%s {"kind": "school", "index": 3} 后面还有一句' % PROGRESS_TAG
    data = parse_progress_line(line)
    assert data == {'kind': 'school', 'index': 3}


# ----------------------------------------------------------------------
# 发出
# ----------------------------------------------------------------------
def test_emit_and_parse_round_trip(caplog):
    """emit 出去的标记要能被 parse 认回来"""
    with caplog.at_level('INFO'):
        emit_progress('school', index=3, dwdm='10284', name='南京大学')

    lines = [record.getMessage() for record in caplog.records]
    assert lines, '没有打出日志'

    data = parse_progress_line(lines[-1])
    assert data == {'kind': 'school', 'index': 3, 'dwdm': '10284', 'name': '南京大学'}


def test_emit_progress_keeps_chinese_readable(caplog):
    """标记里的中文不能被转义掉 —— 后端要显示校名"""
    with caplog.at_level('INFO'):
        emit_progress('school', name='南京大学')

    lines = [record.getMessage() for record in caplog.records]
    assert '南京大学' in lines[-1]
