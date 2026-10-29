# -*- coding: utf-8 -*-
"""进度标记：爬虫往外报进度，Web 后端靠它统计

标记就是一行日志，前面带一个固定前缀，后面跟一段 JSON：

    2026-10-29 14:33:12 [yzw.progress] INFO: YZW_PROGRESS {"kind": "item", "count": 1200}

为什么用 logger 而不是 print
--------------------------
仓库里 yzw/ 下没有 print，全是 logger。走 logger 的好处是：
* Scrapy 自己会配置好 handler（LOG_LEVEL=INFO 时这行一定会打出来）
* 子进程里 stdout / stderr 会被合并成一路，后端按行读就能解析
* print 的话还得额外处理 Scrapy 的 LOG_STDOUT 开关

kind 的取值
-----------
* ``school``  一所学校开始抓了，带 index / dwdm / name
* ``item``    又攒够一批数据了，带 count
* ``done``    抓完了，带 schools / items

后端只要认得 kind，具体字段可以以后再加 —— 解析时多出来的键直接忽略。
"""
import json
import logging

logger = logging.getLogger(__name__)

# 标记前缀，后端靠它从普通日志里把进度行挑出来
PROGRESS_TAG = 'YZW_PROGRESS'

# 攒够多少条才发一次 item 标记 —— 一次全量能抓几十万条，
# 每条都打一行日志的话日志文件会大得没法看
PROGRESS_EVERY = 100


def emit_progress(kind, **fields):
    """打一行进度标记

    :param kind: 进度类型，school / item / done
    :param fields: 附带的字段，比如 count=1200
    """
    payload = {'kind': kind}
    payload.update(fields)
    logger.info('%s %s', PROGRESS_TAG,
                json.dumps(payload, ensure_ascii=False, sort_keys=True))


def parse_progress_line(text):
    """从一行日志里解析进度标记，不是进度行就返回 None

    解析不出来的情况：不是标记行、JSON 坏了、JSON 里没有 kind。
    这三种都返回 None，调用方跳过就行。
    """
    if not text:
        return None

    index = text.find(PROGRESS_TAG)
    if index < 0:
        return None

    rest = text[index + len(PROGRESS_TAG):].strip()
    if not rest:
        return None

    try:
        # raw_decode 只解析第一个 JSON 值，后面的杂音（换行、别的日志）不理会
        data, _ = json.JSONDecoder().raw_decode(rest)
    except (TypeError, ValueError):
        return None

    if not isinstance(data, dict) or not data.get('kind'):
        return None
    return data
