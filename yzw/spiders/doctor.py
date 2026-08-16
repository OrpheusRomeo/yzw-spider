# -*- coding: utf-8 -*-
import json
import scrapy
from yzw.items import DoctorItem
from yzw.spiders.base import BaseSpider


class DoctorSpider(BaseSpider):
    # dwdm: 10284
    # yxsdm: 025
    # zydm: 083000
    # yjfxdm:
    # xxfs:
    # dsbh:
    # _t: 1649243277226

    name = 'doctor'
    start_urls = "https://yz.chsi.com.cn/bsmlcx/cx/listYxsAndZyCollected?start={}&yxsdm={}&zydm={}&yjfxdm=&xxfs=&dsbh=&dwdm=&_t=1649242759688"

    # 大学代码列表
    _university_codes = [10284]

    def get_university_codes(self):
        """获取大学代码列表"""
        return self._university_codes

    def start_requests(self):
        """生成初始请求"""
        for code in self.get_university_codes():
            url = self.start_urls.format(0, '', '')
            yield scrapy.Request(url=url, method='GET', callback=self.parse)

    def parse(self, response):
        """解析 JSON 响应"""
        try:
            json_data = json.loads(response.body.decode('utf-8'))
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析失败: {e}")
            return None

        if "msg" not in json_data:
            return None
        if "totalCount" not in json_data["msg"]:
            return None

        msg = json_data["msg"]
        total = msg.get("totalPage", 0)
        current = msg.get("curPage", 0)
        data_list = msg.get("list", [])

        for i in data_list:
            yxsdm = i.get("yxsdm", "")
            yxsmc = i.get("yxsmc", "")
            yxszsrs = i.get("yxszsrs", "")
            zydm = i.get("zydm", "")
            zymc = i.get("zymc", "")
            zyzsrs = i.get("zyzsrs", "")

            if current < total:
                start = (current - 0) * 20
                new_url = self.start_urls.format(start, yxsdm, zydm)
                item = DoctorItem()
                yield scrapy.Request(url=new_url, callback=self.call_detail, meta={"item": item})

    def call_detail(self, response):
        """解析详情页"""
        item = response.meta["item"]
        item = self.parse_detail_common(response, item)
        yield item

    def get_major_list(self):
        """获取博士专业列表（预留方法）"""
        # TODO: 实现博士专业列表获取逻辑
        return []


if __name__ == '__main__':
    test = DoctorSpider()
    dl = '02'
    major_list = test.get_major(dl)
    print(major_list)
