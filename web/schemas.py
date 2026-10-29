# -*- coding: utf-8 -*-
"""接口的数据模型

前端传过来的选择、返回给前端的选项和状态，都在这里定死形状。
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# 抓取任务
# ----------------------------------------------------------------------
class JobOptions(BaseModel):
    """抓取参数

    限速和 Excel 策略跟 config.yaml 里的同名项是一一对应的。
    """

    delay: float = 3.0
    concurrency: int = 1
    max_schools: int = 0
    excel: str = 'auto'
    excel_max_schools: int = 100


class JobCreate(BaseModel):
    """新建任务的请求

    空的省份 / 学校 / 专业都表示"全部"。
    """

    degree: str = 'master'
    province: List[str] = Field(default_factory=list)
    schools: List[str] = Field(default_factory=list)
    majors: List[str] = Field(default_factory=list)
    options: JobOptions = Field(default_factory=JobOptions)


class JobOut(BaseModel):
    """任务状态

    状态机：pending -> running -> done / stopped / failed / interrupted
    """

    id: str
    status: str = 'pending'
    degree: str = 'master'
    spider: str = 'master'
    province: List[str] = Field(default_factory=list)
    schools: List[str] = Field(default_factory=list)
    majors: List[str] = Field(default_factory=list)
    created_at: str = ''
    started_at: str = ''
    finished_at: str = ''
    items: int = 0
    items_by_degree: Dict[str, int] = Field(default_factory=dict)
    schools_done: int = 0
    stop_requested: bool = False
    exit_code: Optional[int] = None
    message: str = ''


class LogChunk(BaseModel):
    """一段增量日志

    offset 是字节偏移 —— 日志可能有几百 MB，用行号定位会越读越慢。
    """

    offset: int = 0
    next_offset: int = 0
    lines: List[str] = Field(default_factory=list)
    eof: bool = True


# ----------------------------------------------------------------------
# 选项
# ----------------------------------------------------------------------
class ProvinceOut(BaseModel):
    code: str
    name: str
    count: int = 0


class SchoolOut(BaseModel):
    dwdm: str
    name: str
    province: str = ''
    province_code: str = ''


class MajorOut(BaseModel):
    code: str
    name: str


class MajorGroupOut(BaseModel):
    """一个门类下的全部一级学科"""

    code: str
    name: str
    children: List[MajorOut] = Field(default_factory=list)


class SchoolMajorsOut(BaseModel):
    """某所学校开设的专业

    truncated = True 表示接口只给了 10 条、没列全。
    """

    dwdm: str
    name: str = ''
    total: int = 0
    majors: List[MajorOut] = Field(default_factory=list)
    truncated: bool = False


# ----------------------------------------------------------------------
# 结果文件
# ----------------------------------------------------------------------
class ResultFileOut(BaseModel):
    name: str
    path: str
    size: int = 0
    modified: str = ''
