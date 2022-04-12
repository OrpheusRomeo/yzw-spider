import xlwt, xlrd
from xlutils.copy import copy


class ExcelHandler(object):
    def __init__(self):
        self.directory = './result/xlsx/'

    #  在已存在的excel中 添加sheet
    def add_sheet(self, file, sheetname, head):
        book = xlrd.open_workbook(file)
        wb = copy(book)
        sheet = wb.add_sheet(sheetname, cell_overwrite_ok=True) # 如果对同一单元格重复操作会发生overwrite Exception，cell_overwrite_ok为可覆盖
        for i, v in enumerate(head):
            sheet.write(1, i, head[i])  # 填写每行字段名
        wb.save(file)

    def has_sheet(self, file, sheetname):
        book = xlrd.open_workbook(file)
        sheetnames = book.sheet_names()
        if sheetname in sheetnames:
            return True
        else:
            return False
    
    # 初始化一个 excel
    def init_excel(self, filename, sheetname, head):
        book = xlwt.Workbook()  # 新建工作簿
        sheet = book.add_sheet(sheetname, cell_overwrite_ok=True)  # 如果对同一单元格重复操作会发生overwrite Exception，cell_overwrite_ok为可覆盖
        for i, v in enumerate(head):
            sheet.write(1, i, head[i])  # 填写每行字段名
        style = xlwt.XFStyle()  # 新建样式
        font = xlwt.Font()  # 新建字体
        font.name = 'Times New Roman'
        font.bold = True
        style.font = font  # 将style的字体设置为font
        book.save(filename_or_stream=filename)  # 一定要保存
   
    def append_data(self, filename, sheetname, data_dict):
        data = xlrd.open_workbook(filename, formatting_info=True)
        excel = copy(wb=data)  # 完成xlrd对象向xlwt对象转换
        table = data.sheet_by_name(sheetname)  # 通过名称来获取指定页
        excel_table = excel.get_sheet(sheetname) # 获得要操作的页
        nrows = table.nrows  # 获得行数
        for i, key in enumerate(data_dict.keys()):
            excel_table.write(nrows, i, data_dict[key])  # 每行很多列
        excel.save(filename)
    
if __name__=='__main__':
    test = ExcelHandler()
    test.init_excel('Md.xlsx', '919', ['a', 'b', 'c', 'd'])
    test.has_sheet('Md.xlsx', '818')
    test.add_sheet('Md.xlsx', '818')
    test.has_sheet('Md.xlsx', '919')
    test.append_data('Md.xlsx', '919', {'1': 100, '2': 200, '3': 300, '4': 400})
    test.append_data('Md.xlsx', '818', {'1': 600, '2': 700, '3': 800, '4': 900})
    test.append_data('Md.xlsx', '818', {'1': 601, '2': 701, '3': 801, '4': 901})
    test.append_data('Md.xlsx', '818', {'1': 602, '2': 702, '3': 802, '4': 902})


