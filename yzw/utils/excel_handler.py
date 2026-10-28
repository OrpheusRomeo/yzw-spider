import os

import xlrd
import xlwt
from xlutils.copy import copy


class ExcelHandler(object):
    """Excel 读写：新建工作簿、加 sheet、追加行"""

    def __init__(self):
        self.directory = './result/xlsx/'

    def init_excel(self, filename, sheetname, head):
        """初始化一个 excel：首个 sheet 名为 sheetname，内容为表头"""
        directory = os.path.dirname(filename)
        if directory:
            os.makedirs(directory, exist_ok=True)

        book = xlwt.Workbook()  # 新建工作簿
        # cell_overwrite_ok=True：同一单元格重复写入不抛 OverwriteException
        sheet = book.add_sheet(sheetname, cell_overwrite_ok=True)
        for i, v in enumerate(head):
            sheet.write(1, i, head[i])  # 表头写在第 2 行，第 1 行留空
        style = xlwt.XFStyle()  # 新建样式
        font = xlwt.Font()  # 新建字体
        font.name = 'Times New Roman'
        font.bold = True
        style.font = font  # 将 style 的字体设置为 font
        book.save(filename_or_stream=filename)  # 一定要保存

    def has_sheet(self, file, sheetname):
        """判断工作簿中是否已有某个 sheet"""
        book = xlrd.open_workbook(file)
        return sheetname in book.sheet_names()

    def add_sheet(self, file, sheetname, head):
        """在已存在的 excel 中添加 sheet"""
        book = xlrd.open_workbook(file)
        wb = copy(book)
        sheet = wb.add_sheet(sheetname, cell_overwrite_ok=True)
        for i, v in enumerate(head):
            sheet.write(1, i, head[i])  # 填写每行字段名
        wb.save(file)

    def append_data(self, filename, sheetname, data_dict, head=None):
        """往指定 sheet 的末尾追加一行

        head 给出时按表头顺序落列，保证列与表头一一对应；
        不给 head 时退化为按字典键顺序落列。
        """
        data = xlrd.open_workbook(filename, formatting_info=True)
        excel = copy(wb=data)  # 完成 xlrd 对象向 xlwt 对象转换
        table = data.sheet_by_name(sheetname)  # 通过名称来获取指定页
        excel_table = excel.get_sheet(sheetname)  # 获得要操作的页
        nrows = table.nrows  # 获得行数

        if head:
            keys = head
        else:
            keys = list(data_dict.keys())

        for i, key in enumerate(keys):
            value = data_dict.get(key)
            if value is None:
                value = ''
            elif not isinstance(value, (str, int, float, bool)):
                value = str(value)
            excel_table.write(nrows, i, value)  # 每行很多列

        excel.save(filename)


if __name__ == '__main__':
    test = ExcelHandler()
    test.init_excel('Md.xlsx', '919', ['a', 'b', 'c', 'd'])
    test.has_sheet('Md.xlsx', '818')
    test.add_sheet('Md.xlsx', '818', ['a', 'b', 'c', 'd'])
    test.has_sheet('Md.xlsx', '919')
    test.append_data('Md.xlsx', '919', {'1': 100, '2': 200, '3': 300, '4': 400})
    test.append_data('Md.xlsx', '818', {'1': 600, '2': 700, '3': 800, '4': 900})
    test.append_data('Md.xlsx', '818', {'1': 601, '2': 701, '3': 801, '4': 901})
    test.append_data('Md.xlsx', '818', {'1': 602, '2': 702, '3': 802, '4': 902})
