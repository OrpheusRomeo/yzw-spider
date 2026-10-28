# -*- coding: utf-8 -*-
"""输出 pipeline：CSV + JSONL + Excel

* CSV、JSONL 边抓边写 —— 全量抓取几十万行时唯一现实的选择
* Excel 按学校分 sheet，先在内存里攒数据、抓完再决定要不要落盘
  （output.excel: auto 时学校数超过 output.excel_max_schools 就不出 Excel）

输出根目录取自 config.output.directory，下面分 master/ 和 doctor/ 两个子目录。
"""
import json
import logging
import os
import time

from .config import build_config
from .items import DoctorItem, MasterItem
from .utils.csv_handler import CsvHandler
from .utils.excel_handler import ExcelHandler

logger = logging.getLogger(__name__)

# 各文件统一的表头 / 列顺序
HEAD = [
    'Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4',
    'University', 'ExamType', 'College', 'Major', 'StudyType',
    'ResearchInterests', 'Teacher', 'StudentNo', 'Content',
]


class BaseDirectoryPipeline(object):
    """CSV + JSONL + Excel（按学校分 sheet）的公共逻辑"""

    # 由子类指定要处理的 Item 类型，其他类型直接放行
    item_class = None

    # 输出子目录与文件名前缀，由子类指定
    subdir = ''
    filename = ''

    def __init__(self, config=None, crawler=None):
        self.config = config or build_config({})
        self.date = '_' + time.strftime('%Y%m%d%H%M')
        self.head = HEAD
        self.excel = ExcelHandler()
        # Scrapy 2.17 起不再往 pipeline 方法里传 spider 参数，
        # 官方建议自己留着 crawler，用 crawler.spider 拿
        self.crawler = crawler

        self.directory = os.path.join(self.config.output_directory(), self.subdir)
        self.excel_file = os.path.join(self.directory, f'{self.filename}{self.date}.xlsx')
        self.csv_file = os.path.join(self.directory, f'{self.filename}{self.date}.csv')
        self.json_file = os.path.join(self.directory, f'{self.filename}{self.date}.json')

        self.excel_mode = self.config.excel_mode()
        self.excel_max_schools = self.config.excel_max_schools()
        self._excel_sheets = set()
        self._excel_enabled = self.excel_mode != 'never'

        self.csv_handler = CsvHandler()
        self.json_fp = None

    @classmethod
    def from_crawler(cls, crawler):
        """从 spider 写进 settings 的配置里拿输出设置"""
        return cls(crawler.settings.get('YZW_CONFIG_DATA'), crawler=crawler)

    def ensure_ready(self):
        """第一次写数据时才建目录、开文件

        这样只跑 master 时不会在 result/doctor/ 下留下空文件。
        """
        if self.json_fp is not None:
            return
        os.makedirs(self.directory, exist_ok=True)
        self.csv_handler.init_file(self.csv_file, self.head)
        # json 文件整个爬取期间保持打开，爬完再关闭
        self.json_fp = open(self.json_file, 'a', encoding='utf-8')

    def process_item(self, item, spider=None):
        if not isinstance(item, self.item_class):
            # 不是本 pipeline 负责的数据（例如跑 master 时遇到博士数据），原样放行
            return item

        self.ensure_ready()

        # 写入 csv
        self.csv_handler.import_data(item, self.csv_file, self.head)

        # 写入 json（每行一个 JSON 对象）
        self.json_fp.write(json.dumps(dict(item), ensure_ascii=False) + '\n')

        # 攒 excel
        self.append_excel(item)

        return item

    def append_excel(self, item):
        """按学校分 sheet 攒数据，攒够了就不攒了"""
        if not self._excel_enabled:
            return

        university = item.get('University') or 'unknown'
        if university not in self._excel_sheets:
            if (self.excel_mode == 'auto'
                    and len(self._excel_sheets) >= self.excel_max_schools):
                # auto 模式下学校数超了，整个 Excel 就不出了
                self._excel_enabled = False
                self.excel.books.pop(self.excel_file, None)
                logger.warning('学校数超过 %d，放弃 Excel 输出（CSV / JSON 不受影响）',
                               self.excel_max_schools)
                return
            self._excel_sheets.add(university)
            self.excel.add_sheet(self.excel_file, university, self.head)

        self.excel.append_data(self.excel_file, university, item, self.head)

    def close_spider(self, spider=None):
        if self.json_fp is not None:
            try:
                self.json_fp.close()
            except Exception:
                pass
            self.json_fp = None

        if self._excel_enabled and self.excel.row_count(self.excel_file):
            try:
                self.excel.save(self.excel_file)
            except Exception as e:
                logger.warning('Excel 写入失败：%s', e)


class MasterPipeline(BaseDirectoryPipeline):
    """硕士数据"""

    item_class = MasterItem
    subdir = 'master'
    filename = 'master_directory'


class DoctorPipeline(BaseDirectoryPipeline):
    """博士数据"""

    item_class = DoctorItem
    subdir = 'doctor'
    filename = 'doctor_directory'
