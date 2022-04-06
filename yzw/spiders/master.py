# -*- coding: utf-8 -*-
import scrapy
from yzw.items import MasterItem

class MasterSpider(scrapy.Spider):
# 示例 南京大学 02 0201 理论经济学
#issdm: 32
#dwmc: 南京大学
#mldm: 02
#mlmc: 
#yjxkdm: 0201
#xxfs: 
#zymc: 
    name = 'master'
    allowed_domains = ['yz.chsi.com.cn']
    start_urls = 'https://yz.chsi.com.cn/zsml/querySchAction.do?ssdm=&dwmc={}&mldm={}&mlmc=&yjxkdm={}&xxfs=&zymc='
    #keywords = ['南京大学','南开大学','外交学院']
    keywords = ['南京大学']

    def start_requests(self):
        for i in self.keywords:
            for j in self.get_dm():
                major_list = self.get_major(j)
                for k in major_list:
                #for k in ["01", "02", "03"]:
                    url = self.start_urls.format(i, j, k)
                    yield scrapy.Request(url=url, method='GET', callback=self.parse)

    def parse(self, response):
        domain = "https://yz.chsi.com.cn"
        item = MasterItem()
        url_list = response.xpath("//tbody/tr/td[8]/a/@href").extract()
        for i in url_list:
            new_url = domain+i
            item["Link"] = new_url
            yield scrapy.Request(url=new_url, callback=self.call_detail, meta={"item":item})

    def call_detail(self, response):
        item = response.meta["item"]
        Subject1 = response.xpath("//div[@class='zsml-result']/table/tbody/tr[1]/td[1]/text()").extract()
        item["Subject1"] = self.trans_data(Subject1)
        Subject2 = response.xpath("//div[@class='zsml-result']/table/tbody/tr[1]/td[2]/text()").extract()
        item["Subject2"] = self.trans_data(Subject2)
        Subject3 = response.xpath("//div[@class='zsml-result']/table/tbody/tr[1]/td[3]/text()").extract()
        item["Subject3"] = self.trans_data(Subject3)
        Subject4 = response.xpath("//div[@class='zsml-result']/table/tbody/tr[1]/td[4]/text()").extract()
        item["Subject4"] = self.trans_data(Subject4)
        item["University"] = response.xpath("//table[@class='zsml-condition']/tbody/tr[1]/td[2]/text()").extract_first()
        item["ExamType"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[1]/td[4]/text()").extract_first()
        item["College"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[2]/td[2]/text()").extract_first()
        item["Major"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[2]/td[4]/text()").extract_first()
        item["StudyType"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[3]/td[2]/text()").extract_first()
        item["ResearchInterests"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[3]/td[4]/text()").extract_first()
        item["Teacher"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[4]/td[2]/text()").extract_first()
        item["StudentNo"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[4]/td[4]/text()").extract_first()
        item["Content"] = response.xpath("//table[@class='zsml-condition']//tbody/tr[5]/td[1]/text()").extract_first()
        yield item


    def trans_data(self, targets):
        result_list = []
        for target in targets:
            if target.strip().replace('\r\n', '').strip() not in result_list:
                data = target.strip().replace('\r\n', '')
                if data is not "":
                    result_list.append(data)
        if len(result_list) > 1:
            result = " or ".join(result_list)
        else:
            result = result_list[0]
        return result
 


    def get_dm(self):
        data_dict_list = [{"mc":"哲学","dm":"01"},{"mc":"经济学","dm":"02"},{"mc":"法学","dm":"03"},{"mc":"教育学","dm":"04"},{"mc":"文学","dm":"05"},{"mc":"历史学","dm":"06"},{"mc":"理学","dm":"07"},{"mc":"工学","dm":"08"},{"mc":"农学","dm":"09"},{"mc":"医学","dm":"10"},{"mc":"军事学","dm":"11"},{"mc":"管理学","dm":"12"},{"mc":"艺术学","dm":"13"},{"mc":"交叉学科","dm":"14"}]
        data = []
        for i in data_dict_list:
            data.append(i["dm"])
        return data



    def get_major(self, dl):
        major_dict_list = [{"mc":"哲学","dm":"0101"},{"mc":"理论经济学","dm":"0201"},{"mc":"应用经济学","dm":"0202"},{"mc":"金融","dm":"0251"},{"mc":"应用统计","dm":"0252"},{"mc":"税务","dm":"0253"},{"mc":"国际商务","dm":"0254"},{"mc":"保险","dm":"0255"},{"mc":"资产评估","dm":"0256"},{"mc":"审计","dm":"0257"},{"mc":"统计学","dm":"0270"},{"mc":"法学","dm":"0301"},{"mc":"政治学","dm":"0302"},{"mc":"社会学","dm":"0303"},{"mc":"民族学","dm":"0304"},{"mc":"马克思主义理论","dm":"0305"},{"mc":"公安学","dm":"0306"},{"mc":"法律","dm":"0351"},{"mc":"社会工作","dm":"0352"},{"mc":"警务","dm":"0353"},{"mc":"教育学","dm":"0401"},{"mc":"心理学","dm":"0402"},{"mc":"体育学","dm":"0403"},{"mc":"教育","dm":"0451"},{"mc":"体育","dm":"0452"},{"mc":"汉语国际教育","dm":"0453"},{"mc":"应用心理","dm":"0454"},{"mc":"","dm":"0471"},{"mc":"中国语言文学","dm":"0501"},{"mc":"外国语言文学","dm":"0502"},{"mc":"新闻传播学","dm":"0503"},{"mc":"翻译","dm":"0551"},{"mc":"新闻与传播","dm":"0552"},{"mc":"出版","dm":"0553"},{"mc":"考古学","dm":"0601"},{"mc":"中国史","dm":"0602"},{"mc":"世界史","dm":"0603"},{"mc":"文物与博物馆","dm":"0651"},{"mc":"数学","dm":"0701"},{"mc":"物理学","dm":"0702"},{"mc":"化学","dm":"0703"},{"mc":"天文学","dm":"0704"},{"mc":"地理学","dm":"0705"},{"mc":"大气科学","dm":"0706"},{"mc":"海洋科学","dm":"0707"},{"mc":"地球物理学","dm":"0708"},{"mc":"地质学","dm":"0709"},{"mc":"生物学","dm":"0710"},{"mc":"系统科学","dm":"0711"},{"mc":"科学技术史","dm":"0712"},{"mc":"生态学","dm":"0713"},{"mc":"统计学","dm":"0714"},{"mc":"心理学","dm":"0771"},{"mc":"力学","dm":"0772"},{"mc":"材料科学与工程","dm":"0773"},{"mc":"电子科学与技术","dm":"0774"},{"mc":"计算机科学与技术","dm":"0775"},{"mc":"环境科学与工程","dm":"0776"},{"mc":"生物医学工程","dm":"0777"},{"mc":"基础医学","dm":"0778"},{"mc":"公共卫生与预防医学","dm":"0779"},{"mc":"药学","dm":"0780"},{"mc":"中药学","dm":"0781"},{"mc":"医学技术","dm":"0782"},{"mc":"护理学","dm":"0783"},{"mc":"","dm":"0784"},{"mc":"","dm":"0785"},{"mc":"","dm":"0786"},{"mc":"力学","dm":"0801"},{"mc":"机械工程","dm":"0802"},{"mc":"光学工程","dm":"0803"},{"mc":"仪器科学与技术","dm":"0804"},{"mc":"材料科学与工程","dm":"0805"},{"mc":"冶金工程","dm":"0806"},{"mc":"动力工程及工程热物理","dm":"0807"},{"mc":"电气工程","dm":"0808"},{"mc":"电子科学与技术","dm":"0809"},{"mc":"信息与通信工程","dm":"0810"},{"mc":"控制科学与工程","dm":"0811"},{"mc":"计算机科学与技术","dm":"0812"},{"mc":"建筑学","dm":"0813"},{"mc":"土木工程","dm":"0814"},{"mc":"水利工程","dm":"0815"},{"mc":"测绘科学与技术","dm":"0816"},{"mc":"化学工程与技术","dm":"0817"},{"mc":"地质资源与地质工程","dm":"0818"},{"mc":"矿业工程","dm":"0819"},{"mc":"石油与天然气工程","dm":"0820"},{"mc":"纺织科学与工程","dm":"0821"},{"mc":"轻工技术与工程","dm":"0822"},{"mc":"交通运输工程","dm":"0823"},{"mc":"船舶与海洋工程","dm":"0824"},{"mc":"航空宇航科学与技术","dm":"0825"},{"mc":"兵器科学与技术","dm":"0826"},{"mc":"核科学与技术","dm":"0827"},{"mc":"农业工程","dm":"0828"},{"mc":"林业工程","dm":"0829"},{"mc":"环境科学与工程","dm":"0830"},{"mc":"生物医学工程","dm":"0831"},{"mc":"食品科学与工程","dm":"0832"},{"mc":"城乡规划学","dm":"0833"},{"mc":"风景园林学","dm":"0834"},{"mc":"软件工程","dm":"0835"},{"mc":"生物工程","dm":"0836"},{"mc":"安全科学与工程","dm":"0837"},{"mc":"公安技术","dm":"0838"},{"mc":"网络空间安全","dm":"0839"},{"mc":"建筑学","dm":"0851"},{"mc":"城市规划","dm":"0853"},{"mc":"电子信息","dm":"0854"},{"mc":"机械","dm":"0855"},{"mc":"材料与化工","dm":"0856"},{"mc":"资源与环境","dm":"0857"},{"mc":"能源动力","dm":"0858"},{"mc":"土木水利","dm":"0859"},{"mc":"生物与医药","dm":"0860"},{"mc":"交通运输","dm":"0861"},{"mc":"科学技术史","dm":"0870"},{"mc":"管理科学与工程","dm":"0871"},{"mc":"设计学","dm":"0872"},{"mc":"作物学","dm":"0901"},{"mc":"园艺学","dm":"0902"},{"mc":"农业资源与环境","dm":"0903"},{"mc":"植物保护","dm":"0904"},{"mc":"畜牧学","dm":"0905"},{"mc":"兽医学","dm":"0906"},{"mc":"林学","dm":"0907"},{"mc":"水产","dm":"0908"},{"mc":"草学","dm":"0909"},{"mc":"农业","dm":"0951"},{"mc":"兽医","dm":"0952"},{"mc":"风景园林","dm":"0953"},{"mc":"林业","dm":"0954"},{"mc":"科学技术史","dm":"0970"},{"mc":"环境科学与工程","dm":"0971"},{"mc":"食品科学与工程","dm":"0972"},{"mc":"风景园林学","dm":"0973"},{"mc":"基础医学","dm":"1001"},{"mc":"临床医学","dm":"1002"},{"mc":"口腔医学","dm":"1003"},{"mc":"公共卫生与预防医学","dm":"1004"},{"mc":"中医学","dm":"1005"},{"mc":"中西医结合","dm":"1006"},{"mc":"药学","dm":"1007"},{"mc":"中药学","dm":"1008"},{"mc":"特种医学","dm":"1009"},{"mc":"医学技术","dm":"1010"},{"mc":"护理学","dm":"1011"},{"mc":"临床医学","dm":"1051"},{"mc":"口腔医学","dm":"1052"},{"mc":"公共卫生","dm":"1053"},{"mc":"护理","dm":"1054"},{"mc":"药学","dm":"1055"},{"mc":"中药学","dm":"1056"},{"mc":"中医","dm":"1057"},{"mc":"科学技术史","dm":"1071"},{"mc":"生物医学工程","dm":"1072"},{"mc":"","dm":"1073"},{"mc":"","dm":"1074"},{"mc":"军事思想及军事历史","dm":"1101"},{"mc":"战略学","dm":"1102"},{"mc":"战役学","dm":"1103"},{"mc":"战术学","dm":"1104"},{"mc":"军队指挥学","dm":"1105"},{"mc":"军事管理学","dm":"1106"},{"mc":"军队政治工作学","dm":"1107"},{"mc":"军事后勤学","dm":"1108"},{"mc":"军事装备学","dm":"1109"},{"mc":"军事训练学","dm":"1110"},{"mc":"军事","dm":"1151"},{"mc":"管理科学与工程","dm":"1201"},{"mc":"工商管理","dm":"1202"},{"mc":"农林经济管理","dm":"1203"},{"mc":"公共管理","dm":"1204"},{"mc":"图书情报与档案管理","dm":"1205"},{"mc":"工商管理","dm":"1251"},{"mc":"公共管理","dm":"1252"},{"mc":"会计","dm":"1253"},{"mc":"旅游管理","dm":"1254"},{"mc":"图书情报","dm":"1255"},{"mc":"工程管理","dm":"1256"},{"mc":"艺术学理论","dm":"1301"},{"mc":"音乐与舞蹈学","dm":"1302"},{"mc":"戏剧与影视学","dm":"1303"},{"mc":"美术学","dm":"1304"},{"mc":"设计学","dm":"1305"},{"mc":"艺术","dm":"1351"},{"mc":"集成电路科学与工程","dm":"1401"},{"mc":"国家安全学","dm":"1402"}]
        major = []
        for i in major_dict_list:
            if i["dm"][0:2] == dl:
                major.append(i["dm"])
        return major 

 

if __name__=='__main__':
    test = MasterSpider()
    dl = '02'
    major_list = test.get_major(dl)
    print(major_list)
