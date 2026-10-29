# -*- coding: utf-8 -*-
"""爬虫配置：加载、归一化、校验

配置来源优先级（从高到低）：
    1. spider 参数   scrapy crawl all -a config=/path/to.yaml
    2. 环境变量     YZW_CONFIG=/path/to.yaml
    3. Scrapy 设置  -s YZW_CONFIG=/path/to.yaml
    4. 项目根目录   config.yaml

配置项说明见仓库根目录的 config.yaml。
"""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
except ImportError:  # pragma: no cover - 环境没装 PyYAML 时给出明确提示
    yaml = None

from yzw.discovery import PROVINCE_NAMES


# 项目根目录（yzw/config.py -> yzw/ -> 仓库根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.yaml')

# 特殊值：表示"全部"
ALL = 'all'

# 学位层次
DEGREE_MASTER = 'master'
DEGREE_DOCTOR = 'doctor'
DEGREE_BOTH = 'both'
DEGREES = (DEGREE_MASTER, DEGREE_DOCTOR)

# Excel 输出策略
EXCEL_AUTO = 'auto'
EXCEL_ALWAYS = 'always'
EXCEL_NEVER = 'never'
EXCEL_MODES = (EXCEL_AUTO, EXCEL_ALWAYS, EXCEL_NEVER)

DEFAULTS: Dict[str, Any] = {
    'degree': DEGREE_MASTER,
    'province': ALL,
    'schools': [],
    'extra_schools': [],
    'majors': ALL,
    'output': {
        'directory': './result',
        'excel': EXCEL_AUTO,
        'excel_max_schools': 100,
    },
    'request': {
        'delay': 3,
        'concurrency': 1,
        'max_schools': 0,
    },
    'cookie': '',
}

# 可以用命令行 -a 覆盖的顶层配置项
OVERRIDE_KEYS = ('degree', 'province', 'schools', 'extra_schools', 'majors', 'cookie')

# 可以用命令行 -a 覆盖的二级配置项，用点号路径写
OVERRIDE_PATHS = (
    'output.directory',
    'output.excel',
    'output.excel_max_schools',
    'request.delay',
    'request.concurrency',
    'request.max_schools',
)


class ConfigError(Exception):
    """配置不合法"""


@dataclass
class Config:
    """归一化之后的配置"""

    degrees: List[str] = field(default_factory=lambda: [DEGREE_MASTER])
    province: Union[str, List[str]] = ALL
    schools: Union[str, List[str]] = field(default_factory=list)
    extra_schools: List[str] = field(default_factory=list)
    majors: Union[str, List[str]] = ALL
    output: Dict[str, Any] = field(default_factory=dict)
    request: Dict[str, Any] = field(default_factory=dict)
    cookie: str = ''
    source_path: str = ''

    # ------------------------------------------------------------------
    # 常用判定
    # ------------------------------------------------------------------
    def wants_master(self) -> bool:
        return DEGREE_MASTER in self.degrees

    def wants_doctor(self) -> bool:
        return DEGREE_DOCTOR in self.degrees

    def wants(self, degree: str) -> bool:
        """是否要抓某个学位层次"""
        return degree in self.degrees

    def all_schools(self) -> bool:
        """是否抓取全国全部院校"""
        return self.schools == ALL

    def provinces(self) -> List[str]:
        """要抓的省份码；不限（all）时返回空列表

        只在"院校库逐省枚举"这条路上有用 —— 指定了具体院校时省份就没意义了。
        """
        if self.province == ALL:
            return []
        return list(self.province)

    def all_majors(self) -> bool:
        """是否抓取所选学校的全部专业"""
        return self.majors == ALL

    def school_names(self) -> List[str]:
        """指定模式下要抓的院校（名称或代码）"""
        if self.all_schools():
            return list(self.extra_schools)
        return list(self.schools) + list(self.extra_schools)

    def major_names(self) -> List[str]:
        """指定模式下要抓的专业（名称或代码）"""
        if self.all_majors():
            return []
        return list(self.majors)

    def output_directory(self) -> str:
        return self.output.get('directory') or DEFAULTS['output']['directory']

    def excel_mode(self) -> str:
        return self.output.get('excel') or EXCEL_AUTO

    def excel_max_schools(self) -> int:
        return int(self.output.get('excel_max_schools') or 0)

    def delay(self) -> float:
        return float(self.request.get('delay', DEFAULTS['request']['delay']))

    def concurrency(self) -> int:
        return int(self.request.get('concurrency', DEFAULTS['request']['concurrency']))

    def max_schools(self) -> int:
        return int(self.request.get('max_schools') or 0)

    def override(self, overrides: Dict[str, Any]) -> 'Config':
        """用 spider 参数覆盖部分配置，返回新对象

        两种写法都支持：
            -a degree=doctor            顶层配置项直接覆盖
            -a output.directory=./out    二级配置项用点号路径覆盖

        写错的参数名会直接报错，不会被静默忽略。
        """
        data = {
            'degree': self.degrees if len(self.degrees) > 1 else self.degrees[0],
            'province': self.province,
            'schools': self.schools,
            'extra_schools': self.extra_schools,
            'majors': self.majors,
            'output': dict(self.output),
            'request': dict(self.request),
            'cookie': self.cookie,
        }
        for key, value in overrides.items():
            if value is None:
                continue
            if key in OVERRIDE_KEYS:
                data[key] = value
                continue
            if key in OVERRIDE_PATHS:
                group, _, name = key.partition('.')
                data[group][name] = value
                continue
            raise ConfigError(
                '命令行参数 {} 无法识别。可用参数：{}'.format(
                    key, '、'.join(OVERRIDE_KEYS + OVERRIDE_PATHS)))
        return build_config(data, self.source_path)


