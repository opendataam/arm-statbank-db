# arm-statbank-db

[English](README.md) · **Հայերեն** · [Русский](README.ru.md)

[Statbank](https://statbank.armstat.am)-ի՝ Հայաստանի Հանրապետության վիճակագրական կոմիտեի
(Armstat) վիճակագրական տվյալների բազայի եռալեզու (հայերեն, անգլերեն, ռուսերեն) տվյալների
բազա [DuckDB](https://duckdb.org) ձևաչափով։

* **825 աղյուսակ** (824 եզակի), 137 թեմա, 2037 փոփոխական, ~33 000 կատեգորիա,
  ~862 000 դիտարկում․
* բոլոր տեքստերը՝ **հայերենով** (պաշտոնական), **անգլերենով** (պաշտոնական, մեքենայական
  թարգմանությամբ այն դեպքերում, երբ Armstat-ը թարգմանություն չունի) և **ռուսերենով**
  (մեքենայական թարգմանություն)․
* միասնական նորմալացված սխեմա բոլոր աղյուսակների համար, ժամանակաշրջանները վերլուծված են,
  բացակայող արժեքների պայմանական նշանները պահպանված են․
* վերարտադրելի կառուցում բաց աղբյուրներից՝ տարբերակավորված թարգմանությունների հիշողությամբ։

## Ներբեռնում

Պատրաստի տվյալների բազան հրապարակվում է [թողարկումներում](https://github.com/opendataam/arm-statbank-db/releases/latest)՝

| Ֆայլ | Բովանդակություն |
|---|---|
| `armstat.duckdb` | DuckDB տվյալների բազա (~31 ՄԲ) |
| `armstat-parquet.zip` | Նույն տվյալները Parquet ձևաչափով․ `IMPORT DATABASE 'armstat-parquet'`-ը վերստեղծում է բազան |
| `SHA256SUMS` | Ստուգիչ գումարներ |

DuckDB-ն կարող է հարցումներ կատարել նաև առանց ներբեռնելու՝

```sql
INSTALL httpfs; LOAD httpfs;
ATTACH 'https://github.com/opendataam/arm-statbank-db/releases/latest/download/armstat.duckdb' AS armstat (READ_ONLY);
USE armstat;
SELECT table_id, title_en FROM catalog LIMIT 5;
```

## Արագ մեկնարկ

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

## Փաստաթղթեր

| | English | Հայերեն | Русский |
|---|---|---|---|
| Տվյալների մասին | [data.md](docs/en/data.md) | [data.md](docs/hy/data.md) | [data.md](docs/ru/data.md) |
| Տվյալների բազայի տեղեկատու | [database.md](docs/en/database.md) | [database.md](docs/hy/database.md) | [database.md](docs/ru/database.md) |
| Սպասարկում | [maintenance.md](docs/en/maintenance.md) | [maintenance.md](docs/hy/maintenance.md) | [maintenance.md](docs/ru/maintenance.md) |
| Աղյուսակների կատալոգ (ավտոմատ ստեղծվող) | [catalog.md](docs/en/catalog.md) | [catalog.md](docs/hy/catalog.md) | [catalog.md](docs/ru/catalog.md) |

## Ինչպես է կառուցվում

```
statbank-parser exports (English, JSON-stat 2) ─┐
Statbank PX-Web API (Armenian metadata, trees) ─┼─> armstat-db build ─> build/armstat.duckdb
data/translations/*.jsonl (translation memory) ─┘
```

1. **Արժեքները և անգլերեն մետատվյալները** վերցվում են
   [statbank-parser](https://github.com/opendataam/statbank-parser)-ի արտահանումներից՝
   յուրաքանչյուր աղյուսակի ամբողջական JSON-stat 2 ներբեռնումներից։
2. **Հայերեն մետատվյալները** (վերնագրեր, փոփոխականների և արժեքների անվանումներ, չափման
   միավորներ, ծանոթագրություններ) և թեմաների ծառը ներբեռնվում են Statbank API-ից
   `armstat-db fetch` հրամանով և քեշավորվում `data/source/api/` թղթապանակում։ Երկու լեզվային
   տարբերակներն էլ օգտագործում են նույն կոդերը, ուստի տեքստերը միավորվում են ըստ կոդի։
3. **Թարգմանություններ**․ բացակայող անգլերեն տեքստերը թարգմանվում են հայերենից, ռուսերեն
   տեքստերը՝ պաշտոնական անգլերենից (կամ հայերենից)։ Դրանք պահվում են `data/translations/`
   թղթապանակում և վերաօգտագործվում յուրաքանչյուր կառուցման ժամանակ։

## Հրամաններ

| Հրաման | Նկարագրություն |
|---|---|
| `armstat-db fetch` | Ներբեռնում է հայերեն մետատվյալները և թեմաների ծառերը (քեշավորվում են) |
| `armstat-db fetch-values` / `align` | Տվյալների հիման վրա ստուգում է հայերեն և անգլերեն կատեգորիաների համապատասխանությունը |
| `armstat-db refetch TABLE` | Պարսերի սխալ արտահանումը փոխարինում է API-ից ստացված ամբողջական աղյուսակով |
| `armstat-db collect` | Ցուցակագրում է այն տեքստերը, որոնք թարգմանությունների հիշողության մեջ չկան |
| `armstat-db translate` | Թարգմանում է դրանք Claude API-ի միջոցով (`ANTHROPIC_API_KEY`) |
| `armstat-db batches` / `merge-batches` | Ֆայլերի միջոցով թարգմանություն մարդկանց կամ գործակալների համար |
| `armstat-db build` | Կառուցում է `build/armstat.duckdb` ֆայլը |
| `armstat-db validate` | Համաձայնեցվածության ստուգումներ և թարգմանությունների ծածկույթ |
| `armstat-db qa` | Հաշվետվություն է տալիս Armstat-ի լեզվական տարբերակների միջև անվանումների անհամապատասխանությունների մասին |
| `armstat-db release` | Պատրաստում է թողարկման ֆայլերը `build/release`-ում |
| `armstat-db docs` | Նորից ստեղծում է `docs/*/catalog.md` ֆայլերը |
| `armstat-db export TABLE --lang ru -o file.csv` | Արտահանում է մեկ աղյուսակ՝ անվանումներով (CSV/Parquet) |

## Պահոցի կառուցվածք

```
arm-statbank-db/
├── src/armstat_db/          # Python փաթեթ (CLI, բեռնիչներ, կառուցում, թարգմանություն)
│   ├── sql/schema.sql       # տվյալների բազայի սխեմա
│   └── sql/views.sql        # ներկայացումներ (views) և մակրոներ
├── data/
│   ├── source/api/          # PX-Web API-ի քեշավորված մետատվյալներ (hy աղյուսակներ, hy/en ծառեր)
│   └── translations/        # թարգմանությունների հիշողություն, տերմինաբանական բառարան, ոճի ուղեցույց
├── docs/{en,hy,ru}/         # փաստաթղթեր երեք լեզվով
├── tests/                   # pytest թեստերի հավաքածու՝ սինթետիկ տվյալների պատկերով (snapshot)
├── Makefile
└── pyproject.toml
```

## Թարգմանությունների որակ

Ռուսերեն տեքստերը և `en_machine` նշիչով նշված անգլերեն տեքստերը մեքենայական
թարգմանություններ են, որոնք կատարվել են մեծ լեզվական մոդելի (Claude) միջոցով և ստուգվել
ավտոմատ կերպով (ամբողջականություն, գրային համակարգ, կոդեր), սակայն թարգմանիչը դրանք չի
վերանայել։ Դրանք Armstat-ի պաշտոնական թարգմանություններ չեն։ Ուղղումները ողջունելի են․
խմբագրեք `data/translations/*.jsonl` ֆայլերը և նշեք `"reviewed": true`։

## Լիցենզիա

Կոդ՝ MIT։ Վիճակագրական տվյալներ՝ © Հայաստանի Հանրապետության վիճակագրական կոմիտե –
տվյալներն օգտագործելիս նշեք աղբյուրը՝ «Armstat, Statbank, <https://statbank.armstat.am>»։
