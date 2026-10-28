# -*- coding: utf-8 -*-
"""学科代码表：门类 / 一级学科 / 专业

研招网把三张表做成了静态 JSON：

    /zsml/code/ml.json           门类（2 位码，共 14 个）
    /zsml/code/yjxk/{ml}.json    一级学科（4 位码）
    /zsml/code/autozy.do?q=xxx   专业（6 位码），按名称模糊匹配

master.py 原来硬编码的 major_dict_list 既不完整（缺 0271 区域国别学、0299 这类
研究型代码位）也容易过时，这里改成直接读站点自己的表。

代码位数直接决定筛选粒度：2 位=门类，4 位=一级学科，6 位=专业。
"""
import json

API_ML = 'https://yz.chsi.com.cn/zsml/code/ml.json'
API_YJXK = 'https://yz.chsi.com.cn/zsml/code/yjxk/{ml}.json'
API_AUTOZY = 'https://yz.chsi.com.cn/zsml/code/autozy.do?q={q}'

# 筛选粒度
LEVEL_ML = 'ml'       # 门类
LEVEL_YJXK = 'yjxk'   # 一级学科
LEVEL_ZY = 'zy'       # 专业

# 粒度 -> 专业代码前缀长度
LEVEL_PREFIX = {LEVEL_ML: 2, LEVEL_YJXK: 4, LEVEL_ZY: 6}


def parse_code_list(text):
    """解析 {"dms": [{"mc": "经济学", "dm": "02"}]} 这种结构"""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get('dms') or []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get('dm')]


def parse_autozy(text):
    """解析 autozy.do 的返回：[{"mc": "西方经济学", "dm": "020104"}]"""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get('dm')]


class CodeTable(object):
    """门类 / 一级学科 代码表"""

    def __init__(self):
        # [{'mc': '经济学', 'dm': '02'}, ...]
        self.ml_list = []
        # {'02': [{'mc': '理论经济学', 'dm': '0201'}, ...]}
        self.yjxk_map = {}

    # ------------------------------------------------------------------
    # 装载
    # ------------------------------------------------------------------
    def load_ml(self, text):
        self.ml_list = parse_code_list(text)
        return self.ml_list

    def load_yjxk(self, ml, text):
        self.yjxk_map[ml] = parse_code_list(text)
        return self.yjxk_map[ml]

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def ml_codes(self):
        """全部门类代码"""
        return [item['dm'] for item in self.ml_list]

    def ml_name(self, code):
        for item in self.ml_list:
            if item['dm'] == code:
                return item.get('mc') or ''
        return ''

    def yjxk_codes(self, ml):
        """某个门类下的全部一级学科代码"""
        return [item['dm'] for item in self.yjxk_map.get(ml, [])]

    def yjxk_name(self, code):
        """一级学科代码 -> 名称（需要先装载过 yjxk 表）"""
        for items in self.yjxk_map.values():
            for item in items:
                if item['dm'] == code:
                    return item.get('mc') or ''
        return ''

    def resolve_all(self, name_or_code):
        """把配置里写的专业名 / 代码解析成所有可能的 (粒度, 代码)

        纯数字按位数定粒度；中文名先在门类表里找，再在一级学科表里找，
        都不是的话返回空列表 —— 那属于专业（6 位码），要再查 autozy.do。

        同一个名字可能横跨多个层级（"临床医学"既是学术学位的一级学科 1002，
        也是专业学位的一级学科 1051），这里全都返回，由上层一起抓。
        """
        text = str(name_or_code).strip()
        if not text:
            return []

        if text.isdigit():
            length = len(text)
            if length == 2:
                return [(LEVEL_ML, text)]
            if length == 4:
                return [(LEVEL_YJXK, text)]
            if length == 6:
                return [(LEVEL_ZY, text)]
            return []

        matches = []
        for item in self.ml_list:
            if item.get('mc') == text:
                matches.append((LEVEL_ML, item['dm']))

        for items in self.yjxk_map.values():
            for item in items:
                if item.get('mc') == text:
                    matches.append((LEVEL_YJXK, item['dm']))

        return matches

    def resolve(self, name_or_code):
        """解析成第一个匹配的 (粒度, 代码)，没有匹配返回 None"""
        matches = self.resolve_all(name_or_code)
        return matches[0] if matches else None

    def ml_of(self, yjxk_code):
        """一级学科代码 -> 所属门类代码"""
        return yjxk_code[:2] if yjxk_code else ''


def match_major(level, code, zydm):
    """判断一个专业代码是否落在 (粒度, 代码) 指定的范围内"""
    if not zydm:
        return False
    if level == LEVEL_ZY:
        return zydm == code
    prefix = LEVEL_PREFIX.get(level)
    if not prefix:
        return False
    return zydm[:prefix] == code
