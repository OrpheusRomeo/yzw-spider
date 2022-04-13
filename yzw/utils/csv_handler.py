#coding=utf-8
import csv

class CsvHandler(object):
    def __init__(self):
        self.path = './result/csv/master_directory.csv'
        self.name = 'csvHandler'

    #  csv中写入数据
    def import_data(self, item, path=None):
        if path is None:
            path = self.path
        file = open(path, 'a+', encoding='utf-8')
        writer = csv.writer(file)
        writer.writerow(
            (item["University"],item["ExamType"],item["College"],item["Major"],item["ResearchInterests"],item["StudyType"],item["Teacher"],item["StudentNo"],item["Subject1"],item["Subject2"],item["Subject3"],item["Subject4"],item["Content"],item["Link"]))
        return item 
   
if __name__=='__main__':
    test = CsvHandler()
    test.import_data({'University':'nj','Subject1':'jj'}, 'a.csv')
    test.import_data({'University':'bj','Subject1':'wl'}, 'a.csv')
    test.import_data({'University':'qh','Subject1':'zz'}, 'a.csv')
    

