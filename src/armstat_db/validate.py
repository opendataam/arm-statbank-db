"""Consistency checks for a built database. Each check returns ERROR/WARN/OK lines."""

from __future__ import annotations

from pathlib import Path

import duckdb

# (severity, description, SQL returning offending rows; zero rows = pass)
CHECKS = [
    ("ERROR", "observation count equals n_cells",
     """SELECT d.table_id, d.n_cells, count(o.obs_id) AS n
        FROM datasets d LEFT JOIN observations o USING (table_id)
        GROUP BY ALL HAVING count(o.obs_id) <> d.n_cells"""),
    ("ERROR", "n_values equals non-missing observations",
     """SELECT d.table_id FROM datasets d JOIN observations o USING (table_id)
        GROUP BY d.table_id, d.n_values HAVING count(o.value) <> d.n_values"""),
    ("ERROR", "every observation has one code per dimension",
     """SELECT o.table_id, o.obs_id FROM observations o JOIN datasets d USING (table_id)
        WHERE cardinality(o.dims) <> d.n_dimensions LIMIT 20"""),
    ("ERROR", "missing values carry a status symbol and only they do",
     """SELECT table_id, obs_id FROM observations
        WHERE (value IS NULL) <> (status IS NOT NULL) LIMIT 20"""),
    ("ERROR", "dimension sizes match their values",
     """SELECT d.table_id, d.dim_code FROM dimensions d
        LEFT JOIN dimension_values v USING (table_id, dim_code)
        GROUP BY d.table_id, d.dim_code, d.n_values HAVING count(v.value_code) <> d.n_values"""),
    ("ERROR", "topic parents exist",
     """SELECT topic_id FROM topics t WHERE parent_id IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM topics p WHERE p.topic_id = t.parent_id)"""),
    ("ERROR", "every dataset has exactly one primary topic",
     """SELECT table_id FROM datasets d WHERE (SELECT count(*) FROM dataset_topics t
        WHERE t.table_id = d.table_id AND t.is_primary) <> 1"""),
    ("WARN", "no Armenian script in English or Russian labels",
     """SELECT 'dimension_values' AS t, table_id, label_en, label_ru FROM dimension_values
        WHERE regexp_matches(coalesce(label_en,'') || coalesce(label_ru,''), '[Ա-և]')
        UNION ALL
        SELECT 'dimensions', table_id, label_en, label_ru FROM dimensions
        WHERE regexp_matches(coalesce(label_en,'') || coalesce(label_ru,''), '[Ա-և]')
        UNION ALL
        SELECT 'datasets', table_id, title_en, title_ru FROM datasets
        WHERE regexp_matches(coalesce(title_en,'') || coalesce(title_ru,'')
                             || coalesce(unit_en,'') || coalesce(unit_ru,''), '[Ա-և]')
        LIMIT 50"""),
    ("WARN", "no Cyrillic in English labels",
     """SELECT table_id, label_en FROM dimension_values
        WHERE regexp_matches(coalesce(label_en,''), '[Ѐ-ӿ]') LIMIT 20"""),
    ("WARN", "English labels present",
     """SELECT table_id, dim_code, value_code FROM dimension_values
        WHERE label_en IS NULL LIMIT 50"""),
    ("WARN", "Russian labels present",
     """SELECT table_id, dim_code, value_code FROM dimension_values
        WHERE label_ru IS NULL LIMIT 50"""),
    ("WARN", "Armenian labels present",
     """SELECT table_id, dim_code, value_code FROM dimension_values
        WHERE label_hy IS NULL LIMIT 50"""),
    ("WARN", "dataset titles present in all languages",
     """SELECT table_id FROM datasets
        WHERE title_hy IS NULL OR title_en IS NULL OR title_ru IS NULL"""),
]


def validate(database: str | Path) -> list[str]:
    con = duckdb.connect(str(database), read_only=True)
    out = []
    try:
        for severity, name, sql in CHECKS:
            rows = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
            if rows:
                sample = con.execute(f"SELECT * FROM ({sql}) LIMIT 3").fetchall()
                out.append(f"{severity} {name}: {rows} row(s), e.g. {sample}")
            else:
                out.append(f"OK    {name}")
        for row in con.execute("FROM translation_coverage").fetchall():
            entity, n, hy, en, ru, machine = row
            out.append(f"INFO  coverage {entity:<18} n={n:<7} hy={hy:<7} en={en:<7} ru={ru:<7} "
                       f"en_machine={machine}")
    finally:
        con.close()
    return out
