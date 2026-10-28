# -*- coding: utf-8 -*-
"""硕士招生目录爬虫

研招网（yz.chsi.com.cn）硕士专业目录查询接口调用流程：

    1. POST /zsml/rs/dws.do      按院校名查询招生单位 -> 拿到院校代码 dwdm
    2. POST /zsml/rs/dwzys.do    某招生单位的开设专业 -> 拿到专业列表
    3. POST /zsml/rs/yjfxs.do    某专业的学院/研究方向明细 -> 科目、导师、拟招人数
"""
from urllib.parse import urlencode

import scrapy

from yzw.items import MasterItem
from yzw.spiders.base import BaseSpider


class MasterSpider(BaseSpider):
    name = 'master'

    # 大学列表
    _universities = [
        '南京大学', '南开大学',
    ]

    # 学科大类代码
    _discipline_codes = [
        {"mc": "经济学", "dm": "02"},
    ]

    # 每次请求取回的条数
    _page_size = 20

    def get_universities(self):
        """获取大学列表"""
        return self._universities

    def get_dm(self):
        """获取学科大类代码列表"""
        return [i["dm"] for i in self._discipline_codes]

    def start_requests(self):
        """生成初始请求：按院校名查招生单位"""
        for university in self.get_universities():
            form = {
                'dwmc': university, 'dwdm': '', 'ssdm': '', 'xxfs': '',
                'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                'start': 0, 'curPage': 1, 'pageSize': self._page_size,
            }
            yield self.form_request(
                self.API_DWS, form, self.parse_university,
                university=university,
            )

    def parse_university(self, response):
        """解析招生单位列表，逐个专业代码展开请求"""
        msg = self.parse_json(response)
        if not msg:
            return

        for unit in msg.get('list') or []:
            dwdm = unit.get('dwdm')
            dwmc = unit.get('dwmc')
            if not dwdm:
                continue

            for dm in self.get_dm():
                for major_code in self.get_major(dm):
                    form = {
                        'dwdm': dwdm, 'dwmc': dwmc,
                        'zydm': '', 'zymc': '', 'xwlx': '',
                        'mldm': dm, 'yjxkdm': major_code,
                        'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                        'start': 0, 'curPage': 1, 'pageSize': self._page_size,
                    }
                    yield self.form_request(
                        self.API_DWZYS, form, self.parse_major_list,
                        dwdm=dwdm, dwmc=dwmc, start=0, cur_page=1,
                        mldm=dm, yjxkdm=major_code,
                    )

    def parse_major_list(self, response):
        """解析专业列表，对每个专业请求学院/研究方向明细"""
        msg = self.parse_json(response)
        if not msg:
            return

        dwdm = response.meta['dwdm']
        dwmc = response.meta['dwmc']
        cur_page = response.meta['cur_page']

        for major in msg.get('list') or []:
            zydm = major.get('zydm')
            zymc = major.get('zymc')
            if not zydm:
                continue

            form = {
                'zydm': zydm, 'zymc': zymc, 'dwdm': dwdm,
                'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                'start': 0, 'pageSize': self._page_size, 'totalCount': 0,
            }
            yield self.form_request(
                self.API_YJFXS, form, self.parse_detail,
                dwdm=dwdm, dwmc=dwmc, major=major,
            )

        # 专业列表翻页
        total_page = msg.get('totalPage') or 1
        if cur_page < total_page:
            next_page = cur_page + 1
            form = {
                'dwdm': dwdm, 'dwmc': dwmc,
                'zydm': '', 'zymc': '', 'xwlx': '',
                'mldm': response.meta.get('mldm', ''),
                'yjxkdm': response.meta.get('yjxkdm', ''),
                'xxfs': '', 'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                'start': (next_page - 1) * self._page_size,
                'curPage': next_page, 'pageSize': self._page_size,
            }
            yield self.form_request(
                self.API_DWZYS, form, self.parse_major_list,
                dwdm=dwdm, dwmc=dwmc, start=form['start'], cur_page=next_page,
                mldm=response.meta.get('mldm', ''),
                yjxkdm=response.meta.get('yjxkdm', ''),
            )

    def parse_detail(self, response):
        """解析学院/研究方向明细，产出 MasterItem"""
        msg = self.parse_json(response)
        if not msg:
            return

        major = response.meta['major']
        dwmc = response.meta['dwmc']

        for row in msg.get('list') or []:
            item = MasterItem()

            item['University'] = dwmc
            item['College'] = row.get('yxsmc') or ''
            item['Major'] = row.get('zymc') or major.get('zymc') or ''
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
