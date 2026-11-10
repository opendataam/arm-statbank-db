# arm-statbank-db

[English](README.md) · [Հայերեն](README.hy.md) · **Русский**

Трехъязычная (армянский, английский, русский) база данных [DuckDB](https://duckdb.org) на основе
[Statbank](https://statbank.armstat.am) — статистической базы данных Статистического
комитета Республики Армения (Армстат).

* **825 таблиц** (824 уникальные), 137 тем, 2037 измерений, ~33 000 категорий,
  ~862 000 наблюдений;
* все тексты на **армянском** (официальные), **английском** (официальные; машинный перевод там,
  где у Армстата нет перевода) и **русском** (машинный перевод) языках;
* единая нормализованная схема для всех таблиц, временные периоды разобраны, символы пропущенных значений сохранены;
* воспроизводимая сборка из открытых источников с версионируемой памятью переводов.

## Скачать

Готовая база данных публикуется в [релизах](https://github.com/opendataam/arm-statbank-db/releases/latest):

| Файл | Содержимое |
|---|---|
| `armstat.duckdb` | База данных DuckDB (~31 МБ) |
| `armstat-parquet.zip` | Те же данные в Parquet; `IMPORT DATABASE 'armstat-parquet'` воссоздает базу |
| `SHA256SUMS` | Контрольные суммы |

DuckDB может обращаться к ней и без скачивания:

```sql
INSTALL httpfs; LOAD httpfs;
ATTACH 'https://github.com/opendataam/arm-statbank-db/releases/latest/download/armstat.duckdb' AS armstat (READ_ONLY);
USE armstat;
SELECT table_id, title_en FROM catalog LIMIT 5;
```

## Быстрый старт

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

## Документация

| | English | Հայերեն | Русский |
|---|---|---|---|
| О данных | [data.md](docs/en/data.md) | [data.md](docs/hy/data.md) | [data.md](docs/ru/data.md) |
| Справочник по базе данных | [database.md](docs/en/database.md) | [database.md](docs/hy/database.md) | [database.md](docs/ru/database.md) |
| Сопровождение | [maintenance.md](docs/en/maintenance.md) | [maintenance.md](docs/hy/maintenance.md) | [maintenance.md](docs/ru/maintenance.md) |
| Каталог таблиц (генерируется автоматически) | [catalog.md](docs/en/catalog.md) | [catalog.md](docs/hy/catalog.md) | [catalog.md](docs/ru/catalog.md) |

## Как собирается база

```
statbank-parser exports (English, JSON-stat 2) ─┐
Statbank PX-Web API (Armenian metadata, trees) ─┼─> armstat-db build ─> build/armstat.duckdb
data/translations/*.jsonl (translation memory) ─┘
```

1. **Значения и английские метаданные** берутся из выгрузок
   [statbank-parser](https://github.com/opendataam/statbank-parser) — полных загрузок
   всех таблиц в формате JSON-stat 2.
2. **Армянские метаданные** (названия, подписи измерений и их значений, единицы измерения,
   примечания) и дерево тем загружаются из API Statbank командой `armstat-db fetch` и
   кэшируются в `data/source/api/`. В обоих языках используются одни и те же коды, поэтому
   тексты сопоставляются по коду.
3. **Переводы**: недостающие английские тексты переводятся с армянского, русские — с
   официального английского (или с армянского). Переводы хранятся в `data/translations/` и
   повторно используются при каждой сборке.

## Команды

| Команда | Описание |
|---|---|
| `armstat-db fetch` | Загрузить армянские метаданные и деревья тем (с кэшированием) |
| `armstat-db fetch-values` / `align` | Проверить по данным соответствие армянских и английских категорий |
| `armstat-db refetch TABLE` | Заменить некорректную выгрузку парсера полной таблицей из API |
| `armstat-db collect` | Вывести список текстов, которых нет в памяти переводов |
| `armstat-db translate` | Перевести их через Claude API (`ANTHROPIC_API_KEY`) |
| `armstat-db batches` / `merge-batches` | Перевод через файлы — для людей или агентов |
| `armstat-db build` | Собрать `build/armstat.duckdb` |
| `armstat-db validate` | Проверки согласованности и покрытие переводами |
| `armstat-db qa` | Вывести отчет о несогласованных подписях в языковых версиях Армстата |
| `armstat-db release` | Подготовить файлы релиза в `build/release` |
| `armstat-db docs` | Заново сгенерировать `docs/*/catalog.md` |
| `armstat-db export TABLE --lang ru -o file.csv` | Выгрузить одну таблицу с подписями (CSV/Parquet) |

## Структура репозитория

```
arm-statbank-db/
├── src/armstat_db/          # Python-пакет (CLI, загрузчики, сборка, перевод)
│   ├── sql/schema.sql       # схема базы данных
│   └── sql/views.sql        # представления и макросы
├── data/
│   ├── source/api/          # кэш метаданных PX-Web API (таблицы hy, деревья hy/en)
│   └── translations/        # память переводов, глоссарий, руководство по стилю
├── docs/{en,hy,ru}/         # документация на трех языках
├── tests/                   # набор тестов pytest с синтетическим снимком данных
├── Makefile
└── pyproject.toml
```

## Качество перевода

Русские тексты и английские тексты с пометкой `en_machine` — это машинный перевод,
выполненный большой языковой моделью (Claude) и проверенный автоматически (полнота,
алфавит, коды), но не вычитанный переводчиком. Это не официальные переводы Армстата.
Исправления приветствуются: отредактируйте `data/translations/*.jsonl` и установите
`"reviewed": true`.

## Лицензия

Код: MIT. Статистические данные: © Статистический комитет Республики Армения — при
использовании данных указывайте источник: «Armstat, Statbank, https://statbank.armstat.am».
