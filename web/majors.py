# -*- coding: utf-8 -*-
"""专业代码表，和某所学校开设的专业

两件事都要访问研招网，所以放在 runner 那边跑，web 只做转发。

* 代码表    ml.json + yjxk/{门类}.json，都是静态文件，缓存 7 天
* 某校专业  dwzys.do，匿名状态下每个接口只给 10 条
"""
import asyncio
import json
import os
import time

import httpx

from yzw.codes import API_ML, API_YJXK, parse_code_list

from web.jobs import data_dir

# 开设专业接口（和 yzw/spiders/master.py 用的是同一个）
API_DWZYS = 'https://yz.chsi.com.cn/zsml/rs/dwzys.do'

# 代码表缓存的有效期：7 天
CACHE_TTL = 7 * 24 * 3600

# 同时最多打几个请求 —— 别把研招网打毛了
MAX_CONCURRENCY = 6

# 每次请求最多翻几页
MAX_PAGES = 20

# 浏览器发往研招网的表单请求头
AJAX_HEADERS = {
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
}


# ----------------------------------------------------------------------
# 代码表
# ----------------------------------------------------------------------
def codes_path():
    return os.path.join(data_dir(), 'codes.json')


def read_cached_codes():
    """读缓存的代码表；没有或过期返回 None"""
    path = codes_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get('groups'):
        return None
    fetched_at = data.get('fetched_at') or 0
    if time.time() - float(fetched_at) > CACHE_TTL:
        return None
    return data.get('groups')


def write_cached_codes(groups):
    """把代码表缓存起来"""
    path = codes_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {'fetched_at': time.time(), 'groups': groups}
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return groups


async def fetch_code_table(client, sem):
    """从研招网把门类表和一级学科表都拉下来"""
    response = await client.get(API_ML)
    response.raise_for_status()
    ml_list = parse_code_list(response.text)
    if not ml_list:
        raise RuntimeError('门类代码表是空的')

    async def children_of(code):
        async with sem:
            try:
                sub = await client.get(API_YJXK.format(ml=code))
                sub.raise_for_status()
            except (httpx.HTTPError, RuntimeError):
                return []
        return [{'code': item['dm'], 'name': item.get('mc') or ''}
                for item in parse_code_list(sub.text)]

    results = await asyncio.gather(*[children_of(item['dm']) for item in ml_list])

    return [{'code': item['dm'],
             'name': item.get('mc') or '',
             'children': children}
            for item, children in zip(ml_list, results)]


async def code_table(client):
    """代码表：先看缓存，没有或过期就去研招网拉

    拉失败时回退到过期缓存 —— 拿旧的也比让用户什么都选不了强。
    """
    cached = read_cached_codes()
    if cached:
        return cached

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    try:
        groups = await fetch_code_table(client, sem)
    except (httpx.HTTPError, RuntimeError):
        stale = read_stale_codes()
        if stale:
            return stale
        raise

    write_cached_codes(groups)
    return groups


def read_stale_codes():
    """过期了但还能用的代码表"""
    path = codes_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data.get('groups')


# ----------------------------------------------------------------------
# 某所学校开设的专业
# ----------------------------------------------------------------------
def parse_major_rows(text):
    """解析 dwzys.do 的返回，返回 (总数, 行列表)"""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return 0, []
    if not isinstance(data, dict) or not data.get('flag'):
        return 0, []
    msg = data.get('msg') or {}
    if not isinstance(msg, dict):
        return 0, []
    return msg.get('totalCount') or 0, msg.get('list') or []


def cookie_header():
    """研招网登录态；没配就是空"""
    return (os.environ.get('YZW_COOKIE') or '').strip()


async def query_majors(client, sem, dwdm, ml, yjxkdm='', cookie='', start=0):
    """查一次 dwzys.do，返回 (总数, 行列表)"""
    form = {
        'dwdm': dwdm, 'dwmc': '',
        'zydm': '', 'zymc': '', 'xwlx': '',
        'mldm': ml, 'yjxkdm': yjxkdm,
        'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
        'start': start, 'curPage': start // 10 + 1, 'pageSize': 10,
    }
    headers = dict(AJAX_HEADERS)
    if cookie:
        headers['Cookie'] = cookie

    async with sem:
        response = await client.post(API_DWZYS, data=form, headers=headers)
        response.raise_for_status()
    return parse_major_rows(response.text)


async def majors_of_school(client, dwdm, groups=None, cookie=None):
    """某所学校开设的专业

    dwzys.do 每页硬顶 10 条，start>0 一律"请登录"。
    所以按门类逐个查（每个门类一般不超过 10 条）；
    还是超 10 条的门类，再用一级学科收窄一次 —— 收窄后还超就是真的拿不全了。
    """
    if groups is None:
        groups = await code_table(client)

    cookie = cookie if cookie is not None else cookie_header()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    found = {}
    truncated = False

    def add_rows(rows):
        for row in rows:
            code = row.get('zydm')
            if code:
                found[code] = row

    async def collect_group(group):
        """一个门类：超了 10 条就翻页或者按一级学科拆开重查"""
        nonlocal truncated
        ml = group['code']
        count, rows = await query_majors(client, sem, dwdm, ml, '', cookie)

        if count <= len(rows):
            add_rows(rows)
            return

        if cookie:
            # 有登录态就能直接翻页补齐
            add_rows(rows)
            start = len(rows)
            for _ in range(MAX_PAGES):
                if start >= count:
                    break
                _, more = await query_majors(
                    client, sem, dwdm, ml, '', cookie, start=start)
                if not more:
                    break
                add_rows(more)
                start += len(more)
            if start < count:
                truncated = True
            return

        # 匿名状态：只能靠一级学科收窄
        children = group.get('children') or []
        if not children:
            add_rows(rows)
            truncated = True
            return
        for child in children:
            _, sub_rows = await query_majors(
                client, sem, dwdm, ml, child['code'], cookie)
            add_rows(sub_rows)

    await asyncio.gather(*[collect_group(group) for group in groups])

    majors = [{'code': code, 'name': (found[code].get('zymc') or '').strip()}
              for code in found]
    majors.sort(key=lambda item: item['code'])
    return majors, truncated
