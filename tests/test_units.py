import pytest
from conftest import URL, livestock_en

from armstat_db.catalog import ckan_dataset_name, table_cache_key
from armstat_db.jsonstat import first_href, parse_dataset, strip_html
from armstat_db.pxweb import api_path_to_web_url, head_query, web_url_to_api_path
from armstat_db.textutil import (
    fix_homoglyphs,
    has_armenian,
    is_time_dimension,
    needs_translation,
    parse_period,
)
from armstat_db.translation.memory import TranslationMemory
from armstat_db.translation.resolve import Resolver


def test_url_roundtrip():
    path = web_url_to_api_path(URL)
    assert path == "6 Agriculture, forestry and fishing/AF-1.px"
    assert api_path_to_web_url(path, "en") == URL
    with pytest.raises(ValueError):
        web_url_to_api_path("https://example.com/x")


def test_ckan_name_is_stable():
    # must match statbank_parser.ckan.dataset_name (hash of the source URL)
    name = ckan_dataset_name("EF-cpi-mi1", URL)
    assert name.startswith("armstat-ef-cpi-mi1-") and len(name.rsplit("-", 1)[1]) == 10
    assert table_cache_key("a b/EF-gf-3.px") != table_cache_key("c d/EF-gf-3.px")


def test_head_query_selects_first_values():
    q = head_query({"variables": [{"code": "a", "values": ["1", "2"]}]})
    assert q == [{"code": "a", "selection": {"filter": "item", "values": ["1"]}}]


def test_parse_dataset():
    ds = parse_dataset(livestock_en())
    assert [d.code for d in ds.dimensions] == ["marzes", "types", "years"]
    assert ds.unit == "1000 heads" and ds.contents == "Livestock" and ds.decimals == 1
    assert ds.n_cells == 12 and ds.status == {4: "..", 11: "-"}
    obs = list(ds.observations())
    assert obs[5] == (5, {"marzes": "0", "types": "1", "years": "2"}, 6.0, None)
    assert obs[4][2] is None and obs[4][3] == ".."


def test_html_helpers():
    src = "<a href='http://www.mnp.am' >MoE RA</a>"
    assert strip_html(src) == "MoE RA" and first_href(src) == "http://www.mnp.am"


@pytest.mark.parametrize("label,period", [
    ("2015", "2015"), ("2015*", "2015"), ("2015-Q3", "2015-Q3"), ("2015M03", "2015-03"),
    ("January", "--01"), (" august", "--08"), ("Multiyear average values", None),
])
def test_parse_period(label, period):
    assert parse_period(label) == period


def test_time_dimension_detection():
    assert is_time_dimension("years", ["Total"])
    assert is_time_dimension("x", ["2001", "2002", "2003"])
    assert not is_time_dimension("marzes", ["Yerevan", "Lori"])


def test_text_helpers():
    assert has_armenian("ք. Երևան") and not has_armenian("Yerevan")
    assert not needs_translation("2015-2016") and needs_translation("Total")
    assert fix_homoglyphs("H.Тransport") == "H.Transport"      # Cyrillic Т
    assert fix_homoglyphs("Республика") == "Республика"


def test_resolver_rules(tmp_path):
    tm = TranslationMemory(tmp_path)
    tm.add("en-ru", "Cattle", "КРС", "test")
    tm.add("hy-en", "Խոզեր", "Pigs", "test")
    r = Resolver(tm)
    # official English -> Russian from English
    assert r.resolve("Խոշոր", "Cattle").__dict__ == {
        "hy": "Խոշոր", "en": "Cattle", "ru": "КРС", "en_machine": False}
    # Armenian text in the English slot -> machine English, Russian from Armenian
    res = r.resolve(None, "Խոզեր")
    assert (res.hy, res.en, res.ru, res.en_machine) == ("Խոզեր", "Pigs", None, True)
    assert "Խոզեր" in r.missing["hy-ru"]
    # numbers are copied
    assert r.resolve("2020", "2020").ru == "2020"
    # unknown English is reported as missing
    assert r.resolve(None, "Sheep").ru is None and "Sheep" in r.missing["en-ru"]