# ----------------------------------------------------------------------
# 归一化
# ----------------------------------------------------------------------
def _split_names(text: str) -> List[str]:
    """按逗号切分（支持中英文逗号），去掉空白项

    配置文件里用列表写就行，但命令行覆盖只能传字符串：
        scrapy crawl master -a schools=南京大学,南开大学
    """
    parts = re.split(r'[,，]', text)
    return [part.strip() for part in parts if part.strip()]


def _as_name_list(value: Any, field_name: str,
                  default: Union[str, List[str]] = None) -> Union[str, List[str]]:
    """把 'all' / 字符串 / 列表统一成 'all' 或字符串列表"""
    if value is None:
        return [] if default is None else default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return [] if default is None else default
        names = _split_names(value)
        if ALL in names:
            return ALL
        return names
    if isinstance(value, (list, tuple, set)):
        names = []
        for item in value:
            names.extend(_split_names(str(item).strip()))
        if any(name == ALL for name in names):
            return ALL
        return names
    raise ConfigError(f'配置项 {field_name} 类型不对，应为 all / 字符串 / 列表，实际是 {type(value).__name__}')


def _as_str_list(value: Any, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_names(value.strip())
    if isinstance(value, (list, tuple, set)):
        names = []
        for item in value:
            names.extend(_split_names(str(item).strip()))
        return names
    raise ConfigError(f'配置项 {field_name} 类型不对，应为字符串或列表，实际是 {type(value).__name__}')


def _as_provinces(value: Any) -> Union[str, List[str]]:
    """省份码归一化：'all' / [] / '32,33' / ['32','33'] -> 'all' 或 ['32','33']

    省份码必须能在研招网的省份表里找到，写错了直接报错 ——
    静默跳过一个不存在的码，结果就是一个省都不抓，很难查。
    """
    codes = _as_name_list(value, 'province', ALL)
    if codes == ALL:
        return ALL
    if not codes:
        # 空列表 = 不限省份（默认值就是空）
        return ALL

    unknown = [code for code in codes if code not in PROVINCE_NAMES]
    if unknown:
        raise ConfigError(
            '省份码 {} 不存在。可用省份码见 yzw/discovery.py 的 PROVINCES'.format(
                '、'.join(unknown)))
    return codes


def _as_degrees(value: Any) -> List[str]:
    """master / doctor / both 或它们的列表，统一成列表"""
    if value is None:
        return [DEGREE_MASTER]
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ConfigError('配置项 degree 应为 master / doctor / both 或它们的列表')

    degrees: List[str] = []
    for item in value:
        name = str(item).strip().lower()
        if not name:
            continue
        if name == DEGREE_BOTH:
            degrees.extend(DEGREES)
            continue
        if name not in DEGREES:
            raise ConfigError(
                f'配置项 degree 取值 "{item}" 不合法，只能是 {DEGREE_MASTER} / {DEGREE_DOCTOR} / {DEGREE_BOTH}')
        if name not in degrees:
            degrees.append(name)

    if not degrees:
        raise ConfigError('配置项 degree 不能为空')
    return degrees


def _as_output(raw: Any) -> Dict[str, Any]:
    output = dict(DEFAULTS['output'])
    if raw is None:
        return output
    if not isinstance(raw, dict):
        raise ConfigError('配置项 output 应为字典')

    output.update(raw)

    mode = str(output.get('excel', EXCEL_AUTO)).strip().lower()
    if mode not in EXCEL_MODES:
        raise ConfigError(
            f'配置项 output.excel 取值 "{output["excel"]}" 不合法，只能是 {" / ".join(EXCEL_MODES)}')
    output['excel'] = mode

    try:
        output['excel_max_schools'] = int(output.get('excel_max_schools', 0))
    except (TypeError, ValueError):
        raise ConfigError('配置项 output.excel_max_schools 应为整数')
    if output['excel_max_schools'] < 0:
        raise ConfigError('配置项 output.excel_max_schools 不能为负数')

    output['directory'] = str(output.get('directory') or DEFAULTS['output']['directory'])
    return output


def _as_request(raw: Any) -> Dict[str, Any]:
    request = dict(DEFAULTS['request'])
    if raw is None:
        return request
    if not isinstance(raw, dict):
        raise ConfigError('配置项 request 应为字典')

    request.update(raw)

    for key, caster in (('delay', float), ('concurrency', int), ('max_schools', int)):
        try:
            request[key] = caster(request.get(key, DEFAULTS['request'][key]))
        except (TypeError, ValueError):
            raise ConfigError(f'配置项 request.{key} 应为数字')

    if request['delay'] < 0:
        raise ConfigError('配置项 request.delay 不能为负数')
    if request['concurrency'] < 1:
        raise ConfigError('配置项 request.concurrency 至少为 1')
    if request['max_schools'] < 0:
        raise ConfigError('配置项 request.max_schools 不能为负数')
    return request


def build_config(data: Dict[str, Any], source_path: str = '') -> Config:
    """把原始字典归一化成 Config"""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError('配置文件根节点必须是字典')

    unknown = set(data) - set(DEFAULTS)
    if unknown:
        raise ConfigError(
            '配置项 ' + '、'.join(sorted(unknown)) + ' 无法识别，可用配置项：' + '、'.join(sorted(DEFAULTS)))

    return Config(
        degrees=_as_degrees(data.get('degree')),
        province=_as_provinces(data.get('province')),
        schools=_as_name_list(data.get('schools'), 'schools', []),
        extra_schools=_as_str_list(data.get('extra_schools'), 'extra_schools'),
        majors=_as_name_list(data.get('majors'), 'majors', ALL),
        output=_as_output(data.get('output')),
        request=_as_request(data.get('request')),
        cookie=str(data.get('cookie') or '').strip(),
        source_path=source_path,
    )


# ----------------------------------------------------------------------
# 读取
# ----------------------------------------------------------------------
def resolve_config_path(path: Optional[str] = None) -> str:
    """确定要读的配置文件路径"""
    if path:
        return os.path.abspath(os.path.expanduser(path))
    env_path = os.environ.get('YZW_CONFIG')
    if env_path:
        return os.path.abspath(os.path.expanduser(env_path))
    return DEFAULT_CONFIG_PATH


def load_config(path: Optional[str] = None) -> Config:
    """读取配置文件并归一化；文件不存在时返回默认配置"""
    if yaml is None:
        raise ConfigError('缺少 PyYAML 依赖，请先执行：pip install PyYAML')

    config_path = resolve_config_path(path)
    if not os.path.exists(config_path):
        if path:
            raise ConfigError(f'配置文件不存在：{config_path}')
        # 没有 config.yaml 时用内置默认值，spider 仍可跑
        return _with_env_cookie(build_config({}, config_path))

    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise ConfigError(f'配置文件解析失败（{config_path}）：{error}')
    except OSError as error:
        raise ConfigError(f'配置文件读取失败（{config_path}）：{error}')

    if data is None:
        data = {}
    return _with_env_cookie(build_config(data, config_path))


def _with_env_cookie(config: Config) -> Config:
    """环境变量 YZW_COOKIE 覆盖配置文件里的登录态

    Docker 里用环境变量传 cookie 更方便 —— 不用把 cookie 写进镜像或配置文件。
    """
    env_cookie = os.environ.get('YZW_COOKIE', '').strip()
    if env_cookie:
        config.cookie = env_cookie
    return config


def parse_cookie_header(text: str) -> Dict[str, str]:
    """把 "JSESSIONID=xxx; other=yyy" 解析成 cookie 字典

    Scrapy 没有 COOKIES 这个设置项（只有 COOKIES_ENABLED / COOKIES_DEBUG），
    设了也不会发出去 —— 登录态必须挂到 request.cookies 上，
    再由 Scrapy 自带的 CookiesMiddleware 写进 Cookie 请求头。
    """
    cookies = {}
    for part in (text or '').split(';'):
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies
