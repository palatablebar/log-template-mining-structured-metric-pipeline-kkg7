"""算法 A：Drain 日志模板挖掘引擎（纯 Python，不依赖 DB / FastAPI）。

口径（batch-plan gb-555 核心算法 A，逐条对应）：
① tokenize：按空白切分，引号内的空白不切（保留带空格的消息体）；
② 按 token 数分层，层内建前缀树（每个节点按 token 出边），从根逐 token 匹配；
③ 匹配不到出边就停在当前节点，用「通配位个数」算相似度：
   similarity = 1 - mismatch_count / token_count，阈值 0.5（可配）；
   相似度达标则把差异位写成 `<*>` 合并进已有簇，否则新建簇；
④ 变量识别：数字 / IP / UUID / 路径 / hex / 时间戳 优先归为槽位（其余归 str）；
   `key=value` 形态的 token 会先剥掉 key 前缀再判类型，并把 key 记为槽位名；
⑤ 新建模板时记录槽位类型、样本行、首次出现位置；
⑥ 输出模板列表 + 覆盖率（被模板覆盖的行 / 总行）+ 新模板数。

失败态：
- 空行 / 纯符号行 → 归入 `_noise` 模板并单列统计（不参与覆盖率分子）；
- 单模板样本数 < 2 → 状态标 `tentative`（仍列出，但不计入覆盖率分子）。
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from src.constants.enums import EventLevel, SlotType, TemplateStatus
from src.utils.text import normalize_line, sha1_text, template_signature, truncate

WILDCARD = "<*>"
NOISE_TEMPLATE = "_noise"
DEFAULT_SIMILARITY_THRESHOLD = 0.5
TENTATIVE_MIN_SAMPLES = 2
MAX_TEMPLATE_TOKENS = 256
SAMPLE_LINE_LIMIT = 400

_NOISE_RE = re.compile(r"^[^A-Za-z0-9]*$")
_LEVEL_RE = re.compile(r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)\b")
_KV_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*)=")
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?Z?$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_PATH_RE = re.compile(r"^/[A-Za-z0-9._~/\-*{}]*$")
_HEX_RE = re.compile(r"^(?:0x[0-9a-fA-F]+|[0-9a-fA-F]{6,})$")
_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

_TOKEN_SPLIT_RE = re.compile(r'"[^"]*"|\S+')
_LEVEL_MAP = {
    "TRACE": EventLevel.DEBUG.value,
    "DEBUG": EventLevel.DEBUG.value,
    "INFO": EventLevel.INFO.value,
    "WARN": EventLevel.WARN.value,
    "WARNING": EventLevel.WARN.value,
    "ERROR": EventLevel.ERROR.value,
    "FATAL": EventLevel.FATAL.value,
}


def tokenize(line: str) -> list[str]:
    """① tokenize：按空白切分，引号内空白保留（实现：整段引号内容作为一个 token）。"""
    return _TOKEN_SPLIT_RE.findall(line.strip())


def is_noise_token_line(tokens: list[str]) -> bool:
    """空行 / 纯符号行（含只有标点的分隔线）判定为噪声。"""
    return not tokens or all(_NOISE_RE.match(token) for token in tokens)


def split_kv(token: str) -> tuple[str, str]:
    """把 `key=value` 拆成 (key, value)；非 kv 形态返回 ("", token)。"""
    match = _KV_RE.match(token)
    if not match:
        return "", token
    return match.group("key"), token[match.end():]


def classify_slot(token: str) -> str:
    """④ 变量识别：数字 / IP / UUID / 路径 / hex / 时间戳 优先，其余 str。"""
    _key, value = split_kv(token)
    candidate = value.strip('"\'')
    if _TS_RE.match(candidate):
        return SlotType.TS.value
    if _UUID_RE.match(candidate):
        return SlotType.UUID.value
    if _IP_RE.match(candidate):
        return SlotType.IP.value
    if _PATH_RE.match(candidate):
        return SlotType.PATH.value
    if _HEX_RE.match(candidate):
        return SlotType.HEX.value
    if _NUM_RE.match(candidate):
        return SlotType.NUM.value
    if candidate == "":
        return SlotType.UNKNOWN.value
    return SlotType.STR.value


def detect_level(line: str) -> str:
    upper = line.upper()
    match = _LEVEL_RE.search(upper)
    if match:
        return _LEVEL_MAP.get(match.group(1), EventLevel.INFO.value)
    if " ERROR " in f" {upper} " or upper.startswith("ERROR"):
        return EventLevel.ERROR.value
    return EventLevel.INFO.value


@dataclass
class _Cluster:
    """一个模板簇：模板 token 序列 + 槽位观测 + 样本。"""

    token_count: int
    template_tokens: list[str]
    sample_count: int = 1
    sample_line: str = ""
    first_pos: int = 0
    last_pos: int = 0
    slot_observations: dict[int, list[str]] = field(default_factory=dict)
    level_counts: dict[str, int] = field(default_factory=dict)
    known_template_id: int | None = None
    service: str = ""

    def observe(self, tokens: list[str], line: str, position: int, level: str) -> None:
        self.sample_count += 1
        self.last_pos = position
        self.level_counts[level] = self.level_counts.get(level, 0) + 1
        for index, token in enumerate(tokens):
            if self.template_tokens[index] == WILDCARD:
                bucket = self.slot_observations.setdefault(index, [])
                if len(bucket) < 40:
                    bucket.append(token)
        if not self.sample_line:
            self.sample_line = line

    def merge_tokens(self, tokens: list[str]) -> None:
        for index, token in enumerate(tokens):
            if self.template_tokens[index] != WILDCARD and self.template_tokens[index] != token:
                self.template_tokens[index] = WILDCARD

    def slot_types(self) -> list[str]:
        """槽位类型列表：与模板 token 位置对齐；静态位为 `static`。"""
        result: list[str] = []
        for index, token in enumerate(self.template_tokens):
            if token != WILDCARD:
                result.append("static")
                continue
            observed = self.slot_observations.get(index, [])
            result.append(_dominant_slot_type(observed))
        return result

    def slot_names(self) -> list[str]:
        result: list[str] = []
        for index, token in enumerate(self.template_tokens):
            if token != WILDCARD:
                result.append("")
                continue
            observed = self.slot_observations.get(index, [])
            keys = [split_kv(item)[0] for item in observed]
            keys = [key for key in keys if key]
            if keys and len(set(keys)) == 1:
                result.append(keys[0])
            else:
                result.append("")
        return result

    def template_str(self) -> str:
        return " ".join(self.template_tokens)

    def level_hint(self) -> str:
        if not self.level_counts:
            return EventLevel.INFO.value
        return max(self.level_counts.items(), key=lambda item: item[1])[0]


def _dominant_slot_type(observed: list[str]) -> str:
    if not observed:
        return SlotType.UNKNOWN.value
    counts: dict[str, int] = {}
    for token in observed:
        slot = classify_slot(token)
        counts[slot] = counts.get(slot, 0) + 1
    # 时间戳/路径等强类型优先，避免被大量 str 稀释
    for preferred in (SlotType.TS.value, SlotType.UUID.value, SlotType.IP.value, SlotType.PATH.value, SlotType.HEX.value):
        if counts.get(preferred, 0) >= max(1, int(0.5 * len(observed))):
            return preferred
    return max(counts.items(), key=lambda item: item[1])[0]


@dataclass
class MinedTemplate:
    template_str: str
    token_count: int
    slot_types: list[str]
    slot_names: list[str]
    sample_count: int
    sample_line: str
    signature: str
    status: str
    level_hint: str
    first_pos: int = 0
    known_template_id: int | None = None
    service: str = ""

    def to_dict(self) -> dict:
        return {
            "template_str": self.template_str,
            "token_count": self.token_count,
            "slot_types": self.slot_types,
            "slot_names": self.slot_names,
            "sample_count": self.sample_count,
            "sample_line": self.sample_line,
            "signature": self.signature,
            "status": self.status,
            "level_hint": self.level_hint,
            "known_template_id": self.known_template_id,
            "service": self.service,
        }


@dataclass
class MineResult:
    lines_total: int
    covered_lines: int
    noise_lines: int
    tentative_lines: int
    known_hits: int
    templates: list[MinedTemplate]
    new_templates: int
    elapsed_ms: int
    known_templates_used: int = 0
    line_signatures: list[str | None] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if self.lines_total == 0:
            return 0.0
        return round(self.covered_lines / self.lines_total, 4)

    @property
    def coverage_percent(self) -> float:
        return round(self.coverage * 100, 2)

    def to_dict(self) -> dict:
        return {
            "lines_total": self.lines_total,
            "covered_lines": self.covered_lines,
            "noise_lines": self.noise_lines,
            "tentative_lines": self.tentative_lines,
            "known_hits": self.known_hits,
            "coverage": self.coverage,
            "coverage_percent": self.coverage_percent,
            "templates": [item.to_dict() for item in self.templates],
            "new_templates": self.new_templates,
            "elapsed_ms": self.elapsed_ms,
            "known_templates_used": self.known_templates_used,
        }


class _PrefixNode:
    __slots__ = ("children", "clusters")

    def __init__(self) -> None:
        self.children: dict[str, _PrefixNode] = {}
        self.clusters: list[_Cluster] = []


class DrainEngine:
    """Drain 挖掘器。可传入已有模板（DB 里已挖掘的）作为初始簇，实现「先匹配已知再新建」。"""

    def __init__(self, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold
        self._layers: dict[int, _PrefixNode] = {}

    # ---------------------------------------------------------------- 已知模板
    def load_known(self, known: list[dict]) -> int:
        """把 DB 中已有模板灌入前缀树：known 项含 template_id/template_str/slot_types/status/sample_line。"""
        loaded = 0
        for item in known:
            template_str = str(item.get("template_str") or "").strip()
            if not template_str or template_str == NOISE_TEMPLATE:
                continue
            tokens = template_str.split(" ")
            if not tokens or len(tokens) > MAX_TEMPLATE_TOKENS:
                continue
            cluster = _Cluster(
                token_count=len(tokens),
                template_tokens=list(tokens),
                sample_count=max(1, int(item.get("frequency") or 1)),
                sample_line=str(item.get("sample_line") or template_str),
                known_template_id=item.get("template_id"),
                service=str(item.get("service") or ""),
            )
            cluster.level_counts[str(item.get("level_hint") or EventLevel.INFO.value)] = 1
            self._insert(cluster)
            loaded += 1
        return loaded

    # ---------------------------------------------------------------- 内部工具
    def _layer(self, token_count: int) -> _PrefixNode:
        node = self._layers.get(token_count)
        if node is None:
            node = _PrefixNode()
            self._layers[token_count] = node
        return node

    def _search(self, root: _PrefixNode, tokens: list[str]) -> _PrefixNode:
        """从根逐 token 匹配：相同 token 前进，否则吃通配出边；都没有就停在当前节点。"""
        node = root
        for token in tokens:
            child = node.children.get(token)
            if child is None:
                child = node.children.get(WILDCARD)
            if child is None:
                return node
            node = child
        return node

    def _insert(self, cluster: _Cluster) -> None:
        node = self._layer(cluster.token_count)
        for token in cluster.template_tokens:
            if token == WILDCARD:
                break
            node = node.children.setdefault(token, _PrefixNode())
        node.clusters.append(cluster)

    @staticmethod
    def _similarity(template_tokens: list[str], tokens: list[str]) -> float:
        if len(template_tokens) != len(tokens):
            return 0.0
        mismatches = 0
        for existing, incoming in zip(template_tokens, tokens):
            if existing == WILDCARD or existing == incoming:
                continue
            mismatches += 1
        return 1.0 - mismatches / len(template_tokens)

    # ---------------------------------------------------------------- 主流程
    def mine(self, lines: list[str]) -> MineResult:
        started = time.perf_counter()
        clusters: list[_Cluster] = []
        seen_ids: dict[int, _Cluster] = {}
        lines_total = 0
        noise_lines = 0
        known_hits = 0
        position_cluster: list[_Cluster | None] = []

        for position, raw in enumerate(lines):
            line = normalize_line(raw)
            tokens = tokenize(line)
            lines_total += 1
            if is_noise_token_line(tokens) or len(tokens) > MAX_TEMPLATE_TOKENS:
                noise_lines += 1
                position_cluster.append(None)
                continue
            level = detect_level(line)
            service = tokens[2] if len(tokens) > 3 and not tokens[2].startswith("<") else (tokens[1] if len(tokens) > 2 else "")

            layer_root = self._layer(len(tokens))
            node = self._search(layer_root, tokens)
            best: _Cluster | None = None
            best_similarity = 0.0
            for cluster in node.clusters:
                similarity = self._similarity(cluster.template_tokens, tokens)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best = cluster

            if best is not None and best_similarity >= self.similarity_threshold:
                best.merge_tokens(tokens)
                best.observe(tokens, line, position, level)
                if best.known_template_id is not None:
                    known_hits += 1
                position_cluster.append(best)
                continue

            cluster = _Cluster(
                token_count=len(tokens),
                template_tokens=list(tokens),
                sample_count=1,
                sample_line=truncate(line, SAMPLE_LINE_LIMIT),
                first_pos=position,
                last_pos=position,
                service=service,
            )
            cluster.level_counts[level] = 1
            node.clusters.append(cluster)
            clusters.append(cluster)
            seen_ids[id(cluster)] = cluster
            position_cluster.append(cluster)

        # 每个簇的槽位观测补齐（首行里的变量位也要参与类型推断）
        # 说明：首行建簇时把整行当模板，变量位尚未通配，合并时已按差异位逐步通配。
        templates: list[MinedTemplate] = []
        covered = 0
        tentative_lines = 0
        for cluster in clusters:
            if cluster.known_template_id is not None:
                continue
            status = TemplateStatus.MINED.value if cluster.sample_count >= TENTATIVE_MIN_SAMPLES else TemplateStatus.TENTATIVE.value
            if status == TemplateStatus.MINED.value:
                covered += cluster.sample_count
            else:
                tentative_lines += cluster.sample_count
            templates.append(
                MinedTemplate(
                    template_str=cluster.template_str(),
                    token_count=cluster.token_count,
                    slot_types=cluster.slot_types(),
                    slot_names=cluster.slot_names(),
                    sample_count=cluster.sample_count,
                    sample_line=cluster.sample_line,
                    signature=template_signature(cluster.template_str()),
                    status=status,
                    level_hint=cluster.level_hint(),
                    first_pos=cluster.first_pos,
                    service=cluster.service,
                )
            )

        final_signature: dict[int, str] = {}
        for cluster in clusters:
            final_signature[id(cluster)] = template_signature(cluster.template_str())
        line_signatures: list[str | None] = [
            final_signature.get(id(ref)) if ref is not None else None for ref in position_cluster
        ]
        known_covered = known_hits
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return MineResult(
            lines_total=lines_total,
            covered_lines=covered + known_covered,
            noise_lines=noise_lines,
            tentative_lines=tentative_lines,
            known_hits=known_hits,
            templates=sorted(templates, key=lambda item: (-item.sample_count, item.template_str)),
            new_templates=len(templates),
            elapsed_ms=elapsed_ms,
            known_templates_used=len(self._layers),
            line_signatures=line_signatures,
        )


def assign_template(lines: list[str], known: list[dict], threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> dict[str, int]:
    """把一批行按已知模板签名归类，返回 {signature: 命中行数}（用于「应用模板到事件」）。"""
    engine = DrainEngine(threshold)
    engine.load_known(known)
    result = engine.mine(lines)
    counts: dict[str, int] = {}
    for template in result.templates:
        counts[template.signature] = template.sample_count
    return counts

__all__ = [
    "DrainEngine",
    "MineResult",
    "MinedTemplate",
    "NOISE_TEMPLATE",
    "WILDCARD",
    "tokenize",
    "classify_slot",
    "detect_level",
    "is_noise_token_line",
    "split_kv",
    "assign_template",
    "DEFAULT_SIMILARITY_THRESHOLD",
]
