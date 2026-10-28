# -*- coding: utf-8 -*-
"""爬虫基类 —— 配置装载、院校枚举、学科代码表的公共逻辑

整个爬取分成四个阶段，靠 Scrapy 的回调链串起来：

    1. 学科代码表   ml.json -> yjxk/{门类}.json -> autozy.do（按需）
    2. 招生单位枚举 schools=all  走院校库，逐省翻页
                     schools=[..] 走 dws.do，按名称/代码精确查
    3. 专业枚举     dwzys.do，按门类 / 一级学科收窄
    4. 明细         yjfxs.do，超出 10 条时按 tydxs / xxfs 拆开再取
"""
import json
import logging
import os
from urllib.parse import quote, urlencode

import scrapy

from yzw.codes import (API_AUTOZY, API_ML, API_YJXK, LEVEL_ZY, CodeTable,
                       match_major, parse_autozy)
from yzw.config import PROJECT_ROOT, load_config
from yzw.discovery import (PAGE_SIZE, PROVINCE_NAMES, PROVINCES, SchoolCatalog,
                           merge_catalog, parse_school_list)

logger = logging.getLogger(__name__)

# 枚举到的招生单位写到这里，方便核对与复用
CATALOG_PATH = os.path.join(PROJECT_ROOT, 'data', 'schools.json')

# 可以用 -a 在命令行上覆盖的配置项
OVERRIDE_KEYS = ('config', 'degree', 'schools', 'majors', 'cookie')


def parse_cookie_header(text):
    """把 "JSESSIONID=xxx; other=yyy" 解析成 Scrapy 的 COOKIES 字典"""
    cookies = {}
    for part in (text or '').split(';'):
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


