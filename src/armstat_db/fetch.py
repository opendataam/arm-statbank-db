"""Download source metadata from the Statbank PXWeb API into ``data/source/api``.

Two kinds of files are cached (both are committed to the repository so the database
can be rebuilt offline):

* ``api/{lang}/tree.json`` – the navigation tree (folders and tables) in ``lang``.
* ``api/{lang}/tables/{key}.json`` – per-table metadata in ``lang``: the variable/value
  lists (``GET``) and a one-cell JSON-stat 2 response (``POST``) with titles, units,
  notes and sources.

Observation values are *not* fetched here; they come from the statbank-parser exports.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .catalog import load_indicators, table_cache_key
from .config import Paths
from .pxweb import PxWebClient, head_query

log = logging.getLogger(__name__)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def fetch_tree(client: PxWebClient, paths: Paths, lang: str) -> list[dict]:
    nodes = []
    for parent, position, node in client.walk(lang):
        path = f"{parent}/{node['id']}" if parent else node["id"]
        nodes.append({
            "path": path,
            "parent": parent or None,
            "position": position,
            "type": node.get("type"),
            "id": node.get("id"),
            "text": node.get("text"),
            "updated": node.get("updated"),
        })
    _write_json(paths.api_cache(lang) / "tree.json", {
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lang": lang,
        "nodes": nodes,
    })
    log.info("%s tree: %d nodes", lang, len(nodes))
    return nodes


def fetch_table(client: PxWebClient, lang: str, api_path: str) -> dict:
    meta = client.metadata(lang, api_path)
    head = client.jsonstat(lang, api_path, head_query(meta))
    head.pop("value", None)
    head.pop("status", None)
    return {
        "api_path": api_path,
        "lang": lang,
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metadata": meta,
        "head": head,
    }


def fetch_tables(client: PxWebClient, paths: Paths, lang: str, api_paths: list[str],
                 refresh: bool = False, workers: int = 4) -> dict[str, str]:
    """Fetch metadata for ``api_paths``; returns ``{api_path: error}`` for failures."""
    out_dir = paths.api_cache(lang) / "tables"
    todo = [p for p in api_paths
            if refresh or not (out_dir / f"{table_cache_key(p)}.json").exists()]
    log.info("%s: %d tables to fetch (%d cached)", lang, len(todo), len(api_paths) - len(todo))
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_table, client, lang, p): p for p in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            p = futures[fut]
            try:
                _write_json(out_dir / f"{table_cache_key(p)}.json", fut.result())
            except Exception as exc:  # noqa: BLE001 - keep going, report at the end
                errors[p] = str(exc)
                log.error("%s %s: %s", lang, p, exc)
            if i % 50 == 0:
                log.info("%s: %d/%d", lang, i, len(todo))
    if errors:
        _write_json(paths.api_cache(lang) / "errors.json", errors)
    return errors


def fetch_all(paths: Paths, langs=("hy",), tree_langs=("hy", "en"), refresh: bool = False,
              workers: int = 4, max_calls: int = 9, period: float = 10.0
              ) -> dict[str, dict[str, str]]:
    client = PxWebClient(max_calls=max_calls, period=period)
    for lang in tree_langs:
        fetch_tree(client, paths, lang)
    api_paths = sorted({ind.api_path for ind in load_indicators(paths.indicators)})
    return {lang: fetch_tables(client, paths, lang, api_paths, refresh, workers)
            for lang in langs}
