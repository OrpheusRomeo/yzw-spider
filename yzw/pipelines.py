# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import csv
import codecs
import json
from itemadapter import ItemAdapter
from xlutils.copy import copy
from .utils.excel_handler import ExcelHandler
from .utils.csv_handler import CsvHandler


class YzwPipeline(object):
    def __init__(self):
        path = './result/csv/master_directory.csv'
        self.file = open(path,'a+',encoding='utf-8')
        self.writer = csv.writer(self.file)

    def process_item(self, item, spider):
        print(spider.name)
        self.writer.writerow(
            (item["University"],item["ExamType"],item["College"],item["Major"],item["ResearchInterests"],item["StudyType"],item["Teacher"],item["StudentNo"],item["Subject1"],item["Subject2"],item["Subject3"],item["Subject4"],item["Content"],item["Link"]))
        return item

    def close_spider(self, spider):
        self.file.close()

class CsvPipeline(object):
    def __init__(self):
        self.path = './result/csv/master_directory1.csv'
        self.csv_handler = CsvHandler()

    def process_item(self, item, spider):
        print(spider.name)
        self.csv_handler.import_data(item, self.path)
        return item

    def close_spider(self, spider):
        self.file.close()



class JsonPipeline(object):
    def __init__(self):
        self.file = codecs.open('./result/json/master_directory.json', 'w', encoding='utf-8')
    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(line)
        return item
    def spider_closed(self, spider):
        self.file.close()

class ExcelPipeline(object):
    def __init__(self):
        self.file = './result/xlsx/master_directory.xlsx'
        self.head = ['Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4', 'University', 'ExamType', 'College', 'Major', 'Studytype', 'ResearchInterests', 'Teacher', 'StudentNo', 'Content']
        self.test = ExcelHandler()
        self.excel = self.test.init_excel(self.file, 'sheet1', self.head) 

    def process_item(self, item, spider):
        # 调整顺序
        has_sheet = self.test.has_sheet(self.file, item['University'])
        if has_sheet is False:
            self.test.add_sheet(self.file, item['University'], self.head)
            self.test.append_data(self.file, item['University'], item)
        else:
            self.test.append_data(self.file, item['University'], item)
        pass

    def close_spider(self, spider):
        pass
        

