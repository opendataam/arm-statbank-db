"""Tiny synthetic Statbank snapshot used by the tests (no network access)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from armstat_db.catalog import load_indicators, table_cache_key
from armstat_db.config import Paths

FOLDER = "6 Agriculture, forestry and fishing"
URL = ("https://statbank.armstat.am/pxweb/en/ArmStatBank/"
       "ArmStatBank__6 Agriculture, forestry and fishing/AF-1.px/")


def livestock_en() -> dict:
    return {
        "version": "2.0", "class": "dataset",
        "label": "Livestock by marzes, types and years",
        "updated": "2012-07-10T01:51:00Z",
        "role": {"metric": ["ContentsCode"]},
        "id": ["ContentsCode", "marzes", "types", "years"],
        "size": [1, 2, 2, 3],
        "dimension": {
            "ContentsCode": {"label": "EliminatedContents", "category": {
                "index": {"EliminatedValue": 0}, "label": {"EliminatedValue": "Livestock"},
                "unit": {"EliminatedValue": {"base": "1000 heads", "decimals": 1}}}},
            "marzes": {"label": "marzes", "category": {
                "index": {"0": 0, "1": 1},
                "label": {"0": "Republic of Armenia", "1": "Yerevan City"}},
                "extension": {"elimination": False}},
            "types": {"label": "types", "category": {
                "index": {"0": 0, "1": 1}, "label": {"0": "Cattle", "1": "Pigs"}}},
            "years": {"label": "years", "category": {
                "index": {"0": 0, "1": 1, "2": 2},
                "label": {"0": "2022", "1": "2023", "2": "2024"}}},
        },
        "extension": {"px": {"decimals": 1, "official-statistics": False, "language": "en",
                             "contents": "Livestock",
                             "description": "Livestock by marzes, types and years",
                             "heading": ["years"], "stub": ["marzes", "types"],
                             "matrix": "AF-1", "subject-code": "AF-1",
                             "subject-area": "AGRICULTURE"}},
        "value": [1.0, 2.0, 3.0, 4.0, None, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, None],
        "status": {"4": "..", "11": "-"},
        "note": ["*Preliminary data"],
    }


def livestock_hy_cache(api_path: str) -> dict:
    return {
        "api_path": api_path, "lang": "hy", "fetched": "2026-11-10T00:00:00+00:00",
        "metadata": {"title": "Անասուններ", "variables": [
            {"code": "marzes", "text": "ըստ մարզերի", "values": ["0", "1"],
             "valueTexts": ["Հայաստանի Հանրապետություն", "ք. Երևան"]},
            {"code": "types", "text": "ըստ տեսակների", "values": ["0", "1"],
             "valueTexts": ["Խոշոր եղջերավոր", "Խոզեր"]},
            {"code": "years", "text": "ըստ տարիների", "values": ["0", "1", "2"],
             "valueTexts": ["2022", "2023", "2024"]},
        ]},
        "head": {
            "version": "2.0", "class": "dataset", "label": "Անասուններ",
            "id": ["ContentsCode", "marzes", "types", "years"], "size": [1, 1, 1, 1],
            "role": {"metric": ["ContentsCode"]},
            "dimension": {
                "ContentsCode": {"label": "EliminatedContents", "category": {
                    "index": {"EliminatedValue": 0},
                    "label": {"EliminatedValue": "Գյուղատնտեսական կենդանիներ"},
                    "unit": {"EliminatedValue": {"base": "հազ. գլուխ", "decimals": 1}}}},
                "marzes": {"label": "ըստ մարզերի", "category": {"index": {"0": 0},
                                                               "label": {"0": "x"}}},
                "types": {"label": "ըստ տեսակների", "category": {"index": {"0": 0},
                                                                "label": {"0": "x"}}},
                "years": {"label": "ըստ տարիների", "category": {"index": {"0": 0},
                                                               "label": {"0": "2022"}}},
            },
            "extension": {"px": {"contents": "Գյուղատնտեսական կենդանիներ",
                                 "subject-area": "Գյուղատնտեսություն",
                                 "heading": ["years"], "stub": ["marzes", "types"]}},
            "note": ["*Նախնական տվյալներ"],
        },
    }


@pytest.fixture()
def snapshot(tmp_path: Path) -> Paths:
    parser = tmp_path / "statbank-parser"
    (parser / "exports").mkdir(parents=True)
    (parser / "indicators.jsonl").write_text(json.dumps({
        "id": "AF-1", "title": "Livestock by marzes, types and years", "url": URL,
        "topic": "6. Agriculture, forestry and fishing", "subtopics": []}) + "\n")
    paths = Paths(parser_dir=parser, source_dir=tmp_path / "source",
                  translations_dir=tmp_path / "translations", build_dir=tmp_path / "build")
    ind = load_indicators(paths.indicators)[0]
    ind.export_file(paths.exports).write_text(json.dumps(livestock_en()))

    for lang, text, title in (("en", "6. Agriculture, forestry and fishing",
                               "Livestock by marzes, types and years"),
                              ("hy", "6. Գյուղատնտեսություն", "Անասունների գլխաքանակը")):
        d = paths.api_cache(lang)
        d.mkdir(parents=True)
        (d / "tree.json").write_text(json.dumps({"nodes": [
            {"path": FOLDER, "parent": None, "position": 5, "type": "l", "id": FOLDER,
             "text": text},
            {"path": ind.api_path, "parent": FOLDER, "position": 0, "type": "t",
             "id": "AF-1.px", "text": title},
        ]}, ensure_ascii=False))
    tables = paths.api_cache("hy") / "tables"
    tables.mkdir()
    (tables / f"{table_cache_key(ind.api_path)}.json").write_text(
        json.dumps(livestock_hy_cache(ind.api_path), ensure_ascii=False))

    paths.translations_dir.mkdir()
    entries = {
        "en-ru": {
            "Livestock by marzes, types and years": "Поголовье скота по марзам, видам и годам",
            "Livestock": "Скот", "1000 heads": "тыс. голов", "AGRICULTURE": "СЕЛЬСКОЕ ХОЗЯЙСТВО",
            "*Preliminary data": "*Предварительные данные", "marzes": "марзы",
            "types": "виды", "years": "годы", "Republic of Armenia": "Республика Армения",
            "Yerevan City": "г. Ереван", "Cattle": "Крупный рогатый скот", "Pigs": "Свиньи",
            "Agriculture, forestry and fishing": "Сельское хозяйство, лесное и рыбное хозяйство",
        },
    }
    for pair, items in entries.items():
        with open(paths.translations_dir / f"{pair}.jsonl", "w", encoding="utf-8") as fh:
            for s, t in sorted(items.items()):
                fh.write(json.dumps({"source": s, "target": t, "engine": "test",
                                     "reviewed": False}, ensure_ascii=False) + "\n")
    return paths
