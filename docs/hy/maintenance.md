# Սպասարկում

## Պահանջներ

* Python ≥ 3.10, [uv](https://docs.astral.sh/uv/) (կամ pip)
* [statbank-parser](https://github.com/opendataam/statbank-parser)-ի տեղային պատճենը՝
  `indicators.jsonl` ֆայլով և `exports/` թղթապանակով (լռելյայն տեղադրությունը՝
  `../statbank-parser`, կամ նշեք `--parser-dir` / `STATBANK_PARSER_DIR`)
* Ցանցային հասանելիություն դեպի statbank.armstat.am՝ միայն `fetch`-ի համար

```bash
make install            # .venv՝ փաթեթով և dev/translate լրացուցիչ կախվածություններով
```

## Թարմացման ցիկլ

```bash
# 1. թարմացնել անգլերեն տվյալների պատկերը (statbank-parser պահոցում)
python3 -m statbank_parser.cli list-indicators > indicators.jsonl
#    և նորից արտահանել թարմացված աղյուսակները (տե՛ս statbank-parser-ի README-ն)

# 2. թարմացնել հայերեն մետատվյալները և թեմաների ծառերը (≈ 30 րոպե, հարցումների հաճախականությունը սահմանափակված է)
armstat-db fetch --refresh

# 2a. ստուգել հայերեն և անգլերեն կատեգորիաների համապատասխանությունը (≈ 15 րոպե)
armstat-db fetch-values --refresh     # հայերեն արժեքներ -> build/cache (commit չի արվում)
armstat-db align                      # -> data/source/api/hy/alignment.json
armstat-db refetch TABLE_ID …         # փոխարինել սխալ/հնացած արտահանումները, ապա կրկին align

# 3. գտնել դեռևս չթարգմանված տեքստերը
armstat-db collect

# 4. թարգմանել դրանք (տարբերակներից մեկով)
armstat-db translate                     # Claude API, պահանջում է ANTHROPIC_API_KEY
armstat-db batches && …translate files… && armstat-db merge-batches --engine NAME

# 5. կառուցել, ստուգել և նորից ստեղծել կատալոգը
armstat-db build
armstat-db validate
armstat-db qa                         # անվանումների անհամապատասխանություններ -> build/qa/label_swaps.tsv
armstat-db docs
pytest
```

`fetch`-ը յուրաքանչյուր աղյուսակ քեշավորում է `data/source/api/hy/tables/` թղթապանակում․
առանց `--refresh`-ի ներբեռնվում են միայն նոր աղյուսակները։ PX-Web API-ն մեկ IP հասցեից
թույլատրում է 10 վայրկյանում 10 հարցում և մեկ հարցման մեջ 100 000 բջիջ
(`/api/v1/en/?config`)․ `fetch`-ը սահմանափակում է իրեն 10 վայրկյանում 9 հարցումով
(`--max-calls`, `--period`), HTTP 429 պատասխանի դեպքում կրկնում է հարցումը, իսկ
`fetch-values`-ը մեծ աղյուսակները բաժանում է մի քանի հարցման։

## Մշակման շղթա

```
statbank-parser exports (en, JSON-stat 2) ─┐
PX-Web API: hy metadata + hy/en trees ─────┼─> sources.py ─> build.assemble() ─> DuckDB
translation memory (data/translations) ────┘                  │
                                                               └─> missing texts ─> collect
```

| Մոդուլ | Դեր |
|---|---|
| `pxweb.py` | API կլիենտ (հարցումների սահմանափակում, կրկնակի փորձեր), վեբ URL ↔ API ուղի |
| `fetch.py` | Ներբեռնում է ծառերը և յուրաքանչյուր աղյուսակի հայերեն մետատվյալները |
| `align.py` | Ներբեռնում է հայերեն արժեքները, ստուգում/վերականգնում է կատեգորիաների համապատասխանությունը․ սխալ արտահանումների `refetch` |
| `qa.py` | Հաշվետվություն Armstat-ի աղբյուրներում հայերեն/անգլերեն անվանումների անհամապատասխանությունների մասին |
| `catalog.py` | Կարդում է `indicators.jsonl`-ը, գտնում է արտահանման ֆայլերը (նույն անվանակարգմամբ, ինչ statbank-parser-ում) |
| `jsonstat.py` | JSON-stat 2 վերլուծիչ (parser) |
| `sources.py` | Միավորում է անգլերեն արտահանումները, հայերեն մետատվյալները և ծառերը |
| `translation/resolve.py` | Կանոններ, որոնք ընտրում են պաշտոնական կամ մեքենայական թարգմանության տեքստը |
| `translation/memory.py` | Թարգմանությունների հիշողություն (`*.jsonl`) |
| `translation/llm.py` | Claude API-ի backend՝ `translate`-ի համար |
| `translation/batches.py` | Ֆայլային փաթեթներ (batches) API հասանելիություն չունեցող թարգմանիչների համար |
| `build.py`, `sql/schema.sql`, `sql/views.sql` | Տվյալների բազայի կառուցում |
| `validate.py` | Համաձայնեցվածության ստուգումներ |
| `docs.py`, `export.py` | Կատալոգի էջեր, առանձին աղյուսակի արտահանում |

## Թարգմանությունների հիշողություն

`data/translations/{hy-en,hy-ru,en-ru}.jsonl` – յուրաքանչյուր տողում մեկ JSON օբյեկտ,
դասավորված ըստ սկզբնական տեքստի․

```json
{"source": "Livestock", "target": "Поголовье скота", "engine": "…", "reviewed": false}
```

* Բանալին նորմալացված սկզբնական տեքստն է, ուստի բազմաթիվ աղյուսակներում հանդիպող տեքստը
  թարգմանվում է մեկ անգամ։
* Թարգմանությունն ուղղելու համար խմբագրեք `target`-ը և նշեք `"reviewed": true`․ ստուգված
  գրառումները երբեք չեն վերագրանցվում `translate` կամ `merge-batches` հրամաններով։
* Հաստատուն տերմինները գրանցվում են `glossary.tsv` ֆայլում, կանոնները՝ `STYLE.md` ֆայլում։
* Հայերեն տեքստի `hy-ru` գրառումը գերակայում է դրա անգլերեն տեքստի `en-ru` գրառման
  նկատմամբ․ օգտագործեք այն, երբ Armstat-ի անգլերեն տեքստը սխալ է կամ երկիմաստ։
* `merge-batches`-ը մերժում է այն փաթեթային ֆայլը, որի նույնացուցիչները (ids) թվում են
  տեղաշարժված (սկզբնական տեքստի սկզբում եղած կոդերը, օրինակ՝ `17.21`, պետք է հայտնվեն նաև
  թարգմանության սկզբում)։
* Խմբագրելուց հետո գործարկեք `armstat-db build`․ այլ քայլ անհրաժեշտ չէ։

## Ստուգումներ

`armstat-db validate`-ը ստուգում է բջիջների քանակը, բացակայող արժեքների
համաձայնեցվածությունը, փոփոխականների չափերը, թեմաների ծառը, անգլերեն/ռուսերեն տեքստերում
հայատառ տեքստի բացակայությունը և հաշվետվություն է տալիս թարգմանությունների ծածկույթի մասին։
`ERROR` տողերի առկայության դեպքում հրամանն ավարտվում է 1 ելքի կոդով։

## Թողարկում

Տվյալների բազայի ֆայլը commit չի արվում (`build/` թղթապանակն անտեսվում է)։ Կառուցումից հետո՝

```bash
armstat-db release        # build/release: armstat.duckdb, armstat-parquet.zip, SHA256SUMS
gh release create vX.Y.Z build/release/* --title "…" --notes-file NOTES.md
```

Նախապես commit արեք թարմացված `data/` և `docs/` ֆայլերը և թարմացրեք `CHANGELOG.md`-ը․
թողարկման tag-ը պետք է ցույց տա այն commit-ը, որից կառուցվել է բազան։
