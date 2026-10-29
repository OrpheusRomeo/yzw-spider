# -*- coding: utf-8 -*-
"""限流退避中间件的单元测试

    pytest tests/
"""
import asyncio
import json
import os
import sys

import pytest
from scrapy.http import JsonResponse, Request, TextResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yzw.middlewares import ThrottleRetryMiddleware  # noqa: E402


def make_response(payload, url='https://yz.chsi.com.cn/zsml/rs/yjfxs.do'):
    # 研招网的接口回的是 application/json，Scrapy 会用 JsonResponse
    return JsonResponse(
        url=url,
        status=200,
        body=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        request=Request(url=url),
        encoding='utf-8',
    )


def test_throttled_response_is_recognised():
    """研招网的限流是 HTTP 200 + flag:false，不是状态码错误"""
    middleware = ThrottleRetryMiddleware()
    assert middleware.is_throttled(make_response({'flag': False, 'msg': '访问太频繁'})) is True
    assert middleware.is_throttled(make_response({'flag': False, 'msg': '请登录'})) is False
    assert middleware.is_throttled(make_response({'flag': True, 'msg': 'ok'})) is False


def test_non_json_response_is_not_throttled():
    middleware = ThrottleRetryMiddleware()
    response = TextResponse(
        url='https://yz.chsi.com.cn/',
        status=200,
        body='<html>访问太频繁</html>'.encode('utf-8'),
        headers={'Content-Type': 'text/html'},
        request=Request(url='https://yz.chsi.com.cn/'),
        encoding='utf-8',
    )
    assert middleware.is_throttled(response) is False


def test_normal_response_passes_through():
    """没被限流的响应原样返回"""
    middleware = ThrottleRetryMiddleware()
    response = make_response({'flag': True, 'msg': {'totalCount': 1}})
    assert asyncio.run(middleware.process_response(Request('https://x/'), response)) is response


def test_throttled_request_is_rescheduled():
    """限流时退避后重发同一个请求，并且绕开去重"""
    middleware = ThrottleRetryMiddleware(retry_times=3, backoff=0)
    request = Request('https://yz.chsi.com.cn/zsml/rs/yjfxs.do')
    response = make_response({'flag': False, 'msg': '访问太频繁'})

    result = asyncio.run(middleware.process_response(request, response))

    assert isinstance(result, Request)
    assert result.url == request.url
    assert result.dont_filter is True
    assert result.meta['throttle_retries'] == 1


def test_retry_limit_is_respected():
    """重试用完就放弃，把响应原样交回去（不再重试）"""
    middleware = ThrottleRetryMiddleware(retry_times=2, backoff=0)
    request = Request('https://yz.chsi.com.cn/zsml/rs/yjfxs.do')
    request.meta['throttle_retries'] = 2
    response = make_response({'flag': False, 'msg': '访问太频繁'})

    assert asyncio.run(middleware.process_response(request, response)) is response


def test_process_response_is_a_coroutine():
    """Scrapy 2.17+ 不接受返回 Deferred 的 process_response（会报废弃警告）"""
    middleware = ThrottleRetryMiddleware()
    coro = middleware.process_response(Request('https://x/'),
                                       make_response({'flag': True}))
    assert asyncio.iscoroutine(coro)
    asyncio.run(coro)
