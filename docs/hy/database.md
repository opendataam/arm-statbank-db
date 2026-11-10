# Տվյալների բազայի տեղեկատու

Տվյալների բազան մեկ DuckDB ֆայլ է՝ `build/armstat.duckdb`, որը կառուցվում է
`armstat-db build` հրամանով։ Այն արտաքին կախվածություններ չունի․ բացեք այն DuckDB CLI-ով,
Python-ով, R-ով, DBeaver-ով կամ ցանկացած DuckDB կլիենտով։

```bash
duckdb build/armstat.duckdb
```

## Մոդել

```
topics ──< dataset_topics >── datasets ──< dimensions ──< dimension_values
                                  │                              │
                                  └──────< observations >────────┘  (dims MAP: dim_code → value_code)
status_symbols ──< observations.status
translations   (translation memory, provenance of machine translations)
languages, build_info
```

* **Տվյալների հավաքածուն** (dataset) Statbank-ի մեկ աղյուսակ է (մեկ PX ֆայլ), օրինակ՝
  `EF-cpi-mi1`։
* Տվյալների հավաքածուն ունի 2–4 **փոփոխական** (PX փոփոխականներ՝ մարզ, տարի, ցուցանիշ, …)։
  PXWeb-ի տեխնիկական `ContentsCode` փոփոխականը որպես փոփոխական չի պահվում․ Statbank-ում այն
  միշտ ունի մեկ արժեք, ուստի դրա տեքստը և չափման միավորը պահվում են `datasets.contents_*` և
  `datasets.unit_*` սյունակներում։
* Յուրաքանչյուր փոփոխական ունի **փոփոխականի արժեքներ** (կատեգորիաներ)՝ կոդերով և
  անվանումներով։
* **Դիտարկումն** աղյուսակի մեկ բջիջն է՝ յուրաքանչյուր փոփոխականի մեկական արժեքի համակցություն
  և թիվը (կամ բացակայող արժեքի պայմանական նշանը)։

### Լեզվային սյունակներ

Մարդու համար ընթեռնելի յուրաքանչյուր տեքստ ունի երեք սյունակ՝ `*_hy` (հայերեն), `*_en`
(անգլերեն), `*_ru` (ռուսերեն)։

| Լեզու | Ծագում |
|---|---|
| `hy` | Armstat-ի պաշտոնական տեքստը՝ հայերեն ինտերֆեյսից։ NULL, եթե Armstat-ը հայերեն տարբերակ չունի (1 աղյուսակ)։ |
| `en` | Armstat-ի պաշտոնական տեքստը՝ անգլերեն ինտերֆեյսից։ Այն դեպքերում, երբ Armstat-ը տեքստը թողել է չթարգմանված (հայատառ տեքստ անգլերեն ինտերֆեյսում), այն թարգմանվում է հայերենից մեքենայական թարգմանությամբ և նշվում `en_machine = TRUE` նշիչով։ |
| `ru` | Միշտ մեքենայական թարգմանություն՝ պաշտոնական անգլերեն տեքստից կամ հայերենից, երբ պաշտոնական անգլերեն տեքստ չկա կամ երբ հայերենից թարգմանությունն ավելացվել է որպես ուղղում։ |

Բոլոր մեքենայական թարգմանությունները ցուցակագրված են `translations` աղյուսակում՝ դրանք
ստեղծած համակարգի (engine) նշումով։

## Աղյուսակներ

### `datasets`

| Սյունակ | Տեսակ | Նկարագրություն |
|---|---|---|
| `table_id` | VARCHAR, PK | PX աղյուսակի նույնացուցիչը, ինչպես օգտագործվում է Statbank-ում, օրինակ՝ `EF-cpi-mi1` |
| `matrix`, `subject_code` | VARCHAR | PX-ի `MATRIX` և `SUBJECT-CODE` բանալի բառերը |
| `title_hy/en/ru` | VARCHAR | Ամբողջական վերնագիրը՝ ինչպես ցուցադրվում է Statbank-ի ծառում |
| `contents_hy/en/ru` | VARCHAR | Աղյուսակի հակիրճ առարկան (PX `CONTENTS`) |
| `unit_hy/en/ru` | VARCHAR | Բոլոր արժեքների չափման միավորը |
| `decimals` | TINYINT | Armstat-ի ցուցադրած տասնորդական նիշերի քանակը |
| `subject_area_hy/en/ru` | VARCHAR | PX `SUBJECT-AREA` |
| `source_hy/en/ru`, `source_link` | VARCHAR | Տվյալների աղբյուրը (եթե նշված է)՝ առանց HTML-ի․ առաջին հիպերհղումը |
| `note_hy/en/ru` | VARCHAR | Ծանոթագրություններ՝ բաժանված նոր տողերով |
| `updated` | TIMESTAMPTZ | Armstat-ում աղյուսակի վերջին թարմացումը (PX `LAST-UPDATED`) |
| `official_statistics` | BOOLEAN | PX `OFFICIAL-STATISTICS` նշիչ |
| `n_dimensions`, `n_cells`, `n_values` | INT | Փոփոխականների, բջիջների, արժեք ունեցող բջիջների քանակը |
| `first_period`, `last_period` | VARCHAR | Ժամանակային փոփոխականի միջակայքը (նորմալացված, տե՛ս `period`) |
| `stub`, `heading` | VARCHAR[] | Statbank-ի կայքում տողերով / սյունակներով ցուցադրվող փոփոխականները |
| `en_origin` | VARCHAR | `armstat` – ամբողջ անգլերեն տեքստը պաշտոնական է․ `partial` – որոշ անվանումներ ստացվել են մեքենայական թարգմանությամբ․ `machine` – վերնագիրը ստացվել է մեքենայական թարգմանությամբ |
| `hy_available` | BOOLEAN | Հայերեն մետատվյալները գտնվել են API-ում |
| `api_path` | VARCHAR | Ուղին `https://statbank.armstat.am/api/v1/{lang}/ArmStatBank/` հասցեի ներքո |
| `url_hy`, `url_en` | VARCHAR | Աղյուսակի էջերը statbank.armstat.am կայքում |
| `ckan_name`, `ckan_url` | VARCHAR | Նույն աղյուսակը data.opendata.am կայքում |

