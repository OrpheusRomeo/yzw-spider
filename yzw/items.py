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
    # name = scrapy.Field()
    University = scrapy.Field()
    College = scrapy.Field()
    Major = scrapy.Field()
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

