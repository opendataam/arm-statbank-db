# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] – 2026-11-10

### Added

- DuckDB schema for Statbank tables: `datasets`, `topics`, `dataset_topics`, `dimensions`,
  `dimension_values`, `observations` (with `dims` MAP and normalised `period`),
  `status_symbols`, `translations`, `languages`, `build_info`.
- Views and macros: `catalog`, `topic_paths`, `observation_dims`, `data_long`,
  `table_data()`, `table_long()`, `translation_coverage`.
- `armstat-db` CLI: `fetch`, `fetch-values`, `align`, `refetch`, `collect`, `translate`, `batches`,
  `merge-batches`, `build`, `validate`, `qa`, `docs`, `export`.
- Verification of the Armenian/English category correspondence by data (`align`) and a
  report of label inconsistencies in Armstat's sources (`qa`).
- PX-Web API client with a shared rate limiter; cached Armenian metadata for 824 tables and
  the topic trees in Armenian and English.
- Translation memory (`hy→en`, `hy→ru`, `en→ru`; 9,481 entries), glossary and style guide;
  Claude API backend and file-based batches (with id-shift detection) for translation;
  `hy→ru` entries override `en→ru` where Armstat's English is ambiguous.
- Export overrides: 9 tables re-downloaded from the English API (`IC-co-1-2024`, whose
  statbank-parser export is faulty, and 8 tables updated by Armstat after the parser run).
- `armstat-db release`: database file, Parquet bundle and checksums for GitHub releases.
- Documentation in English, Armenian and Russian; generated table catalogue.
- Test suite with a synthetic snapshot; GitHub Actions workflow.
