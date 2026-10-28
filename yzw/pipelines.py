# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import json
import os
import time

from .items import DoctorItem, MasterItem
from .utils.csv_handler import CsvHandler
from .utils.excel_handler import ExcelHandler

# 各文件统一的表头 / 列顺序
HEAD = [
    'Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4',
    'University', 'ExamType', 'College', 'Major', 'StudyType',
    'ResearchInterests', 'Teacher', 'StudentNo', 'Content',
]


class BaseDirectoryPipeline(object):
    """写 Excel 的公共逻辑：按学校分 sheet，列顺序与表头一致"""

    # 由子类指定要处理的 Item 类型，其他类型直接放行
    item_class = None

    # 输出目录与文件名前缀，由子类指定
    directory = ''
    filename = ''

    def __init__(self):
        self.date = '_' + time.strftime('%Y%m%d%H%M')
        self.excel_file = os.path.join(
            self.directory, f'{self.filename}{self.date}.xlsx')
        self.head = HEAD
        self.excel = ExcelHandler()
        self._excel_ready = False

    def ensure_excel(self):
        """第一次写数据时才创建工作簿。

        这样只跑 master 时不会在 result/doctor/ 下留下空文件。
        """
        if self._excel_ready:
            return

        # 输出目录不存在时自动创建
        os.makedirs(self.directory, exist_ok=True)
        self.excel.init_excel(self.excel_file, 'sheet1', self.head)
        self._excel_ready = True

    def process_item(self, item, spider):
        if not isinstance(item, self.item_class):
            # 不是本 pipeline 负责的数据（例如跑 master 时遇到博士数据），原样放行
            return item

        self.ensure_excel()

        university = item.get('University') or 'unknown'
        if not self.excel.has_sheet(self.excel_file, university):
            self.excel.add_sheet(self.excel_file, university, self.head)
        self.excel.append_data(self.excel_file, university, item, self.head)

        return item

    def close_spider(self, spider):
        pass


class MasterPipeline(BaseDirectoryPipeline):
    """硕士数据：csv + json + xlsx 三种格式"""

    item_class = MasterItem
    directory = './result/master/'
    filename = 'master_directory'

    def __init__(self):
        super().__init__()

        self.csv_file = os.path.join(
            self.directory, f'{self.filename}{self.date}.csv')
        self.json_file = os.path.join(
            self.directory, f'{self.filename}{self.date}.json')

        self.csv_handler = CsvHandler()
        self.json_fp = None

    def ensure_excel(self):
        super().ensure_excel()

        if self.json_fp is None:
            os.makedirs(self.directory, exist_ok=True)
            self.csv_handler.init_file(self.csv_file, self.head)
            # json 文件整个爬取期间保持打开，爬完再关闭
            self.json_fp = open(self.json_file, 'a', encoding='utf-8')

    def process_item(self, item, spider):
        if not isinstance(item, self.item_class):
            return item

        self.ensure_excel()

        # 写入 csv
        self.csv_handler.import_data(item, self.csv_file, self.head)

        # 写入 json（每行一个 JSON 对象）
        self.json_fp.write(json.dumps(dict(item), ensure_ascii=False) + '\n')
        self.json_fp.flush()

        # 写入 excel
        super().process_item(item, spider)

        return item

    def close_spider(self, spider):
        if self.json_fp is not None:
            try:
                self.json_fp.close()
            except Exception:
                pass


class DoctorPipeline(BaseDirectoryPipeline):
    """博士数据：xlsx"""

    item_class = DoctorItem
    directory = './result/doctor/'
    filename = 'doctor_directory'
