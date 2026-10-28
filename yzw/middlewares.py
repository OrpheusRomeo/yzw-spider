# -*- coding: utf-8 -*-
"""下载中间件：接口限流自动退避重试

研招网的接口在请求太密的时候，会返回 **HTTP 200 + {"flag": false, "msg": "访问太频繁"}**。
Scrapy 自带的重试只看状态码（5xx / 429），这种"伪成功"的响应不会被重试，
结果就是那一批数据被静默丢掉 —— 全量抓几小时之后才发现少了一大片，很难补。

这里在下载中间件里把这种响应认出来，退避一段时间后重发同一个请求。
"""
import json
import logging

from twisted.internet.task import deferLater

logger = logging.getLogger(__name__)

# 接口提示"太频繁"的措辞（研招网实际用的是"访问太频繁"）
THROTTLE_KEYWORDS = ('频繁', '太快', '稍后', '太多')


class ThrottleRetryMiddleware(object):
    """遇到限流就退避重试

    配置项：
        THROTTLE_RETRY_TIMES  最多重试几次（默认 3）
        THROTTLE_BACKOFF      第一次退避多少秒，之后按次数递增（默认 10）
    """

    def __init__(self, retry_times=3, backoff=10, crawler=None):
        self.retry_times = retry_times
        self.backoff = backoff
        # Scrapy 2.17 起不再往中间件方法里传 spider 参数，
        # 官方建议自己留着 crawler，用 crawler.spider 拿
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            retry_times=crawler.settings.getint('THROTTLE_RETRY_TIMES', 3),
            backoff=crawler.settings.getfloat('THROTTLE_BACKOFF', 10),
            crawler=crawler,
        )

    def get_spider(self, spider=None):
        """拿到 spider 实例：新版 Scrapy 不再传这个参数"""
        if spider is not None:
            return spider
        return getattr(self.crawler, 'spider', None)

    def process_response(self, request, response, spider=None):
        if not self.is_throttled(response):
            return response

        retries = request.meta.get('throttle_retries', 0)
        if retries >= self.retry_times:
            self.log('error', '接口限流，重试 %d 次仍然失败，跳过这条数据：%s',
                     retries, request.url)
            return response

        wait = self.backoff * (retries + 1)
        self.log('warning', '接口限流，%.0f 秒后重试（第 %d 次）：%s',
                 wait, retries + 1, request.url)

        new_request = request.copy()
        new_request.meta['throttle_retries'] = retries + 1
        # 同一个 URL 重发，必须绕开去重
        new_request.dont_filter = True

        # 延迟到点再把请求交回给引擎
        from twisted.internet import reactor
        return deferLater(reactor, wait, lambda: new_request)

    def log(self, level, message, *args):
        """记日志 —— spider 拿不到时退回模块级 logger"""
        spider = self.get_spider()
        target = spider.logger if spider is not None else logger
        getattr(target, level)(message, *args)

    @staticmethod
    def is_throttled(response):
        """判断响应是不是"访问太频繁"这类限流响应"""
        if response is None:
            return False

        content_type = response.headers.get('Content-Type', b'').decode('utf-8', 'ignore')
        if 'json' not in content_type.lower():
            return False

        try:
            data = json.loads(response.text)
        except (ValueError, TypeError, AttributeError):
            # AttributeError: 二进制响应没有 .text
            return False

        if not isinstance(data, dict) or data.get('flag'):
            return False

        message = str(data.get('msg') or '')
        return any(word in message for word in THROTTLE_KEYWORDS)
