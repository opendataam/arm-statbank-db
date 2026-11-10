"""Prepare release assets in ``build/release``.

* ``armstat.duckdb`` – the database (can be attached over HTTPS, see the README);
* ``armstat-parquet.zip`` – the same data as Parquet files with ``schema.sql`` and
  ``load.sql`` (``IMPORT DATABASE 'armstat-parquet'`` recreates the database);
* ``SHA256SUMS``.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from importlib import resources
from pathlib import Path

import duckdb

from .config import Paths


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _fix_schema(schema: Path) -> None:
    """Keep exported tables, replace views/macros by views.sql (dependency order).

    ``EXPORT DATABASE`` writes views alphabetically, so a view can precede the view it
    depends on (``catalog`` before ``topic_paths``) and ``IMPORT DATABASE`` fails.
    """
    lines = schema.read_text(encoding="utf-8").splitlines()
    tables = [ln for ln in lines if not re.match(r"CREATE (VIEW|MACRO)\b", ln)]
    views = resources.files("armstat_db").joinpath("sql", "views.sql").read_text("utf-8")
    schema.write_text("\n".join(tables) + "\n\n" + views, encoding="utf-8")


def make_release(paths: Paths) -> list[Path]:
    db = paths.database
    if not db.exists():
        raise SystemExit(f"{db} not found: run `armstat-db build` first")
    out = paths.build_dir / "release"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    target_db = out / "armstat.duckdb"
    shutil.copy2(db, target_db)

    export_dir = out / "armstat-parquet"
    con = duckdb.connect(str(db), read_only=True)
    try:
        con.execute(f"EXPORT DATABASE '{export_dir}' (FORMAT parquet, COMPRESSION zstd)")
    finally:
        con.close()
    _fix_schema(export_dir / "schema.sql")

    check = duckdb.connect()
    try:
        check.execute(f"IMPORT DATABASE '{export_dir}'")
        n = check.execute("SELECT count(*) FROM observations").fetchone()[0]
        check.execute("SELECT count(*) FROM catalog").fetchone()
    finally:
        check.close()
    if not n:
        raise SystemExit("Parquet export check failed")

    archive = out / "armstat-parquet.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:  # parquet is compressed
        for f in sorted(export_dir.iterdir()):
            zf.write(f, f"armstat-parquet/{f.name}")
    shutil.rmtree(export_dir)

    assets = [target_db, archive]
    (out / "SHA256SUMS").write_text(
        "".join(f"{_sha256(a)}  {a.name}\n" for a in assets), encoding="utf-8")
    return [*assets, out / "SHA256SUMS"]
