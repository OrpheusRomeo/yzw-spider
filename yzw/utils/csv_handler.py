# coding=utf-8
import csv
import os


class CsvHandler(object):
    """CSV 写入：首次写入时自动补表头"""

    def __init__(self):
        self.path = './result/csv/master_directory.csv'
        self.name = 'csvHandler'

    def init_file(self, path, head):
        """确保文件存在且带有表头"""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, 'w', encoding='utf-8', newline='') as file:
                csv.writer(file).writerow(head)

    def import_data(self, item, path=None, head=None):
        """向 csv 追加一行数据"""
        if path is None:
            path = self.path

        if head is None:
            # 与 yzw.pipelines.HEAD 保持一致（正常路径由 pipeline 传 head 进来）
            head = ['Link', 'Subject1', 'Subject2', 'Subject3', 'Subject4',
                    'Province', 'ProvinceCode',
                    'University', 'SchoolCode',
                    'College',
                    'Major', 'MajorCode',
                    'MajorSub', 'MajorSubCode',
                    'MajorCategory', 'MajorCategoryCode',
                    'ExamType', 'StudyType',
                    'ResearchInterests', 'Teacher', 'StudentNo', 'Content']

        exists = os.path.exists(path) and os.path.getsize(path) > 0
        with open(path, 'a', encoding='utf-8', newline='') as file:
            writer = csv.writer(file)
            if not exists:
                writer.writerow(head)
            writer.writerow([item.get(key) or '' for key in head])

        return item


if __name__ == '__main__':
    test = CsvHandler()
    test.import_data({'University': 'nj', 'Subject1': 'jj'}, 'a.csv')
    test.import_data({'University': 'bj', 'Subject1': 'wl'}, 'a.csv')
    test.import_data({'University': 'qh', 'Subject1': 'zz'}, 'a.csv')
