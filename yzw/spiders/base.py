# -*- coding: utf-8 -*-
"""爬虫基类 —— 配置装载、院校枚举、学科代码表的公共逻辑

整个爬取分成四个阶段，靠 Scrapy 的回调链串起来：

    1. 学科代码表   ml.json -> yjxk/{门类}.json -> autozy.do（按需）
    2. 招生单位枚举 schools=[- all] 走院校库，逐省翻页
                     schools=[..]     走 dws.do，按名称/代码精确查
    3. 专业枚举     dwzys.do，按门类 / 一级学科收窄
    4. 明细         yjfxs.do，超出 10 条时按 tydxs / xxfs 拆开再取
"""
import json
import logging
import os
from urllib.parse import quote, urlencode

import scrapy
from scrapy.exceptions import UsageError

from yzw.codes import (API_AUTOZY, API_ML, API_YJXK, LEVEL_ZY, CodeTable,
                       match_major, parse_autozy)
from yzw.config import (OVERRIDE_KEYS, OVERRIDE_PATHS, PROJECT_ROOT,
                         load_config)
from yzw.discovery import (PAGE_SIZE, PROVINCE_NAMES, PROVINCES, SchoolCatalog,
                           base_name, merge_catalog, parse_school_list)
from yzw.progress import emit_progress

logger = logging.getLogger(__name__)

