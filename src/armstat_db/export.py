"""Export one table from the database as a labelled CSV or Parquet file."""

from __future__ import annotations

from pathlib import Path

import duckdb

LABEL = {"hy": "label_hy", "en": "label_en", "ru": "label_ru"}


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def export_table(database: Path, table_id: str, lang: str, output: str, wide: bool = True) -> None:
    con = duckdb.connect(str(database), read_only=True)
    try:
        dims = con.execute(
            f"SELECT dim_code, coalesce({LABEL[lang]}, label_en, dim_code) FROM dimensions "
            "WHERE table_id = ? ORDER BY position", [table_id]).fetchall()
        if not dims:
            raise SystemExit(f"unknown table_id: {table_id}")
        if wide:
            # one column per dimension (value label), plus value and status
            cols, joins = [], []
            seen: set[str] = set()
            for i, (code, label) in enumerate(dims):
                name = label if label not in seen else f"{label} ({code})"
                seen.add(name)
                joins.append(
                    f"JOIN dimension_values v{i} ON v{i}.table_id = o.table_id "
                    f"AND v{i}.dim_code = {duckdb_literal(code)} "
                    f"AND v{i}.value_code = o.dims[{duckdb_literal(code)}]")
                cols.append(f"coalesce(v{i}.{LABEL[lang]}, v{i}.label_en, v{i}.value_code) "
                            f"AS {_quote_ident(name)}")
            sql = (f"SELECT {', '.join(cols)}, o.value, o.status FROM observations o "
                   f"{' '.join(joins)} WHERE o.table_id = {duckdb_literal(table_id)} "
                   "ORDER BY o.obs_id")
        else:
            sql = f"FROM table_long({duckdb_literal(table_id)}, lang := '{lang}')"
        fmt = "FORMAT PARQUET" if output.lower().endswith(".parquet") else "FORMAT CSV, HEADER"
        con.execute(f"COPY ({sql}) TO {duckdb_literal(output)} ({fmt})")
    finally:
        con.close()


def duckdb_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
