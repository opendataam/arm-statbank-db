# Сопровождение

## Требования

* Python ≥ 3.10, [uv](https://docs.astral.sh/uv/) (или pip)
* Рабочая копия [statbank-parser](https://github.com/opendataam/statbank-parser) с
  `indicators.jsonl` и `exports/` (по умолчанию в `../statbank-parser`; другое расположение
  задается через `--parser-dir` / `STATBANK_PARSER_DIR`)
* Доступ к сети (statbank.armstat.am) нужен только для `fetch`

```bash
make install            # .venv с пакетом и дополнительными зависимостями dev/translate
```

## Цикл обновления

```bash
# 1. обновить английский снимок (в репозитории statbank-parser)
python3 -m statbank_parser.cli list-indicators > indicators.jsonl
#    и заново выгрузить изменившиеся таблицы (см. README statbank-parser)

# 2. обновить армянские метаданные и деревья тем (≈ 30 мин, с ограничением частоты запросов)
armstat-db fetch --refresh

# 2a. проверить соответствие армянских и английских категорий (≈ 15 мин)
armstat-db fetch-values --refresh     # армянские значения -> build/cache (не коммитится)
armstat-db align                      # -> data/source/api/hy/alignment.json
armstat-db refetch TABLE_ID …         # заменить некорректные/устаревшие выгрузки, затем снова align

# 3. найти тексты, которые еще не переведены
armstat-db collect

# 4. перевести их (один из вариантов)
armstat-db translate                     # Claude API, нужен ANTHROPIC_API_KEY
armstat-db batches && …translate files… && armstat-db merge-batches --engine NAME

# 5. собрать базу, проверить ее и заново сгенерировать каталог
armstat-db build
armstat-db validate
armstat-db qa                         # несогласованные подписи -> build/qa/label_swaps.tsv
armstat-db docs
pytest
```

`fetch` кэширует каждую таблицу в `data/source/api/hy/tables/`; без `--refresh`
загружаются только новые таблицы. PX-Web API допускает 10 запросов за 10 секунд с одного
IP-адреса и 100 000 ячеек на запрос (`/api/v1/en/?config`); `fetch` ограничивает себя
9 запросами за 10 секунд (`--max-calls`, `--period`), повторяет запрос при ответе
HTTP 429, а `fetch-values` разбивает большие таблицы на несколько запросов.

## Конвейер обработки

```
statbank-parser exports (en, JSON-stat 2) ─┐
PX-Web API: hy metadata + hy/en trees ─────┼─> sources.py ─> build.assemble() ─> DuckDB
translation memory (data/translations) ────┘                  │
                                                               └─> missing texts ─> collect
```

| Модуль | Назначение |
|---|---|
| `pxweb.py` | Клиент API (ограничение частоты запросов, повторные попытки), соответствие веб-URL ↔ путь в API |
| `fetch.py` | Загрузка деревьев и армянских метаданных по каждой таблице |
| `align.py` | Загрузка армянских значений, проверка и восстановление соответствия категорий; `refetch` некорректных выгрузок |
| `qa.py` | Отчет о несогласованности армянских и английских подписей в источниках Армстата |
| `catalog.py` | Чтение `indicators.jsonl`, поиск файлов выгрузки (с теми же именами, что в statbank-parser) |
| `jsonstat.py` | Парсер JSON-stat 2 |
| `sources.py` | Объединение английских выгрузок, армянских метаданных и деревьев |
| `translation/resolve.py` | Правила выбора между официальными и машинными текстами |
| `translation/memory.py` | Память переводов (`*.jsonl`) |
| `translation/llm.py` | Бэкенд Claude API для `translate` |
| `translation/batches.py` | Пакеты в файлах для переводчиков без доступа к API |
| `build.py`, `sql/schema.sql`, `sql/views.sql` | Сборка базы данных |
| `validate.py` | Проверки согласованности |
| `docs.py`, `export.py` | Страницы каталога, выгрузка отдельных таблиц |

## Память переводов

`data/translations/{hy-en,hy-ru,en-ru}.jsonl` — по одному JSON-объекту на строку, записи
отсортированы по исходному тексту:

```json
{"source": "Livestock", "target": "Поголовье скота", "engine": "…", "reviewed": false}
```

* Ключом служит нормализованный исходный текст, поэтому текст, общий для многих таблиц,
  переводится один раз.
* Чтобы исправить перевод, отредактируйте `target` и установите `"reviewed": true`;
  проверенные записи никогда не перезаписываются командами `translate` и `merge-batches`.
* Устоявшиеся термины вносятся в `glossary.tsv`, правила — в `STYLE.md`.
* Запись `hy-ru` для армянского текста имеет приоритет над записью `en-ru` для
  соответствующего английского текста: используйте ее, когда английский текст Армстата
  ошибочен или неоднозначен.
* `merge-batches` отклоняет пакетный файл, идентификаторы в котором выглядят сдвинутыми
  (коды вида `17.21` в начале исходного текста должны стоять и в начале перевода).
* После редактирования выполните `armstat-db build` — других шагов не требуется.

## Проверки

`armstat-db validate` проверяет число ячеек, согласованность пропущенных значений, размеры
измерений, дерево тем, отсутствие армянского письма в английских и русских текстах, а также
выводит покрытие переводами. Если есть строки `ERROR`, команда завершается с кодом 1.

## Публикация релиза

Файл базы данных не хранится в репозитории (каталог `build/` игнорируется). Опубликуйте
`build/armstat.duckdb` как файл релиза (или на data.opendata.am) вместе со значениями
`build_info` и закоммитьте обновленные файлы в `data/` и `docs/`.
