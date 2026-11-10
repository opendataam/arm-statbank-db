import csv

import duckdb

from armstat_db.build import build_database
from armstat_db.export import export_table
from armstat_db.translation.collect import collect_pending
from armstat_db.validate import validate


def test_build_end_to_end(snapshot, tmp_path):
    report = build_database(snapshot)
    assert report["datasets"] == 1 and report["observations"] == 12
    db = snapshot.database
    con = duckdb.connect(str(db), read_only=True)
    try:
        row = con.execute("""SELECT title_hy, title_en, title_ru, unit_hy, unit_ru, note_ru,
                                    first_period, last_period, n_values, en_origin
                             FROM datasets""").fetchone()
        assert row == ("Անասունների գլխաքանակը", "Livestock by marzes, types and years",
                       "Поголовье скота по марзам, видам и годам", "հազ. գլուխ", "тыс. голов",
                       "*Предварительные данные", "2022", "2024", 10, "armstat")
        # obs_id 5 = Republic of Armenia / Pigs / 2024
        assert con.execute("""SELECT dims, period, value FROM observations
                              WHERE obs_id = 5""").fetchone() == (
            {"marzes": "0", "types": "1", "years": "2"}, "2024", 6.0)
        labels = con.execute("""SELECT labels FROM table_data('AF-1', lang := 'ru')
                                WHERE obs_id = 5""").fetchone()[0]
        assert labels == {"marzes": "Республика Армения", "types": "Свиньи", "years": "2024"}
        assert con.execute("SELECT status FROM observations WHERE obs_id = 4").fetchone() == ("..",)
        assert con.execute("SELECT count(*) FROM data_long").fetchone() == (36,)
        assert con.execute("SELECT topic_ru FROM catalog").fetchone() == (
            "Сельское хозяйство, лесное и рыбное хозяйство",)
    finally:
        con.close()

    problems = validate(db)
    assert not [p for p in problems if p.startswith("ERROR")], problems

    out = tmp_path / "af1.csv"
    export_table(db, "AF-1", "hy", str(out))
    with open(out, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["ըստ մարզերի"] == "Հայաստանի Հանրապետություն" and rows[0]["value"] == "1.0"


def test_collect_reports_untranslated(snapshot):
    stats = collect_pending(snapshot)
    # every text in the fixture is translated except the Armenian-only subject title
    assert stats["en-ru"]["texts"] == 0
    assert stats["hy-en"]["texts"] == 0


def test_docs_catalog(snapshot, tmp_path):
    from armstat_db.docs import generate_docs

    build_database(snapshot)
    written = generate_docs(snapshot, docs_dir=tmp_path / "docs")
    assert {p.parent.name for p in written} == {"en", "hy", "ru"}
    ru = (tmp_path / "docs" / "ru" / "catalog.md").read_text(encoding="utf-8")
    assert "Поголовье скота по марзам, видам и годам" in ru and "`AF-1`" in ru


def test_release_assets(snapshot):
    from armstat_db.release import make_release

    build_database(snapshot)
    names = [p.name for p in make_release(snapshot)]
    assert names == ["armstat.duckdb", "armstat-parquet.zip", "SHA256SUMS"]
