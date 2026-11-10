# Database reference

The database is a single DuckDB file, `build/armstat.duckdb`, built by `armstat-db build`.
It has no external dependencies: open it with the DuckDB CLI, Python, R, DBeaver or any
DuckDB client.

```bash
duckdb build/armstat.duckdb
```

## Model

```
topics ──< dataset_topics >── datasets ──< dimensions ──< dimension_values
                                  │                              │
                                  └──────< observations >────────┘  (dims MAP: dim_code → value_code)
status_symbols ──< observations.status
translations   (translation memory, provenance of machine translations)
languages, build_info
```

* A **dataset** is one Statbank table (one PX file), e.g. `EF-cpi-mi1`.
* A dataset has 2–4 **dimensions** (PX variables: marz, year, indicator, …).
  The technical PXWeb dimension `ContentsCode` is not stored as a dimension: in Statbank it
  always has one value, so its text and unit are stored in `datasets.contents_*` and
  `datasets.unit_*`.
* Each dimension has **dimension values** (categories) with codes and labels.
* An **observation** is one cell of the table: a combination of one value of each dimension
  and the number (or a missing-value symbol).

### Language columns

Every human-readable text has three columns: `*_hy` (Armenian), `*_en` (English),
`*_ru` (Russian).

| Language | Origin |
|---|---|
| `hy` | Official Armstat text from the Armenian interface. NULL if Armstat has no Armenian version (1 table). |
| `en` | Official Armstat text from the English interface. Where Armstat left a text untranslated (Armenian script in the English interface), it is machine-translated from Armenian and flagged with `en_machine = TRUE`. |
| `ru` | Always machine-translated: from the official English text, or from Armenian when no official English exists or when a translation from Armenian was added as a correction. |

All machine translations are listed in `translations` with the engine that produced them.

## Tables

### `datasets`

| Column | Type | Description |
|---|---|---|
| `table_id` | VARCHAR, PK | PX table id as used by Statbank, e.g. `EF-cpi-mi1` |
| `matrix`, `subject_code` | VARCHAR | PX `MATRIX` and `SUBJECT-CODE` keywords |
| `title_hy/en/ru` | VARCHAR | Full title as shown in the Statbank tree |
| `contents_hy/en/ru` | VARCHAR | Short subject of the table (PX `CONTENTS`) |
| `unit_hy/en/ru` | VARCHAR | Unit of measure of all values |
| `decimals` | TINYINT | Number of decimals shown by Armstat |
| `subject_area_hy/en/ru` | VARCHAR | PX `SUBJECT-AREA` |
| `source_hy/en/ru`, `source_link` | VARCHAR | Data source (when given), HTML removed; first hyperlink |
| `note_hy/en/ru` | VARCHAR | Footnotes, newline-separated |
| `updated` | TIMESTAMPTZ | Last update of the table at Armstat (PX `LAST-UPDATED`) |
| `official_statistics` | BOOLEAN | PX `OFFICIAL-STATISTICS` flag |
| `n_dimensions`, `n_cells`, `n_values` | INT | Number of dimensions, cells, non-missing cells |
| `first_period`, `last_period` | VARCHAR | Range of the time dimension (normalised, see `period`) |
| `stub`, `heading` | VARCHAR[] | Dimensions shown as rows / columns on the Statbank site |
| `en_origin` | VARCHAR | `armstat` – all English official; `partial` – some labels machine-translated; `machine` – title machine-translated |
| `hy_available` | BOOLEAN | Armenian metadata was found in the API |
| `api_path` | VARCHAR | Path under `https://statbank.armstat.am/api/v1/{lang}/ArmStatBank/` |
| `url_hy`, `url_en` | VARCHAR | Table pages on statbank.armstat.am |
| `ckan_name`, `ckan_url` | VARCHAR | The same table on data.opendata.am |

### `topics`

Navigation tree of Statbank (8 sections and their sub-sections).

