"""Check and repair the correspondence of Armenian and English categories.

Statbank publishes separate PX files per language. Value codes are positional ("0", "1",
…), and in some tables the Armenian file lists categories in a different order than the
English one (e.g. "Dilijan, Berd, Ayrum" vs "Berd, Dilijan, Ayrum"). Joining labels by code
would then attach Armenian labels to the wrong data.

This module downloads the Armenian *values* of every table (cached in
``build/cache/values/hy``, not committed), compares them with the English export and, per
dimension, matches categories whose data slices contain the same multiset of values. The
result is written to ``data/source/api/hy/alignment.json`` (committed) and used by the
build: ``label_hy`` of English value code ``c`` is taken from Armenian code ``remap[c]``.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

from .catalog import load_export, load_indicators, override_file, table_cache_key
from .config import Paths
from .jsonstat import METRIC_DIM, merge_chunks, parse_dataset
from .pxweb import PxWebClient
from .textutil import is_time_dimension

log = logging.getLogger(__name__)

MAX_CELLS = 100_000          # PXWeb API limit (GET /api/v1/en/?config)


def values_cache(paths: Paths, lang: str = "hy") -> Path:
    return paths.build_dir / "cache" / "values" / lang


def alignment_file(paths: Paths) -> Path:
    return paths.api_cache("hy") / "alignment.json"


# --------------------------------------------------------------------------- download


def _chunk_queries(variables: list[dict]) -> list[list[dict]]:
    sizes = [len(v["values"]) for v in variables]
    total = 1
    for s in sizes:
        total *= s
    if total <= MAX_CELLS:
        return [[{"code": v["code"], "selection": {"filter": "all", "values": ["*"]}}
                 for v in variables]]
    big = max(range(len(variables)), key=lambda i: sizes[i])
    per = max(1, MAX_CELLS // (total // sizes[big]))
    values = variables[big]["values"]
    queries = []
    for start in range(0, len(values), per):
        q = []
        for i, v in enumerate(variables):
            if i == big:
                q.append({"code": v["code"],
                          "selection": {"filter": "item", "values": values[start:start + per]}})
            else:
                q.append({"code": v["code"], "selection": {"filter": "all", "values": ["*"]}})
        queries.append(q)
    return queries


def fetch_values(paths: Paths, refresh: bool = False, max_calls: int = 9,
                 period: float = 10.0) -> dict[str, str]:
    client = PxWebClient(max_calls=max_calls, period=period)
    out_dir = values_cache(paths)
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = {}
    api_paths = sorted({i.api_path for i in load_indicators(paths.indicators)})
    for n, api_path in enumerate(api_paths, 1):
        key = table_cache_key(api_path)
        target = out_dir / f"{key}.json"
        meta_file = paths.api_cache("hy") / "tables" / f"{key}.json"
        if (target.exists() and not refresh) or not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))["metadata"]
        try:
            chunks = []
            for q in _chunk_queries(meta["variables"]):
                js = client.jsonstat("hy", api_path, q)
                chunks.append({k: js.get(k) for k in ("id", "size", "dimension", "value",
                                                      "status")})
            target.write_text(json.dumps({"api_path": api_path, "chunks": chunks},
                                         ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            errors[api_path] = str(exc)
            log.error("%s: %s", api_path, exc)
        if n % 50 == 0:
            log.info("values: %d/%d", n, len(api_paths))
    return errors


def refetch_tables(paths: Paths, table_ids: list[str], max_calls: int = 9,
                   period: float = 10.0) -> list[str]:
    """Download complete English tables from the API and store them as export overrides.

    Use for tables whose statbank-parser export is faulty (see ``align``: very low
    agreement with the Armenian data). Files: ``data/source/api/en/overrides/*.json.gz``.
    """
    import gzip

    client = PxWebClient(max_calls=max_calls, period=period)
    written = []
    wanted = set(table_ids)
    done = set()
    for ind in load_indicators(paths.indicators):
        if ind.px_id not in wanted or ind.px_id in done:
            continue
        meta = client.metadata("en", ind.api_path)
        chunks = [client.jsonstat("en", ind.api_path, q)
                  for q in _chunk_queries(meta["variables"])]
        merged = merge_chunks(chunks)
        merged.setdefault("extension", {}).setdefault("px", {})
        merged["extension"]["armstat_db"] = {
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "api_path": ind.api_path, "reason": "statbank-parser export replaced"}
        target = override_file(paths.overrides, ind)
        target.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(target, "wt", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False)
        written.append(str(target))
        done.add(ind.px_id)
    return written


# --------------------------------------------------------------------------- alignment


def _cells(js: dict):
    """Yield ``({dim_code: value_code}, value)`` for every cell of a JSON-stat response."""
    ids = [d for d in js["id"] if d != METRIC_DIM]
    order = []
    for d in js["id"]:
        idx = js["dimension"][d]["category"]["index"]
        codes = [c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])] \
            if isinstance(idx, dict) else list(idx)
        order.append(codes)
    values = js.get("value") or []
    if isinstance(values, dict):
        values = [values.get(str(i)) for i in range(len(list(product(*order))))]
    for i, combo in enumerate(product(*order)):
        coords = dict(zip(js["id"], combo, strict=True))
        yield {d: coords[d] for d in ids}, values[i] if i < len(values) else None


def _norm(v):
    return None if v is None else round(float(v), 6)


def _hy_dim_map(en_dims: list[str], hy_ids: list[str]) -> dict[str, str]:
    """en dim code -> hy dim code; by code, else by position when the counts match."""
    hy_dims = [d for d in hy_ids if d != METRIC_DIM]
    if all(d in hy_dims for d in en_dims):
        return {d: d for d in en_dims}
    if len(hy_dims) == len(en_dims):
        return {d: d if d in hy_dims else hy_dims[i] for i, d in enumerate(en_dims)}
    return {d: d for d in en_dims if d in hy_dims}


def align_table(en_js: dict, hy_chunks: list[dict]) -> dict:
    """Compare Armenian and English data of one table.

    Returns ``{"agreement_before", "agreement_after", "remap", "dim_map"}`` where
    ``remap[dim][en_code]`` is the Armenian code carrying the same data, or ``None`` when
    no Armenian category can be confirmed (the Armenian label is then left empty).
    """
    en = parse_dataset(en_js)
    dims = [d.code for d in en.dimensions]
    dim_map = _hy_dim_map(dims, hy_chunks[0]["id"]) if hy_chunks else {}
    hy_cells: dict[tuple, float | None] = {}
    hy_labels: dict[str, dict[str, str]] = defaultdict(dict)
    for js in hy_chunks:
        for d in dims:
            cat = js["dimension"].get(dim_map.get(d, d), {}).get("category", {})
            hy_labels[d].update(cat.get("label", {}))
        for coords, v in _cells(js):
            if all(dim_map.get(d) in coords for d in dims):
                hy_cells[tuple(coords[dim_map[d]] for d in dims)] = _norm(v)
    en_cells = {tuple(c[d] for d in dims): _norm(v) for _, c, v, _ in en.observations()}

    def agreement(maps) -> float:
        hit = tot = 0
        for key, v in en_cells.items():
            if v is None:
                continue
            tot += 1
            hk = tuple(maps[i].get(k) for i, k in enumerate(key))
            hit += hy_cells.get(hk) == v
        return hit / tot if tot else 1.0

    is_time = [is_time_dimension(d.code, [lab for _, lab in d.values]) for d in en.dimensions]
    mapping: list[dict] = [{c: c for c, _ in d.values} for d in en.dimensions]
    before = agreement(mapping)
    best = before

    # time dimensions: match by label, but only if it explains the data better
    # (in some tables Armstat's year labels differ between the language versions)
    for i, d in enumerate(en.dimensions):
        if not is_time[i] or best >= 0.995:
            continue
        by_label = {lab.strip(): c for c, lab in hy_labels[d.code].items()}
        trial = list(mapping)
        trial[i] = {c: by_label.get(lab.strip(), c) for c, lab in d.values}
        score = agreement(trial)
        if score > best:
            mapping, best = trial, score

    # other dimensions: match categories whose slices hold the same multiset of values
    for i, d in enumerate(en.dimensions):
        size_differs = len(hy_labels[d.code]) != len(d.values)
        if is_time[i] or (best >= 0.995 and not size_differs):
            continue
        sig_en: dict[str, Counter] = defaultdict(Counter)
        for key, v in en_cells.items():
            if v is not None:
                sig_en[key[i]][v] += 1
        wanted = [set(m.values()) if is_time[j] else None for j, m in enumerate(mapping)]
        sig_hy: dict[str, Counter] = defaultdict(Counter)
        for key, v in hy_cells.items():
            if v is not None and all(w is None or key[j] in w for j, w in enumerate(wanted)):
                sig_hy[key[i]][v] += 1
        # candidates: Armenian categories whose values contain all values of the English
        # slice (the Armenian table may be newer and hold extra periods)
        inverted: dict[float, set[str]] = defaultdict(set)
        for h, sig in sig_hy.items():
            for v in sig:
                inverted[v].add(h)
        confirmed: dict[str, str] = {}
        for c, _ in d.values:
            vals = sig_en[c]
            if not vals:
                continue
            rare = min(vals, key=lambda v: len(inverted.get(v, ())))
            cands = [h for h in inverted.get(rare, ())
                     if all(sig_hy[h][v] >= n for v, n in vals.items())]
            if len(cands) == 1:
                confirmed[c] = cands[0]
            elif c in cands:
                confirmed[c] = c
        taken = set(confirmed.values())
        new: dict[str, str | None] = {}
        for c, _ in d.values:
            if c in confirmed:
                new[c] = confirmed[c]
            elif size_differs:
                new[c] = None              # cannot be confirmed: leave the label empty
            else:
                new[c] = c if c not in taken else None
        trial = list(mapping)
        trial[i] = new
        score = agreement(trial)
        if score >= best or size_differs:
            mapping, best = trial, max(best, score)

    remap = {}
    for d, m in zip(en.dimensions, mapping, strict=True):
        changed = {c: h for c, h in m.items() if c != h}
        if changed:
            remap[d.code] = changed
    return {"agreement_before": round(before, 4), "agreement_after": round(best, 4),
            "remap": remap, "dim_map": {k: v for k, v in dim_map.items() if k != v}}


def align_all(paths: Paths) -> dict:
    cache = values_cache(paths)
    tables: dict[str, dict] = {}
    checked = 0
    by_id: dict[str, object] = {}
    for ind in load_indicators(paths.indicators):
        by_id.setdefault(ind.px_id, ind)
    for table_id, ind in sorted(by_id.items()):
        f = cache / f"{table_cache_key(ind.api_path)}.json"
        if not f.exists():
            continue
        en_js = load_export(paths, ind)
        hy = json.loads(f.read_text(encoding="utf-8"))
        res = align_table(en_js, hy["chunks"])
        checked += 1
        if res["remap"] or res["dim_map"] or res["agreement_after"] < 0.995:
            tables[table_id] = res
    out = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "description": "Armenian value codes for English value codes where the Armenian PX "
                       "file orders categories differently; agreement = share of English "
                       "non-missing cells equal in the Armenian data after mapping.",
        "checked": checked,
        "tables": tables,
    }
    target = alignment_file(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"checked": checked,
            "remapped": sum(bool(t["remap"] or t["dim_map"]) for t in tables.values()),
            "low_agreement": sum(t["agreement_after"] < 0.995 for t in tables.values()),
            "file": str(target)}


def load_alignment(paths: Paths) -> dict[str, dict]:
    f = alignment_file(paths)
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding="utf-8")).get("tables", {})
