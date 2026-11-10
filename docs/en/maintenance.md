# Maintenance

## Requirements

* Python ≥ 3.10, [uv](https://docs.astral.sh/uv/) (or pip)
* A checkout of [statbank-parser](https://github.com/opendataam/statbank-parser) with
  `indicators.jsonl` and `exports/` (default location `../statbank-parser`, or set
  `--parser-dir` / `STATBANK_PARSER_DIR`)
* Network access to statbank.armstat.am only for `fetch`

```bash
make install            # .venv with the package and dev/translate extras
```

## Update cycle

```bash
# 1. refresh the English snapshot (in the statbank-parser repository)
python3 -m statbank_parser.cli list-indicators > indicators.jsonl
#    and re-export changed tables (see statbank-parser README)

# 2. refresh Armenian metadata and the topic trees (≈ 30 min, rate-limited)
armstat-db fetch --refresh

# 2a. verify that Armenian and English categories correspond (≈ 15 min)
armstat-db fetch-values --refresh     # Armenian values -> build/cache (not committed)
armstat-db align                      # -> data/source/api/hy/alignment.json
armstat-db refetch TABLE_ID …         # replace faulty/outdated exports, then align again

# 3. find texts that are not yet translated
armstat-db collect

# 4. translate them (one of)
armstat-db translate                     # Claude API, needs ANTHROPIC_API_KEY
armstat-db batches && …translate files… && armstat-db merge-batches --engine NAME

# 5. build, check and regenerate the catalogue
armstat-db build
armstat-db validate
armstat-db qa                         # label inconsistencies -> build/qa/label_swaps.tsv
armstat-db docs
pytest
```

`fetch` caches every table in `data/source/api/hy/tables/`; without `--refresh` only new
tables are downloaded. The PX-Web API allows 10 requests per 10 seconds per IP and
100,000 cells per query (`/api/v1/en/?config`); `fetch` limits itself to 9 requests per
10 seconds (`--max-calls`, `--period`), retries on HTTP 429, and `fetch-values` splits
larger tables into several queries.

## Pipeline

```
statbank-parser exports (en, JSON-stat 2) ─┐
PX-Web API: hy metadata + hy/en trees ─────┼─> sources.py ─> build.assemble() ─> DuckDB
translation memory (data/translations) ────┘                  │
                                                               └─> missing texts ─> collect
```

| Module | Role |
|---|---|
| `pxweb.py` | API client (rate limit, retries), web URL ↔ API path |
| `fetch.py` | Downloads trees and per-table Armenian metadata |
| `align.py` | Downloads Armenian values, verifies/repairs the category correspondence; `refetch` of faulty exports |
| `qa.py` | Report on Armenian/English label inconsistencies in Armstat's sources |
| `catalog.py` | Reads `indicators.jsonl`, finds export files (same naming as statbank-parser) |
| `jsonstat.py` | JSON-stat 2 parser |
| `sources.py` | Joins English exports, Armenian metadata and trees |
| `translation/resolve.py` | Rules that choose official vs. machine texts |
| `translation/memory.py` | Translation memory (`*.jsonl`) |
| `translation/llm.py` | Claude API backend for `translate` |
| `translation/batches.py` | File-based batches for translators without API access |
| `build.py`, `sql/schema.sql`, `sql/views.sql` | Database build |
| `validate.py` | Consistency checks |
| `docs.py`, `export.py` | Catalogue pages, per-table export |

## Translation memory

`data/translations/{hy-en,hy-ru,en-ru}.jsonl` – one JSON object per line, sorted by source:

```json
{"source": "Livestock", "target": "Поголовье скота", "engine": "…", "reviewed": false}
```

* The key is the normalised source text, so a text shared by many tables is translated once.
* To correct a translation, edit `target` and set `"reviewed": true`; reviewed entries are
  never overwritten by `translate` or `merge-batches`.
* Fixed terms go to `glossary.tsv`; rules to `STYLE.md`.
* An `hy-ru` entry for an Armenian text takes precedence over the `en-ru` entry of its
  English text: use it when Armstat's English is wrong or ambiguous.
* `merge-batches` rejects a batch file whose ids look shifted (codes such as `17.21` at
  the start of a source must appear at the start of its target).
* After editing, run `armstat-db build` – no other step is needed.

## Checks

`armstat-db validate` verifies cell counts, missing-value consistency, dimension sizes, the
topic tree, absence of Armenian script in English/Russian texts and reports translation
coverage. `ERROR` lines make the command exit with status 1.

## Releasing

The database file is not committed (`build/` is ignored). After a build:

```bash
armstat-db release        # build/release: armstat.duckdb, armstat-parquet.zip, SHA256SUMS
gh release create vX.Y.Z build/release/* --title "…" --notes-file NOTES.md
```

Commit the updated `data/` and `docs/` files and update `CHANGELOG.md` first; the
release tag should point at the commit the database was built from.