class BaseSpider(scrapy.Spider):
    """研究生招生信息爬虫基类"""

    allowed_domains = ['yz.chsi.com.cn']

    # 公共字段（博士和硕士共用）
    common_fields = [
        'University', 'College', 'Major', 'ResearchInterests',
        'Teacher', 'StudentNo', 'StudyType', 'ExamType', 'Content',
        'Subject1', 'Subject2', 'Subject3', 'Subject4', 'Link'
    ]

    # 研招网接口地址（2025-09 改版后的新接口）
    API_DWS = 'https://yz.chsi.com.cn/zsml/rs/dws.do'          # 按招生单位查询
    API_DWZYS = 'https://yz.chsi.com.cn/zsml/rs/dwzys.do'      # 某招生单位的开设专业
    API_YJFXS = 'https://yz.chsi.com.cn/zsml/rs/yjfxs.do'      # 某专业的学院/研究方向明细
    API_ZYDETAIL = 'https://yz.chsi.com.cn/zsml/zydetail.do'  # 专业详情页

    # 院校库：完整招生单位列表，服务端渲染、可以自由翻页
    API_SCHOOL_LIST = 'https://yz.chsi.com.cn/sch/search.do'

    # 学科代码表
    API_CODE_ML = API_ML
    API_CODE_YJXK = API_YJXK
    API_CODE_AUTOZY = API_AUTOZY

    # 浏览器发往研招网的表单请求头
    AJAX_HEADERS = {
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
    }

    # 学习方式代码 -> 名称
    STUDY_TYPES = {'1': '全日制', '2': '非全日制'}

    # 本 spider 负责的学位层次；None = 不限（all spider 按配置自己分发）
    degree_kind = None

    # 硕士侧接口每页的条数（服务端硬顶 10 条）
    PAGE_SIZE = 10

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def __init__(self, name=None, **kwargs):
        overrides = {}
        for key in OVERRIDE_KEYS:
            if key in kwargs:
                overrides[key] = kwargs.pop(key)

        super().__init__(name=name, **kwargs)

        self.config = load_config(overrides.pop('config', None))
        if overrides:
            self.config = self.config.override(overrides)

        # 运行时状态
        self.codes = CodeTable()          # 门类 / 一级学科代码表
        self.catalog = SchoolCatalog()    # 招生单位清单
        self.major_filters = []           # [(粒度, 代码), ...]
        self._table_resolved = set()      # 在门类表/一级学科表里查到过的专业名
        self._pending_yjxk = 0
        self._pending_autozy = []
        self._seen_majors = set()         # (dwdm, zydm)，避免同一个专业抓两遍
        self._crawled_schools = 0
        self._pending_provinces = []      # 还没枚举的省份（逐省推进，用完即弃）

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        spider.apply_settings(crawler.settings)
        return spider

    def apply_settings(self, settings):
        """把配置里的限速、cookie 写进 Scrapy 设置

        Crawler.crawl() 里 _create_spider() 排在 _create_engine() 前面，
        所以这里改设置能生效。
        """
        settings.set('DOWNLOAD_DELAY', self.config.delay())
        settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', self.config.concurrency())
        settings.set('CONCURRENT_REQUESTS', self.config.concurrency())
        if self.config.cookie:
            settings.set('COOKIES', parse_cookie_header(self.config.cookie))
        # pipeline 要用同一份配置（输出目录、Excel 策略），挂到 settings 上传过去
        settings.set('YZW_CONFIG_DATA', self.config)

    # ------------------------------------------------------------------
    # 初始请求
    # ------------------------------------------------------------------
    async def start(self):
        """Scrapy 2.13+ 的初始请求入口。

        Scrapy 2.16 起不再调度 start_requests()，2.13~2.15 则通过它调度，
        这里显式转发一次，兼顾新旧版本。
        """
        for request in self.initial_requests():
            yield request

    def start_requests(self):
        """兼容入口"""
        return self.initial_requests()

    def initial_requests(self):
        """初始请求：先装学科代码表，再枚举招生单位"""
        if self.degree_kind and not self.config.wants(self.degree_kind):
            self.logger.warning(
                '配置里的 degree 是 %s，本 spider 只抓 %s，因此不启动；'
                '要抓 %s 请改配置或换 spider',
                '/'.join(self.config.degrees), self.degree_kind, self.degree_kind)
            return

        if self.needs_code_table():
            yield self.get_request(self.API_CODE_ML, self.parse_code_ml)
        else:
            yield from self.resolve_majors()

    def needs_code_table(self):
        """是否需要装载学科代码表（子类可覆盖）"""
        return bool(self.config.major_names())

    # ------------------------------------------------------------------
    # 阶段一：学科代码表
    # ------------------------------------------------------------------
    def parse_code_ml(self, response):
        """门类表 -> 继续装一级学科表"""
        self.codes.load_ml(response.text)
        codes = self.codes.ml_codes()
        if not codes:
            self.logger.warning('门类代码表是空的，专业筛选会退化成全量抓取')
            yield from self.resolve_majors()
            return

        self._pending_yjxk = len(codes)
        for ml in codes:
            yield self.get_request(
                self.API_CODE_YJXK.format(ml=ml), self.parse_code_yjxk, ml=ml)

    def parse_code_yjxk(self, response):
        """一级学科表"""
        self.codes.load_yjxk(response.meta['ml'], response.text)
        self._pending_yjxk -= 1
        if self._pending_yjxk > 0:
            return
        yield from self.resolve_majors()

    # ------------------------------------------------------------------
    # 专业名称 -> 代码
    # ------------------------------------------------------------------
    def resolve_majors(self):
        """把配置里的专业列表解析成 (粒度, 代码)"""
        self.major_filters = []
        names = self.config.major_names()

        for name in names:
            for level, code in self.codes.resolve_all(name):
                self.add_major_filter(level, code)
                self._table_resolved.add(name)

        if not names:
            yield from self.after_majors_resolved()
            return

        # 再查一次专业表：同名专业可能横跨学术学位和专业学位
        # （"临床医学"既是 1002 这个一级学科，也是 105100 这个专业学位专业，
        #   一级学科代码表里只有前者）
        self._pending_autozy = list(names)
        for name in names:
            yield self.get_request(
                self.API_CODE_AUTOZY.format(q=quote(name)),
                self.parse_code_autozy, major=name)

    def after_majors_resolved(self):
        """专业解析完毕后的下一步（子类可覆盖）"""
        yield from self.begin_school_phase()

    def parse_code_autozy(self, response):
        """专业名 -> 专业代码（6 位）

        只认名称完全对得上的结果：autozy.do 是模糊匹配，
        查"经济学"会返回几十个沾边的专业，全收进来反而是噪音。
        """
        name = response.meta['major']
        items = parse_autozy(response.text)
        exact = [item for item in items
                 if (item.get('mc') or '').strip() == name]

        for item in exact:
            self.add_major_filter(LEVEL_ZY, item['dm'])

        if not exact and name not in self._table_resolved:
            candidates = '、'.join((item.get('mc') or '') for item in items[:5])
            self.logger.warning(
                '专业 "%s" 在研招网代码表里没有精确匹配%s',
                name, ('，相近的有：%s' % candidates) if candidates else '')

        if name in self._pending_autozy:
            self._pending_autozy.remove(name)
        if self._pending_autozy:
            return
        yield from self.after_majors_resolved()

    def add_major_filter(self, level, code):
        if (level, code) not in self.major_filters:
            self.major_filters.append((level, code))

    def major_groups(self):
        """本轮要发给 dwzys.do 的收窄条件 [(门类, 一级学科, 专业), ...]"""
        groups = []
        # 没有专业限制时按门类逐个抓 —— 和 match_major 的语义保持一致
        if self.config.all_majors() or not self.major_filters:
            for ml in self.codes.ml_codes():
                groups.append((ml, '', ''))
            return groups

        for level, code in self.major_filters:
            ml = code[:2]
            yjxk = code if level == 'yjxk' else ''
            zy = code if level == 'zy' else ''
            groups.append((ml, yjxk, zy))
        return groups

    def match_major(self, zydm):
        """专业代码是否落在配置指定的范围内"""
        if not self.major_filters:
            return True
        return any(match_major(level, code, zydm)
                   for level, code in self.major_filters)

    # ------------------------------------------------------------------
    # 阶段二：招生单位枚举
    # ------------------------------------------------------------------
    def begin_school_phase(self):
        """枚举要抓的招生单位"""
        if self.config.all_schools():
            # 逐省推进：一个省翻完再排下一个省。
            # 这样 request.max_schools 到量就能直接停下来，
            # 不会把 31 个省的白名单全跑一遍。
            self._pending_provinces = list(PROVINCES)
            ssdm = self._pending_provinces.pop(0)[0]
            yield self.school_page_request(ssdm, 0)
        else:
            for name in self.config.school_names():
                yield self.resolve_school_request(name)

    def school_page_request(self, ssdm, start):
        """院校库分页请求：ssdm 是省份码，start 是偏移量"""
        url = f'{self.API_SCHOOL_LIST}?ssdm={ssdm}&start={start}'
        return scrapy.Request(url=url, callback=self.parse_school_page,
                              meta={'ssdm': ssdm, 'start': start})

    def parse_school_page(self, response):
        """解析院校库列表页，逐省枚举招生单位"""
        ssdm = response.meta['ssdm']
        start = response.meta['start']
        units = parse_school_list(response.text, ssdm)

        for unit in units:
            self.catalog.add(unit)

        if len(units) == PAGE_SIZE:
            # 这一页满 20 条，后面还有
            yield self.school_page_request(ssdm, start + PAGE_SIZE)
            return

        self.logger.info('省份 %s 枚举完成，共 %d 所',
                         PROVINCE_NAMES.get(ssdm, ssdm),
                         len(self.catalog.schools_of(ssdm)))

        for unit in self.catalog.schools_of(ssdm):
            if self.school_limit_reached():
                break
            self._crawled_schools += 1
            yield from self.school_requests(unit)

        # 这个省翻完了，接着排下一个省
        if self._pending_provinces and not self.school_limit_reached():
            next_ssdm = self._pending_provinces.pop(0)[0]
            yield self.school_page_request(next_ssdm, 0)

    def resolve_school_request(self, name):
        """按院校名称或院校代码精确查招生单位"""
        form = {
            'dwmc': '', 'dwdm': '', 'ssdm': '', 'xxfs': '', 'tydxs': '',
            'jsggjh': '', 'jsxbjh': '', 'dwlxs': '',
            'start': 0, 'curPage': 1, 'pageSize': 10,
        }
        if str(name).isdigit():
            form['dwdm'] = str(name)
        else:
            form['dwmc'] = str(name)
        return self.form_request(self.API_DWS, form, self.parse_resolved_school,
                                 school=str(name))

    def parse_resolved_school(self, response):
        """解析招生单位查询结果"""
        msg = self.parse_json(response)
        name = response.meta['school']
        units = msg.get('list') or []

        unit = None
        if str(name).isdigit():
            unit = units[0] if units else None
        else:
            for candidate in units:
                if candidate.get('dwmc') == name:
                    unit = candidate
                    break
            if unit is None and units:
                self.logger.warning('院校 "%s" 没有精确匹配，按第一条 "%s" 处理',
                                    name, units[0].get('dwmc'))
                unit = units[0]

        if not unit:
            self.logger.error('院校 "%s" 没查到', name)
            return

        self.catalog.add(unit)
        self._crawled_schools += 1
        yield from self.school_requests(unit)

    def school_limit_reached(self):
        """试跑模式：抓够 config.request.max_schools 所就停"""
        limit = self.config.max_schools()
        return limit > 0 and self._crawled_schools >= limit

    def school_requests(self, unit):
        """针对一所招生单位生成抓取请求（子类实现）"""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # 翻页（需要登录态）
    # ------------------------------------------------------------------
    def paged_requests(self, url, form, callback, meta, total, step=None):
        """配了登录态时，按 start 逐页把剩下的记录取回来

        硕士侧的接口 start>0 默认要登录才放行（返回"请登录"），
        匿名状态下只能靠收窄条件绕开。
        配了 cookie（研招网登录态）之后这条路就能走通，
        记录不会再卡在"每页 10 条"上。

        没配 cookie 时这里什么都不产出，继续用收窄条件的办法。
        """
        if not self.config.cookie:
            return

        step = step or self.PAGE_SIZE
        start = step
        while start < total:
            page_form = dict(form, start=start)
            if 'pageSize' in page_form:
                page_form['curPage'] = start // step + 1

            page_meta = dict(meta)
            page_meta['form'] = page_form
            page_meta['split'] = 'paged'

            yield self.form_request(url, page_form, callback, **page_meta)
            start += step

    # ------------------------------------------------------------------
    # 通用请求/解析工具
    # ------------------------------------------------------------------
    @staticmethod
    def trans_data(targets):
        """处理科目数据，去重并用 'or' 连接多值"""
        result_list = []
        for target in targets:
            if target.strip().replace('\r\n', '').strip() not in result_list:
                data = target.strip().replace('\r\n', '')
                if data != "":
                    result_list.append(data)
        if len(result_list) > 1:
            result = " or ".join(result_list)
        elif result_list:
            result = result_list[0]
        else:
            result = ""
        return result

    def form_request(self, url, formdata, callback, **meta):
        """构造研招网的表单 POST 请求"""
        return scrapy.Request(
            url=url,
            method='POST',
            body=urlencode(formdata).encode('utf-8'),
            headers=self.AJAX_HEADERS,
            callback=callback,
            meta=meta,
        )

    def get_request(self, url, callback, **meta):
        """构造 GET 请求"""
        return scrapy.Request(url=url, callback=callback, meta=meta)

    def parse_json(self, response):
        """解析研招网的 JSON 响应，失败返回空字典"""
        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"JSON 解析失败: {e} (url={response.url})")
            return {}

        if not data.get('flag'):
            self.logger.warning(f"接口返回失败: {data.get('msg')} (url={response.url})")
            return {}

        return data.get('msg') or {}

    def study_type(self, code):
        """学习方式代码转名称"""
        return self.STUDY_TYPES.get(str(code), '')

    @staticmethod
    def merge_subject(current, text):
        """向单个科目槽位追加一个取值（去重后用 ' or ' 连接）"""
        if not text:
            return current
        if not current:
            return text
        if text in current:
            return current
        return f"{current} or {text}"

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------
    def closed(self, reason):
        """把枚举到的招生单位写进 data/schools.json

        定向抓取（schools: [南京大学]）时枚举到的只有一所，如果直接覆盖，
        会把之前生成好的全国清单冲掉 —— 所以这里只做合并、不做替换。
        """
        if not self.catalog.count():
            return
        try:
            total, added = merge_catalog(CATALOG_PATH, self.catalog.all())
            self.logger.info('招生单位清单已写入 %s（共 %d 所，本次新增 %d 所）',
                             CATALOG_PATH, total, added)
        except OSError as e:
            self.logger.warning('招生单位清单写入失败：%s', e)