### `topics`

Statbank-ի նավարկման ծառը (8 բաժին և դրանց ենթաբաժինները)։

| Սյունակ | Նկարագրություն |
|---|---|
| `topic_id` (PK) | Թղթապանակի ուղին API-ում, օրինակ՝ `1 Econnomy and finance/12 Consumer Prices` (Armstat-ի ուղղագրությամբ) |
| `parent_id` | Ծնող թղթապանակը․ NULL՝ բաժինների համար |
| `level`, `position` | Խորությունը (1 = բաժին) և հերթականությունը նույն մակարդակի տարրերի միջև |
| `code` | Համարակալումը՝ վերցված անվանումից, օրինակ՝ `1.2` |
| `name_hy/en/ru`, `en_machine` | Անվանումներ՝ առանց համարակալման |
| `n_tables` | Անմիջապես այս թղթապանակում գտնվող աղյուսակները |

### `dataset_topics`

Կապում է տվյալների հավաքածուները թեմաներին։ Աղյուսակը կարող է հրապարակված լինել երկու
թղթապանակում (`EF-gf-3`)․ կապերից մեկն ունի `is_primary = TRUE`։

### `dimensions`

| Սյունակ | Նկարագրություն |
|---|---|
| `table_id`, `dim_code` (PK) | PX փոփոխականի կոդը, օրինակ՝ `marzes`, `years` |
| `position` | 0-ից սկսվող հերթական համարը․ որոշում է `obs_id`-ի կարգը |
| `placement` | `stub` (տողեր) կամ `heading` (սյունակներ) կայքում |
| `is_time` | Ժամանակային փոփոխական (տարիներ, եռամսյակներ, ամիսներ)՝ որոշվում է էվրիստիկ եղանակով՝ ըստ կոդի և անվանումների |
| `elimination` | PXWeb նշիչ․ փոփոխականը կարող է բաց թողնվել հարցումից |
| `label_hy/en/ru`, `en_machine` | Փոփոխականի անվանումը |
| `n_values` | Արժեքների քանակը |

### `dimension_values`

| Սյունակ | Նկարագրություն |
|---|---|
| `table_id`, `dim_code`, `value_code` (PK) | PX արժեքի կոդը (սովորաբար `0`, `1`, …) |
| `position` | 0-ից սկսվող հերթական համարը փոփոխականի ներսում |
| `label_hy/en/ru`, `en_machine` | Կատեգորիայի անվանումը |
| `period`, `year` | Ժամանակային փոփոխականների համար՝ նորմալացված ժամանակաշրջանը (`2015`, `2015-Q1`, `2015-03`․ առանց տարվա ամիսը՝ `--03`) և դրա տարին |

### `observations`

| Սյունակ | Նկարագրություն |
|---|---|
| `table_id`, `obs_id` (PK) | `obs_id`-ն բջջի ինդեքսն է՝ հաշված ըստ տողերի (row-major) կարգի փոփոխականների վրայով՝ `position`-ի հերթականությամբ (JSON-stat ինդեքսը) |
| `dims` | `MAP(VARCHAR, VARCHAR)` – բջջի `{dim_code: value_code}` |
| `period` | Բջջի ժամանակաշրջանը․ տարվա և ամսվա փոփոխականները միավորվում են (`1993-01`) |
| `value` | DOUBLE․ NULL, երբ արժեքը բացակայում է |
| `status` | Բացակայող արժեքի պայմանական նշանը, լրացվում է միայն այն դեպքում, երբ `value`-ն NULL է (տե՛ս `status_symbols`) |

