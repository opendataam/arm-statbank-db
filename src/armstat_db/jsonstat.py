"""Parse JSON-stat 2.0 datasets produced by PXWeb.

PXWeb always adds a ``ContentsCode`` metric dimension. In Statbank every table has a
single eliminated contents value, so that dimension carries table-level metadata
(``contents`` and ``unit``) rather than a real breakdown; :func:`parse_dataset` moves it
into :class:`Dataset` fields.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product

METRIC_DIM = "ContentsCode"


@dataclass
class Dimension:
    code: str
    label: str
    position: int
    placement: str | None             # "stub" | "heading" | None
    elimination: bool | None
    values: list[tuple[str, str]]     # [(value_code, label)] in index order


@dataclass
class Dataset:
    label: str
    updated: datetime | None
    language: str | None
    contents: str | None
    description: str | None
    unit: str | None
    decimals: int | None
    official_statistics: bool | None
    matrix: str | None
    subject_code: str | None
    subject_area: str | None
    source: str | None
    notes: list[str]
    stub: list[str]
    heading: list[str]
    dimensions: list[Dimension]       # without the ContentsCode dimension
    size: list[int]                   # sizes of ``dimensions``
    values: list[float | None] = field(repr=False, default_factory=list)
    status: dict[int, str] = field(repr=False, default_factory=dict)

    @property
    def n_cells(self) -> int:
        n = 1
        for s in self.size:
            n *= s
        return n

    def observations(self):
        """Yield ``(obs_id, {dim_code: value_code}, value, status)`` in row-major order."""
        codes = [d.code for d in self.dimensions]
        value_codes = [[c for c, _ in d.values] for d in self.dimensions]
        for obs_id, combo in enumerate(product(*value_codes)):
            yield (obs_id, dict(zip(codes, combo, strict=True)),
                   self.values[obs_id] if obs_id < len(self.values) else None,
                   self.status.get(obs_id))


_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href\s*=\s*['"]([^'"]+)['"]""", re.I)


def strip_html(text: str | None) -> str | None:
    if text is None:
        return None
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", text))).strip() or None


def first_href(text: str | None) -> str | None:
    if not text:
        return None
    m = _HREF.search(text)
    return m.group(1).strip() if m else None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ordered_categories(category: dict) -> list[tuple[str, str]]:
    index = category.get("index", {})
    labels = category.get("label", {})
    if isinstance(index, list):
        order = index
    else:
        order = [code for code, _ in sorted(index.items(), key=lambda kv: kv[1])]
    if not order:
        order = list(labels)
    return [(str(code), labels.get(code, str(code))) for code in order]


def _notes(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [n.strip() for n in raw if n and n.strip()]


def parse_dataset(js: dict, with_values: bool = True) -> Dataset:
    ids: list[str] = js["id"]
    sizes: list[int] = js["size"]
    px = js.get("extension", {}).get("px", {})
    stub, heading = px.get("stub", []) or [], px.get("heading", []) or []

    metric_ids = set(js.get("role", {}).get("metric", [])) | {METRIC_DIM}
    contents = unit = None
    decimals = px.get("decimals")
    dims: list[Dimension] = []
    dim_sizes: list[int] = []
    for did, size in zip(ids, sizes, strict=True):
        dim = js["dimension"][did]
        cats = _ordered_categories(dim.get("category", {}))
        if did in metric_ids:
            if size != 1:
                raise ValueError(f"metric dimension {did!r} has {size} categories; "
                                 "multi-contents tables are not supported")
            code, contents = cats[0]
            u = dim.get("category", {}).get("unit", {}).get(code) or {}
            unit = u.get("base")
            decimals = u.get("decimals", decimals)
            continue
        placement = "stub" if did in stub else "heading" if did in heading else None
        dims.append(Dimension(
            code=did,
            label=dim.get("label") or did,
            position=len(dims),
            placement=placement,
            elimination=dim.get("extension", {}).get("elimination"),
            values=cats,
        ))
        dim_sizes.append(size)

    values: list = []
    status: dict[int, str] = {}
    if with_values:
        raw = js.get("value", [])
        if isinstance(raw, dict):
            n = 1
            for s in sizes:
                n *= s
            values = [None] * n
            for k, v in raw.items():
                values[int(k)] = v
        else:
            values = list(raw)
        raw_status = js.get("status")
        if isinstance(raw_status, dict):
            status = {int(k): v for k, v in raw_status.items() if v is not None}
        elif isinstance(raw_status, list):
            status = {i: v for i, v in enumerate(raw_status) if v is not None}
        elif isinstance(raw_status, str):
            status = {i: raw_status for i in range(len(values))}

    return Dataset(
        label=js.get("label", ""),
        updated=_parse_time(js.get("updated")),
        language=px.get("language"),
        contents=px.get("contents") or contents,
        description=px.get("description"),
        unit=unit,
        decimals=decimals,
        official_statistics=px.get("official-statistics"),
        matrix=px.get("matrix"),
        subject_code=px.get("subject-code"),
        subject_area=px.get("subject-area"),
        source=js.get("source"),
        notes=_notes(js.get("note")),
        stub=[s for s in stub if s not in metric_ids],
        heading=[h for h in heading if h not in metric_ids],
        dimensions=dims,
        size=dim_sizes,
        values=values,
        status=status,
    )


def merge_chunks(chunks: list[dict]) -> dict:
    """Merge JSON-stat 2 responses that split one dimension into several queries.

    All chunks must have the same dimension ids; categories of every dimension are united
    in order of appearance and values/status are re-laid out row-major.
    """
    if len(chunks) == 1:
        return chunks[0]
    ids = chunks[0]["id"]
    order: dict[str, list[str]] = {d: [] for d in ids}
    labels: dict[str, dict[str, str]] = {d: {} for d in ids}
    cells: dict[tuple, tuple] = {}
    for js in chunks:
        codes = []
        for d in ids:
            cat = js["dimension"][d]["category"]
            idx = cat["index"]
            dim_codes = ([c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])]
                         if isinstance(idx, dict) else list(idx))
            for c in dim_codes:
                if c not in labels[d]:
                    order[d].append(c)
                    labels[d][c] = cat.get("label", {}).get(c, c)
            codes.append(dim_codes)
        values = js.get("value") or []
        status = js.get("status") or {}
        for i, combo in enumerate(product(*codes)):
            v = values[i] if isinstance(values, list) and i < len(values) else (
                values.get(str(i)) if isinstance(values, dict) else None)
            st = status.get(str(i)) if isinstance(status, dict) else (
                status[i] if isinstance(status, list) and i < len(status) else None)
            cells[combo] = (v, st)
    merged = dict(chunks[0])
    merged["dimension"] = {}
    for d in ids:
        dim = dict(chunks[0]["dimension"][d])
        cat = dict(dim["category"])
        cat["index"] = {c: i for i, c in enumerate(order[d])}
        cat["label"] = {c: labels[d][c] for c in order[d]}
        dim["category"] = cat
        merged["dimension"][d] = dim
    merged["size"] = [len(order[d]) for d in ids]
    values, status = [], {}
    for i, combo in enumerate(product(*(order[d] for d in ids))):
        v, st = cells.get(combo, (None, None))
        values.append(v)
        if st is not None:
            status[str(i)] = st
    merged["value"] = values
    merged["status"] = status
    return merged
