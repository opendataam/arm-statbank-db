"""Quality report on Armstat's own labels: Armenian and English labels that disagree.

The Armenian and English PX files of a table are separate. ``align`` verifies that their
*data* match code by code; this report looks at the *labels* and lists proper names
(towns, countries) whose English label matches the transliterated Armenian label of
another category of the same dimension – a sign that one language version has its labels
shuffled. Which version is right has to be decided case by case (e.g. by the data);
the database keeps both official texts unchanged.

Output: ``build/qa/label_swaps.tsv``.
"""

from __future__ import annotations

import csv
import difflib
import re
from collections import defaultdict
from pathlib import Path

import duckdb

_TRANSLIT = {
    "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "e", "ը": "y",
    "թ": "t", "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "k", "հ": "h",
    "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y", "ն": "n", "շ": "sh", "ո": "o",
    "չ": "ch", "պ": "p", "ջ": "j", "ռ": "r", "ս": "s", "վ": "v", "տ": "t", "ր": "r",
    "ց": "ts", "ւ": "u", "փ": "p", "ք": "k", "օ": "o", "ֆ": "f", "և": "ev",
}
_NAME = re.compile(r"[A-Z][A-Za-z' .()-]{2,38}")


def transliterate(text: str) -> str:
    text = text.lower().replace("ու", "u")
    return "".join(_TRANSLIT.get(ch, ch) for ch in text)


def _similarity(a: str, b: str) -> float:
    a, b = re.sub(r"[^a-z]", "", a.lower()), re.sub(r"[^a-z]", "", b.lower())
    return difflib.SequenceMatcher(None, a, b).ratio()


def find_label_swaps(database: Path) -> list[dict]:
    con = duckdb.connect(str(database), read_only=True)
    try:
        rows = con.execute("""
            SELECT table_id, dim_code, value_code, position, label_hy, label_en
            FROM dimension_values
            WHERE label_hy IS NOT NULL AND NOT en_machine
            ORDER BY table_id, dim_code, position""").fetchall()
    finally:
        con.close()
    dims: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if _NAME.fullmatch(r[5].strip()):
            dims[(r[0], r[1])].append(r)
    found = []
    for (table_id, dim_code), names in dims.items():
        translit = {r[2]: transliterate(r[4]) for r in names}
        for r in names:
            own = _similarity(r[5], translit[r[2]])
            if own >= 0.6:
                continue
            best = max(names, key=lambda w: _similarity(r[5], translit[w[2]]))
            score = _similarity(r[5], translit[best[2]])
            # require the swap to be mutual-ish: the other category's own pair is also poor
            other_own = _similarity(best[5], translit[best[2]])
            if best is not r and score >= 0.8 and other_own < 0.6:
                found.append({
                    "table_id": table_id, "dim_code": dim_code, "value_code": r[2],
                    "label_en": r[5], "label_hy": r[4],
                    "matching_hy_code": best[2], "matching_hy_label": best[4],
                    "score": round(score, 2),
                })
    return found


def write_report(database: Path, out_dir: Path) -> dict:
    swaps = find_label_swaps(database)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "label_swaps.tsv"
    fields = ["table_id", "dim_code", "value_code", "label_en", "label_hy",
              "matching_hy_code", "matching_hy_label", "score"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(swaps)
    return {"label_swaps": len(swaps),
            "dimensions": len({(s["table_id"], s["dim_code"]) for s in swaps}),
            "file": str(path)}
