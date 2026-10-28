# -*- coding: utf-8 -*-
"""博士招生目录爬虫

研招网（yz.chsi.com.cn）博士专业目录查询接口调用流程：

    1. POST /zsml/rs/dws.do                    按院校代码反查院校名称
    2. GET  /bsmlcx/cx/listYxsAndZyCollected   某院校的学院 + 专业列表
    3. GET  /bsmlcx/cx/listCxZymlCollected     某专业的研究方向/导师/考试科目明细
"""
import json
from urllib.parse import urlencode

import scrapy

from yzw.items import DoctorItem
from yzw.spiders.base import BaseSpider


class DoctorSpider(BaseSpider):
    name = 'doctor'

    # 博士目录查询接口
    API_YXS_AND_ZY = 'https://yz.chsi.com.cn/bsmlcx/cx/listYxsAndZyCollected'
    API_CX_ZYML = 'https://yz.chsi.com.cn/bsmlcx/cx/listCxZymlCollected'

    # 博士专业目录页（用于生成 Link）
    API_ZYML_INDEX = 'https://yz.chsi.com.cn/bsmlcx/cx/zymlIndex'

    # 大学代码列表（10284 = 南京大学）
    _university_codes = [10284]

    # 限定专业代码（zydm），留空表示抓取全部专业
    # 例：['020100'] 只抓"理论经济学"
    _major_filter = ['020200']

    # 博士目录一般不单列考试方式，统一按研招网口径记为"申请-考核"
    _exam_type = '申请-考核'

    # 每次请求取回的条数
    _page_size = 20

    def get_university_codes(self):
        """获取大学代码列表"""
        return self._university_codes

    def start_requests(self):
        """生成初始请求：按院校代码反查院校名称"""
        for code in self.get_university_codes():
            form = {
                'dwdm': code, 'dwmc': '', 'ssdm': '', 'xxfs': '',
                'tydxs': '', 'jsggjh': '', 'jsxbjh': '',
                'start': 0, 'curPage': 1, 'pageSize': self._page_size,
            }
            yield self.form_request(
                self.API_DWS, form, self.parse_university,
                dwdm=str(code),
            )

    def parse_university(self, response):
        """解析招生单位，拿到院校名称后拉取学院/专业列表"""
        msg = self.parse_json(response)
        if not msg:
            return

        for unit in msg.get('list') or []:
            dwdm = unit.get('dwdm')
            dwmc = unit.get('dwmc')
            if not dwdm:
                continue

            params = {
                'dwdm': dwdm, 'start': 0,
                'yxsdm': '', 'zydm': '', 'yjfxdm': '', 'xxfs': '', 'dsbh': '',
            }
            yield scrapy.Request(
                url=f"{self.API_YXS_AND_ZY}?{urlencode(params)}",
                callback=self.parse_yxs_list,
                meta={'dwdm': dwdm, 'dwmc': dwmc, 'start': 0, 'cur_page': 1},
            )

    def parse_yxs_list(self, response):
        """解析学院 + 专业列表，对每个专业请求明细"""
        msg = self.parse_json(response)
        if not msg:
            return

        dwdm = response.meta['dwdm']
        dwmc = response.meta['dwmc']
        cur_page = response.meta['cur_page']

        for row in msg.get('list') or []:
            yxsdm = row.get('yxsdm')
            zydm = row.get('zydm')
            if not yxsdm or not zydm:
                continue

            # 专业代码过滤
            if self._major_filter and zydm not in self._major_filter:
                continue

            params = {
                'dwdm': dwdm, 'yxsdm': yxsdm, 'zydm': zydm,
                'yjfxdm': '', 'xxfs': '', 'dsbh': '',
            }
            yield scrapy.Request(
                url=f"{self.API_CX_ZYML}?{urlencode(params)}",
                callback=self.parse_detail,
                meta={'dwdm': dwdm, 'dwmc': dwmc, 'row': row},
            )

        # 学院/专业列表翻页
        total_page = msg.get('totalPage') or 1
        if cur_page < total_page:
            next_page = cur_page + 1
            start = (next_page - 1) * self._page_size
            params = {
                'dwdm': dwdm, 'start': start,
                'yxsdm': '', 'zydm': '', 'yjfxdm': '', 'xxfs': '', 'dsbh': '',
            }
            yield scrapy.Request(
                url=f"{self.API_YXS_AND_ZY}?{urlencode(params)}",
                callback=self.parse_yxs_list,
                meta={'dwdm': dwdm, 'dwmc': dwmc, 'start': start, 'cur_page': next_page},
            )

    def parse_detail(self, response):
        """解析研究方向 / 导师 / 考试科目明细，产出 DoctorItem"""
        rows = self.parse_json_list(response)
        if not rows:
            return

        row = response.meta['row']
        dwmc = response.meta['dwmc']
        dwdm = response.meta['dwdm']

        for detail in rows:
            item = DoctorItem()

            item['University'] = dwmc
            item['College'] = row.get('yxsmc') or ''
            item['Major'] = row.get('zymc') or ''
            item['ResearchInterests'] = detail.get('yjfxmc') or ''
            item['Teacher'] = detail.get('dsxm') or ''
            item['StudentNo'] = self.format_student_no(detail)
            item['StudyType'] = self.study_type(detail.get('xxfs'))
            item['ExamType'] = self._exam_type
            item['Content'] = detail.get('yjfxbz') or detail.get('dsbz') or ''

            for index, text in self.extract_subjects(detail.get('kskm')):
                item[f'Subject{index}'] = text

            item['Link'] = f"{self.API_ZYML_INDEX}?dwdm={dwdm}"
            yield item

    def format_student_no(self, detail):
        """拟招人数：优先用方向人数，其次用导师人数"""
        for key in ('yjfxzsrs', 'dszsrs'):
            value = detail.get(key)
            if value is not None:
                return str(value)
        return ''

    def extract_subjects(self, kskm):
        """从考试科目中提取 Subject1~Subject4。

        kskm 结构：[[[{'key': 代码, 'value': 名称}, ...], [...], [...]], ...]
        外层是科目组（组之间用"或"分隔），中层是科目类别（外语/专业课一/专业课二...），
        内层是该类别下的可选科目。
        """
        buckets = ['', '', '', '']
        for group in kskm or []:
            for slot, options in enumerate(group[:4]):
                names = []
                for option in options or []:
                    name = (option.get('value') or '').strip()
                    if not name:
                        continue
                    code = (option.get('key') or '').strip()
                    text = f"({code}){name}" if code else name
                    if text not in names:
                        names.append(text)
                if not names:
                    continue
                buckets[slot] = self.merge_subject(buckets[slot], ' or '.join(names))
        return list(enumerate(buckets, start=1))

    def parse_json_list(self, response):
        """博士明细接口的 msg 直接是一个列表"""
        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"JSON 解析失败: {e} (url={response.url})")
            return []

        if not data.get('flag'):
            self.logger.warning(f"接口返回失败: {data.get('msg')} (url={response.url})")
            return []

        msg = data.get('msg')
        if isinstance(msg, list):
            return msg
        return msg.get('list') or [] if isinstance(msg, dict) else []
