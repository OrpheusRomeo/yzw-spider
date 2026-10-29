# -*- coding: utf-8 -*-
"""下载中间件：接口限流自动退避重试

研招网的接口在请求太密的时候，会返回 **HTTP 200 + {"flag": false, "msg": "访问太频繁"}**。
Scrapy 自带的重试只看状态码（5xx / 429），这种"伪成功"的响应不会被重试，
结果就是那一批数据被静默丢掉 —— 全量抓几小时之后才发现少了一大片，很难补。

这里在下载中间件里把这种响应认出来，退避一段时间后重发同一个请求。
"""
import asyncio
import json
import logging

from yzw.config import parse_cookie_header

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

    async def process_response(self, request, response, spider=None):
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

        # 延迟到点再把请求交回给引擎。
        # 这里用协程而不是直接返回 Deferred —— Scrapy 2.17+ 会对返回 Deferred
        # 的 process_response 报 ScrapyDeprecationWarning。
        # 用 asyncio.sleep 而不是 Twisted 的 deferLater：协程里 await 一个
        # 外部 Deferred 会被 Twisted 判成 "Task got bad yield"。
        await asyncio.sleep(wait)
        return new_request

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


class LoginCookieMiddleware(object):
    """把配置里的研招网登录态挂到每个请求上

    Scrapy 没有 COOKIES 这个设置项（只有 COOKIES_ENABLED / COOKIES_DEBUG），
    设了也不会发出去 —— 登录态必须挂到 request.cookies 上，
    再由 Scrapy 自带的 CookiesMiddleware 写进 Cookie 请求头。

    挂在 request.cookies 上（而不是直接写 Cookie 头）是为了保留服务端的更新：
    服务端 Set-Cookie 换新的 JSESSIONID 时，cookie jar 里两份都在，
    不会因为写死了一个旧值就发不出去。

    这里必须做成**下载中间件**（DOWNLOADER_MIDDLEWARES）：
    Scrapy 2.17 起的 spider middleware 已经不支持 process_request 了
    （只剩 process_spider_input / process_start / process_spider_output /
    process_spider_exception），写成 spider middleware 会被静默忽略 ——
    中间件注册了、请求也发了，就是没有 Cookie 头。

    优先级要小于 CookiesMiddleware 的 700：下载中间件的 process_request
    按优先级从小到大执行，我们得赶在它前面把 cookie 塞进 request.cookies。
    """

    def __init__(self, cookies=None):
        self.cookies = cookies or {}

    @classmethod
    def from_crawler(cls, crawler):
        """从 spider 写进 settings 的配置里拿登录态"""
        config = crawler.settings.get('YZW_CONFIG_DATA')
        cookie = getattr(config, 'cookie', '') if config is not None else ''
        return cls(parse_cookie_header(cookie))

    def process_request(self, request, spider=None):
        if not self.cookies:
            return None
        request.cookies.update(self.cookies)
        return None
