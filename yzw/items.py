# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class YzwItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class MasterItem(scrapy.Item):
    # define the fields for your item here like:
    # --- 层次信息 ---
    Province = scrapy.Field()        # 省份名称，如 江苏
    ProvinceCode = scrapy.Field()    # 省份代码，如 32
    University = scrapy.Field()      # 校名，如 南京大学
    SchoolCode = scrapy.Field()      # 招生单位代码，如 10284
    College = scrapy.Field()         # 学院 / 招生单位名称
    Major = scrapy.Field()           # 专业名称，如 理论经济学
    MajorCode = scrapy.Field()       # 专业代码（6 位），如 020100
    MajorSub = scrapy.Field()        # 专业小类（一级学科）名称，如 理论经济学
    MajorSubCode = scrapy.Field()    # 专业小类代码（4 位），如 0201
    MajorCategory = scrapy.Field()   # 专业大类（门类）名称，如 经济学
    MajorCategoryCode = scrapy.Field()  # 专业大类代码（2 位），如 02
    # --- 明细 ---
    ResearchInterests = scrapy.Field()
    Teacher = scrapy.Field()
    StudentNo = scrapy.Field()
    StudyType = scrapy.Field()
    ExamType = scrapy.Field()
    Content = scrapy.Field()
    Subject1 = scrapy.Field()
    Subject2 = scrapy.Field()
    Subject3 = scrapy.Field()
    Subject4 = scrapy.Field()
    Link = scrapy.Field()
    pass

class DoctorItem(scrapy.Item):
    # define the fields for your item here like:
    # --- 层次信息 ---
    # 博士接口不返回省份和专业层级，能拿到就填，拿不到留空
    Province = scrapy.Field()        # 省份名称，如 江苏
    ProvinceCode = scrapy.Field()    # 省份代码，如 32
    University = scrapy.Field()      # 校名，如 南京大学
    SchoolCode = scrapy.Field()      # 招生单位代码，如 10284
    College = scrapy.Field()         # 学院 / 招生单位名称
    Major = scrapy.Field()           # 专业名称，如 理论经济学
    MajorCode = scrapy.Field()       # 专业代码（6 位），如 020100
    MajorSub = scrapy.Field()        # 专业小类（一级学科）名称 —— 接口不提供
    MajorSubCode = scrapy.Field()    # 专业小类代码（4 位）—— 接口不提供
    MajorCategory = scrapy.Field()   # 专业大类（门类）名称 —— 接口不提供
    MajorCategoryCode = scrapy.Field()  # 专业大类代码（2 位）—— 接口不提供
    # --- 明细 ---
    ResearchInterests = scrapy.Field()
    Teacher = scrapy.Field()
    StudentNo = scrapy.Field()
    StudyType = scrapy.Field()
    ExamType = scrapy.Field()
    Content = scrapy.Field()
    Subject1 = scrapy.Field()
    Subject2 = scrapy.Field()
    Subject3 = scrapy.Field()
    Subject4 = scrapy.Field()
    Link = scrapy.Field()
    pass

