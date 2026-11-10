# Справочник по базе данных

База данных — это один файл DuckDB, `build/armstat.duckdb`, который создается командой
`armstat-db build`. Внешних зависимостей у нее нет: ее можно открыть в DuckDB CLI, Python,
R, DBeaver или любом другом клиенте DuckDB.

```bash
duckdb build/armstat.duckdb
```

## Модель

```
topics ──< dataset_topics >── datasets ──< dimensions ──< dimension_values
                                  │                              │
                                  └──────< observations >────────┘  (dims MAP: dim_code → value_code)
status_symbols ──< observations.status
translations   (translation memory, provenance of machine translations)
languages, build_info
```

* **Набор данных** (dataset) — одна таблица Statbank (один PX-файл), например `EF-cpi-mi1`.
* У набора данных 2–4 **измерения** (переменные PX: марз, год, показатель, …).
  Техническое измерение PXWeb `ContentsCode` не хранится как измерение: в Statbank у него
  всегда одно значение, поэтому его текст и единица измерения хранятся в `datasets.contents_*`
  и `datasets.unit_*`.
* У каждого измерения есть **значения измерения** (категории) с кодами и подписями.
* **Наблюдение** — одна ячейка таблицы: сочетание из одного значения каждого измерения и
  числа (или символа пропущенного значения).

### Языковые столбцы

Каждый текст, предназначенный для чтения человеком, представлен тремя столбцами: `*_hy`
(армянский), `*_en` (английский), `*_ru` (русский).

| Язык | Происхождение |
|---|---|
| `hy` | Официальный текст Армстата из армянского интерфейса. NULL, если у Армстата нет армянской версии (1 таблица). |
| `en` | Официальный текст Армстата из английского интерфейса. Если Армстат оставил текст непереведенным (армянское письмо в английском интерфейсе), он машинно переводится с армянского и помечается `en_machine = TRUE`. |
| `ru` | Всегда машинный перевод: с официального английского текста или с армянского, если официального английского текста нет или если перевод с армянского добавлен в качестве исправления. |

Все машинные переводы перечислены в `translations` с указанием системы перевода (engine),
которая их выполнила.

## Таблицы

### `datasets`

| Столбец | Тип | Описание |
|---|---|---|
| `table_id` | VARCHAR, PK | Идентификатор PX-таблицы в том виде, в каком он используется в Statbank, например `EF-cpi-mi1` |
| `matrix`, `subject_code` | VARCHAR | Ключевые слова PX `MATRIX` и `SUBJECT-CODE` |
| `title_hy/en/ru` | VARCHAR | Полное название, как в дереве Statbank |
| `contents_hy/en/ru` | VARCHAR | Краткое описание предмета таблицы (PX `CONTENTS`) |
| `unit_hy/en/ru` | VARCHAR | Единица измерения всех значений |
| `decimals` | TINYINT | Число знаков после запятой, которое показывает Армстат |
| `subject_area_hy/en/ru` | VARCHAR | PX `SUBJECT-AREA` |
| `source_hy/en/ru`, `source_link` | VARCHAR | Источник данных (если указан), без HTML; первая гиперссылка |
| `note_hy/en/ru` | VARCHAR | Сноски, разделенные переводом строки |
| `updated` | TIMESTAMPTZ | Время последнего обновления таблицы у Армстата (PX `LAST-UPDATED`) |
| `official_statistics` | BOOLEAN | Флаг PX `OFFICIAL-STATISTICS` |
| `n_dimensions`, `n_cells`, `n_values` | INT | Число измерений, ячеек и непропущенных ячеек |
| `first_period`, `last_period` | VARCHAR | Диапазон временного измерения (в нормализованном виде, см. `period`) |
| `stub`, `heading` | VARCHAR[] | Измерения, которые на сайте Statbank показаны в строках / столбцах |
| `en_origin` | VARCHAR | `armstat` — все английские тексты официальные; `partial` — часть подписей переведена машинно; `machine` — название переведено машинно |
| `hy_available` | BOOLEAN | Армянские метаданные найдены в API |
| `api_path` | VARCHAR | Путь относительно `https://statbank.armstat.am/api/v1/{lang}/ArmStatBank/` |
| `url_hy`, `url_en` | VARCHAR | Страницы таблицы на statbank.armstat.am |
| `ckan_name`, `ckan_url` | VARCHAR | Та же таблица на data.opendata.am |

### `topics`

Навигационное дерево Statbank (8 разделов и их подразделы).

| Столбец | Описание |
|---|---|
| `topic_id` (PK) | Путь к папке в API, например `1 Econnomy and finance/12 Consumer Prices` (в написании Армстата) |
| `parent_id` | Родительская папка; NULL для разделов |
| `level`, `position` | Глубина (1 = раздел) и порядок среди элементов того же уровня |
| `code` | Номер из названия, например `1.2` |
| `name_hy/en/ru`, `en_machine` | Названия без номера |
| `n_tables` | Число таблиц непосредственно в этой папке |

### `dataset_topics`

Связывает наборы данных с темами. Таблица может быть опубликована в двух папках
(`EF-gf-3`); у одной из связей `is_primary = TRUE`.

### `dimensions`

