# yzw-spider · 研究生招生目录爬虫

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Scrapy](https://img.shields.io/badge/scrapy-2.13--2.19-green.svg)](https://scrapy.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

基于 [Scrapy](https://scrapy.org/) 的研究生招生专业目录爬虫，抓取[中国研究生招生信息网](https://yz.chsi.com.cn/)的**硕士 / 博士**招生目录，解析出院校、学院、专业、研究方向、指导教师、拟招人数、初试科目等信息，并导出为 **CSV / JSON / Excel** 三种格式。

> 起因：考研需要提前查清目标院校的考试科目和招生名额。

**目标学校、目标专业、学位层次全部写在 `config.yaml` 里**，改配置即可换目标，不用动代码；也支持"全国所有学校 × 所有专业"的全量模式。

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装](#安装)
- [Docker 部署](#docker-部署)
- [Web 控制台](#web-控制台)
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
- **Web 控制台**：页面上选省份 / 院校 / 专业 / 学位层次就能开抓，实时看进度、日志和已抓条数，跑完直接下载结果（见 [Web 控制台](#web-控制台)）。
- **粒度自动下钻**：专业写名字就行 —— `经济学` → 门类 `02`，`应用经济学` → 一级学科 `0202`，`西方经济学` → 专业 `020104`。
- **层次字段齐全**：省份、学校代码、专业名称 / 代码、专业小类、专业大类一个不少，输出 22 列。
- **多校区不漏**：写 `中国石油大学` 会把 (华东)、(北京) 两个校区都抓全；
  而 `交通大学` 这种本体名对不上的会明确报错跳过，不会抓错学校。
- **全国枚举**：按省份逐省翻研招网院校库，能拿到全部 936 所招生单位及其代码（`schools: [- all]`）。
- **走 JSON 接口**：直接调用研招网的目录查询接口，不解析 HTML 列表页，页面改版时受影响更小。
- **字段完整**：院校、学院、专业、研究方向、指导教师、拟招人数、学习方式、考试方式、备注，以及初试科目 1–4。
- **多格式导出**：同一份数据同时写出 CSV、JSON、Excel 三种格式，文件名带运行时间戳。
- **Docker 一键部署**：不用在机器上装 Python，`docker compose up -d` 就能跑；结果落在宿主机目录，容器删了数据还在。
- **Excel 分校分表**：按学校名自动建 sheet，列顺序与表头严格对齐；学校太多时自动放弃 Excel，只留 CSV / JSON。
- **限流自动退避**：接口返回"访问太频繁"时自动等待重试，不会静默丢数据。
- **不静默失败**：目标为空、学位层次对不上、校名/专业名对不上、明细超出接口上限 —— 都在日志里明确报出来。

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.10+（实测 3.12.13 / 3.13.13） |
| Scrapy | 2.13 ~ 2.19（实测 2.17.0 / 2.19.0） |
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

> 如果机器上已经有装了 Scrapy 的 conda 环境，直接用那个也行，不必新建。
> 判断依据：`python -c "import scrapy; print(scrapy.__version__)"` 能打印出版本号就说明可用。

---

## Docker 部署

不想在机器上装 Python？用 Docker 跑。仓库里已经带了 `Dockerfile` 和 `docker-compose.yml`，
抓取结果落在宿主机目录里，容器删了数据还在。

### 1. 准备

```bash
# 复制一份环境变量模板（.env 不入库，.env.example 是模板）
cp .env.example .env

# 确认 config.yaml 在（目标学校 / 专业 / 层次都在里面改）
ls config.yaml
```

> `config.yaml` 必须存在。compose 用的是"绑定挂载"，
> 文件不存在时 Docker 会**创建一个同名目录**顶替它，容器里就会报"配置文件读取失败"。

### 2. `.env` 里都有什么

`docker compose` 会自动读项目根目录下的 `.env`，把里面的值填进 `docker-compose.yml`
的 `${...}` 占位符。模板见 `.env.example`：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TZ` | `Asia/Shanghai` | 容器时区。**改完要重新 `docker compose build`** —— 时区是烤进镜像的 |
| `RESULT_DIR` | `./result` | 抓取结果放在宿主机哪个目录 |
| `DATA_DIR` | `./data` | 院校清单缓存放在宿主机哪个目录 |
| `CONFIG_FILE` | `./config.yaml` | 配置文件在宿主机哪个位置 |
| `USER_ID` / `GROUP_ID` | `1000` | 容器用户的 uid/gid，要和宿主机对上（`id -u` / `id -g`） |
| `SPIDER` | `all` | 默认抓哪个入口：`master` / `doctor` / `all` |
| `WEB_PORT` | `8000` | Web 控制台在宿主机上的端口（8000 被占了就改这里） |
| `WEB_HOST` | `127.0.0.1` | Web 控制台监听地址。**这个服务没有认证**，默认只绑本机 |
| `YZW_COOKIE` | 空 | 研招网登录态（可选，见下） |

> 存储目录写成**绝对路径**也行，比如 `RESULT_DIR=/mnt/data/yzw`。
> 容器里的挂载点是固定的（`/app/result`、`/app/data`），换宿主机路径不用改容器内部。

### 3. 造镜像

```bash
docker compose build
```

镜像基于 `python:3.13-slim`，`pip install -r requirements.txt`，
以 `.env` 里 `USER_ID`/`GROUP_ID` 指定的普通用户跑（和宿主机用户对得上，
挂出来的文件不会被 root 占住）。时区取 `.env` 的 `TZ`，
同时写进 `TZ` 环境变量和 `/etc/localtime`，输出文件名里的时间戳和本地一致。

### 4. 开跑

```bash
# 后台跑（推荐，全量要跑十几个小时）
docker compose up -d

# 跟日志
docker compose logs -f

# 看还在不在跑
docker compose ps        # 跑完就退出了，用 ps -a 能看到已退出的容器和退出码
docker compose ps -a

# 跑完了收工（数据不丢）
docker compose down
```

临时跑一次别的组合：

```bash
docker compose run --rm yzw crawl master -a degree=master -a schools=南京大学
docker compose run --rm yzw crawl all    -a degree=both
```

### 5. 文件怎么持久化

`docker-compose.yml` 里三个挂载，宿主机那一侧来自 `.env`：

| 容器里 | 宿主机上（`.env`） | 放什么 |
| --- | --- | --- |
| `/app/result` | `RESULT_DIR`（默认 `./result`） | 抓取结果：`master/` `doctor/` 下的 CSV / JSONL / Excel |
| `/app/data` | `DATA_DIR`（默认 `./data`） | 院校清单缓存 `schools.json`（容器里枚举到的招生单位会写回来） |
| `/app/config.yaml` | `CONFIG_FILE`（默认 `./config.yaml`） | 目标学校 / 专业 / 学位层次（只读挂载） |

```bash
# 宿主机上直接看结果，和在容器里跑没区别
ls -l result/master/
```

数据全在宿主机上，所以：

- `docker compose down` / `docker rm` 都不影响已有结果
- 换台机器只要把 `result/` 和 `data/` 拷过去就行
- 想要备份的话，备份 `result/` 就够了

### 6. 传登录态（可选）

匿名状态下研招网每个接口只给 10 条数据，配了 cookie 才能翻页。
在 `.env` 里填就行，不用改 `config.yaml`：

```
YZW_COOKIE=JSESSIONID=xxx; CHSICC_CLIENTFLAGZSML=xxx
```

```bash
docker compose up -d
```

cookie 的传递链路是：

```
.env 的 YZW_COOKIE  →  容器环境变量  →  配置对象 config.cookie
→  下载中间件 LoginCookieMiddleware  →  request.cookies
→  Scrapy 自带的 CookiesMiddleware  →  Cookie 请求头
```

> cookie 等于登录态，`.env` 已经加进 `.gitignore`，别手动提交上去。
>
> 顺带一提：Scrapy 没有 `COOKIES` 这个设置项（只有 `COOKIES_ENABLED` / `COOKIES_DEBUG`），
> 在 `apply_settings` 里 `settings.set('COOKIES', ...)` 是不管用的 ——
> 登录态只能挂到 `request.cookies` 上，才会被写进请求头。
> 而且这个中间件必须是**下载中间件**：Scrapy 2.17 起的 spider middleware
> 已经不支持 `process_request` 了，注册成 spider middleware 会被静默忽略。

### 7. 常见用法

```bash
# 改完 config.yaml 后重新跑（不用重建镜像，改的是挂载进去的文件）
docker compose up -d --force-recreate

# 改完 .env 里的路径 / SPIDER 之后（只有 TZ 需要重建镜像）
docker compose up -d --force-recreate

# 看容器里的时区和用户对不对
docker compose run --rm --entrypoint sh yzw -c 'date; id'

# 进容器里手动排查
docker compose run --rm --entrypoint bash yzw
```

### 8. 全量跑要多久

全量 = 936 所院校 × 全部专业，约 15 ~ 25 万次请求，**十几到几十小时**。
容器是按"长跑"设计的：`restart: "no"`（跑完就退出，不自动重跑），
断电重启后用 `docker compose up -d` 重新起一次即可 —— 已经抓到的结果留在 `./result` 里，
但注意**同名文件会按时间戳另存一份**，不会覆盖（文件名带 `_<年月日时分>`）。

> 想断点续跑，先把 `result/` 里的文件名去掉时间戳那一段，
> 再把 `data/schools.json` 一起带上（里面记着已枚举到的院校）。

---

## Web 控制台

不想改 `config.yaml`、不想开终端盯日志的话，起一个网页控制台：
在页面上选**省份 / 院校 / 专业 / 学位层次**，点「开始抓取」，
页面上实时显示状态、已抓条数和日志，跑完直接下载结果文件。

爬虫本身的行为一行没变 —— 老的 `scrapy crawl` 用法和 YAML 配置照旧可用，
Web 只是多了一个驱动入口。

### 长什么样

```
┌─────────────────────────────────────────────┬──────────────────────────────┐
│ 抓取目标                                     │ 任务                         │
│   学位层次  [硕士][博士][全部]               │  [抓取中] 已抓 1234 条        │
│   省份      [江苏 ▾]  （不选 = 全国）        │  院校 12 所  耗时 8 分 20 秒  │
│   院校      ☑ 抓全部院校                     │  ┌──────────────────────────┐ │
│   专业      ☑ 抓全部专业  [查该校专业]       │  │ 日志实时滚动…             │ │
│   ▸ 高级选项（限速 / 试跑 / Excel）          │  └──────────────────────────┘ │
│   [开始抓取]                                 ├──────────────────────────────┤
└─────────────────────────────────────────────┴──────────────────────────────┤
                                                       结果文件（可下载）      │
```

### 怎么起

Docker（推荐）：

```bash
docker compose up -d web runner
# 打开 http://localhost:8000
```

> 8000 端口被占了的话，改 `.env` 里的 `WEB_PORT`（比如 `8900`），
> 然后 `docker compose up -d web runner` 重新起，访问 `http://localhost:8900`。

本地开发：

```bash
# 后端依赖
pip install -r requirements-web.txt

# 前端（另开一个终端）
cd frontend && npm install && npm run dev    # http://localhost:5173

# 后端 + 执行器（再开两个终端）
uvicorn web.runner:app --port 8001
uvicorn web.app:app    --port 8000
```

### 它是怎么搭的

```
浏览器 (Vue 3 + Element Plus)
   │  轮询 2 秒：GET /api/jobs/{id} + /api/jobs/{id}/logs?offset=N
   ▼
web 容器 (FastAPI，端口 8000，对外)
   ├─ 选项      ← 读共享卷 data/schools.json、data/codes.json
   ├─ 调度      ← 写 data/jobs/<id>/config.yaml，再调执行器
   ├─ 状态/日志 ← 读共享卷 data/jobs/<id>/status.json、log
   └─ 结果      ← 读共享卷 result/
   │  HTTP（只 3 个端点）
   ▼
runner 容器 (FastAPI，端口 8001，只在 compose 内网)
   └─ 子进程：python -m scrapy crawl master|doctor|all -a config=<生成的 yaml>
      cwd=/app，日志和状态写回共享卷
```

**为什么爬虫要跑在子进程里**：Twisted 的 reactor 是**进程级单例且不可重启**，
同一个进程里跑完第一个任务，第二个任务必然 `ReactorNotRestartable`。
子进程顺带解决崩溃隔离、内存隔离、日志流式输出三个问题。

**为什么拆成两个容器**：研招网限流很硬，同时只该跑一个爬虫；
把"页面"和"抓取"分开，抓取的重活不会把页面拖慢，两者只靠共享卷传文件。

### 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/options/provinces` | 31 个省 + 各省院校数 |
| GET | `/api/options/schools?province=32&kw=南京` | 院校列表 |
| GET | `/api/options/majors` | 门类 / 一级学科代码表 |
| GET | `/api/majors-of-school?dwdm=10284` | 实时查某校开设的专业 |
| POST | `/api/jobs` | 新建任务（已有任务在跑 → 409） |
| GET | `/api/jobs` | 任务列表 |
| GET | `/api/jobs/{id}` | 任务状态 |
| GET | `/api/jobs/{id}/logs?offset=&limit=` | 增量日志 |
| POST | `/api/jobs/{id}/stop` | 停止任务 |
| GET | `/api/results` | 结果文件列表 |
| GET | `/api/results/download?path=` | 下载结果文件 |

执行器（`web.runner`）另外有 `POST /run`、`POST /stop/{id}`、`GET /codes`、
`GET /majors-of-school`、`GET /health`。

### 几个要注意的地方

- **没有认证**。默认只绑 `127.0.0.1`（`.env` 的 `WEB_HOST`）。
  要给内网其他人用就改成 `0.0.0.0`，但要自己确保网络是可信的 ——
  任何人都能通过这个页面启动爬虫、下载结果。
- **登录态只走环境变量** `YZW_COOKIE`，不会写进生成的 `config.yaml`，
  也不会回显到页面上。
- **同时只跑一个任务**。研招网扛不住并发，而且两个爬虫同时写
  `data/schools.json`（`merge_catalog` 是"读-改-写"）会互相覆盖。
  页面上的第二个任务会直接被拒（409）。
- **别和 `yzw` 服务同时跑**。`docker compose up -d yzw` 是一次性任务，
  和网页任务抢同一个 `data/schools.json`。
- **专业列表可能不全**。研招网的 `dwzys.do` 匿名状态下每个接口只给 10 条，
  页面上的「查该校专业」会按 14 个门类分别去查，凑出来的结果仍然可能缺；
  配了 `YZW_COOKIE` 才能翻页取全。

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
scrapy crawl master -a config=other.yaml           # 用另一份配置文件
scrapy crawl all    -a degree=both                 # 命令行临时改学位层次
scrapy crawl master -a schools=all                 # 命令行临时抓全国
scrapy crawl master -a schools=all -a province=32   # 只枚举江苏省的院校
scrapy crawl master -a schools=南京大学,南开大学     # 逗号分隔多个
scrapy crawl master -a majors=应用经济学,金融学      # 专业同理
scrapy crawl master -a extra_schools=某某大学        # 补漏的院校
scrapy crawl master -a output.directory=./out       # 换输出目录
scrapy crawl master -a request.delay=0.5            # 临时调限速
scrapy crawl master -a request.max_schools=3        # 只抓前 3 所（试跑）
scrapy crawl master -s LOG_LEVEL=INFO              # 调整日志级别
```

> 命令行能覆盖这些项：
> `degree`、`province`、`schools`、`extra_schools`、`majors`、`cookie`，
> 以及 `output.directory`、`output.excel`、`output.excel_max_schools`、
> `request.delay`、`request.concurrency`、`request.max_schools`。
>
> **参数名写错会直接报错退出**，不会被静默忽略 —— 以前 `-a output.directory=xxx`
> 拼错成 `output.dir` 就会悄悄写到默认目录去。
>
> 命令行只能传字符串，所以多个值用**逗号分隔**（中英文逗号都认）。
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
| `province` | 列表 | 限定省份（省份码，如 `32` = 江苏）。`- all` / 不写 = 全国 31 个省；只在"枚举全部院校"这条路上有用 |
| `schools` | 列表 | 目标学校，**一律用列表写**。`- all` = 全国全部；否则填校名（`南京大学`）或招生单位代码（`10284`） |
| `extra_schools` | 列表 | 手工补漏的院校。指定模式下追加在 `schools` 后面；`schools: [- all]` 时在省份枚举跑完后补上 |
| `majors` | 列表 | 目标专业，**一律用列表写**。`- all` = 所选学校的全部专业；否则填专业名或专业代码 |
| `output.directory` | 路径 | 输出根目录，默认 `./result`，下面分 `master/` 和 `doctor/` |
| `output.excel` | `auto` / `always` / `never` | Excel 输出策略，默认 `auto` |
| `output.excel_max_schools` | 整数 | `auto` 模式下的学校数阈值，默认 100 |
| `request.delay` | 秒 | 同一站点两次请求的间隔，默认 3 |
| `request.concurrency` | 整数 | 并发数，默认 1 |
| `request.max_schools` | 整数 | `>0` 只抓前 N 所学校（试跑用），`0` = 不限，默认 0 |
| `cookie` | 字符串 | 研招网登录态 cookie，可选。环境变量 `YZW_COOKIE` 优先于这里的值 |

### 目标学校怎么写

`schools` 一律用**列表**写，只有一项也是列表：

```yaml
schools:                        # ① 全部学校（按省份逐省枚举）
  - all

schools:                        # ② 单个学校 —— 也是列表
  - 南京大学

schools:                        # ③ 几个学校
  - 南京大学
  - 南开大学
```

几个细节：

- 校名和招生单位代码可以混用：`schools: [南京大学, 10284]`。
  代码就是研招网的招生单位代码（`10284` = 南京大学），院校库枚举出来的也是它。
- **校名会先在院校清单（`data/schools.json`）里换成招生单位代码再查**，
  因为 `dws.do` 的 `dwmc` 是**子串匹配**：`交通大学` 能命中 8 所（没有一所真叫"交通大学"），
  `大学` 更是能匹配 485 所却只返回 10 条。换成 `dwdm` 就是精确查，一所不差。
  清单里查不到的校名才退回按名字查，这时**只认本体名对得上的结果**：
  ```
  ERROR: 院校 "交通大学" 匹配到 8 所，没有一所是它本身，已跳过。（校名是子串匹配，"交通大学"能匹配 8 所）请写全称或改用招生单位代码。候选：北京交通大学、大连交通大学、上海交通大学、华东交通大学、西南交通大学
  ```
  爬虫不会替你猜第一条 —— 抓错学校比不抓更糟。
- **多校区会逐个抓全**。校名里的括号是校区 / 研究所后缀，去掉之后本体名相同就算同一所大学：
  ```
  schools:
    - 中国石油大学       # -> 中国石油大学(华东) + 中国石油大学(北京)，两个都抓
  ```
  院校清单里一共 13 组这样的多校区单位，涉及 88 所：

  | 本体名 | 校区数 | 举例 |
  | --- | --- | --- |
  | 中国石油大学 | 2 | (华东) (北京) |
  | 中国地质大学 | 2 | (武汉) (北京) |
  | 中国矿业大学 | 2 | 本部 (北京) |
  | 华北电力大学 | 2 | 本部 (保定) |
  | 中国航空研究院 | 23 | 十几个研究所 |
  | 中国舰船研究院 | 21 | 十几个研究所 |
  | 中国兵器科学研究院 | 15 | 十几个研究所 |

  注意 `交通大学` **不是**多校区 —— 上海交通大学、华东交通大学、华北交通大学……
  本体名各不相同，是四所不同的学校，必须写全名。爬虫正是靠本体名区分这两者的。
- **命令行覆盖只能传字符串**，这时用逗号分隔（`schools` / `majors` / `extra_schools` 都一样）：
  ```bash
  scrapy crawl master -a schools=南京大学,南开大学
  ```
  中英文逗号都认。
- **`schools` 写空或漏写会直接报错退出**，不会悄悄空跑一圈：
  ```
  ERROR: 配置里没有指定任何院校，没有可抓的目标；要抓全国请写 schools: [- all]，要抓指定院校请写 schools: [校名]
  ```
- `extra_schools` 是给"院校库里没收录、枚举漏掉"的院校兜底的。
  它在两种模式下都生效：指定模式下追加在 `schools` 后面；
  `schools: [- all]` 时在 31 个省枚举跑完后单独补一次，已经被枚举抓到过的院校不会重复抓。

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
majors:
  - all
```

**③ 全量：全国所有学校 × 所有专业**

```yaml
degree: master
schools:
  - all
majors:
  - all
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

`schools: [- all]` 时，爬虫按**省份**逐个翻研招网院校库：

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

枚举是**逐省推进**的：一个省翻完再排下一个省。所以 `request.max_schools` 到量就能停下来，
不会把 31 个省的白名单全跑一遍。

枚举也可以**只跑某几个省**（`province`）—— 省份码用的是研招网那套
（`11` 北京 / `32` 江苏 / `61` 陕西 …，共 31 个，写错会直接报错）：

```yaml
province:
  - "32"      # 只枚举江苏，3 个请求就拿到全省 56 所院校
```

全国要 61 个请求，只跑江苏 3 个就够 —— 只想要某几所学校、又懒得一个个填的时候很好用。

`extra_schools` 在全量模式下同样生效 —— 省份枚举全部跑完后会再补一次，
用来兜底"院校库里没收录、枚举漏掉"的院校；已经被枚举抓到过的不会重复抓。

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

（也可以用环境变量 `YZW_COOKIE` 传，优先级比 `config.yaml` 高 ——
Docker 部署时更方便，不用把登录态写进配置文件。）

`start` 翻页就能用，"每页 10 条"的限制随之消失，枚举也不必再靠收窄条件绕。

---

## 目录结构

```
yzw-spider/
├── config.yaml                # ★ 唯一的配置入口：学校 / 专业 / 学位层次 / 限速 / 输出
├── requirements.txt            # 爬虫依赖清单
├── requirements-web.txt        # Web 控制台的依赖（fastapi / uvicorn / httpx）
├── scrapy.cfg                  # Scrapy 项目配置（入口设置 yzw.settings）
├── Dockerfile                  # 爬虫容器镜像（python:3.13-slim）
├── Dockerfile.web              # Web 控制台镜像（node 打包前端 + python 运行时）
├── docker-compose.yml          # 编排 + 持久化挂载（yzw / web / runner）
├── .env                        # 部署环境变量（时区 / 存储目录 / 用户 / cookie），不入库
├── .env.example                # .env 的模板
├── .dockerignore
├── LICENSE                     # MIT
├── README.md
├── data/
│   ├── schools.json            # 全国招生单位清单（936 所，爬虫自动维护）
│   ├── codes.json              # 门类 / 一级学科代码表缓存（Web 用，7 天过期）
│   └── jobs/                   # 网页任务的配置 / 日志 / 状态（不入库）
├── result/                     # 爬取结果输出目录（自动创建）
│   ├── master/                 # 硕士数据：csv / json / xlsx
│   └── doctor/                 # 博士数据：csv / json / xlsx
├── frontend/                   # Web 控制台前端（Vue 3 + Vite + Element Plus）
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js             # 挂载 + Element Plus 中文语言包
│       ├── api.js              # 后端接口封装
│       ├── App.vue             # 单页布局
│       └── components/
│           ├── TargetForm.vue  # 目标选择：省份 / 院校 / 专业 / 学位
│           ├── JobPanel.vue     # 状态、计数、日志窗口
│           └── ResultPanel.vue  # 结果文件列表与下载
├── scripts/
│   └── build_school_catalog.py # 单独重建 data/schools.json
├── tests/                      # pytest 用例
│   ├── test_config.py          # 配置层的解析、归一化、校验
│   ├── test_codes.py           # 学科代码表与院校清单
│   ├── test_spiders.py         # 爬虫调度：枚举分支、去重
│   ├── test_progress.py        # 进度标记的发出与解析
│   ├── test_web.py             # Web 后端：配置生成、路径安全、任务接口
│   └── test_runner.py          # 执行器：起任务、读日志、停任务
├── web/                        # Web 控制台后端
│   ├── app.py                  # 对外的接口 + 前端静态文件托管
│   ├── runner.py               # 执行器：拉起爬虫子进程、读日志、写状态
│   ├── jobs.py                 # 任务配置生成、状态与日志读写
│   ├── options.py              # 选项数据源：省份、院校
│   ├── majors.py               # 代码表缓存、某校专业查询
│   └── schemas.py              # 接口的数据模型
└── yzw/
    ├── config.py               # 配置加载、归一化、校验
    ├── codes.py                # 门类 / 一级学科 / 专业代码表
    ├── discovery.py            # 院校库枚举（按省翻页）
    ├── items.py                # MasterItem / DoctorItem 字段定义
    ├── middlewares.py          # 限流退避重试中间件 + 登录态注入
    ├── pipelines.py            # MasterPipeline / DoctorPipeline，文件落盘
    ├── progress.py             # 进度标记（Web 端靠它统计进度）
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

`MasterItem` 与 `DoctorItem` 字段完全一致，共 22 个 —— 层次信息（省份 / 学校 / 专业三级）
在两个学位层次里都有，接口给不了的留空。

### 层次信息

| 字段 | 含义 | 硕士取值来源 | 博士取值来源 |
| --- | --- | --- | --- |
| `Province` | 省份名称，如 `江苏` | `szss` | `szss`（从招生单位记录带过来） |
| `ProvinceCode` | 省份代码，如 `32` | `szssm` | `szssm` |
| `University` | 校名，如 `南京大学` | `dwmc` | `dwmc` |
| `SchoolCode` | 招生单位代码，如 `10284` | `dwdm` | `dwdm` |
| `College` | 学院 / 招生单位名称 | `yxsmc` | `yxsmc` |
| `Major` | 专业名称，如 `理论经济学` | `zymc` | `zymc` |
| `MajorCode` | 专业代码（6 位），如 `020100` | `zydm` | `zydm` |
| `MajorSub` | 专业小类（一级学科）名称，如 `理论经济学` | `yjxkmc` | 接口不提供，留空 |
| `MajorSubCode` | 专业小类代码（4 位），如 `0201` | `yjxkdm` | 接口不提供，留空 |
| `MajorCategory` | 专业大类（门类）名称，如 `经济学` | `mlmc` | 接口不提供，留空 |
| `MajorCategoryCode` | 专业大类代码（2 位），如 `02` | `mldm` | 接口不提供，留空 |

专业三级的代码关系是研招网自己的口径：

```
专业大类（门类，2 位）  02   经济学
  └─ 专业小类（一级学科，4 位）  0201  理论经济学
       └─ 专业（6 位）  020100  理论经济学
```

> 硕士明细接口（`yjfxs.do`）的每一行都自带 `szss` / `szssm` / `dwdm` / `zydm` /
> `mldm` / `yjxkdm` 这一整套层次字段，是直接取来的，没有二次推导。
>
> 博士的两个接口（`listYxsAndZyCollected` / `listCxZymlCollected`）**不返回**省份和专业层级：
> 省份靠招生单位记录带过来（`dws.do` 和院校库清单里都有），
> 专业层级接口确实没有，就留空，不拿硕士代码表硬凑。

### 明细信息

| 字段 | 含义 | 硕士取值来源 | 博士取值来源 |
| --- | --- | --- | --- |
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
- **三种格式的列顺序一致**，都是：
  `Link, Subject1~4, Province, ProvinceCode, University, SchoolCode, College, Major, MajorCode, MajorSub, MajorSubCode, MajorCategory, MajorCategoryCode, ExamType, StudyType, ResearchInterests, Teacher, StudentNo, Content`。
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
| 1 | `/zsml/rs/dws.do` | POST | 查招生单位（`schools` 指定具体学校时用；校名先换成 `dwdm` 再精确查） |
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
| `dws.do` | 每页硬顶 10 条；`start > 0` 一律"请登录"；`pageSize` 被忽略；**`dwmc` 是子串匹配**（`大学` 匹配 485 所却只给 10 条） | **不用它枚举院校**，改用院校库 `/sch/search.do`（可自由翻页）；只用来查一次：校名先在院校清单里换成 `dwdm` 精确查（多校区则一个校区一个请求）；退回按名字查时只认本体名对得上的候选 |
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

**Q：报错"配置里没有指定任何院校，没有可抓的目标"**
`schools` 写空了或者漏写了。填成列表即可：

```yaml
schools:
  - 南京大学
```

要抓全国就写 `- all`。爬虫在这种情况下**一个请求都不会发**，直接报错退出。

**Q：`scrapy crawl master` 提示"配置里的 degree 是 doctor，本 spider 只抓 master"**
`master` 这个入口只负责硕士。要抓博士用 `scrapy crawl doctor`，
两个都要就 `scrapy crawl all`。

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

**Q：日志里出现"专业 XXX 在研招网代码表里没有精确匹配"**
专业名写得太简略了。研招网的自动补全接口是模糊匹配，写 `经济` 会返回几十个沾边的专业，
爬虫只认名称完全对得上的，所以会跳过并提示。写全称（如 `应用经济学`）或直接写代码（`0202`）。

**Q：报错"院校 XXX 匹配到 N 所，没有一所是它本身，已跳过"**
校名写短了。研招网按校名查是**子串匹配**，`交通大学` 会命中 8 所带"交通大学"的院校，
但上海交通大学、华东交通大学是四所**不同**的学校，本体名跟"交通大学"对不上，
爬虫不敢替你猜（抓错学校比不抓更糟），所以报错并列出候选。
写全称（`北京交通大学`）或者直接写招生单位代码（`10004`）即可。

> 反过来，`中国石油大学` 这种**本体名一致**的多校区是允许的，
> (华东)、(北京) 两个校区都会抓到 —— 见[目标学校怎么写](#目标学校怎么写)。

**Q：`ValueError: Missing scheme in request url: h`**
Scrapy 版本过老（< 2.13 不认识 `async def start()`）或代码被改乱。装成 `pip install -r requirements.txt` 的版本即可。

**Q：Excel 打开提示「文件格式与扩展名不匹配」**
`.xlsx` 实际是 Excel 97-2003 二进制格式，见[输出文件](#输出文件)说明。用 WPS / LibreOffice / pandas 读取不受影响。

**Q：想先小范围试跑**
在 `config.yaml` 里加一行 `request.max_schools: 3`，只抓前 3 所学校。
枚举会跟着停，不会白跑一遍全国。

**Q：跑完发现 result/doctor/ 是空的**
只跑 `master` 时博士目录不会产生文件 —— 文件是第一条数据落盘时才建的，
两个 pipeline 各自只处理自己那类 Item。

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

### 10. 按校名查招生单位是子串匹配

`dws.do` 的 `dwmc` 走的是**子串匹配**：查 `交通大学` 返回 8 所带"交通大学"的院校，
查 `大学` 的 `totalCount` 是 485 但每页只给 10 条 —— 精确匹配的那一条很可能压根没出现在结果里。

爬虫的做法是：校名先在院校清单 `data/schools.json` 里换成 `dwdm` 精确查（一所不差）；
清单里没有的才退回按名字查，且只接受**本体名（去掉括号后缀）与查询一致**的候选：

- `中国石油大学` → (华东)、(北京) 本体名一致，是同一所大学的两个校区，**都抓**
- `交通大学` → 北京交通大学、大连交通大学…… 本体名全对不上，是四所不同的学校，**一个都不抓**

> 院校清单来自研招网院校库，覆盖 936 所招生单位。
> 清单外的院校会走"按名字查 + 本体名必须对得上"这条严格的路。

### 11. 博士目录没有省份和专业层级

硕士侧的 `yjfxs.do` 每行都带 `szss` / `szssm` / `mldm` / `yjxkdm`，
博士侧的两个接口（`listYxsAndZyCollected` / `listCxZymlCollected`）**一个都不返回**。

- **省份**：靠招生单位记录带过来（`dws.do` 的返回和院校库清单里都有 `szss` / `szssm`），能填上。
- **专业小类 / 专业大类**：接口确实没有。理论上可以用 `zydm` 前 4 位 + 本地一级学科代码表推导，
  但那是推导值不是接口原值，而且博士专业里有 `1201Z3`、`085706` 这类非标准码，
  推导出来未必对得上，所以**留空**。要这两级请看硕士目录的数据。

---

## 声明

本项目数据仅供学习考研参考，不用于任何商业用途。请合理控制请求频率，遵守目标站点的 `robots.txt` 与服务条款，尊重网站方权益。

---

## 许可证

[MIT](LICENSE)
