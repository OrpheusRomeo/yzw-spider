# -*- coding: utf-8 -*-
"""硕士招生目录爬虫

研招网（yz.chsi.com.cn）硕士专业目录查询接口调用流程：

    1. 招生单位   schools=all 走院校库逐省枚举；指定院校走 dws.do
    2. 开设专业   dwzys.do，按门类 -> 一级学科两级收窄
    3. 学院明细   yjfxs.do，超出 10 条时按 tydxs / xxfs 拆开再取

dwzys.do / yjfxs.do 都是每页硬顶 10 条，而且 start>0 一律返回"请登录"，
所以枚举专业只能靠收窄条件（门类、一级学科）规避，不能靠翻页。
"""
import json
from urllib.parse import urlencode

import scrapy

from yzw.items import MasterItem
from yzw.spiders.base import BaseSpider


class MasterSpider(BaseSpider):
    name = 'master'

    # 本 spider 只负责硕士
    degree_kind = 'master'

    # 每次请求取回的条数（接口硬顶 10 条，给大也没用）
    _page_size = 10

    def __init__(self, name=None, **kwargs):
        super().__init__(name=name, **kwargs)
        # 明细行去重：(dwdm, zydm, 整行内容)
        self._seen_details = set()

    def needs_code_table(self):
        """硕士侧一定要代码表：全量抓取时按门类收窄，指定专业时按名称解析"""
        return True

    def school_requests(self, unit):
        """一所学校 -> 按门类 / 一级学科发 dwzys.do"""
        dwdm = unit.get('dwdm')
        dwmc = unit.get('dwmc')

        for ml, yjxk, zy in self.major_groups():
            form = {
                'dwdm': dwdm, 'dwmc': dwmc,
                'zydm': zy, 'zymc': '', 'xwlx': '',
                'mldm': ml, 'yjxkdm': yjxk,
                'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                'start': 0, 'curPage': 1, 'pageSize': self._page_size,
            }
            yield self.form_request(
                self.API_DWZYS, form, self.parse_major_list,
                dwdm=dwdm, dwmc=dwmc, ml=ml, yjxkdm=yjxk, zydm=zy, form=form,
                szss=unit.get('szss') or '', szssm=unit.get('szssm') or '')

    def parse_major_list(self, response):
        """解析专业列表，对每个专业请求学院/研究方向明细"""
        msg = self.parse_json(response)
        if not msg:
            return

        dwdm = response.meta['dwdm']
        dwmc = response.meta['dwmc']
        ml = response.meta['ml']
        yjxkdm = response.meta['yjxkdm']
        zydm_filter = response.meta['zydm']

        majors = msg.get('list') or []
        total = msg.get('totalCount') or 0

        if total > len(majors):
            if yjxkdm or zydm_filter:
                # 已经收窄到一级学科 / 专业了还是超 10 条，
                # 只剩"配了登录态直接翻页"这一条路
                yield from self.paged_requests(
                    self.API_DWZYS, response.meta['form'],
                    self.parse_major_list, response.meta, total)
            else:
                # 门类这一档超过 10 条 —— 再用一级学科收窄一次
                children = self.codes.yjxk_codes(ml)
                if children:
                    for child in children:
                        form = {
                            'dwdm': dwdm, 'dwmc': dwmc,
                            'zydm': '', 'zymc': '', 'xwlx': '',
                            'mldm': ml, 'yjxkdm': child,
                            'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                            'start': 0, 'curPage': 1, 'pageSize': self._page_size,
                        }
                        yield self.form_request(
                            self.API_DWZYS, form, self.parse_major_list,
                            dwdm=dwdm, dwmc=dwmc, ml=ml, yjxkdm=child, zydm='',
                            form=form,
                            szss=response.meta.get('szss') or '',
                            szssm=response.meta.get('szssm') or '')
                else:
                    self.logger.warning('%s 的 %s 门类有 %d 个专业，超过 10 条且没有一级学科可拆',
                                        dwmc, ml, total)

        for major in majors:
            zydm = major.get('zydm')
            if not zydm:
                continue
            if not self.match_major(zydm):
                continue
            if not self.mark_major_seen(dwdm, zydm):
                continue
            yield from self.detail_requests(
                dwdm, dwmc, major,
                response.meta.get('szss') or '', response.meta.get('szssm') or '')

    def detail_requests(self, dwdm, dwmc, major, szss='', szssm=''):
        """某个专业 -> 学院 / 研究方向明细"""
        form = {
            'zydm': major.get('zydm') or '', 'zymc': major.get('zymc') or '',
            'dwdm': dwdm,
            'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
            'start': 0, 'pageSize': self._page_size, 'totalCount': 0,
        }
        yield self.form_request(
            self.API_YJFXS, form, self.parse_detail,
            dwdm=dwdm, dwmc=dwmc, major=major, form=form, split='',
            szss=szss, szssm=szssm)

    def parse_detail(self, response):
        """解析学院/研究方向明细，产出 MasterItem"""
        msg = self.parse_json(response)
        if not msg:
            return

        rows = msg.get('list') or []
        total = msg.get('totalCount') or 0

        if total > len(rows):
            # 明细被截断到 10 条，先试试带登录态能不能直接翻页
            yield from self.paged_requests(
                self.API_YJFXS, response.meta['form'],
                self.parse_detail, response.meta, total)

            # 再用收窄条件拆开重取
            splits = self.detail_splits(response.meta)
            if splits:
                for form, split in splits:
                    yield self.form_request(
                        self.API_YJFXS, form, self.parse_detail,
                        dwdm=response.meta['dwdm'], dwmc=response.meta['dwmc'],
                        major=response.meta['major'], form=form, split=split,
                        szss=response.meta.get('szss') or '',
                        szssm=response.meta.get('szssm') or '')
            elif response.meta.get('split') != 'paged':
                # 拆到底了还是超 10 条：研招网匿名接口本身也只给 10 条，
                # 这部分数据拿不到，明确记下来，不静默丢
                self.logger.warning(
                    '专业 %s(%s) 的明细有 %d 条，接口只返回 %d 条，'
                    '拆到 %s 之后仍超 10 条，剩余数据拿不到',
                    response.meta['major'].get('zymc'),
                    response.meta['major'].get('zydm'),
                    total, len(rows), response.meta.get('split') or '无')

        major = response.meta['major']
        dwmc = response.meta['dwmc']
        dwdm = response.meta['dwdm']

        for row in rows:
            # 多个维度拆出来的结果可能有重叠，按整行内容去重
            if not self.mark_detail_seen(dwdm, major.get('zydm'), row):
                continue

            item = MasterItem()

            # 层次信息：明细行自带省份、院校代码、完整专业代码层级
            item['Province'] = row.get('szss') or response.meta.get('szss') or ''
            item['ProvinceCode'] = row.get('szssm') or response.meta.get('szssm') or ''
            item['University'] = dwmc
            item['SchoolCode'] = dwdm or row.get('dwdm') or ''
            item['College'] = row.get('yxsmc') or ''
            item['Major'] = row.get('zymc') or major.get('zymc') or ''
            item['MajorCode'] = row.get('zydm') or major.get('zydm') or ''
            item['MajorSub'] = row.get('yjxkmc') or major.get('yjxkmc') or ''
            item['MajorSubCode'] = row.get('yjxkdm') or major.get('yjxkdm') or ''
            item['MajorCategory'] = row.get('mlmc') or major.get('mlmc') or ''
            item['MajorCategoryCode'] = row.get('mldm') or major.get('mldm') or ''
            item['ResearchInterests'] = row.get('yjfxmc') or ''
            item['Teacher'] = row.get('zdjs') or ''
            item['StudentNo'] = row.get('nzsrsstr') or str(row.get('nzsrs') or '')
            item['StudyType'] = self.study_type(row.get('xxfs'))
            item['ExamType'] = row.get('ksfsmc') or ''
            item['Content'] = row.get('zybz') or ''

            for index, text in self.extract_subjects(row.get('kskmz')):
                item[f'Subject{index}'] = text

            item['Link'] = self.build_detail_url(major, row)
            yield item

    def detail_splits(self, meta):
        """明细超过 10 条时的拆分方案

        yjfxs.do 每页硬顶 10 条、start>0 一律"请登录"，
        所以只能靠收窄条件把结果拆开重取。
        实测这个接口 **只认 tydxs（统招 / 非统招）** 一个筛选条件：
        xxfs / jsggjh / jsxbjh 传进去直接报"参数错误"。

        多数专业 tydxs 一步就能拆全（7 + 5 = 12 = totalCount）；
        如果一个专业的研究方向 tydxs 全都一样，那就真的拿不全了
        （研招网匿名状态下自己也只能看到 10 条），只能记警告。
        """
        form = meta.get('form') or {}
        split = meta.get('split') or ''

        if split == '':
            return [(dict(form, tydxs='0'), 'tydxs'),
                    (dict(form, tydxs='1'), 'tydxs')]
        return []

    def mark_major_seen(self, dwdm, zydm):
        """同一个专业的明细只抓一遍（门类查询和一级学科查询会重复命中）"""
        key = (str(dwdm), str(zydm))
        if key in self._seen_majors:
            return False
        self._seen_majors.add(key)
        return True

    def mark_detail_seen(self, dwdm, zydm, row):
        """明细行去重：多维度拆分出来的结果可能有重叠"""
        key = (str(dwdm), str(zydm),
               json.dumps(row, sort_keys=True, ensure_ascii=False))
        if key in self._seen_details:
            return False
        self._seen_details.add(key)
        return True

    def extract_subjects(self, kskmz):
        """从考试科目中提取 Subject1~Subject4。

        kskmz 结构：[{'km1Vo': 政治, 'km2Vo': 外语, 'km3Vo': 业务课一, 'km4Vo': 业务课二}, ...]
        每一组对应研招网页面上的一行科目，多组之间用"或"分隔。
        """
        buckets = ['', '', '', '']
        for group in kskmz or []:
            for slot in range(4):
                vo = group.get(f'km{slot + 1}Vo') or {}
                name = (vo.get('kskmmc') or '').strip()
                if not name:
                    continue
                code = (vo.get('kskmdm') or '').strip()
                text = f"({code}){name}" if code else name
                buckets[slot] = self.merge_subject(buckets[slot], text)
        return list(enumerate(buckets, start=1))

    def build_detail_url(self, major, row):
        """拼出研招网上的专业详情页地址"""
        params = {
            'zydm': major.get('zydm') or '',
            'zymc': major.get('zymc') or '',
            'xwlx': major.get('xwlx') or '',
            'mldm': major.get('mldm') or '',
            'mlmc': major.get('mlmc') or '',
            'yjxkdm': major.get('yjxkdm') or '',
            'yjxkmc': row.get('yjfxmc') or major.get('yjxkmc') or '',
            'xxfs': row.get('xxfs') or '',
            'tydxs': row.get('tydxs') or '',
            'jsggjh': row.get('jsggjh') or '',
            'jsxbjh': row.get('jsxbjh') or '',
            'sign': major.get('sign') or '',
        }
        return f"{self.API_ZYDETAIL}?{urlencode(params)}"
