# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import codecs
import json
from itemadapter import ItemAdapter
from xlutils.copy import copy
from .utils.excel_handler import ExcelHandler
from .utils.csv_handler import CsvHandler

       
class MasterPipeline(object):
    def __init__(self):
        self.path = './result/master/'
        self.name = 'master_directory'
        self.csv_file = self.path + self.name + '.csv'
        self.json_file = self.path + self.name + '.json'
        self.excel_file = self.path + self.name + '.xlsx'
        self.head = ['Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4', 'University', 'ExamType', 'College', 'Major', 'Studytype', 'ResearchInterests', 'Teacher', 'StudentNo', 'Content']
        self.csv_handler = CsvHandler()
        self.test = ExcelHandler()
        self.excel = self.test.init_excel(self.excel_file, 'sheet1', self.head) 

    def process_item(self, item, spider):
        #print(item)
        # 调整顺序
        # 三种文件可以根据自身需要进行舍弃, 注释代码即可        
        # 写入 csv
        self.csv_handler.import_data(item, self.csv_file)
        # 写入 json
        file = codecs.open(self.json_file, 'a', encoding='utf-8')
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        file.write(line)
        # 写入 excel
        has_sheet = self.test.has_sheet(self.excel_file, item['University'])
        if has_sheet is False:
            self.test.add_sheet(self.excel_file, item['University'], self.head)
            self.test.append_data(self.excel_file, item['University'], item)
        else:
            self.test.append_data(self.excel_file, item['University'], item)
        pass

    def close_spider(self, spider):
        pass


class DoctorPipeline(object):
    def __init__(self):
        self.file = './result/xlsx/doctor_directory.xlsx'
        self.head = ['Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4', 'University', 'ExamType', 'College', 'Major', 'Studytype', 'ResearchInterests', 'Teacher', 'StudentNo', 'Content']
        self.test = ExcelHandler()
        self.excel = self.test.init_excel(self.file, 'sheet1', self.head) 


