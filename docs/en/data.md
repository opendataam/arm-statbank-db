# About the data

## Source

[Statbank](https://statbank.armstat.am) is the statistical database of the
Statistical Committee of the Republic of Armenia (Armstat). It runs on PX-Web and
publishes multidimensional tables in Armenian and English, with a web interface and a JSON
API (`https://statbank.armstat.am/api/v1/{hy|en}/ArmStatBank/`).

This database combines two collections:

| Part | Collected by | Content |
|---|---|---|
| Values and English metadata | [statbank-parser](https://github.com/opendataam/statbank-parser) (`indicators.jsonl`, `exports/*.json`, JSON-stat 2) | All cells of all tables, English labels, units, notes |
| Armenian metadata and the navigation tree | `armstat-db fetch` (PX-Web API) | Armenian titles, dimension and value labels, units, notes; topic tree in both languages |

Both interfaces of Statbank use the same variable and value codes, so the Armenian texts
are joined to the English ones by code. The statbank-parser exports are also published
as CSV/XLSX/JSON-stat on [data.opendata.am](https://data.opendata.am) (`datasets.ckan_url`).

## Coverage

Statbank is organised in eight sections:

1. Economy and finances (national accounts, prices, finances, banking, …)
2. Population and social processes (demography, education, health, social protection, housing, …)
3. Industry (including energy), construction, trade and services
4. Transport, communication and tourism
5. Foreign trade
6. Agriculture, forestry and fishing (including the 2014 Agricultural Census)
7. Food security
8. Environment

The full list of tables with titles, units and periods is in the generated
[catalogue](catalog.md).

## Structure of a table

Every Statbank table is a PX cube: a set of dimensions (for example *marz × type ×
year*) and one value per combination. In the database:

* `datasets` – one row per table with titles, unit, notes, source and update time;
* `dimensions` / `dimension_values` – the dimensions and their categories;
* `observations` – every cell, with its value or a missing-value symbol.

Missing cells are kept: Statbank uses symbols (`..`, `-`, `...`, `x`, `.`) instead of
numbers; they are stored in `observations.status` with `value = NULL`.

Time dimensions (years, quarters, months) are detected automatically and their labels are
normalised in `dimension_values.period` and `observations.period` (`2015`, `2015-Q1`,
`2015-03`). Labels that are not plain periods ("Multiyear average values") keep
`period = NULL`.

## Languages and translation

| | Armenian | English | Russian |
|---|---|---|---|
| Origin | Armstat | Armstat; machine translation where Armstat has none | machine translation |
| Flag | – | `en_machine`, `datasets.en_origin` | (always machine) |

* About 3 % of the tables in the English interface of Statbank are not translated by
  Armstat (their labels are in Armenian), and some other tables contain single
  untranslated labels. These texts were translated from Armenian to English.
* Russian texts were translated from the official English text (more precise for
  statistical terminology) and from Armenian only where no official English exists.
  Where Armstat's English is ambiguous or wrong (for example, both «Գողություն» (theft)
  and «Ավազակություն» (brigandage) are called "Robbery"), a translation from the Armenian
  original (`hy→ru` memory) overrides the one from English.
* Translations are made with a large language model (Claude) following the
  [style guide](../../data/translations/STYLE.md) and the
  [glossary](../../data/translations/glossary.tsv). They are not official translations of
  Armstat and may contain errors; `translations.reviewed` marks entries checked by a person.
* Obvious source defects are corrected on load: Cyrillic letters inside Latin English words
  ("Тransportations" written with a Cyrillic "Т"), extra whitespace, HTML in sources.

## Consistency of the two language versions

Armstat publishes a separate PX file for each language, and value codes are positional
(`0`, `1`, …). `armstat-db align` downloads the Armenian *values* of every table and checks
that they equal the English values code by code; if a table listed categories in a
different order, the Armenian labels would be re-attached by matching data
(`data/source/api/hy/alignment.json`).

In the current snapshot all 823 tables with an Armenian version agree code by code
(≥ 99.5 % of non-missing cells); in two tables a dimension has different codes in the two
languages and is matched by position. The check also found one faulty statbank-parser
export (`IC-co-1-2024`, the largest table, assembled from several downloads) and eight
tables updated by Armstat after the parser run. These nine tables were downloaded again
from the English API with `armstat-db refetch` and are stored in
`data/source/api/en/overrides/`; the build uses them instead of the parser exports.

The *labels* themselves are sometimes inconsistent in Armstat's sources: in a few tables
one language version has town or country names in a different order than the other
(e.g. Dilijan / Berd / Ayrum, Talin / Aparan, Argentina / Venezuela). The data show that
either version can be the wrong one, so the database keeps both official texts unchanged;
`armstat-db qa` lists these cases in `build/qa/label_swaps.tsv`.

## Known limitations

* The snapshot reflects the state of Statbank at the time of the parser run
  (`build_info.parser_revision`) and of `fetch` (`data/source/api/*/tables/*.json`, field
  `fetched`). Tables updated later may have more periods at Armstat than here.
* One table (`IC-sr-03-2024`) is published only in English, so it has no Armenian texts.
* Meanings of missing-value symbols follow the PX-Web convention; Armstat publishes no legend
  in the API.
* Armstat's English texts contain translation errors and typos; they are kept as published
  (except Cyrillic look-alike letters), and the Russian translation may inherit them.
* Dimension names in PX files are terse and lower-case ("marzes", "years"); they are kept as
  published.
* Machine translations of very specific classifications (commodity groups, crime types,
  occupations) should be checked before official use.

## Citation

Source of the statistics: Statistical Committee of the Republic of Armenia (Armstat),
Statbank, https://statbank.armstat.am. Database, Armenian–English alignment and
translations: OpenData Armenia, arm-statbank-db.
