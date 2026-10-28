# Scrapy settings for yzw project
#
# 目标学校 / 目标专业 / 学位层次都放在仓库根目录的 config.yaml 里，
# 这里只放爬虫本身的开关；限速、并发、cookie 会被 config.yaml 覆盖
# （见 yzw/spiders/base.py 的 apply_settings）。

BOT_NAME = 'yzw'

SPIDER_MODULES = ['yzw.spiders']
NEWSPIDER_MODULE = 'yzw.spiders'


# ── 配置 ──────────────────────────────────────────
# 配置文件路径。留空 = 用项目根目录的 config.yaml；
# 也可以在这里写绝对路径，或用 scrapy crawl master -a config=xxx.yaml 覆盖。
YZW_CONFIG = None


# ── 请求头 ────────────────────────────────────────
# 研招网对默认的 Scrapy UA 不友好，换成真实浏览器的
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}


# Obey robots.txt rules
# 研招网的 /robots.txt 返回 404 页面，等于没有限制，这里保持开启
ROBOTSTXT_OBEY = True


# ── 限速 ──────────────────────────────────────────
# 下面是默认值，实际生效的值来自 config.yaml 的 request 段
DOWNLOAD_DELAY = 3
CONCURRENT_REQUESTS_PER_DOMAIN = 1
CONCURRENT_REQUESTS = 1

# Enable and configure the AutoThrottle extension
# 站点响应慢的时候自动降速，比固定 delay 更稳
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False


# ── 接口限流退避重试 ──────────────────────────────
# 研招网的接口请求太密时返回 HTTP 200 + {"flag": false, "msg": "访问太频繁"}，
# Scrapy 自带的重试只看状态码，这种响应不会被重试，会静默丢数据。
# 下面这个中间件专门认它，退避后重发。
DOWNLOADER_MIDDLEWARES = {
    'yzw.middlewares.ThrottleRetryMiddleware': 543,
}
THROTTLE_RETRY_TIMES = 3
THROTTLE_BACKOFF = 10


# ── 输出 ──────────────────────────────────────────
# 配置对象由 spider 写进来，pipeline 从这里取输出目录 / Excel 策略
ITEM_PIPELINES = {
    'yzw.pipelines.MasterPipeline': 300,
    'yzw.pipelines.DoctorPipeline': 301,
}


# ── 杂项 ──────────────────────────────────────────
# 重试：研招网偶尔会抽风
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# 请求之间的随机抖动交给 AUTOTHROTTLE 处理

# 关闭 telnet 控制台，省得本地开端口
TELNETCONSOLE_ENABLED = False

# 关闭 cookie 中间件？—— 不关，登录态需要它
COOKIES_ENABLED = True

# HTTP 缓存（默认关闭，调试接口时打开很有用）
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 3600
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_IGNORE_HTTP_CODES = [403, 404, 500]
