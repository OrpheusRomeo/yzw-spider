# yzw-spider · 研究生招生目录爬虫

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/scrapy-2.13--2.17-green.svg)](https://scrapy.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

基于 [Scrapy](https://scrapy.org/) 的研究生招生专业目录爬虫，抓取[中国研究生招生信息网](https://yz.chsi.com.cn/)的**硕士 / 博士**招生目录，解析出院校、学院、专业、研究方向、指导教师、拟招人数、初试科目等信息，并导出为 **CSV / JSON / Excel** 三种格式。

> 起因：考研需要提前查清目标院校的考试科目和招生名额。

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [数据字段](#数据字段)
- [输出文件](#输出文件)
- [配置说明](#配置说明)
- [接口说明](#接口说明)
- [常见问题](#常见问题)
- [已知问题](#已知问题)
- [声明](#声明)
- [许可证](#许可证)

---

## 功能特性

- **双爬虫**：`master`（硕士）与 `doctor`（博士）两个独立 spider，共用同一套字段定义与解析基类（`BaseSpider`）。
- **走 JSON 接口**：直接调用研招网的目录查询接口，不解析 HTML 列表页，页面改版时受影响更小。
- **字段完整**：院校、学院、专业、研究方向、指导教师、拟招人数、学习方式、考试方式、备注，以及初试科目 1–4。
- **多格式导出**：同一份数据同时写出 CSV、JSON、Excel 三种格式，文件名带运行时间戳。
- **Excel 分校分表**：按学校名自动建 sheet，列顺序与表头严格对齐。
- **学科代码内置**：完整收录研究生学科专业目录代码表（`01`–`14` 大类，共 140+ 个专业代码），无需手工维护。
- **输出目录自建**：结果目录不存在时自动创建，克隆下来直接跑。
- **配置简单**：改学校列表、改学科大类即可换目标，无需改解析逻辑。

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.12（3.10+ 均可，实测 3.12.13 / 3.13.13） |
| Scrapy | 2.13 ~ 2.17 |
| 操作系统 | Linux / macOS / Windows 均可 |

> 爬虫在基类里同时提供了 `start_requests()` 和 `async def start()`，因此 Scrapy 2.16 前后都能正常启动，
> 不需要为不同版本改代码。

---

## 安装

### 方式一：conda 环境（推荐）

```bash
conda create -n yzw python=3.12 -y
conda activate yzw
pip install -r requirements.txt
```

### 方式二：venv 虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 方式三：系统 Python

```bash
pip install -r requirements.txt
```

---

## 快速开始

```bash
# 运行硕士爬虫
scrapy crawl master

# 运行博士爬虫
scrapy crawl doctor
```

在仓库根目录执行即可；`scrapy.cfg` 会自动向上查找，因此在 `yzw/` 子目录下执行同样有效。
输出目录 `result/` 不需要手动创建，脚本会自动建好。

### 常用参数

```bash
scrapy crawl master -s DOWNLOAD_DELAY=1      # 临时调小请求间隔（默认 3 秒）
scrapy crawl master -s LOG_LEVEL=INFO        # 调整日志级别
scrapy crawl master -s CONCURRENT_REQUESTS=4  # 调整并发数
```

---

## 目录结构

```
yzw-spider/
├── requirements.txt          # 依赖清单
├── scrapy.cfg                # Scrapy 项目配置（入口设置 yzw.settings）
├── LICENSE                   # MIT
├── README.md
├── result/                   # 爬取结果输出目录（自动创建）
│   ├── master/               # 硕士数据：csv / json / xlsx
│   └── doctor/               # 博士数据：xlsx
└── yzw/
    ├── items.py              # MasterItem / DoctorItem 字段定义
    ├── middlewares.py        # Scrapy 默认中间件
    ├── pipelines.py          # MasterPipeline / DoctorPipeline，文件落盘
    ├── settings.py           # 项目配置（间隔、pipeline 注册）
    ├── spiders/
    │   ├── base.py           # BaseSpider：公共字段、接口常量、科目解析
    │   ├── master.py         # 硕士爬虫
    │   └── doctor.py         # 博士爬虫
    └── utils/
        ├── csv_handler.py    # CSV 写入
        └── excel_handler.py  # Excel 初始化 / 建 sheet / 追加行
```

---

## 数据字段

`MasterItem` 与 `DoctorItem` 字段完全一致，共 14 个：

| 字段 | 含义 | 硕士取值来源 | 博士取值来源 |
| --- | --- | --- | --- |
| `University` | 院校名称 | `dwmc` | `dwmc` |
| `College` | 学院 / 招生单位名称 | `yxsmc` | `yxsmc` |
| `Major` | 专业名称 | `zymc` | `zymc` |
| `ResearchInterests` | 研究方向 | `yjfxmc` | `yjfxmc` |
| `Teacher` | 指导教师 | `zdjs` | `dsxm` |
| `StudentNo` | 拟招人数 | `nzsrsstr`（文本，如 `专业：3(不含推免)`） | `yjfxzsrs` / `dszsrs`（数字） |
| `StudyType` | 学习方式 | `xxfs`（`1` 全日制 / `2` 非全日制） | 同左 |
| `ExamType` | 考试方式 | `ksfsmc`（统考 / 推免等） | 接口不提供，固定记为 `申请-考核` |
| `Content` | 备注说明 | `zybz` | `yjfxbz` / `dsbz` |
| `Subject1` | 初试科目 1 | 政治 | 外语 |
| `Subject2` | 初试科目 2 | 外语 | 专业课一 |
| `Subject3` | 初试科目 3 | 业务课一 | 专业课二 |
| `Subject4` | 初试科目 4 | 业务课二 | 科目不足时留空 |
| `Link` | 详情页链接 | `zydetail.do` 专业详情页 | `zymlIndex` 博士目录页 |

科目格式为 `(代码)名称`，同一槽位存在多个可选项时用 ` or ` 连接，对应研招网页面上的「或」：

```
Subject1 = (101)思想政治理论
Subject2 = (201)英语（一） or (202)俄语 or (203)日语
Subject3 = (303)数学（三）
Subject4 = (818)经济学原理
```

> 硕士是「政治 / 外语 / 业务课一 / 业务课二」，博士（申请-考核）通常是「外语 / 专业课一 / 专业课二」，
> 因此两边的 `Subject1` 含义并不完全对应。

---

## 输出文件

一次运行生成一组带时间戳的文件（时间戳在第一次写入时生成，三种格式共用）：

| spider | 文件 | 说明 |
| --- | --- | --- |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.csv` | 逗号分隔，含表头 |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.json` | **每行一个 JSON 对象**（JSON Lines） |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.xlsx` | Excel，按学校分 sheet |
| `doctor` | `result/doctor/doctor_directory_<YYYYMMDDHHMM>.xlsx` | Excel，按学校分 sheet |

几个容易踩的细节：

- **三种格式的列顺序一致**，都是：`Link, Subject1~4, University, ExamType, College, Major, StudyType, ResearchInterests, Teacher, StudentNo, Content`。
- **`.json` 其实是 JSONL**：每行一条独立 JSON 记录，不是标准 JSON 数组。
- **`.xlsx` 其实是 Excel 97-2003 格式**：文件由 `xlwt` 写出，二进制结构是 `.xls`（BIFF8），只是扩展名写成了 `.xlsx`。用 Excel 打开会提示「文件格式与扩展名不匹配」，用 WPS / LibreOffice / pandas 则可直接读取。
- **Excel 表头在第 2 行**，第 1 行留空；工作簿里还会保留一个初始的 `sheet1`（只有表头、没有数据）。
- Excel 按学校名建 sheet，sheet 名受 Excel 限制最多 31 字符。
- **跑 `master` 不会产生博士文件**，反之亦然：两个 pipeline 各自只处理自己那类 Item。

---

## 配置说明

### 换目标院校（硕士）

编辑 `yzw/spiders/master.py`：

```python
_universities = [
    '南京大学', '南开大学',
]

_discipline_codes = [
    {"mc": "经济学", "dm": "02"},
]
```

`_discipline_codes` 用的是学科**大类**代码（`01` 哲学、`02` 经济学、`03` 法学 … `14` 交叉学科）。
每个大类下的具体专业代码从 `yzw/spiders/base.py` 的 `major_dict_list` 中自动展开，
即每个大类会依次请求该大类下的每个一级学科 / 专业学位类别。

### 换目标院校（博士）

编辑 `yzw/spiders/doctor.py`：

```python
_university_codes = [10284]   # 10284 = 南京大学，10075 = 南开大学

_major_filter = []            # 限定专业代码（zydm），留空表示抓取全部
# 例：['020100'] 只抓"理论经济学"；['020200'] 只抓"应用经济学"
```

### 调整抓取频率

`yzw/settings.py`：

```python
DOWNLOAD_DELAY = 3           # 同一站点两次请求的间隔（秒）
ROBOTSTXT_OBEY = True        # 遵守目标站 robots.txt
```

### 增删输出格式

`yzw/settings.py` 的 `ITEM_PIPELINES`，以及 `yzw/pipelines.py` 中对应 pipeline 的 `process_item()`。

---

## 接口说明

研招网 2025-09 改版后，旧的 `zsml/querySchAction.do` 已下线。当前爬虫调用的是新接口。

**硕士（`zsml`）**

| 步骤 | 接口 | 方法 | 作用 |
| --- | --- | --- | --- |
| 1 | `/zsml/rs/dws.do` | POST | 按院校名查招生单位，拿到院校代码 `dwdm` |
| 2 | `/zsml/rs/dwzys.do` | POST | 某招生单位的开设专业列表（按 `mldm` + `yjxkdm` 过滤） |
| 3 | `/zsml/rs/yjfxs.do` | POST | 某专业的学院 / 研究方向明细，含科目、导师、拟招人数 |
| — | `/zsml/zydetail.do` | GET | 专业详情页，仅用于生成 `Link` |

**博士（`bsmlcx`）**

| 步骤 | 接口 | 方法 | 作用 |
| --- | --- | --- | --- |
| 1 | `/zsml/rs/dws.do` | POST | 按院校代码反查院校名称 |
| 2 | `/bsmlcx/cx/listYxsAndZyCollected` | GET | 某院校的学院 + 专业列表 |
| 3 | `/bsmlcx/cx/listCxZymlCollected` | GET | 某专业的研究方向 / 导师 / 考试科目明细 |

以上接口均为研招网页面自身在用的公开查询接口，POST 请求带
`X-Requested-With: XMLHttpRequest` 与 `application/x-www-form-urlencoded` 表单头。

---

## 常见问题

**Q：抓不到数据 / 所有请求都是 404**
研招网改过版。跑一次 `scrapy crawl master -s LOG_LEVEL=DEBUG`，看实际请求的接口返回了什么；
若接口路径已变，需要按[接口说明](#接口说明)重新定位。

**Q：`ValueError: Missing scheme in request url: h`**
Scrapy 版本过老（< 2.13 不认识 `async def start()`）或代码被改乱。装成 `pip install -r requirements.txt` 的版本即可。

**Q：Excel 打开提示「文件格式与扩展名不匹配」**
`.xlsx` 实际是 Excel 97-2003 二进制格式，见[输出文件](#输出文件)说明。用 WPS / LibreOffice / pandas 读取不受影响。

**Q：想先小范围试跑**
硕士：把 `_universities` 缩到 1–2 所、`_discipline_codes` 缩到 1 个大类；
博士：把 `_university_codes` 缩到 1 所、`_major_filter` 填 1–2 个专业代码。
再把 `DOWNLOAD_DELAY` 调小。

**Q：导师字段是空的**
硕士目录的 `zdjs` 字段大部分院校不上报，属正常现象；博士目录的 `dsxm` 一般有值。

---

## 已知问题

以下问题为当前实现的已知限制。

### 1. 研招网接口可能再次改版

站点 2025-09 改版过一次，`zsml/querySchAction.do` 等旧接口直接 404。
当前代码依赖的新接口若再次调整，需要重新逆向页面 JS 并更新 `base.py` 里的接口常量。

### 2. `.xlsx` 实际是 Excel 97-2003 格式

`xlwt` 只能写 BIFF8，扩展名写成 `.xlsx` 会让 Excel 弹格式警告。
要输出真正的 xlsx 需换用 `openpyxl`。

### 3. `.json` 是 JSONL 而非 JSON 数组

逐行写入，便于断点续写和流式处理，但用标准 JSON 解析器读需要包一层数组。

### 4. Excel 追加是 O(n²)

每写一行都要把整个工作簿读出来、改完再写回去（`xlrd` + `xlutils.copy` 的限制）。
数据量在几千行以内没问题，上万行会明显变慢。

### 5. 博士目录不提供考试方式

博士接口没有「考试方式」字段，`ExamType` 统一写成 `申请-考核`（可在
`yzw/spiders/doctor.py` 的 `_exam_type` 中改）。

### 6. 硕士与博士的科目槽位语义不同

硕士 `Subject1~4` 是 政治 / 外语 / 业务课一 / 业务课二；
博士是 外语 / 专业课一 / 专业课二（不足时 `Subject4` 留空）。

### 7. 拟招人数格式不统一

硕士是研招网的文本（如 `专业：3(不含推免)`），博士是纯数字，跨表对比时需要留意。

### 8. `.gitignore` 路径过时

忽略规则写的是旧路径 `/yzw/result/master/`，而实际输出目录在仓库根目录 `result/` 下，目前未被忽略。

---

## 声明

本项目数据仅供学习考研参考，不用于任何商业用途。请合理控制请求频率，遵守目标站点的 `robots.txt` 与服务条款，尊重网站方权益。

---

## 许可证

[MIT](LICENSE)
