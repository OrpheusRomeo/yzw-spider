import os

import xlwt


class ExcelHandler(object):
    """Excel 写入：先在内存里攒数据，最后一次性建簿落盘

    原来的写法是每写一行就 xlrd 打开工作簿 + xlutils.copy + save，
    几百行就明显变慢、几千行基本卡死（整体 O(n²)）。
    改成攒在内存里、结束时一次性写出，同样的数据量快一个数量级，
    而且顺带能支持"抓完之后再决定要不要出 Excel"这种需求。
    """

    def __init__(self):
        # filename -> {sheetname: (表头, [行, ...])}
        self.books = {}

    def init_excel(self, filename, sheetname, head):
        """初始化一个 excel：首个 sheet 名为 sheetname，内容为表头"""
        self.add_sheet(filename, sheetname, head)

    def add_sheet(self, filename, sheetname, head):
        """在内存里的工作簿中加一个 sheet"""
        book = self.books.setdefault(filename, {})
        if sheetname in book:
            return
        book[sheetname] = (list(head or []), [])

    def has_sheet(self, filename, sheetname):
        """判断工作簿中是否已有某个 sheet"""
        return sheetname in self.books.get(filename, {})

    def append_data(self, filename, sheetname, data_dict, head=None):
        """往指定 sheet 的末尾追加一行数据

        head 给出时按表头顺序落列，保证列与表头一一对应；
        不给 head 时退化为按字典键顺序落列。
        """
        book = self.books.setdefault(filename, {})
        if sheetname not in book:
            book[sheetname] = (list(head or []), [])
        sheet_head, rows = book[sheetname]
        keys = head if head is not None else sheet_head

        row = []
        for key in keys:
            value = data_dict.get(key)
            if value is None:
                value = ''
            elif not isinstance(value, (str, int, float, bool)):
                value = str(value)
            row.append(value)
        rows.append(row)

    def row_count(self, filename):
        """工作簿里一共攒了多少行"""
        return sum(len(rows) for _, rows in self.books.get(filename, {}).values())

    def save(self, filename):
        """把内存里的数据一次性写成工作簿"""
        book_data = self.books.get(filename)
        if not book_data:
            return False

        directory = os.path.dirname(filename)
        if directory:
            os.makedirs(directory, exist_ok=True)

        workbook = xlwt.Workbook()
        style = xlwt.XFStyle()
        font = xlwt.Font()
        font.name = 'Times New Roman'
        font.bold = True
        style.font = font

        for sheetname, (head, rows) in book_data.items():
            sheet = workbook.add_sheet(sheetname, cell_overwrite_ok=True)
            for i, v in enumerate(head):
                sheet.write(1, i, v, style)   # 表头写在第 2 行，第 1 行留空
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    sheet.write(r + 2, c, value)

        workbook.save(filename)
        return True


if __name__ == '__main__':
    test = ExcelHandler()
    test.init_excel('Md.xlsx', '919', ['a', 'b', 'c', 'd'])
    test.has_sheet('Md.xlsx', '818')
    test.add_sheet('Md.xlsx', '818', ['a', 'b', 'c', 'd'])
    test.has_sheet('Md.xlsx', '919')
    test.append_data('Md.xlsx', '919', {'1': 100, '2': 200, '3': 300, '4': 400})
    test.append_data('Md.xlsx', '818', {'1': 600, '2': 700, '3': 800, '4': 900})
    test.save('Md.xlsx')
