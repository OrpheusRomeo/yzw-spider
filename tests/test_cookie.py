# -*- coding: utf-8 -*-
"""登录态（cookie）能不能真的发出去的单元测试

    pytest tests/
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from scrapy.http import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.config import build_config, parse_cookie_header  # noqa: E402
from yzw.middlewares import LoginCookieMiddleware  # noqa: E402
from yzw.spiders.base import BaseSpider  # noqa: E402


# ----------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------
def test_parse_cookie_header():
    assert parse_cookie_header('JSESSIONID=abc; CHSICC_CLIENTFLAGZSML=def') == {
        'JSESSIONID': 'abc', 'CHSICC_CLIENTFLAGZSML': 'def'}
    assert parse_cookie_header('') == {}
    assert parse_cookie_header('没有等号') == {}


# ----------------------------------------------------------------------
# 中间件：把 cookie 挂到 request.cookies 上
# ----------------------------------------------------------------------
def test_cookie_is_attached_to_request():
    middleware = LoginCookieMiddleware({'JSESSIONID': 'abc'})
    request = Request('https://yz.chsi.com.cn/zsml/rs/dws.do')
    assert middleware.process_request(request) is None
    assert request.cookies['JSESSIONID'] == 'abc'


def test_no_cookie_leaves_request_alone():
    middleware = LoginCookieMiddleware({})
    request = Request('https://yz.chsi.com.cn/')
    middleware.process_request(request)
    assert not request.cookies


def test_middleware_reads_cookie_from_settings():
    """cookie 从 spider 写进 settings 的配置里拿"""
    from scrapy.settings import Settings

    settings = Settings()
    settings.set('YZW_CONFIG_DATA', build_config({'cookie': 'JSESSIONID=xyz'}))

    class FakeCrawler(object):
        def __init__(self, s):
            self.settings = s

    middleware = LoginCookieMiddleware.from_crawler(FakeCrawler(settings))
    assert middleware.cookies == {'JSESSIONID': 'xyz'}


def test_middleware_is_registered_as_downloader_middleware():
    """回归测试：必须注册成下载中间件，且排在 CookiesMiddleware 前面

    Scrapy 2.17 起的 spider middleware 已经不支持 process_request 了，
    注册成 spider middleware 会被静默忽略 —— 中间件在、请求也在，就是没有 Cookie 头。
    """
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    downloader = dict(settings.getwithbase('DOWNLOADER_MIDDLEWARES'))
    spider = dict(settings.getwithbase('SPIDER_MIDDLEWARES'))

    path = 'yzw.middlewares.LoginCookieMiddleware'
    assert path in downloader, '登录态中间件没注册成下载中间件'
    assert path not in spider, '登录态中间件不该注册成 spider middleware'

    # 下载中间件的 process_request 按优先级从小到大执行，
    # 必须赶在 Scrapy 自带的 CookiesMiddleware（700）前面把 cookie 塞进去
    cookies_mw = 'scrapy.downloadermiddlewares.cookies.CookiesMiddleware'
    assert downloader[path] < downloader[cookies_mw], \
        '登录态中间件排在 CookiesMiddleware 后面，cookie 写不进请求头'


# ----------------------------------------------------------------------
# 端到端：cookie 真的出现在请求头上
# ----------------------------------------------------------------------
class EchoHandler(BaseHTTPRequestHandler):
    """把收到的 Cookie 头回显在响应里"""

    received = []

    def do_GET(self):
        EchoHandler.received.append(self.headers.get('Cookie', ''))
        body = json.dumps({'cookie': self.headers.get('Cookie', '')}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def echo_server():
    server = HTTPServer(('127.0.0.1', 0), EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%d' % server.server_port
    server.shutdown()


def test_cookie_reaches_the_server(echo_server):
    """跑一次真实请求，确认 Cookie 请求头真的发出去了

    以前是在 apply_settings 里 settings.set('COOKIES', ...)，
    但 Scrapy 根本没有 COOKIES 这个设置项 —— 设了也不会发出去，
    配了 cookie 也还是只能拿到 10 条。
    """
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()

    EchoHandler.received = []

    class EchoSpider(BaseSpider):
        name = 'echo'
        allowed_domains = ['127.0.0.1']

        def initial_requests(self):
            yield Request(echo_server + '/echo')

    process = CrawlerProcess(settings)
    process.crawl(EchoSpider, cookie='JSESSIONID=wire-test')
    process.start()

    assert EchoHandler.received, '没有收到任何请求'
    assert any('JSESSIONID=wire-test' in c for c in EchoHandler.received), \
        'Cookie 头没发出去：%r' % EchoHandler.received
