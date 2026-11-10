# arm-statbank-db

**English** · [Հայերեն](README.hy.md) · [Русский](README.ru.md)

A trilingual (Armenian, English, Russian) [DuckDB](https://duckdb.org) database of
[Statbank](https://statbank.armstat.am) – the statistical database of the Statistical
Committee of the Republic of Armenia (Armstat).

* **825 tables** (824 unique), 137 topics, 2,037 dimensions, ~33,000 categories,
  ~862,000 observations;
* every text in **Armenian** (official), **English** (official, machine-translated where
  Armstat has no translation) and **Russian** (machine translation);
* one normalised schema for all tables, time periods parsed, missing-value symbols kept;
* reproducible build from open sources, with a versioned translation memory.

## Download

The ready-made database is published in [Releases](https://github.com/opendataam/arm-statbank-db/releases/latest):

| File | Content |
|---|---|
| `armstat.duckdb` | DuckDB database (~31 MB) |
| `armstat-parquet.zip` | The same data as Parquet files; `IMPORT DATABASE 'armstat-parquet'` recreates it |
| `SHA256SUMS` | Checksums |

DuckDB can also query it without downloading:

```sql
INSTALL httpfs; LOAD httpfs;
ATTACH 'https://github.com/opendataam/arm-statbank-db/releases/latest/download/armstat.duckdb' AS armstat (READ_ONLY);
USE armstat;
SELECT table_id, title_en FROM catalog LIMIT 5;
```

## Quick start

```bash
git clone https://github.com/opendataam/statbank-parser ../statbank-parser
make install
make build validate        # -> build/armstat.duckdb
```

```sql
-- duckdb build/armstat.duckdb
SELECT table_id, title_en, title_ru, first_period, last_period FROM catalog LIMIT 5;

SELECT labels['marzes'] AS marz, labels['types'] AS type, period, value
FROM table_data('AF-1-2024', lang := 'ru')
WHERE period = '2024';
```

## Documentation

| | English | Հայերեն | Русский |
|---|---|---|---|
| About the data | [data.md](docs/en/data.md) | [data.md](docs/hy/data.md) | [data.md](docs/ru/data.md) |
| Database reference | [database.md](docs/en/database.md) | [database.md](docs/hy/database.md) | [database.md](docs/ru/database.md) |
| Maintenance | [maintenance.md](docs/en/maintenance.md) | [maintenance.md](docs/hy/maintenance.md) | [maintenance.md](docs/ru/maintenance.md) |
| Table catalogue (generated) | [catalog.md](docs/en/catalog.md) | [catalog.md](docs/hy/catalog.md) | [catalog.md](docs/ru/catalog.md) |

## How it is built

```
statbank-parser exports (English, JSON-stat 2) ─┐
Statbank PX-Web API (Armenian metadata, trees) ─┼─> armstat-db build ─> build/armstat.duckdb
data/translations/*.jsonl (translation memory) ─┘
```

1. **Values and English metadata** come from the
   [statbank-parser](https://github.com/opendataam/statbank-parser) exports – complete
   JSON-stat 2 downloads of every table.
2. **Armenian metadata** (titles, dimension and value labels, units, notes) and the topic
   tree are downloaded from the Statbank API by `armstat-db fetch` and cached in
   `data/source/api/`. Both languages share codes, so texts are joined by code.
3. **Translations**: missing English texts are translated from Armenian, Russian texts from
   the official English (or Armenian). They are stored in `data/translations/` and reused on
   every build.

## Commands

| Command | Description |
|---|---|
| `armstat-db fetch` | Download Armenian metadata and the topic trees (cached) |
| `armstat-db fetch-values` / `align` | Verify that Armenian and English categories match by their data |
| `armstat-db refetch TABLE` | Replace a faulty parser export by the complete table from the API |
| `armstat-db collect` | List texts that are not in the translation memory |
| `armstat-db translate` | Translate them with the Claude API (`ANTHROPIC_API_KEY`) |
| `armstat-db batches` / `merge-batches` | File-based translation for people or agents |
| `armstat-db build` | Build `build/armstat.duckdb` |
| `armstat-db validate` | Consistency checks and translation coverage |
| `armstat-db qa` | Report label inconsistencies between Armstat's language versions |
| `armstat-db release` | Prepare release assets in `build/release` |
| `armstat-db docs` | Regenerate `docs/*/catalog.md` |
| `armstat-db export TABLE --lang ru -o file.csv` | Export one table with labels (CSV/Parquet) |

## Repository layout

```
arm-statbank-db/
├── src/armstat_db/          # Python package (CLI, loaders, build, translation)
│   ├── sql/schema.sql       # database schema
│   └── sql/views.sql        # views and macros
├── data/
│   ├── source/api/          # cached PX-Web API metadata (hy tables, hy/en trees)
│   └── translations/        # translation memory, glossary, style guide
├── docs/{en,hy,ru}/         # documentation in three languages
├── tests/                   # pytest suite with a synthetic snapshot
├── Makefile
└── pyproject.toml
```

## Translation quality

Russian texts and the English texts marked `en_machine` are machine translations made
with a large language model (Claude) and checked automatically (completeness, script,
codes), but not reviewed by a translator. They are not official Armstat translations.
Corrections are welcome: edit `data/translations/*.jsonl` and set `"reviewed": true`.

## License

Code: MIT. Statistics: © Statistical Committee of the Republic of Armenia – cite
"Armstat, Statbank, https://statbank.armstat.am" when using the data.
