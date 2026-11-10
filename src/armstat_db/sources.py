"""Assemble the bilingual source model from the parser exports and cached API metadata.

Inputs
------
* ``statbank-parser/indicators.jsonl`` – catalogue of tables (English web interface).
* ``statbank-parser/exports/*.json`` – complete English JSON-stat 2 exports (the values).
* ``data/source/api/{hy,en}/tree.json`` – navigation tree from the API.
* ``data/source/api/hy/tables/*.json`` – Armenian table metadata from the API.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from .catalog import Indicator, load_export, load_indicators, override_file, table_cache_key
from .config import Paths
from .jsonstat import Dataset, parse_dataset

log = logging.getLogger(__name__)

_TOPIC_CODE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.*)$", re.S)


def split_topic_name(text: str | None) -> tuple[str | None, str | None]:
    """``'1.2 Consumer Prices'`` -> ``('1.2', 'Consumer Prices')``."""
    if not text:
        return None, None
    m = _TOPIC_CODE.match(text)
    if m:
        return m.group(1), m.group(2).strip()
    return None, text.strip()


@dataclass
class TreeNode:
    path: str
    parent: str | None
    position: int
    type: str
    text: str | None
    updated: str | None


def load_tree(paths: Paths, lang: str) -> dict[str, TreeNode]:
    f = paths.api_cache(lang) / "tree.json"
    if not f.exists():
        log.warning("no %s tree at %s (run `armstat-db fetch`)", lang, f)
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    return {n["path"]: TreeNode(n["path"], n["parent"], n["position"], n["type"], n["text"],
                                n.get("updated"))
            for n in data["nodes"]}


@dataclass
class HyTable:
    """Armenian metadata of one table from the API."""
    title: str | None                       # tree text
    variables: dict[str, dict]              # code -> {text, values: {code: text}}
    head: Dataset | None                    # one-cell JSON-stat (table-level metadata)


def load_hy_table(paths: Paths, api_path: str, tree_hy: dict[str, TreeNode]) -> HyTable | None:
    f = paths.api_cache("hy") / "tables" / f"{table_cache_key(api_path)}.json"
    if not f.exists():
        return None
    raw = json.loads(f.read_text(encoding="utf-8"))
    variables = {}
    for v in raw["metadata"].get("variables", []):
        variables[v["code"]] = {
            "text": v.get("text"),
            "values": dict(zip(v.get("values", []), v.get("valueTexts", []), strict=False)),
        }
    head = None
    if raw.get("head"):
        try:
            head = parse_dataset(raw["head"], with_values=False)
        except (KeyError, ValueError) as exc:
            log.warning("bad hy head for %s: %s", api_path, exc)
    node = tree_hy.get(api_path)
    return HyTable(title=node.text if node else raw["metadata"].get("title"),
                   variables=variables, head=head)


@dataclass
class TableSource:
    table_id: str
    indicators: list[Indicator]             # >1 when the table is in several folders
    en: Dataset
    en_title: str | None
    hy: HyTable | None

    @property
    def primary(self) -> Indicator:
        return self.indicators[0]


@dataclass
class SourceModel:
    tree_en: dict[str, TreeNode]
    tree_hy: dict[str, TreeNode]
    tables: list[TableSource] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def load_sources(paths: Paths, with_values: bool = True) -> SourceModel:
    tree_en, tree_hy = load_tree(paths, "en"), load_tree(paths, "hy")
    model = SourceModel(tree_en=tree_en, tree_hy=tree_hy)

    by_id: dict[str, list[Indicator]] = {}
    for ind in load_indicators(paths.indicators):
        by_id.setdefault(ind.px_id, []).append(ind)

    for table_id, inds in by_id.items():
        export = inds[0].export_file(paths.exports)
        override = override_file(paths.overrides, inds[0])
        if not export.exists() and not override.exists():
            model.problems.append(f"ERROR {table_id}: export missing {export.name}")
            continue
        if override.exists():
            model.problems.append(f"INFO {table_id}: parser export replaced by {override.name}")
        en = parse_dataset(load_export(paths, inds[0]), with_values)
        if len(inds) > 1:  # same id in several folders: keep one copy if the data match
            for other in inds[1:]:
                if other.export_file(paths.exports).exists():
                    o = parse_dataset(load_export(paths, other), with_values)
                    if (o.values, o.status) != (en.values, en.status):
                        model.problems.append(
                            f"WARN {table_id}: copies in different folders differ; "
                            f"using {inds[0].api_path}")
        node_en = tree_en.get(inds[0].api_path)
        en_title = node_en.text if node_en else inds[0].title_en
        hy = None
        for ind in inds:
            hy = load_hy_table(paths, ind.api_path, tree_hy)
            if hy:
                break
        if hy is None:
            model.problems.append(f"WARN {table_id}: no Armenian metadata")
        model.tables.append(TableSource(table_id, inds, en, en_title, hy))
    return model
