# -*- coding: utf-8 -*-
"""硕士 + 博士一起抓

配置里 degree 写成 both 时用这个入口：

    scrapy crawl all

硕士和博士是两套接口（zsml 目录 / bsmlcx 目录），但前面的准备工作是共用的：
学科代码表只装一次，招生单位也只枚举一次，然后按学校分发给两个子 spider。
"""
from yzw.spiders.base import BaseSpider
from yzw.spiders.doctor import DoctorSpider
from yzw.spiders.master import MasterSpider


class AllSpider(BaseSpider):
    name = 'all'

    def __init__(self, name=None, **kwargs):
        super().__init__(name=name, **kwargs)
        self._subs = []

    # ------------------------------------------------------------------
    # 子 spider
    # ------------------------------------------------------------------
    def make_subs(self):
        """按配置里的学位层次建出硕士 / 博士子 spider

        子 spider 共用同一份配置、同一份代码表，接到同一个 crawler 上
        共享限速等设置。
        """
        if self._subs:
            return self._subs

        for degree in self.config.degrees:
            spider_cls = MasterSpider if degree == 'master' else DoctorSpider
            sub = spider_cls()
            sub.config = self.config
            sub.codes = self.codes          # 共用代码表，不用装两遍
            # _set_crawler 是 Scrapy from_crawler 内部用的官方钩子，
            # 把子 spider 接到同一个 crawler 上
            sub._set_crawler(self.crawler)
            self._subs.append(sub)

        self.logger.info('本次同时抓取：%s',
                         '、'.join(s.name for s in self._subs))
        return self._subs

    def needs_code_table(self):
        """硕士侧一定要代码表；博士侧只在指定了专业时需要"""
        if 'master' in self.config.degrees:
            return True
        return bool(self.config.major_names())

    # ------------------------------------------------------------------
    # 阶段衔接
    # ------------------------------------------------------------------
    def after_majors_resolved(self):
        """专业解析完毕 -> 把筛选条件分发给子 spider，然后开始枚举学校"""
        subs = self.make_subs()
        for sub in subs:
            sub.major_filters = list(self.major_filters)
        yield from self.begin_school_phase()

    def school_requests(self, unit):
        """一所学校 -> 分发给硕士 / 博士两个子 spider"""
        for sub in self._subs:
            yield from sub.school_requests(unit)