def test_memory_roundtrip(tmp_path):
    tm = TranslationMemory(tmp_path)
    assert tm.add("en-ru", " Total\r\n", "Всего", "x")
    assert not tm.add("en-ru", "Total", "Итого", "y")           # no silent overwrite
    tm.save()
    assert TranslationMemory(tmp_path).get("en-ru", "Total") == "Всего"


def test_batch_alignment_score():
    from armstat_db.translation.batches import alignment_score

    items = {0: {"source": "17.21 Manufacture of paper"}, 1: {"source": "Total"}}
    assert alignment_score(items, {0: "17.21 Производство бумаги", 1: "Всего"}) == (1, 1)
    assert alignment_score(items, {0: "Осадки", 1: "Всего"}) == (0, 1)


def test_hy_ru_overrides_en_ru(tmp_path):
    tm = TranslationMemory(tmp_path)
    tm.add("en-ru", "Robbery", "Грабеж", "test")
    tm.add("hy-ru", "Գողություն", "Кража", "test")
    r = Resolver(tm)
    assert r.resolve("Գողություն", "Robbery").ru == "Кража"
    assert r.resolve("Ավազակություն", "Robbery").ru == "Грабеж"


def test_transliteration():
    from armstat_db.qa import transliterate

    assert transliterate("Դիլիջան") == "dilijan"
    assert transliterate("Գյումրի") == "gyumri"


def test_merge_chunks():
    from armstat_db.jsonstat import merge_chunks

    def chunk(codes, values):
        return {"id": ["a", "b"], "size": [len(codes), 2],
                "dimension": {"a": {"category": {"index": {c: i for i, c in enumerate(codes)},
                                                 "label": {c: c.upper() for c in codes}}},
                              "b": {"category": {"index": {"x": 0, "y": 1},
                                                 "label": {"x": "X", "y": "Y"}}}},
                "value": values, "status": {"1": ".."}}
    m = merge_chunks([chunk(["p", "q"], [1, None, 3, 4]), chunk(["r"], [5, 6])])
    assert m["size"] == [3, 2] and m["value"] == [1, None, 3, 4, 5, 6]
    assert m["status"] == {"1": "..", "5": ".."}
    assert list(m["dimension"]["a"]["category"]["label"]) == ["p", "q", "r"]


def _hy_chunk(en: dict, marz_order: list[str], extra_year: bool = False) -> dict:
    """Armenian JSON-stat with the same data, marzes listed in ``marz_order``."""
    from itertools import product

    years = ["0", "1", "2"] + (["3"] if extra_year else [])
    year_labels = {"0": "2022", "1": "2023", "2": "2024", "3": "2025"}
    values = []
    en_vals = en["value"]
    for m, t, y in product(marz_order, ["0", "1"], years):
        values.append(None if y == "3" else en_vals[int(m) * 6 + int(t) * 3 + int(y)])
    return {"id": ["ContentsCode", "marzes", "types", "years"],
            "size": [1, 2, 2, len(years)],
            "dimension": {
                "ContentsCode": {"category": {"index": {"EliminatedValue": 0}}},
                "marzes": {"category": {"index": {"0": 0, "1": 1},
                                        "label": {"0": "Ա", "1": "Բ"}}},
                "types": {"category": {"index": {"0": 0, "1": 1},
                                       "label": {"0": "Գ", "1": "Դ"}}},
                "years": {"category": {"index": {y: i for i, y in enumerate(years)},
                                       "label": {y: year_labels[y] for y in years}}}},
            "value": values}


def test_align_identity_and_swap():
    from armstat_db.align import align_table

    en = livestock_en()
    same = align_table(en, [_hy_chunk(en, ["0", "1"])])
    assert same["agreement_before"] == 1.0 and same["remap"] == {}
    swapped = align_table(en, [_hy_chunk(en, ["1", "0"], extra_year=True)])
    assert swapped["agreement_after"] == 1.0
    assert swapped["remap"] == {"marzes": {"0": "1", "1": "0"}}
