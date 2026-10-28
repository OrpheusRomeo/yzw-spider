# yzw-spider · 研究生招生目录爬虫

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/scrapy-2.13--2.17-green.svg)](https://scrapy.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

基于 [Scrapy](https://scrapy.org/) 的研究生招生专业目录爬虫，抓取[中国研究生招生信息网](https://yz.chsi.com.cn/)的**硕士 / 博士**招生目录，解析出院校、学院、专业、研究方向、指导教师、拟招人数、初试科目等信息，并导出为 **CSV / JSON / Excel** 三种格式。

> 起因：考研需要提前查清目标院校的考试科目和招生名额。

**目标学校、目标专业、学位层次全部写在 `config.yaml` 里**，改配置即可换目标，不用动代码；也支持"全国所有学校 × 所有专业"的全量模式。

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [全量抓取](#全量抓取)
- [目录结构](#目录结构)
- [数据字段](#数据字段)
- [输出文件](#输出文件)
- [接口说明](#接口说明)
- [常见问题](#常见问题)
- [已知问题](#已知问题)
- [声明](#声明)
- [许可证](#许可证)

---

## 功能特性

- **配置驱动**：学位层次（硕士 / 博士 / 两者）、目标学校、目标专业、输出目录、限速全部由 `config.yaml` 决定。
- **三种入口**：`master`（硕士）、`doctor`（博士）、`all`（两者一起抓），共用同一份配置。
- **粒度自动下钻**：专业写名字就行 —— `经济学` → 门类 `02`，`应用经济学` → 一级学科 `0202`，`西方经济学` → 专业 `020104`。
- **全国枚举**：按省份逐省翻研招网院校库，能拿到全部 936 所招生单位及其代码（`schools: all`）。
- **走 JSON 接口**：直接调用研招网的目录查询接口，不解析 HTML 列表页，页面改版时受影响更小。
- **字段完整**：院校、学院、专业、研究方向、指导教师、拟招人数、学习方式、考试方式、备注，以及初试科目 1–4。
- **多格式导出**：同一份数据同时写出 CSV、JSON、Excel 三种格式，文件名带运行时间戳。
- **Excel 分校分表**：按学校名自动建 sheet，列顺序与表头严格对齐；学校太多时自动放弃 Excel，只留 CSV / JSON。
- **限流自动退避**：接口返回"访问太频繁"时自动等待重试，不会静默丢数据。

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.10+（实测 3.12.13 / 3.13.13） |
| Scrapy | 2.13 ~ 2.17 |
| 操作系统 | Linux / macOS / Windows 均可 |

> 爬虫在基类里同时提供了 `start_requests()` 和 `async def start()`，因此 Scrapy 2.16 前后都能正常启动，
> 不需要为不同版本改代码；中间件和 pipeline 的 `spider` 参数也写成了可选，
> 2.17 起不再传这个参数也不会报错。

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
# 只抓硕士
scrapy crawl master

# 只抓博士
scrapy crawl doctor

# 硕士 + 博士都抓
scrapy crawl all
```

在仓库根目录执行即可；`scrapy.cfg` 会自动向上查找，因此在 `yzw/` 子目录下执行同样有效。
输出目录不需要手动创建，脚本会自动建好。

跑之前先看一眼 `config.yaml`，确认目标学校 / 专业 / 学位层次。

### 常用参数

```bash
scrapy crawl master -a config=other.yaml     # 用另一份配置文件
scrapy crawl all    -a degree=both           # 命令行临时改学位层次
scrapy crawl master -a schools=all           # 命令行临时抓全国
scrapy crawl master -s LOG_LEVEL=INFO        # 调整日志级别
```

> 命令行参数只覆盖 `config` / `degree` / `schools` / `majors` / `cookie` 这几项，
> 限速、输出目录等还是在 `config.yaml` 里改。
>
> `degree` 是有约束的：`scrapy crawl master` 只抓硕士，配置里写了 `degree: doctor`
> 的话它会直接跳过并提示，`scrapy crawl all` 才会按配置同时抓两个学位层次。

---

## 配置说明

全部配置在仓库根目录的 **`config.yaml`**。配置文件查找顺序（从高到低）：

1. `scrapy crawl all -a config=/path/to.yaml`
2. 环境变量 `YZW_CONFIG=/path/to.yaml`
3. Scrapy 设置 `-s YZW_CONFIG=/path/to.yaml`
4. 仓库根目录的 `config.yaml`

### 全部配置项

| 配置项 | 取值 | 说明 |
| --- | --- | --- |
| `degree` | `master` / `doctor` / `both` | 学位层次。`both` 等价于硕士 + 博士 |
| `schools` | `all` 或列表 | 目标学校。`all` = 全国全部；否则填校名（`南京大学`）或招生单位代码（`10284`） |
| `extra_schools` | 列表 | 手工补漏的院校，追加在 `schools` 后面 |
| `majors` | `all` 或列表 | 目标专业。`all` = 所选学校的全部专业；否则填专业名或专业代码 |
| `output.directory` | 路径 | 输出根目录，默认 `./result`，下面分 `master/` 和 `doctor/` |
| `output.excel` | `auto` / `always` / `never` | Excel 输出策略，默认 `auto` |
| `output.excel_max_schools` | 整数 | `auto` 模式下的学校数阈值，默认 100 |
| `request.delay` | 秒 | 同一站点两次请求的间隔，默认 3 |
| `request.concurrency` | 整数 | 并发数，默认 1 |
| `request.max_schools` | 整数 | `>0` 只抓前 N 所学校（试跑用），`0` = 不限，默认 0 |
| `cookie` | 字符串 | 研招网登录态 cookie，可选 |

### 三个例子

**① 只抓某校某个专业（硕士）**

```yaml
degree: master
schools:
  - 南京大学
majors:
  - 应用经济学
request:
  delay: 3
  concurrency: 1
```

**② 只抓博士**

```yaml
degree: doctor
schools:
  - 南京大学
  - 10284          # 代码和校名可以混用
majors: all
```

**③ 全量：全国所有学校 × 所有专业**

```yaml
degree: master
schools: all
majors: all
output:
  directory: ./result
  excel: never          # 全量数据量太大，明确关掉 Excel
request:
  delay: 1
  concurrency: 2
```

> 全量之前建议先加一行 `request.max_schools: 3` 试跑一遍，确认链路没问题再放开。

### 专业名的粒度是自动的

写名字就行，爬虫会按"门类 → 一级学科 → 专业"逐级往下钻，能钻到哪层就抓哪层：

| 写的名字 | 解析成 | 含义 |
| --- | --- | --- |
| `经济学` | 门类 `02` | 经济学门类下全部专业 |
| `应用经济学` | 一级学科 `0202` | 应用经济学下的全部专业 |
| `西方经济学` | 专业 `020104` | 只抓西方经济学这一个专业 |
| `0202` | 一级学科 `0202` | 同上，代码写法 |
| `020104` | 专业 `020104` | 同上，代码写法 |

同名会横跨多个层级时一并抓 —— 比如 `临床医学` 既是学术学位的一级学科 `1002`，
也是专业学位的专业 `105100`，两个都会抓。

> 专业名请写全。研招网的自动补全接口是模糊匹配，写 `经济` 会返回几十个沾边的专业，
> 这种情况爬虫会跳过并在日志里提示。

### Excel 输出策略

| 模式 | 行为 |
| --- | --- |
| `auto`（默认） | 学校数 ≤ `excel_max_schools` 才出 Excel；超过就只出 CSV / JSON |
| `always` | 一定出 Excel（学校很多时会很慢、很占内存） |
| `never` | 不出 Excel |

`auto` 模式在发现学校数超阈值的那一刻就会放弃 Excel，不会有"内存爆掉"的问题。

---

## 全量抓取

`schools: all` 时，爬虫按**省份**逐个翻研招网院校库：

```
https://yz.chsi.com.cn/sch/search.do?ssdm=32&start=20
```

院校库是服务端渲染的完整列表，每页 20 条、`start` 可以自由翻页、不需要登录，
每条记录里直接带招生单位代码 `dwdm`（校徽图片地址就是 `.../xh/{dwdm}.jpg`）。

- 31 个省份全部枚举完共 **936 所**招生单位，约 **61 次请求**
- 枚举结果会写进 `data/schools.json`（**只做合并、不做覆盖** —— 定向抓某所学校时
  不会把已有的全国清单冲掉），也可以单独重新生成：

```bash
python scripts/build_school_catalog.py
```

### 规模与耗时

| 项目 | 硕士全量 | 博士全量 |
| --- | --- | --- |
| 招生单位 | 936 所 | 936 所 |
| 请求量级 | 约 15 ~ 25 万次 | 约 5 ~ 10 万次 |
| 数据行数 | 约 20 ~ 40 万行 | 约 10 ~ 20 万行 |
| CSV 体积 | 100 MB 量级 | 50 MB 量级 |

耗时可以按这个公式估：**总请求数 × `request.delay` ÷ `request.concurrency`**。

| 配置 | 硕士全量预计 |
| --- | --- |
| `delay: 3` / `concurrency: 1` | 100 小时以上，不现实 |
| `delay: 1` / `concurrency: 2` | 20 ~ 35 小时 |
| `delay: 0.3` / `concurrency: 4` | 4 ~ 6 小时 |

请求太密会被限流（接口返回"访问太频繁"）。爬虫会自动退避重试，
但**把 `delay` 调大比让重试机制兜底更靠谱**。全量建议 `delay: 1` / `concurrency: 2`。

### 用 cookie 打开"翻页"这把钥匙

研招网的硕士接口 `start > 0` 会返回 `{"flag": false, "msg": "请登录"}`（网页自己也会弹登录框），
匿名状态下**每个专业最多只能拿到 10 条明细**。

在 `config.yaml` 里填上研招网的登录 cookie 之后：

```yaml
cookie: "JSESSIONID=xxxxxxxx; CHSICC_CLIENTFLAGZSML=xxxxxxxx"
```

`start` 翻页就能用，"每页 10 条"的限制随之消失，枚举也不必再靠收窄条件绕。

---

## 目录结构

```
yzw-spider/
├── config.yaml                # ★ 唯一的配置入口：学校 / 专业 / 学位层次 / 限速 / 输出
├── requirements.txt            # 依赖清单
├── scrapy.cfg                  # Scrapy 项目配置（入口设置 yzw.settings）
├── LICENSE                     # MIT
├── README.md
├── data/
│   └── schools.json            # 全国招生单位清单（936 所，爬虫自动维护）
├── result/                     # 爬取结果输出目录（自动创建）
│   ├── master/                 # 硕士数据：csv / json / xlsx
│   └── doctor/                 # 博士数据：csv / json / xlsx
├── scripts/
│   └── build_school_catalog.py # 单独重建 data/schools.json
├── tests/                      # pytest 用例
│   ├── test_config.py
│   └── test_codes.py
└── yzw/
    ├── config.py               # 配置加载、归一化、校验
    ├── codes.py                # 门类 / 一级学科 / 专业代码表
    ├── discovery.py            # 院校库枚举（按省翻页）
    ├── items.py                # MasterItem / DoctorItem 字段定义
    ├── middlewares.py          # 限流退避重试中间件
    ├── pipelines.py            # MasterPipeline / DoctorPipeline，文件落盘
    ├── settings.py             # 项目配置（限速、UA、pipeline 注册）
    ├── spiders/
    │   ├── base.py             # BaseSpider：配置装载、枚举调度、代码表
    │   ├── master.py           # 硕士爬虫
    │   ├── doctor.py           # 博士爬虫
    │   └── all.py              # 硕士 + 博士一起抓
    └── utils/
        ├── csv_handler.py      # CSV 写入
        └── excel_handler.py    # Excel 建簿 / 分 sheet / 追加行（内存缓冲）
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

命名规则：`<输出目录>/<master|doctor>/<前缀>_<YYYYMMDDHHMM>.<扩展名>`

| 部分 | 取值 |
| --- | --- |
| 输出目录 | `config.yaml` 的 `output.directory`，默认 `./result` |
| 子目录 | 硕士 `master` / 博士 `doctor` |
| 前缀 | 硕士 `master_directory` / 博士 `doctor_directory` |
| 时间戳 | `%Y%m%d%H%M`（年月日时分），**爬取启动时刻** |
| 扩展名 | `.csv` / `.json` / `.xlsx` |

一次运行的实际产物：

```
result/master/master_directory_202610281704.csv
result/master/master_directory_202610281704.json
result/master/master_directory_202610281704.xlsx
result/doctor/doctor_directory_202610281704.csv
result/doctor/doctor_directory_202610281704.json
result/doctor/doctor_directory_202610281704.xlsx
```

| spider | 文件 | 说明 |
| --- | --- | --- |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.csv` | 逗号分隔，含表头 |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.json` | **每行一个 JSON 对象**（JSON Lines） |
| `master` | `result/master/master_directory_<YYYYMMDDHHMM>.xlsx` | Excel，按学校分 sheet |
| `doctor` | `result/doctor/doctor_directory_<YYYYMMDDHHMM>.csv` | 同上 |
| `doctor` | `result/doctor/doctor_directory_<YYYYMMDDHHMM>.json` | 同上 |
| `doctor` | `result/doctor/doctor_directory_<YYYYMMDDHHMM>.xlsx` | 同上 |

几个容易踩的细节：

- **三种格式共用同一个时间戳**：同一次运行生成的文件只差扩展名。
- **时间戳是爬取启动时刻**，不是第一条数据落盘的时刻 —— pipeline 在 crawler 初始化时就创建好了。
- **文件是懒创建的**：目录和文件都等到第一条数据写入时才建。所以只跑 `master` 时
  `result/doctor/` 下不会有文件产生（不是空文件，是根本没有）。
- **同一分钟内重复跑会追加**：JSON 以追加模式打开，CSV 也一样。正常情况下两次运行撞不到同一分钟；
  真撞上了，数据会接到同一个文件里而不是覆盖。
- **三种格式的列顺序一致**，都是：`Link, Subject1~4, University, ExamType, College, Major, StudyType, ResearchInterests, Teacher, StudentNo, Content`。
- **`.json` 其实是 JSONL**：每行一条独立 JSON 记录，不是标准 JSON 数组。
- **`.xlsx` 其实是 Excel 97-2003 格式**：文件由 `xlwt` 写出，二进制结构是 `.xls`（BIFF8），只是扩展名写成了 `.xlsx`。用 Excel 打开会提示「文件格式与扩展名不匹配」，用 WPS / LibreOffice / pandas 则可直接读取。
- **Excel 表头在第 2 行**，第 1 行留空。
- Excel 按学校名建 sheet，sheet 名受 Excel 限制最多 31 字符。
- **跑 `master` 不会产生博士文件**，反之亦然：两个 pipeline 各自只处理自己那类 Item。

---

## 接口说明

研招网 2025-09 改版后，旧的 `zsml/querySchAction.do` 已下线。当前爬虫调用的是新接口。

**硕士（`zsml`）**

| 步骤 | 接口 | 方法 | 作用 |
| --- | --- | --- | --- |
| 0 | `/sch/search.do` | GET | **院校库**：按省份翻页，拿到全国招生单位及 `dwdm` |
| 1 | `/zsml/rs/dws.do` | POST | 按校名 / 校码精确查招生单位（`schools` 指定具体学校时用） |
| 2 | `/zsml/rs/dwzys.do` | POST | 某招生单位的开设专业列表（按 `mldm` + `yjxkdm` 收窄） |
| 3 | `/zsml/rs/yjfxs.do` | POST | 某专业的学院 / 研究方向明细，含科目、导师、拟招人数 |
| — | `/zsml/code/ml.json` | GET | 学科门类代码表（14 个） |
| — | `/zsml/code/yjxk/{门类}.json` | GET | 一级学科代码表（共 176 个） |
| — | `/zsml/code/autozy.do?q=` | GET | 专业代码自动补全（6 位码） |
| — | `/zsml/zydetail.do` | GET | 专业详情页，仅用于生成 `Link` |

**博士（`bsmlcx`）**

| 步骤 | 接口 | 方法 | 作用 |
| --- | --- | --- | --- |
| 0 | `/sch/search.do` | GET | 同上，共用院校清单 |
| 1 | `/bsmlcx/cx/listYxsAndZyCollected` | GET | 某院校的学院 + 专业列表 |
| 2 | `/bsmlcx/cx/listCxZymlCollected` | GET | 某专业的研究方向 / 导师 / 考试科目明细 |

以上接口均为研招网页面自身在用的公开查询接口，POST 请求带
`X-Requested-With: XMLHttpRequest` 与 `application/x-www-form-urlencoded` 表单头。

### 接口硬约束（爬虫的绕行办法）

这几条是实测出来的，直接决定了实现方式：

| 接口 | 约束 | 绕行办法 |
| --- | --- | --- |
| `dws.do` | 每页硬顶 10 条；`start > 0` 一律"请登录"；`pageSize` 被忽略 | **不用它枚举院校**，改用院校库 `/sch/search.do`（可自由翻页）；只用来按校名精确查一次 |
| `dwzys.do` | 每页硬顶 10 条；`start > 0` 一律"请登录" | 用 `mldm`（14 门类）→ `yjxkdm`（176 个一级学科）两级收窄，每组 ≤ 10 条，**彻底避开登录墙** |
| `yjfxs.do` | 每页硬顶 10 条；`start > 0` 一律"请登录"；**只认 `tydxs` 一个筛选条件**（`xxfs` / `jsggjh` / `jsxbjh` 传进去报"参数错误"） | 按 `tydxs=0` / `tydxs=1` 拆成两支重取（多数专业 7 + 5 = 12 正好拿全） |
| `listYxsAndZyCollected` | `dwdm` 必填；`start` 步进 20 **可自由翻页**，无登录墙 | 直接翻页 |
| `listCxZymlCollected` | `msg` 是裸数组，不受条数限制 | 无需处理 |

**为什么院校枚举不用硕士目录的 `dws.do`**：它匿名状态下翻不了页，
按省枚举只能拿到每省前 10 所。院校库 `/sch/search.do` 是服务端渲染的完整列表，
31 个省合计 936 所，与 `dws.do` 逐省 `totalCount`（合计 931）对得上 ——
多出来的那几条是院校库收录、但不在硕士目录里的单位。

---

## 常见问题

**Q：抓不到数据 / 所有请求都是 404**
研招网改过版。跑一次 `scrapy crawl master -s LOG_LEVEL=DEBUG`，看实际请求的接口返回了什么；
若接口路径已变，需要按[接口说明](#接口说明)重新定位。

**Q：日志里出现"接口返回失败: 请登录"**
这是研招网的登录墙，出现在 `start > 0` 的翻页请求上。
匿名状态下爬虫已经绕开了这条路径（靠收窄条件），但如果你在日志里看到它，
说明某个接口的收窄条件没生效 —— 用 `scrapy crawl ... -s LOG_LEVEL=DEBUG` 排查。

**Q：日志里出现"访问太频繁"**
请求太密被限流了。中间件会自动退避重试（10s → 20s → 30s），
但更好的办法是把 `request.delay` 调大、`request.concurrency` 调小。

**Q：日志里出现"专业 XXX 的明细有 N 条，接口只返回 10 条"**
见[已知问题](#已知问题)第 3 条 —— 这是研招网接口自身的限制，不是爬虫的 bug。

**Q：`ValueError: Missing scheme in request url: h`**
Scrapy 版本过老（< 2.13 不认识 `async def start()`）或代码被改乱。装成 `pip install -r requirements.txt` 的版本即可。

**Q：Excel 打开提示「文件格式与扩展名不匹配」**
`.xlsx` 实际是 Excel 97-2003 二进制格式，见[输出文件](#输出文件)说明。用 WPS / LibreOffice / pandas 读取不受影响。

**Q：想先小范围试跑**
在 `config.yaml` 里加一行 `request.max_schools: 3`，只抓前 3 所学校。
枚举会跟着停，不会白跑一遍全国。

**Q：导师字段是空的**
硕士目录的 `zdjs` 字段大部分院校不上报，属正常现象；博士目录的 `dsxm` 一般有值。

**Q：怎么跑单元测试**
```bash
pytest tests/
```

---

## 已知问题

以下问题为当前实现的已知限制。

### 1. 研招网接口可能再次改版

站点 2025-09 改版过一次，`zsml/querySchAction.do` 等旧接口直接 404。
当前代码依赖的新接口若再次调整，需要重新逆向页面 JS 并更新 `base.py` 里的接口常量。

### 2. 匿名状态下接口不能翻页

硕士侧三个接口 `dws.do` / `dwzys.do` / `yjfxs.do` 的 `start > 0` 一律返回"请登录"，
只有每页前 10 条。爬虫靠收窄条件（门类 / 一级学科 / `tydxs`）绕开，
**枚举招生单位则改用院校库绕开**。

配了 `cookie` 之后翻页可用，这条限制就不存在了。

### 3. 个别专业的明细只能拿到前 10 条

如果一个专业的研究方向**全部是同一个 `tydxs`**（比如南开大学"应用经济学"12 条都是统招），
那么 `tydxs` 拆分也救不回来 —— 研招网匿名状态下自己也只能看到 10 条。
这种情况爬虫会在日志里明确记下来：

```
WARNING: 专业 应用经济学(020200) 的明细有 12 条，接口只返回 10 条，
         拆到 tydxs 之后仍超 10 条，剩余数据拿不到
```

**不会静默丢数据** —— 缺口在日志里看得见。全量跑完可以 `grep "仍超 10 条"` 统计缺口。

### 4. `.xlsx` 实际是 Excel 97-2003 格式

`xlwt` 只能写 BIFF8，扩展名写成 `.xlsx` 会让 Excel 弹格式警告。
要输出真正的 xlsx 需换用 `openpyxl`。

### 5. `.json` 是 JSONL 而非 JSON 数组

逐行写入，便于流式处理，但用标准 JSON 解析器读需要包一层数组。

### 6. Excel 写出改成了内存缓冲

早先的写法是每写一行就 `xlrd` 打开工作簿 + `xlutils.copy` + save，整体 O(n²)，
几千行基本卡死。现在改成在内存里攒数据、爬完一次性建簿落盘，快一个数量级。
代价是 `always` 模式下数据量大时会占内存 —— `auto` 模式在超过阈值后会主动放弃 Excel。

### 7. 博士目录不提供考试方式

博士接口没有「考试方式」字段，`ExamType` 统一写成 `申请-考核`（可在
`yzw/spiders/doctor.py` 的 `_exam_type` 中改）。

### 8. 硕士与博士的科目槽位语义不同

硕士 `Subject1~4` 是 政治 / 外语 / 业务课一 / 业务课二；
博士是 外语 / 专业课一 / 专业课二（不足时 `Subject4` 留空）。

### 9. 拟招人数格式不统一

硕士是研招网的文本（如 `专业：3(不含推免)`），博士是纯数字，跨表对比时需要留意。

---

## 声明

本项目数据仅供学习考研参考，不用于任何商业用途。请合理控制请求频率，遵守目标站点的 `robots.txt` 与服务条款，尊重网站方权益。

---

## 许可证

[MIT](LICENSE)