### `status_symbols`

| Նշան | Նշանակություն (PX-Web-ի պայմանականություն) |
|---|---|
| `.` | Կատեգորիան կիրառելի չէ |
| `..` | Տվյալներ չկան |
| `...` | Տվյալները դեռ հասանելի չեն կամ ենթակա չեն հրապարակման |
| `-` | Երևույթը բացակայում է |
| `x` | Գաղտնի տվյալներ |

Armstat-ը այս նշանների բացատրությունը API-ում չի հրապարակում․ դրանց իմաստները համապատասխանում
են PX-Web-ի ընդունված պայմանականություններին։

### `translations`

Թարգմանությունների հիշողություն՝ `src_lang`, `tgt_lang`, `source`, `target`, `engine`, `reviewed`։
Զույգեր՝ `hy→en`, `hy→ru`, `en→ru`։ Նույն բովանդակությունը տարբերակավորված է
`data/translations/*.jsonl` ֆայլերում։

### `languages`, `build_info`

Լեզուների ցանկը՝ տեքստերի ծագման նշումով․ կառուցման մետատվյալներ (ժամանակ, տարբերակներ,
քանակներ, դեռևս չթարգմանված տեքստերի թիվը)։

## Ներկայացումներ (views) և մակրոներ

| Օբյեկտ | Նկարագրություն |
|---|---|
| `catalog` | Մեկ տող յուրաքանչյուր աղյուսակի համար՝ թեմայի ուղով և վերնագրով բոլոր լեզուներով |
| `topic_paths` | Թեմայի ամբողջական ուղին, օրինակ՝ `Economy and finances / Consumer Prices / Monthly indicators` |
| `observation_dims` | `observations.dims`-ի բացված (unnest) տեսքը․ մեկ տող յուրաքանչյուր (դիտարկում, փոփոխական) զույգի համար |
| `data_long` | Երկար (long) ձևաչափ՝ փոփոխականների և արժեքների անվանումներով բոլոր լեզուներով |
| `table_data(table_id, lang := 'en')` | Մեկ տող յուրաքանչյուր դիտարկման համար՝ `labels` MAP-ով `{dim_code: label}` մեկ լեզվով (բացակայող անվանումների փոխարեն օգտագործվում է անգլերենը, ապա՝ կոդը) |
| `table_long(table_id, lang := 'en')` | Մեկ տող յուրաքանչյուր (դիտարկում, փոփոխական) զույգի համար մեկ լեզվով – մուտքային տվյալներ `PIVOT`-ի համար |
| `translation_coverage` | Քանի տեքստ կա յուրաքանչյուր լեզվով և դրանցից քանիսն են ստացվել մեքենայական թարգմանությամբ |

## Հարցումների օրինակներ

```sql
-- գտնել աղյուսակներ
SELECT table_id, title_en, first_period, last_period
FROM catalog WHERE title_en ILIKE '%consumer price%';

-- ամսական ՍԳԻ-ն որպես ժամանակային շարք
SELECT period, value
FROM observations
WHERE table_id = 'EF-cpi-mi1'
ORDER BY period;

-- աղյուսակ ռուսերեն անվանումներով
SELECT labels['marzes'] AS marz, labels['types'] AS type, period, value
FROM table_data('AF-1-2024', lang := 'ru');

-- լայն աղյուսակ, մեկ սյունակ յուրաքանչյուր փոփոխականի համար (հայերեն անվանումներ)
PIVOT (SELECT obs_id, dimension, label, value FROM table_long('AF-1-2024', lang := 'hy'))
ON dimension USING first(label) GROUP BY obs_id, value ORDER BY obs_id;

-- զտում ըստ կոդերի
SELECT o.period, o.value
FROM observations o
WHERE o.table_id = 'AF-1-2024' AND o.dims['marzes'] = '0' AND o.dims['types'] = '0';

-- փոփոխականի արժեքների անվանումները երեք լեզվով
SELECT value_code, label_hy, label_en, label_ru
FROM dimension_values WHERE table_id = 'AF-1-2024' AND dim_code = 'marzes'
ORDER BY position;

-- մեքենայական թարգմանությամբ ստացված անգլերեն անվանումներ
SELECT table_id, label_hy, label_en FROM dimension_values WHERE en_machine;
```

Python-ում․

```python
import duckdb
con = duckdb.connect("build/armstat.duckdb", read_only=True)
df = con.sql("FROM table_data('EF-cpi-mi1', lang := 'en')").df()
```

Մեկ աղյուսակի արտահանում անվանումներով ֆայլի տեսքով․

```bash
armstat-db export AF-1-2024 --lang ru -o af-1-2024.ru.csv
armstat-db export AF-1-2024 --lang hy -o af-1-2024.hy.parquet
```