| Столбец | Описание |
|---|---|
| `table_id`, `dim_code` (PK) | Код переменной PX, например `marzes`, `years` |
| `position` | Порядковый номер (с 0); определяет порядок `obs_id` |
| `placement` | `stub` (строки) или `heading` (столбцы) на сайте |
| `is_time` | Временное измерение (годы, кварталы, месяцы) — определяется эвристически по коду и подписям |
| `elimination` | Флаг PXWeb: измерение можно не указывать в запросе |
| `label_hy/en/ru`, `en_machine` | Название измерения |
| `n_values` | Число значений |

### `dimension_values`

| Столбец | Описание |
|---|---|
| `table_id`, `dim_code`, `value_code` (PK) | Код значения PX (обычно `0`, `1`, …) |
| `position` | Порядковый номер внутри измерения (с 0) |
| `label_hy/en/ru`, `en_machine` | Подпись категории |
| `period`, `year` | Для временных измерений: нормализованный период (`2015`, `2015-Q1`, `2015-03`; месяц без года записывается как `--03`) и его год |

### `observations`

| Столбец | Описание |
|---|---|
| `table_id`, `obs_id` (PK) | `obs_id` — индекс ячейки при построчном (row-major) обходе измерений в порядке `position` (индекс JSON-stat) |
| `dims` | `MAP(VARCHAR, VARCHAR)` — `{dim_code: value_code}` ячейки |
| `period` | Период ячейки; измерения года и месяца объединяются (`1993-01`) |
| `value` | DOUBLE; NULL, если значение пропущено |
| `status` | Символ пропущенного значения; заполняется, только если `value` равно NULL (см. `status_symbols`) |

### `status_symbols`

| Символ | Значение (соглашение PX-Web) |
|---|---|
| `.` | Категория неприменима |
| `..` | Данные отсутствуют |
| `...` | Данные пока отсутствуют или не подлежат публикации |
| `-` | Явление отсутствует |
| `x` | Конфиденциальные данные |

Армстат не публикует расшифровку этих символов в API; их значения соответствуют
общепринятым соглашениям PX-Web.

### `translations`

Память переводов: `src_lang`, `tgt_lang`, `source`, `target`, `engine`, `reviewed`.
Языковые пары: `hy→en`, `hy→ru`, `en→ru`. То же содержимое хранится под контролем версий в
`data/translations/*.jsonl`.

### `languages`, `build_info`

Список языков с происхождением текстов; метаданные сборки (время, версии, количественные
показатели, число еще не переведенных текстов).

## Представления и макросы

| Объект | Описание |
|---|---|
| `catalog` | По одной строке на таблицу с путем в дереве тем и названием на всех языках |
| `topic_paths` | Полный путь темы, например `Economy and finances / Consumer Prices / Monthly indicators` |
| `observation_dims` | Развернутый `observations.dims`: одна строка на пару (наблюдение, измерение) |
| `data_long` | Длинный формат с подписями измерений и значений на всех языках |
| `table_data(table_id, lang := 'en')` | Одна строка на наблюдение с MAP `labels` `{dim_code: label}` на одном языке (при отсутствии подписи используется английская, а затем код) |
| `table_long(table_id, lang := 'en')` | Одна строка на пару (наблюдение, измерение) на одном языке — входные данные для `PIVOT` |
| `translation_coverage` | Сколько текстов есть на каждом языке и сколько из них переведено машинно |

## Примеры запросов

```sql
-- поиск таблиц
SELECT table_id, title_en, first_period, last_period
FROM catalog WHERE title_en ILIKE '%consumer price%';

-- месячный ИПЦ как временной ряд
SELECT period, value
FROM observations
WHERE table_id = 'EF-cpi-mi1'
ORDER BY period;

-- таблица с русскими подписями
SELECT labels['marzes'] AS marz, labels['types'] AS type, period, value
FROM table_data('AF-1-2024', lang := 'ru');

-- широкая таблица, по одному столбцу на измерение (армянские подписи)
PIVOT (SELECT obs_id, dimension, label, value FROM table_long('AF-1-2024', lang := 'hy'))
ON dimension USING first(label) GROUP BY obs_id, value ORDER BY obs_id;

-- фильтр по кодам
SELECT o.period, o.value
FROM observations o
WHERE o.table_id = 'AF-1-2024' AND o.dims['marzes'] = '0' AND o.dims['types'] = '0';

-- подписи измерения на трех языках
SELECT value_code, label_hy, label_en, label_ru
FROM dimension_values WHERE table_id = 'AF-1-2024' AND dim_code = 'marzes'
ORDER BY position;

-- английские подписи, переведенные машинно
SELECT table_id, label_hy, label_en FROM dimension_values WHERE en_machine;
```

Из Python:

```python
import duckdb
con = duckdb.connect("build/armstat.duckdb", read_only=True)
df = con.sql("FROM table_data('EF-cpi-mi1', lang := 'en')").df()
```

Выгрузка одной таблицы в файл с подписями:

```bash
armstat-db export AF-1-2024 --lang ru -o af-1-2024.ru.csv
armstat-db export AF-1-2024 --lang hy -o af-1-2024.hy.parquet
```
