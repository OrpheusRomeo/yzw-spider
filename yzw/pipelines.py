# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import csv
import codecs
import json
from itemadapter import ItemAdapter

class YzwPipeline(object):
    def __init__(self):
        path_yzw = './result/csv/shuoshimulu.csv'
        self.file_yzw = open(path_yzw,'a+',encoding='utf-8')
        self.writer_yzw = csv.writer(self.file_yzw)

    def process_item(self, item, spider):
        print(spider.name)
        self.writer_yzw.writerow(
            (item["University"],item["ExamType"],item["College"],item["Major"],item["ResearchInterests"],item["StudyType"],item["Teacher"],item["StudentNo"],item["Subject1"],item["Subject2"],item["Subject3"],item["Subject4"],item["Content"],item["Link"]))
        return item

    def close_spider(self,spider):
        self.file.close()


class JsonPipeline(object):
    def __init__(self):
        self.file = codecs.open('./result/json/shuoshimulu.json', 'w', encoding='utf-8')
    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(line)
        return item
    def spider_closed(self, spider):
        self.file.close()