| Column | Description |
|---|---|
| `topic_id` (PK) | Folder path in the API, e.g. `1 Econnomy and finance/12 Consumer Prices` (Armstat's spelling) |
| `parent_id` | Parent folder; NULL for sections |
| `level`, `position` | Depth (1 = section) and order among siblings |
| `code` | Numbering from the name, e.g. `1.2` |
| `name_hy/en/ru`, `en_machine` | Names without the numbering |
| `n_tables` | Tables directly in this folder |

### `dataset_topics`

Links datasets to topics. A table can be published in two folders (`EF-gf-3`); one link has
`is_primary = TRUE`.

### `dimensions`

| Column | Description |
|---|---|
| `table_id`, `dim_code` (PK) | PX variable code, e.g. `marzes`, `years` |
| `position` | 0-based order; defines the order of `obs_id` |
| `placement` | `stub` (rows) or `heading` (columns) on the site |
| `is_time` | Time dimension (years, quarters, months) – heuristic on code and labels |
| `elimination` | PXWeb flag: dimension may be left out of a query |
| `label_hy/en/ru`, `en_machine` | Dimension name |
| `n_values` | Number of values |

### `dimension_values`

| Column | Description |
|---|---|
| `table_id`, `dim_code`, `value_code` (PK) | PX value code (usually `0`, `1`, …) |
| `position` | 0-based order inside the dimension |
| `label_hy/en/ru`, `en_machine` | Category label |
| `period`, `year` | For time dimensions: normalised period (`2015`, `2015-Q1`, `2015-03`; a month without year is `--03`) and its year |

### `observations`

| Column | Description |
|---|---|
| `table_id`, `obs_id` (PK) | `obs_id` is the row-major cell index over the dimensions in `position` order (the JSON-stat index) |
| `dims` | `MAP(VARCHAR, VARCHAR)` – `{dim_code: value_code}` of the cell |
| `period` | Period of the cell; year and month dimensions are combined (`1993-01`) |
| `value` | DOUBLE; NULL when missing |
| `status` | Missing-value symbol, set only when `value` is NULL (see `status_symbols`) |

### `status_symbols`

| Symbol | Meaning (PX-Web convention) |
|---|---|
| `.` | Category not applicable |
| `..` | Data not available |
| `...` | Data not yet available or not for publication |
| `-` | Magnitude nil |
| `x` | Confidential |

Armstat does not publish a legend for these symbols in the API; the meanings follow the
usual PX-Web conventions.

### `translations`

Translation memory: `src_lang`, `tgt_lang`, `source`, `target`, `engine`, `reviewed`.
Pairs: `hy→en`, `hy→ru`, `en→ru`. The same content is versioned in
`data/translations/*.jsonl`.

### `languages`, `build_info`

Language list with the origin of texts; build metadata (time, versions, counts, number of
texts still untranslated).

## Views and macros

| Object | Description |
|---|---|
| `catalog` | One row per table with its topic path and title in all languages |
| `topic_paths` | Full topic path, e.g. `Economy and finances / Consumer Prices / Monthly indicators` |
| `observation_dims` | `observations.dims` unnested: one row per (observation, dimension) |
| `data_long` | Long format with dimension and value labels in all languages |
| `table_data(table_id, lang := 'en')` | One row per observation with `labels` MAP `{dim_code: label}` in one language (missing labels fall back to English, then to the code) |
| `table_long(table_id, lang := 'en')` | One row per (observation, dimension) in one language – input for `PIVOT` |
| `translation_coverage` | How many texts exist per language and how many are machine-translated |

## Example queries

```sql
-- find tables
SELECT table_id, title_en, first_period, last_period
FROM catalog WHERE title_en ILIKE '%consumer price%';

-- monthly CPI as a time series
SELECT period, value
FROM observations
WHERE table_id = 'EF-cpi-mi1'
ORDER BY period;

-- a table with Russian labels
SELECT labels['marzes'] AS marz, labels['types'] AS type, period, value
FROM table_data('AF-1-2024', lang := 'ru');

-- wide table, one column per dimension (Armenian labels)
PIVOT (SELECT obs_id, dimension, label, value FROM table_long('AF-1-2024', lang := 'hy'))
ON dimension USING first(label) GROUP BY obs_id, value ORDER BY obs_id;

-- filter by codes
SELECT o.period, o.value
FROM observations o
WHERE o.table_id = 'AF-1-2024' AND o.dims['marzes'] = '0' AND o.dims['types'] = '0';

-- labels of a dimension in three languages
SELECT value_code, label_hy, label_en, label_ru
FROM dimension_values WHERE table_id = 'AF-1-2024' AND dim_code = 'marzes'
ORDER BY position;

-- machine-translated English labels
SELECT table_id, label_hy, label_en FROM dimension_values WHERE en_machine;
```

From Python:

```python
import duckdb
con = duckdb.connect("build/armstat.duckdb", read_only=True)
df = con.sql("FROM table_data('EF-cpi-mi1', lang := 'en')").df()
```

Export one table as a labelled file:

```bash
armstat-db export AF-1-2024 --lang ru -o af-1-2024.ru.csv
armstat-db export AF-1-2024 --lang hy -o af-1-2024.hy.parquet
```
