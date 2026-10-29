# 研招网爬虫的 Docker 镜像
#
#   docker compose build
#   docker compose up -d                 # 后台开跑
#   docker compose logs -f               # 看进度
#   docker compose run --rm yzw crawl master -a degree=master   # 临时跑一次
#
# 结果目录 /app/result 和院校清单 /app/data 在 compose 里挂到了宿主机，
# 容器删了重建，数据都还在。
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依赖单独一层，改代码不用重装依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 时区：输出文件名里带时间戳，容器默认 UTC 会和本地时间差 8 小时。
# python:3.13-slim 自带 zoneinfo 数据，不用额外装 tzdata 包。
# 光设 TZ 环境变量也够用，这里再把 /etc/localtime 指过去，
# 免得直接读 /etc/localtime 的程序（比如某些 C 工具）拿到 UTC。
# 时区由 .env 的 TZ 传进来（见 docker-compose.yml 的 build.args）。
# 这段放在装依赖之后 —— 改时区不用重装依赖。
ARG TZ=Asia/Shanghai
ENV TZ=${TZ}
RUN ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && echo "${TZ}" > /etc/timezone

COPY . .

# 用普通用户跑，挂到宿主机上的文件才归宿主机用户所有
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN set -eux; \
    groupadd -g "${GROUP_ID}" yzw 2>/dev/null || true; \
    useradd -u "${USER_ID}" -g "${GROUP_ID}" -m -d /home/yzw yzw 2>/dev/null || true; \
    mkdir -p /app/result /app/data; \
    chown -R "${USER_ID}:${GROUP_ID}" /app

USER yzw

ENTRYPOINT ["scrapy"]
CMD ["crawl", "all"]
