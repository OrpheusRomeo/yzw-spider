# -*- coding: utf-8 -*-
import scrapy
from yzw.items import MasterItem
from yzw.spiders.base import BaseSpider


class MasterSpider(BaseSpider):
    # 示例 南京大学 02 0201 理论经济学
    # issdm: 32
    # dwmc: 南京大学
    # mldm: 02
    # mlmc:
    # yjxkdm: 0201
    # xxfs:
    # zymc:
    name = 'master'
    start_urls = 'https://yz.chsi.com.cn/zsml/querySchAction.do?ssdm=&dwmc={}&mldm={}&mlmc=&yjxkdm={}&xxfs=&zymc='

    # 大学列表
    _universities = [
        '南京大学', '南开大学', '外交学院', '武汉大学', '华中科技大学',
        '清华大学', '北京大学', '中科院大学', '浙江大学', '复旦大学',
        '上海交通大学', '中国科学技术大学', '哈尔滨工业大学', '西安交通大学'
    ]

    # 学科大类代码
    _discipline_codes = [
        {"mc": "哲学", "dm": "01"}, {"mc": "经济学", "dm": "02"},
        {"mc": "法学", "dm": "03"}, {"mc": "教育学", "dm": "04"},
        {"mc": "文学", "dm": "05"}, {"mc": "历史学", "dm": "06"},
        {"mc": "理学", "dm": "07"}, {"mc": "工学", "dm": "08"},
        {"mc": "农学", "dm": "09"}, {"mc": "医学", "dm": "10"},
        {"mc": "军事学", "dm": "11"}, {"mc": "管理学", "dm": "12"},
        {"mc": "艺术学", "dm": "13"}, {"mc": "交叉学科", "dm": "14"}
    ]

    def get_universities(self):
        """获取大学列表"""
        return self._universities

    def get_dm(self):
        """获取学科大类代码列表"""
        return [i["dm"] for i in self._discipline_codes]

    def start_requests(self):
        """生成初始请求"""
        for university in self.get_universities():
            for discipline_code in self.get_dm():
                major_list = self.get_major(discipline_code)
                for major_code in major_list:
                    url = self.start_urls.format(university, discipline_code, major_code)
                    yield scrapy.Request(url=url, method='GET', callback=self.parse)

    def parse(self, response):
        """解析列表页"""
        domain = "https://yz.chsi.com.cn"
        url_list = response.xpath("//tbody/tr/td[8]/a/@href").extract()

        for href in url_list:
            item = MasterItem()
            new_url = domain + href
            item["Link"] = new_url
            yield scrapy.Request(url=new_url, callback=self.call_detail, meta={"item": item})

    def call_detail(self, response):
        """解析详情页"""
        item = response.meta["item"]
        item = self.parse_detail_common(response, item)
        item["Link"] = response.meta["item"]["Link"]
        yield item


if __name__ == '__main__':
    test = MasterSpider()
    dl = '02'
    major_list = test.get_major(dl)
    print(major_list)
