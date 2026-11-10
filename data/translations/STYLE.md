# Translation style guide

Applies to every machine or human translation stored in `data/translations/*.jsonl`.
The texts are metadata of official statistics of Armenia (Armstat Statbank): table titles,
dimension names, category labels, units, footnotes and data sources.

## General

- Translate completely and faithfully. Do not summarise, explain, add or drop information.
- Use established terminology of official statistics: SNA 2008 / СНС 2008, NACE Rev.2,
  ISIC, COICOP, HS, ILO definitions; Russian as in Rosstat and CIS-Stat yearbooks.
- Use `glossary.tsv` for fixed terms (country, marzes, currency, survey names).
- Keep unchanged: numbers, years, ranges, codes and classification prefixes (`A.`, `B-E`,
  `01-03`, `(A1)`), abbreviations of classifications (NACE, COICOP, ISIC, HS, ESA),
  chemical formulas, footnote markers (`*`, `**`, `¹`), units such as `%`, `‰`, `km`.
- Keep line breaks and list structure of footnotes.
- Keep the capitalisation pattern: dimension names in PX files are often lower case
  ("marzes", "types of economic activity") – keep them lower case in the translation;
  ALL-CAPS titles stay ALL CAPS.
- If the source has an obvious typo ("Emploment"), translate the intended word.
- Never leave words of the source language untranslated, except proper names that have no
  translation, codes and abbreviations listed above.

## Russian

- Table titles follow the PX pattern "*Subject* by *dim1*, *dim2* and *dim3*" ->
  "*Предмет* по *dim1*, *dim2* и *dim3*", e.g. "Livestock by marzes, types and years" ->
  "Поголовье скота по марзам, видам и годам".
- marz -> марз; "Aragatsotn Marz" -> "марз Арагацотн"; "Yerevan City" -> "г. Ереван";
  "marzes" -> "марзы", "by marzes" -> "по марзам".
- Towns: Гюмри, Ванадзор, Вагаршапат (Эчмиадзин), Абовян, Капан, Раздан (Hrazdan),
  Армавир, Арташат, Аштарак, Гавар, Горис, Дилижан, Иджеван, Ехегнадзор, Севан, Чаренцаван,
  Масис, Мецамор, Сисиан, Алаверди, Степанаван, Спитак, Ташир, Берд, Ноемберян, Мартуни,
  Варденис, Джермук, Агарак, Мегри, Каджаран, Дастакерт, Ахтала, Туманян, Шамлуг, Ноемберян.
- Units: "thousand AMD"/"thousand drams" -> "тыс. драмов"; "million AMD" -> "млн драмов";
  "billion AMD" -> "млрд драмов"; "1000 US dollars" -> "тыс. долларов США";
  "persons" -> "человек"; "thousand persons" -> "тыс. человек"; "units" -> "единиц";
  "tonnes"/"tons" -> "тонн"; "hectares" -> "гектаров"; "as of January 1" -> "на 1 января";
  "per 1000 population" -> "на 1000 человек населения".
- Common abbreviations: GDP -> ВВП, CPI -> ИПЦ, PPI -> ИЦП, SNA -> СНС, VAT -> НДС,
  EAEU -> ЕАЭС, CIS -> СНГ, EU -> ЕС, RA -> РА, NGO -> НПО, PPP -> ППС.
- "Total" -> "Всего"; "of which" -> "в том числе"; "including" -> "включая";
  "other" -> "прочие"/"другие" by context; "not specified" -> "не указано".
- Use correct grammatical case and agreement; prefer neutral official style.

## English (from Armenian)

- Follow Armstat's own English usage where it exists elsewhere in the database
  (e.g. "Republic of Armenia", "Yerevan City", "Aragatsotn Marz", "by marzes").
- Armenian place names in Armstat transliteration: Gyumri, Vanadzor, Vagharshapat,
  Hrazdan, Abovyan, Kapan, Ijevan, Yeghegnadzor, Goris, Dilijan, Sevan, Gavar, Artashat.

## File format

Batch input (`pending/batches/{pair}-NNN.jsonl`): `{"id", "pair", "source", "context"}`;
`context` is the title of the table where the text occurs – use it to choose the meaning,
never translate it. Batch output (`{pair}-NNN.out.jsonl`, may be split into
`.out.jsonl`, `.out2.jsonl`, ...): one `{"id": n, "target": "..."}` per input id.
