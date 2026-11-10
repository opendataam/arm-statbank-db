"""Read the statbank-parser catalog (``indicators.jsonl``) and locate its exports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .pxweb import web_url_to_api_path


def ckan_dataset_name(px_id: str, url: str) -> str:
    """Dataset name used by statbank-parser for data.opendata.am and for export files.

    Must stay identical to ``statbank_parser.ckan.dataset_name``.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", px_id.lower()).strip("-") or "table"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"armstat-{slug[:81].rstrip('-')}-{digest}"


def table_cache_key(api_path: str) -> str:
    """File-system safe, unique key for an API path (used for cached API files)."""
    px_file = api_path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.px$", "", px_file, flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    digest = hashlib.sha256(api_path.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


@dataclass(frozen=True)
class Indicator:
    px_id: str
    title_en: str
    url_en: str
    topic_en: str
    subtopics_en: tuple[str, ...] = field(default_factory=tuple)

    @property
    def api_path(self) -> str:
        return web_url_to_api_path(self.url_en)

    @property
    def folder_path(self) -> str:
        return self.api_path.rsplit("/", 1)[0]

    @property
    def ckan_name(self) -> str:
        return ckan_dataset_name(self.px_id, self.url_en)

    def export_file(self, exports_dir: Path, ext: str = "json") -> Path:
        return exports_dir / f"{self.ckan_name}.{ext}"


def override_file(overrides_dir: Path, ind: Indicator) -> Path:
    return overrides_dir / f"{ind.ckan_name}.json.gz"


def load_export(paths, ind: Indicator) -> dict:
    """English JSON-stat of a table: API override if present, else the parser export."""
    import gzip

    f = override_file(paths.overrides, ind)
    if f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(ind.export_file(paths.exports).read_text(encoding="utf-8"))


def load_indicators(path: Path) -> list[Indicator]:
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            items.append(Indicator(
                px_id=row["id"],
                title_en=row["title"],
                url_en=row["url"],
                topic_en=row.get("topic") or "",
                subtopics_en=tuple(row.get("subtopics") or ()),
            ))
    return items