# 枚举到的招生单位写到这里，方便核对与复用
CATALOG_PATH = os.path.join(PROJECT_ROOT, 'data', 'schools.json')

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
        # -a 传进来的参数要么是认识的配置项，要么直接报错 ——
        # 拼错参数名（比如 output.directory 写成 output.dir）静默忽略最坑人
        overrides = {}
        config_path = kwargs.pop('config', None)
        for key in list(kwargs):
            if key in OVERRIDE_KEYS or key in OVERRIDE_PATHS:
                overrides[key] = kwargs.pop(key)
            else:
                raise UsageError(
                    '命令行参数 {} 无法识别。可用参数：config、{}'.format(
                        key, '、'.join(OVERRIDE_KEYS + OVERRIDE_PATHS)))

        super().__init__(name=name, **kwargs)

        self.config = self.load_base_config(config_path)
        if overrides:
            self.config = self.config.override(overrides)

        # 运行时状态
        self.codes = CodeTable()          # 门类 / 一级学科代码表
        self.catalog = SchoolCatalog()    # 本次枚举到的招生单位
        # 已有的全国院校清单，用来把校名解析成招生单位代码
        self.catalog_index = SchoolCatalog.load(CATALOG_PATH)
        self.major_filters = []           # [(粒度, 代码), ...]
        self._table_resolved = set()      # 在门类表/一级学科表里查到过的专业名
        self._pending_yjxk = 0
        self._pending_autozy = []
        self._seen_majors = set()         # (dwdm, zydm)，避免同一个专业抓两遍
        self._crawled_schools = 0
        self._crawled_codes = set()       # 已经抓过的招生单位代码
        self._pending_provinces = []      # 还没枚举的省份（逐省推进，用完即弃）
        self._extras_done = False         # extra_schools 是否已经补过

    def load_base_config(self, config_path):
        """读配置文件，子类可以换成别的来源（测试里换成空配置）"""
        return load_config(config_path)

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
        # pipeline 和中间件要用同一份配置（输出目录、Excel 策略、登录态），
        # 挂到 settings 上传过去
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

        # 目标为空就别白跑一遍代码表了
        if self.no_targets():
            return

        if self.needs_code_table():
            yield self.get_request(self.API_CODE_ML, self.parse_code_ml)
        else:
            yield from self.resolve_majors()

    def no_targets(self):
        """一个院校都没指定时报错，返回 True 表示不用继续了"""
        if self.config.all_schools() or self.config.school_names():
            return False
        self.logger.error(
            '配置里没有指定任何院校，没有可抓的目标；'
            '要抓全国请写 schools: [- all]，要抓指定院校请写 schools: [校名]')
        return True

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
            self._pending_provinces = self.pending_provinces()
            if not self._pending_provinces:
                self.logger.error('配置的省份里没有可枚举的省份，没有可抓的目标')
                return
            ssdm = self._pending_provinces.pop(0)[0]
            yield self.school_page_request(ssdm, 0)
        else:
            names = self.config.school_names()
            if self.no_targets():
                return
            for name in names:
                yield from self.resolve_school_requests(name)

    def pending_provinces(self):
        """这次要枚举哪些省，按省份表里的顺序排

        配置里限定了省份就只排那几个 —— 走院校库 sch/search.do?ssdm=xx，
        三个请求就能拿到全省的院校，不用把每所院校展开成一次 dws.do 请求
        （dws.do 匿名状态下每页硬顶 10 条，start>0 一律请登录）。
        """
        wanted = set(self.config.provinces())
        if not wanted:
            return list(PROVINCES)
        return [item for item in PROVINCES if item[0] in wanted]

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
            # 走 crawl_unit 而不是就地展开 —— "开始抓一所学校"只有这一处，
            # 进度标记也只在这里发一次
            yield from self.crawl_unit(unit)

        # 这个省翻完了，接着排下一个省
        if self._pending_provinces and not self.school_limit_reached():
            next_ssdm = self._pending_provinces.pop(0)[0]
            yield self.school_page_request(next_ssdm, 0)
        elif not self._extras_done and not self.school_limit_reached():
            # 省份枚举跑完了，把 extra_schools 补上 ——
            # 它们是给"院校库里没收录、枚举漏掉"的院校兜底的
            self._extras_done = True
            for name in self.config.extra_schools:
                if self.school_limit_reached():
                    break
                yield from self.resolve_school_requests(name)

    def resolve_school_requests(self, name):
        """按院校名称或院校代码查招生单位，一个校区一个请求

        校名先在院校清单（data/schools.json）里按"本体名"匹配：
        "中国石油大学" -> 中国石油大学(华东) + 中国石油大学(北京)，两个校区都抓。
        本体名对不上的（"交通大学"其实是上海交通大学、华东交通大学等四所不同的学校）
        在清单里就匹配不到，会退回按名字查接口，由接口结果判定。

        dws.do 的 dwmc 是子串匹配，直接拿校名查并不可靠
        （实测 dwmc=大学 能匹配 485 所，但只返回 10 条）。
        """
        form = {
            'dwmc': '', 'dwdm': '', 'ssdm': '', 'xxfs': '', 'tydxs': '',
            'jsggjh': '', 'jsxbjh': '', 'dwlxs': '',
            'start': 0, 'curPage': 1, 'pageSize': 10,
        }
        text = str(name).strip()

        # 填代码就按代码查
        if text.isdigit():
            yield self.form_request(
                self.API_DWS, dict(form, dwdm=text), self.parse_resolved_school,
                school=text, by_code=True, dwdm=text)
            return

        # 校名先从院校清单里找同名（含多校区）
        campuses = self.catalog_index.find_by_base_name(text)
        if campuses:
            if len(campuses) > 1:
                self.logger.info(
                    '院校 "%s" 匹配到 %d 个校区，逐个抓取：%s',
                    text, len(campuses),
                    '、'.join(u.get('dwmc') or '' for u in campuses))
            for unit in campuses:
                yield self.form_request(
                    self.API_DWS, dict(form, dwdm=unit['dwdm']),
                    self.parse_resolved_school,
                    school=unit.get('dwmc') or text, by_code=True,
                    dwdm=unit['dwdm'])
            return

        # 清单里没有 -> 退回按名字查，由接口结果判定是不是同一所大学
        yield self.form_request(
            self.API_DWS, dict(form, dwmc=text), self.parse_resolved_school,
            school=text, by_code=False)

    def parse_resolved_school(self, response):
        """解析招生单位查询结果

        按代码查的（从院校清单换来的 dwdm）结果唯一，直接用。
        按名字查的只接受"本体名与查询一致"的候选：
        - "中国石油大学" -> (华东)、(北京) 本体名一致，是同一所大学的两个校区，都抓
        - "交通大学"     -> 北京交通大学、大连交通大学…… 本体名全对不上，一个都不抓
        """
        msg = self.parse_json(response)
        name = response.meta['school']
        units = msg.get('list') or []
        total = msg.get('totalCount') or 0

        if response.meta.get('by_code'):
            # 按代码查的，返回的就是它
            candidates = units[:1]
            if not candidates:
                self.logger.error('院校 "%s" 没查到，跳过', name)
            elif candidates[0].get('dwdm') != response.meta.get('dwdm'):
                self.logger.error(
                    '院校 "%s" 返回的代码是 %s，与请求的 %s 对不上，已跳过',
                    name, candidates[0].get('dwdm'), response.meta.get('dwdm'))
                candidates = []
        else:
            key = base_name(name)
            candidates = [u for u in units
                          if base_name(u.get('dwmc') or '') == key]
            if not candidates:
                names = '、'.join(u.get('dwmc') or '' for u in units[:5])
                if total > 1:
                    self.logger.error(
                        '院校 "%s" 匹配到 %d 所，没有一所是它本身，已跳过。'
                        '（校名是子串匹配，"交通大学"能匹配 8 所）'
                        '请写全称或改用招生单位代码。候选：%s',
                        name, total, names)
                elif total == 1:
                    self.logger.error(
                        '院校 "%s" 没有精确匹配（唯一候选是 %s），已跳过。'
                        '请写全称或改用招生单位代码。', name, names)
                else:
                    self.logger.error(
                        '院校 "%s" 没查到，已跳过。'
                        '请写全称或改用招生单位代码。', name)
            elif total > len(units):
                self.logger.warning(
                    '院校 "%s" 匹配到 %d 所，接口只返回了 %d 条，可能漏掉部分校区',
                    name, total, len(units))

        for unit in candidates:
            if self.school_limit_reached():
                break
            yield from self.crawl_unit(unit)

    def crawl_unit(self, unit):
        """一所招生单位 -> 抓它的专业明细"""
        self.catalog.add(unit)
        dwdm = unit.get('dwdm')
        if dwdm in self._crawled_codes:
            # 全量模式下 extra_schools 可能已经被省份枚举抓到过了
            self.logger.info('院校 %s 已经抓过，跳过', unit.get('dwmc'))
            return
        self._crawled_codes.add(dwdm)
        self._crawled_schools += 1
        emit_progress('school', index=self._crawled_schools,
                      dwdm=dwdm, name=unit.get('dwmc') or '')
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
        emit_progress('done', schools=self._crawled_schools)
        if not self.catalog.count():
            return
        try:
            total, added = merge_catalog(CATALOG_PATH, self.catalog.all())
            self.logger.info('招生单位清单已写入 %s（共 %d 所，本次新增 %d 所）',
                             CATALOG_PATH, total, added)
        except OSError as e:
            self.logger.warning('招生单位清单写入失败：%s', e)
