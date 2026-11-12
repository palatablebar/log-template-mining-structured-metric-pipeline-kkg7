"""文本归一与指纹工具（模板签名、行 hash、槽位分类辅助）。"""
from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")

TEMPLATE_WILDCARD = "<*>"
NOISE_TEMPLATE = "_noise"


def normalize_line(raw: str) -> str:
    """压缩连续空白并去首尾空白；保留引号内原始内容。"""
    return _WS_RE.sub(" ", raw.strip())


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def line_hash(source_key: str, raw_line: str) -> str:
    """事件自然键：日志源 + 原始行（同一行重复导入视为同一条事件）。"""
    return sha1_text(f"{source_key}::{normalize_line(raw_line)}")


def template_signature(template_str: str) -> str:
    return sha1_text(template_str)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
