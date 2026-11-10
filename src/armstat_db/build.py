"""Build the trilingual DuckDB database.

The same assembly pass (:func:`assemble`) is used by ``build`` and by ``collect``, so the
list of texts awaiting translation always matches what the build would leave empty.
"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from urllib.parse import quote

import duckdb

from . import __version__
from .align import load_alignment
from .config import Paths
from .jsonstat import first_href, strip_html
from .pxweb import api_path_to_web_url
from .sources import SourceModel, TableSource, load_sources, split_topic_name
from .textutil import is_time_dimension, parse_period, period_year
from .translation.memory import TranslationMemory
from .translation.resolve import Resolver

log = logging.getLogger(__name__)

CKAN_DATASET_URL = "https://data.opendata.am/dataset/"

STATUS_SYMBOLS = [
    # symbol, hy, en, ru  (conventional PX-Web meanings; Armstat publishes no legend in the API)
    (".", "Կատեգորիան կիրառելի չէ",
     "Category not applicable", "Категория неприменима"),
    ("..", "Տվյալներ չկան կամ հասանելի չեն",
     "Data not available", "Данные отсутствуют или недоступны"),
    ("...", "Տվյալները դեռ հասանելի չեն կամ ենթակա չեն հրապարակման",
     "Data not yet available or not for publication",
     "Данные ещё не доступны или не подлежат публикации"),
    ("-", "Երևույթը բացակայում է (զրո)",
     "Magnitude nil (no occurrence)", "Явление отсутствует (ноль)"),
    ("x", "Գաղտնի տվյալներ",
     "Confidential data", "Конфиденциальные данные"),
]

LANGUAGES = [
    ("hy", "հայերեն", "Armenian", "армянский", "armstat"),
    ("en", "անգլերեն", "English", "английский", "mixed"),
    ("ru", "ռուսերեն", "Russian", "русский", "machine"),
]


def _url(api_path: str, lang: str) -> str:
    return quote(api_path_to_web_url(api_path, lang), safe=":/,()'")


def _join_notes(notes: list[str] | None) -> str | None:
    return "\n".join(notes) if notes else None


@dataclass
class Assembled:
    topics: list[dict] = field(default_factory=list)
    datasets: list[dict] = field(default_factory=list)
    dataset_topics: list[dict] = field(default_factory=list)
    dimensions: list[dict] = field(default_factory=list)
    dimension_values: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _assemble_topics(model: SourceModel, resolver: Resolver, out: Assembled) -> None:
    folders: dict[str, None] = {}
    for t in model.tables:
        for ind in t.indicators:
            parts = ind.folder_path.split("/")
            for i in range(1, len(parts) + 1):
                folders["/".join(parts[:i])] = None
    for tree in (model.tree_en, model.tree_hy):
        for node in tree.values():
            if node.type == "l":
                folders[node.path] = None

    for path in sorted(folders):
        en_node, hy_node = model.tree_en.get(path), model.tree_hy.get(path)
        code_en, name_en = split_topic_name(en_node.text if en_node else None)
        code_hy, name_hy = split_topic_name(hy_node.text if hy_node else None)
        if name_en is None:  # fall back to the folder id ("12 Consumer Prices")
            code_en, name_en = split_topic_name(path.rsplit("/", 1)[-1])
        r = resolver.resolve(name_hy, name_en, context="Statbank topic")
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        node = en_node or hy_node
        out.topics.append({
            "topic_id": path,
            "parent_id": parent,
            "level": path.count("/") + 1,
            "position": node.position if node else 0,
            "code": code_en or code_hy,
            "name_hy": r.hy, "name_en": r.en, "name_ru": r.ru,
            "en_machine": r.en_machine,
        })


def _assemble_table(t: TableSource, resolver: Resolver, out: Assembled,
                    alignment: dict | None = None) -> None:
    en, hy = t.en, t.hy
    align = (alignment or {}).get(t.table_id, {})
    remaps = align.get("remap", {})
    dim_map = align.get("dim_map", {})
    hy_head = hy.head if hy else None
    ctx = t.en_title or en.description or en.label

    def res(hy_text, en_text):
        return resolver.resolve(hy_text, en_text, context=ctx)

    title = res(hy.title if hy else None,
                t.en_title or en.description or en.label)
    contents = res(hy_head.contents if hy_head else None, en.contents)
    unit = res(hy_head.unit if hy_head else None, en.unit)
    area = res(hy_head.subject_area if hy_head else None, en.subject_area)
    source = res(strip_html(hy_head.source) if hy_head else None, strip_html(en.source))
    note = res(_join_notes(hy_head.notes) if hy_head else None, _join_notes(en.notes))

    machine_flags = [title.en_machine, contents.en_machine, unit.en_machine]

    for dim in en.dimensions:
        hv = (hy.variables.get(dim_map.get(dim.code, dim.code)) if hy else None) or {}
        labels_en = [lab for _, lab in dim.values]
        is_time = is_time_dimension(dim.code, labels_en)
        dl = res(hv.get("text"), dim.label)
        machine_flags.append(dl.en_machine)
        out.dimensions.append({
            "table_id": t.table_id, "dim_code": dim.code, "position": dim.position,
            "placement": dim.placement, "is_time": is_time, "elimination": dim.elimination,
            "label_hy": dl.hy, "label_en": dl.en, "label_ru": dl.ru,
            "en_machine": dl.en_machine, "n_values": len(dim.values),
        })
        hy_values = hv.get("values", {})
        remap = remaps.get(dim.code, {})   # en code -> hy code (see align.py)
        for pos, (code, label_en) in enumerate(dim.values):
            hy_code = remap.get(code, code)    # None: no confirmed Armenian category
            vl = res(hy_values.get(hy_code) if hy_code is not None else None, label_en)
            machine_flags.append(vl.en_machine)
            period = parse_period(label_en) if is_time else None
            out.dimension_values.append({
                "table_id": t.table_id, "dim_code": dim.code, "value_code": code,
                "position": pos, "label_hy": vl.hy, "label_en": vl.en, "label_ru": vl.ru,
                "en_machine": vl.en_machine, "period": period, "year": period_year(period),
            })
        if hy and hy_values:
            missing = [c for c, _ in dim.values if c not in hy_values]
            if missing:
                out.problems.append(f"INFO {t.table_id}.{dim.code}: {len(missing)} value codes "
                                    f"without Armenian label (table changed since export?)")

    if not any(machine_flags):
        en_origin = "armstat"
    elif title.en_machine:
        en_origin = "machine"
    else:
        en_origin = "partial"

    prim = t.primary
    out.datasets.append({
        "table_id": t.table_id, "matrix": en.matrix, "subject_code": en.subject_code,
        "title_hy": title.hy, "title_en": title.en, "title_ru": title.ru,
        "contents_hy": contents.hy, "contents_en": contents.en, "contents_ru": contents.ru,
        "unit_hy": unit.hy, "unit_en": unit.en, "unit_ru": unit.ru,
        "decimals": en.decimals,
        "subject_area_hy": area.hy, "subject_area_en": area.en, "subject_area_ru": area.ru,
        "source_hy": source.hy, "source_en": source.en, "source_ru": source.ru,
        "source_link": first_href(en.source) or (first_href(hy_head.source) if hy_head else None),
        "note_hy": note.hy, "note_en": note.en, "note_ru": note.ru,
        "updated": en.updated.isoformat() if en.updated else None,
        "official_statistics": en.official_statistics,
        "n_dimensions": len(en.dimensions), "n_cells": en.n_cells,
        "n_values": sum(v is not None for v in en.values),
        "first_period": None, "last_period": None,
        "stub": en.stub, "heading": en.heading,
        "en_origin": en_origin, "hy_available": hy is not None,
        "api_path": prim.api_path,
        "url_hy": _url(prim.api_path, "hy"), "url_en": _url(prim.api_path, "en"),
        "ckan_name": prim.ckan_name, "ckan_url": CKAN_DATASET_URL + prim.ckan_name,
    })
    for i, ind in enumerate(t.indicators):
        out.dataset_topics.append({"table_id": t.table_id, "topic_id": ind.folder_path,
                                   "api_path": ind.api_path, "is_primary": i == 0})


def _period_key(period: str) -> tuple:
    # '2015' < '2015-Q1' < '2015-03' is not meaningful; compare by (year, rest)
    return (period[:4], period[4:])


def assemble(model: SourceModel, resolver: Resolver,
             alignment: dict | None = None) -> Assembled:
    out = Assembled(problems=list(model.problems))
    _assemble_topics(model, resolver, out)
    for t in model.tables:
        _assemble_table(t, resolver, out, alignment)

    # derived columns: period range of each table, number of tables per topic
    time_dims = {(d["table_id"], d["dim_code"]) for d in out.dimensions if d["is_time"]}
    periods: dict[str, list[str]] = {}
    for v in out.dimension_values:
        p = v["period"]
        if p and not p.startswith("--") and (v["table_id"], v["dim_code"]) in time_dims:
            periods.setdefault(v["table_id"], []).append(p)
    for d in out.datasets:
        ps = periods.get(d["table_id"])
        if ps:
            d["first_period"] = min(ps, key=_period_key)
            d["last_period"] = max(ps, key=_period_key)
    counts: dict[str, int] = {}
    for dt in out.dataset_topics:
        counts[dt["topic_id"]] = counts.get(dt["topic_id"], 0) + 1
    for tp in out.topics:
        tp["n_tables"] = counts.get(tp["topic_id"], 0)
    return out


# --------------------------------------------------------------------------- loading


def _bulk_insert(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict],
                 tmpdir: Path) -> None:
    if not rows:
        return
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    types = {r[0]: r[1] for r in con.execute(f"DESCRIBE {table}").fetchall()}
    use = [c for c in cols if c in rows[0]]
    path = tmpdir / f"{table}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({c: r[c] for c in use}, ensure_ascii=False, default=str) + "\n")
    spec = ", ".join(f"'{c}': '{types[c]}'" for c in use)
    col_list = ", ".join(f'"{c}"' for c in use)
    con.execute(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM "
                f"read_json('{path}', format='newline_delimited', columns={{{spec}}})")


def _load_observations(con, model: SourceModel, tmpdir: Path) -> None:
    path = tmpdir / "observations.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["table_id", "obs_id", "value", "status"])
        for t in model.tables:
            values, status = t.en.values, t.en.status
            for obs_id in range(t.en.n_cells):
                v = values[obs_id] if obs_id < len(values) else None
                w.writerow([t.table_id, obs_id, "" if v is None else repr(float(v)),
                            status.get(obs_id, "")])
    con.execute(f"""
        CREATE TEMP TABLE obs_raw AS
        SELECT * FROM read_csv('{path}', header=true, nullstr='',
            columns={{'table_id': 'VARCHAR', 'obs_id': 'INTEGER', 'value': 'DOUBLE',
                      'status': 'VARCHAR'}})
    """)
    # stride of each dimension in the row-major JSON-stat layout
    con.execute("""
        CREATE TEMP TABLE dim_strides AS
        SELECT table_id, dim_code, position, n_values, is_time,
               COALESCE(PRODUCT(n_values) OVER (
                   PARTITION BY table_id ORDER BY position DESC
                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 1)::BIGINT AS stride
        FROM dimensions
    """)
    # period: a year/quarter/month value of the time dimension(s); a separate month
    # dimension ('--03') is combined with the year ('2015') into '2015-03'.
    con.execute("""
        INSERT INTO observations (table_id, obs_id, dims, period, value, status)
        WITH cells AS (
            SELECT o.table_id, o.obs_id,
                   map_from_entries(list((s.dim_code, v.value_code) ORDER BY s.position)) AS dims,
                   max(v.period) FILTER (WHERE s.is_time AND v.period NOT LIKE '--%') AS p_year,
                   max(v.period) FILTER (WHERE s.is_time AND v.period LIKE '--%') AS p_month,
                   any_value(o.value) AS value, any_value(o.status) AS status
            FROM obs_raw o
            JOIN dim_strides s ON s.table_id = o.table_id
            JOIN dimension_values v
              ON v.table_id = o.table_id AND v.dim_code = s.dim_code
             AND v.position = (o.obs_id // s.stride) % s.n_values
            GROUP BY o.table_id, o.obs_id
        )
        SELECT table_id, obs_id, dims,
               CASE WHEN p_month IS NOT NULL AND length(p_year) = 4
                    THEN p_year || substr(p_month, 2)
                    ELSE coalesce(p_year, p_month) END,
               value, status
        FROM cells
        ORDER BY table_id, obs_id
    """)


def _git_revision(directory: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(directory), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sql(name: str) -> str:
    return resources.files("armstat_db").joinpath("sql", name).read_text(encoding="utf-8")


def build_database(paths: Paths, output: str | None = None) -> dict:
    model = load_sources(paths, with_values=True)
    tm = TranslationMemory(paths.translations_dir)
    resolver = Resolver(tm)
    data = assemble(model, resolver, load_alignment(paths))

    target = Path(output) if output else paths.database
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = target.with_suffix(".building.duckdb")
    tmp_db.unlink(missing_ok=True)

    con = duckdb.connect(str(tmp_db))
    try:
        con.execute(_sql("schema.sql"))
        con.executemany("INSERT INTO languages VALUES (?, ?, ?, ?, ?)", LANGUAGES)
        con.executemany("INSERT INTO status_symbols VALUES (?, ?, ?, ?)", STATUS_SYMBOLS)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _bulk_insert(con, "topics", data.topics, td)
            _bulk_insert(con, "datasets", data.datasets, td)
            _bulk_insert(con, "dataset_topics", data.dataset_topics, td)
            _bulk_insert(con, "dimensions", data.dimensions, td)
            _bulk_insert(con, "dimension_values", data.dimension_values, td)
            log.info("loading observations")
            _load_observations(con, model, td)
            tm_rows = [dict(zip(("src_lang", "tgt_lang", "source", "target", "engine",
                                 "reviewed"), r, strict=True)) for r in tm.rows()]
            _bulk_insert(con, "translations", tm_rows, td)
        con.execute(_sql("views.sql"))

        report = {
            "database": str(target),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "version": __version__,
            "parser_revision": _git_revision(paths.parser_dir),
            "topics": len(data.topics),
            "datasets": len(data.datasets),
            "dimensions": len(data.dimensions),
            "dimension_values": len(data.dimension_values),
            "observations": con.execute("SELECT count(*) FROM observations").fetchone()[0],
            "translations": len(tm_rows),
            "missing_translations": {k: len(v) for k, v in resolver.missing.items()},
            "problems": len(data.problems),
        }
        con.executemany("INSERT INTO build_info VALUES (?, ?)",
                        [(k, json.dumps(v) if isinstance(v, dict) else str(v))
                         for k, v in report.items()])
        con.execute("CHECKPOINT")
    finally:
        con.close()
    tmp_db.replace(target)
    (target.parent / "build-problems.txt").write_text("\n".join(data.problems) + "\n",
                                                      encoding="utf-8")
    return report


def collect_missing(paths: Paths) -> tuple[Resolver, Assembled]:
    model = load_sources(paths, with_values=False)
    resolver = Resolver(TranslationMemory(paths.translations_dir))
    return resolver, assemble(model, resolver, load_alignment(paths))
