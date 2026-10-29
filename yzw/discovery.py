# -*- coding: utf-8 -*-
"""院校枚举：按省份从研招网院校库拉取全部招生单位

为什么不用硕士目录的 dws.do 枚举
------------------------------
dws.do 匿名状态下每页硬顶 10 条，而且 start>0 一律返回
``{"flag": false, "msg": "请登录", "msg2": true}``（网页自己也会弹登录框），
所以拿它翻页枚举全国院校是走不通的。

院校库 /sch/search.do 则是服务端渲染的完整列表：

    https://yz.chsi.com.cn/sch/search.do?ssdm=32&start=20

* 每页 20 条，start 可以自由翻页，不需要登录
* ssdm 用的就是硕士目录那套省份码（一区 21 个 + 二区 10 个 = 31 个）
* 每条记录里直接带招生单位代码 dwdm —— 校徽图片地址就是 .../xh/{dwdm}.jpg

实测 31 个省份合计 936 条，与 dws.do 逐省 totalCount（合计 931）对得上；
多出来的那几条是院校库收录、但不在硕士目录里的单位（北京的 3 所、天津和浙江各 1 所）。
"""
import json
import os
import re

# 院校库列表接口
SCHOOL_LIST_URL = 'https://yz.chsi.com.cn/sch/search.do'

# 院校库每页条数
PAGE_SIZE = 20

# 研招网自带的省份树（一区 21 个 + 二区 10 个 = 31 个）
PROVINCES = [
    ('11', '北京'), ('12', '天津'), ('13', '河北'), ('14', '山西'), ('15', '内蒙古'),
    ('21', '辽宁'), ('22', '吉林'), ('23', '黑龙江'), ('31', '上海'), ('32', '江苏'),
    ('33', '浙江'), ('34', '安徽'), ('35', '福建'), ('36', '江西'), ('37', '山东'),
    ('41', '河南'), ('42', '湖北'), ('43', '湖南'), ('44', '广东'), ('45', '广西'),
    ('46', '海南'), ('50', '重庆'), ('51', '四川'), ('52', '贵州'), ('53', '云南'),
    ('54', '西藏'), ('61', '陕西'), ('62', '甘肃'), ('63', '青海'), ('64', '宁夏'),
    ('65', '新疆'),
]

PROVINCE_NAMES = dict(PROVINCES)

# 一条院校记录里：
#   <img src='.../xh/10284.jpg'>                      -> 招生单位代码
#   <a ... schoolInfo--schId-368194.dhtml> 南京大学 </a> -> 校名、schId
#   <i class="iconfont">&#xe6a4;</i> 江苏              -> 所在地
_CODE_RE = re.compile(r'common/xh/(\w+)\.jpg')
_NAME_RE = re.compile(r'schoolInfo--schId-(\d+)\.dhtml"[^>]*>\s*([^<]+?)\s*<')
_AREA_RE = re.compile(r'iconfont">&#xe6a4;</i>\s*([^<]+?)\s*<')

# 校名里的括号后缀表示校区 / 研究所：
#   中国石油大学(华东)、中国地质大学(武汉)、中国航空研究院(601所)
# 归一化时去掉它，只留学校本体名 —— 用于把同一所大学的多个校区归成一组。
_PAREN_RE = re.compile(r'[（(][^（()）]*[)）]')


def base_name(name):
    """去掉校名里的括号后缀和顿号分隔，只留学校本体名

    中国石油大学(华东)                          -> 中国石油大学
    中国地质大学(武汉)                          -> 中国地质大学
    中国兵器科学研究院(西安近代化学研究所)、…      -> 中国兵器科学研究院
    上海交通大学                                  -> 上海交通大学
    """
    first = re.split(r'[、,，]', str(name or ''))[0]
    return _PAREN_RE.sub('', first).strip()



def parse_school_list(html, ssdm=''):
    """从院校库列表页里解析出招生单位

    返回 [{'dwdm': '10284', 'dwmc': '南京大学', 'schId': '368194',
           'szss': '江苏', 'szssm': '32'}, ...]
    """
    schools = []
    for block in re.split(r'<div class="sch-item"', html)[1:]:
        block = block[:5000]
        code = _CODE_RE.search(block)
        name = _NAME_RE.search(block)
        if not code or not name:
            continue
        area = _AREA_RE.search(block)
        schools.append({
            'dwdm': code.group(1),
            'dwmc': name.group(2).strip(),
            'schId': name.group(1),
            'szss': area.group(1).strip() if area else '',
            'szssm': ssdm,
        })
    return schools


class SchoolCatalog(object):
    """招生单位清单，按 dwdm 去重"""

    def __init__(self, schools=None):
        self.schools = {}
        for unit in schools or []:
            self.add(unit)

    def add(self, unit):
        """加入一所招生单位（dwdm 重复时以先到者为准）"""
        dwdm = unit.get('dwdm')
        if not dwdm:
            return None
        self.schools.setdefault(str(dwdm), unit)
        return self.schools[str(dwdm)]

    def get(self, dwdm):
        return self.schools.get(str(dwdm))

    def all(self):
        """按 dwdm 排序返回全部招生单位"""
        return [self.schools[code] for code in sorted(self.schools)]

    def count(self):
        return len(self.schools)

    def find_by_name(self, name):
        """按校名精确查找"""
        for unit in self.schools.values():
            if unit.get('dwmc') == name:
                return unit
        return None

    def find_by_base_name(self, name):
        """按学校本体名查找，返回同一所大学的所有校区

        "中国石油大学" -> [中国石油大学(华东), 中国石油大学(北京)]
        "交通大学"     -> []（上海交通大学、华东交通大学是四所不同的学校，
                                本体名对不上，不会被当成多校区）
        """
        key = base_name(name)
        if not key:
            return []
        return [unit for unit in self.all()
                if base_name(unit.get('dwmc') or '') == key]

    def find_by_code(self, code):
        return self.schools.get(str(code))

    def province_counts(self):
        """各省已获取数量，形如 {'32': 56, ...}"""
        counts = {}
        for unit in self.schools.values():
            ssdm = unit.get('szssm') or ''
            counts[ssdm] = counts.get(ssdm, 0) + 1
        return counts

    def schools_of(self, ssdm):
        """某个省份码下的全部招生单位"""
        return [unit for unit in self.all()
                if (unit.get('szssm') or '') == str(ssdm)]

    # ------------------------------------------------------------------
    # 落盘
    # ------------------------------------------------------------------
    def to_dict(self):
        return {
            'source': SCHOOL_LIST_URL,
            'count': len(self.schools),
            'schools': self.all(),
        }

    @classmethod
    def from_dict(cls, data):
        if not data:
            return cls()
        return cls(data.get('schools') or [])

    def save(self, path):
        """写入 data/schools.json"""
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path):
        """读取 data/schools.json，文件不存在时返回空清单"""
        if not path or not os.path.exists(path):
            return cls()
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except (OSError, ValueError):
            return cls()
        return cls.from_dict(data)


def merge_catalog(path, units):
    """把 units 合并进 path 里的清单并写回，返回 (总数, 新增数)

    定向抓取（schools: [南京大学]）时枚举到的只有一所，如果直接覆盖，
    会把之前生成好的全国清单冲掉 —— 所以这里只做合并、不做替换。
    已存在的记录以文件里的为准（院校库解析出来的字段更全）。
    """
    catalog = SchoolCatalog.load(path)
    before = catalog.count()
    for unit in units:
        catalog.add(unit)
    catalog.save(path)
    return catalog.count(), catalog.count() - before
