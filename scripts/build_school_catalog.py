#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 data/schools.json —— 全国招生单位清单

院校库 /sch/search.do 是服务端渲染的完整列表，每页 20 条、可以自由翻页，
所以逐省翻一遍就能拿到全国所有招生单位（含 dwdm），大约 100 次请求。

    python scripts/build_school_catalog.py

结果写进 data/schools.json，爬虫跑全量模式时也会实时更新这个文件。
"""
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.discovery import (PAGE_SIZE, PROVINCE_NAMES, PROVINCES,  # noqa: E402
                           SCHOOL_LIST_URL, SchoolCatalog, parse_school_list)

CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'schools.json')

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8', 'ignore')


def build(delay=1.0, provinces=None):
    """逐省翻页，收集所有招生单位"""
    catalog = SchoolCatalog()
    provinces = provinces or PROVINCES

    for ssdm, province in provinces:
        start = 0
        found = 0
        while True:
            url = f'{SCHOOL_LIST_URL}?ssdm={ssdm}&start={start}'
            html = fetch(url)
            units = parse_school_list(html, ssdm)
            for unit in units:
                catalog.add(unit)
            found += len(units)

            if len(units) < PAGE_SIZE:
                break
            start += PAGE_SIZE
            time.sleep(delay)

        print('%-6s %4d 所' % (province, found), flush=True)
        time.sleep(delay)

    return catalog


def main():
    delay = float(os.environ.get('YZW_CATALOG_DELAY', '1'))
    catalog = build(delay=delay)

    print('-' * 30)
    print('合计 %d 所招生单位' % catalog.count())
    for ssdm, count in sorted(catalog.province_counts().items(),
                              key=lambda item: -item[1]):
        print('  %-6s %4d' % (PROVINCE_NAMES.get(ssdm, ssdm), count))

    catalog.save(CATALOG_PATH)
    print('已写入 %s' % CATALOG_PATH)


if __name__ == '__main__':
    main()
