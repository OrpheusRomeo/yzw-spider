# -*- coding: utf-8 -*-
"""选项数据源：省份、院校

院校清单在共享卷的 data/schools.json 里 ——
仓库里提交了一份全国清单（936 所），爬虫每跑一次也会往里合并新枚举到的。
"""
import os

from yzw.discovery import PROVINCES, SchoolCatalog

from web.jobs import data_dir


def catalog_path():
    return os.path.join(data_dir(), 'schools.json')


def load_catalog():
    """读院校清单；文件不在就返回空清单"""
    return SchoolCatalog.load(catalog_path())


def provinces():
    """31 个省 + 各省已知的院校数"""
    catalog = load_catalog()
    counts = catalog.province_counts()
    return [{'code': code, 'name': name, 'count': counts.get(code, 0)}
            for code, name in PROVINCES]


def schools(province='', keyword=''):
    """院校列表

    province 是省份码，keyword 是校名里的关键词，两个都能空。
    """
    catalog = load_catalog()
    units = catalog.all()

    if province:
        units = [unit for unit in units
                 if (unit.get('szssm') or '') == str(province)]

    keyword = (keyword or '').strip()
    if keyword:
        units = [unit for unit in units
                 if keyword in (unit.get('dwmc') or '')]

    return [{'dwdm': unit.get('dwdm') or '',
             'name': unit.get('dwmc') or '',
             'province': unit.get('szss') or '',
             'province_code': unit.get('szssm') or ''}
            for unit in units]
