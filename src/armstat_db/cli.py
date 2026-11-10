"""Command-line interface: ``armstat-db <command>`` (or ``python -m armstat_db``)."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import default_paths


def _paths(args):
    return default_paths(args.parser_dir, args.source_dir, args.translations_dir, args.build_dir)


def cmd_fetch(args) -> int:
    from .fetch import fetch_all

    tree_langs = () if args.no_tree else tuple(args.tree_lang)
    errors = fetch_all(_paths(args), langs=tuple(args.lang), tree_langs=tree_langs,
                       refresh=args.refresh, workers=args.workers,
                       max_calls=args.max_calls, period=args.period)
    failed = sum(len(e) for e in errors.values())
    print(json.dumps({lang: len(e) for lang, e in errors.items()}))
    return 1 if failed else 0


def cmd_fetch_values(args) -> int:
    from .align import fetch_values

    errors = fetch_values(_paths(args), refresh=args.refresh, max_calls=args.max_calls,
                          period=args.period)
    print(json.dumps({"errors": len(errors)}))
    return 1 if errors else 0


def cmd_refetch(args) -> int:
    from .align import refetch_tables

    for path in refetch_tables(_paths(args), args.tables):
        print(path)
    return 0


def cmd_align(args) -> int:
    from .align import align_all

    print(json.dumps(align_all(_paths(args)), ensure_ascii=False))
    return 0


def cmd_collect(args) -> int:
    from .translation.collect import collect_pending

    stats = collect_pending(_paths(args))
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    return 0


def cmd_translate(args) -> int:
    from .translation.llm import translate_pending

    stats = translate_pending(_paths(args), backend=args.backend, model=args.model,
                              batch_size=args.batch_size, limit=args.limit,
                              pair=args.pair)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_import(args) -> int:
    from .translation.memory import import_batch_results

    stats = import_batch_results(_paths(args), args.files, engine=args.engine)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_batches(args) -> int:
    from .translation.batches import make_batches

    pairs = args.pair or ["hy-en", "hy-ru", "en-ru"]
    print(json.dumps(make_batches(_paths(args), max_chars=args.max_chars, pairs=pairs)))
    return 0


def cmd_merge_batches(args) -> int:
    from .translation.batches import merge_batches

    result = merge_batches(_paths(args), engine=args.engine)
    print(json.dumps(result))
    return 1 if result["rejected"] else 0


def cmd_build(args) -> int:
    from .build import build_database

    report = build_database(_paths(args), output=args.output)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def cmd_validate(args) -> int:
    from .validate import validate

    problems = validate(_paths(args).database if not args.database else args.database)
    for p in problems:
        print(p)
    return 1 if any(p.startswith("ERROR") for p in problems) else 0


def cmd_qa(args) -> int:
    from .qa import write_report

    paths = _paths(args)
    print(json.dumps(write_report(paths.database, paths.build_dir / "qa"), ensure_ascii=False))
    return 0


def cmd_docs(args) -> int:
    from .docs import generate_docs

    written = generate_docs(_paths(args))
    for path in written:
        print(path)
    return 0


def cmd_release(args) -> int:
    from .release import make_release

    for path in make_release(_paths(args)):
        print(path)
    return 0


def cmd_export(args) -> int:
    from .export import export_table

    export_table(_paths(args).database, args.table, args.lang, args.output, wide=not args.long)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="armstat-db", description=__doc__)
    p.add_argument("--parser-dir", help="statbank-parser checkout (default: ../statbank-parser "
                                         "or $STATBANK_PARSER_DIR)")
    p.add_argument("--source-dir", help="cached API metadata (default: data/source)")
    p.add_argument("--translations-dir", help="translation memory (default: data/translations)")
    p.add_argument("--build-dir", help="output directory (default: build)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("fetch", help="download Armenian metadata from the PXWeb API")
    s.add_argument("--lang", action="append", default=None,
                   help="table metadata language(s) (default: hy)")
    s.add_argument("--tree-lang", action="append", default=None,
                   help="navigation tree language(s) (default: hy, en)")
    s.add_argument("--no-tree", action="store_true", help="skip the navigation trees")
    s.add_argument("--refresh", action="store_true", help="re-download cached tables")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--max-calls", type=int, default=9,
                   help="rate limit: requests per --period seconds (default 9 per 10 s)")
    s.add_argument("--period", type=float, default=10.0)
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("fetch-values",
                       help="download Armenian data values (build/cache) for `align`")
    s.add_argument("--refresh", action="store_true")
    s.add_argument("--max-calls", type=int, default=9)
    s.add_argument("--period", type=float, default=10.0)
    s.set_defaults(func=cmd_fetch_values)

    s = sub.add_parser("refetch", help="replace faulty parser exports by complete English "
                                       "tables from the API (data/source/api/en/overrides)")
    s.add_argument("tables", nargs="+", help="table_id(s)")
    s.set_defaults(func=cmd_refetch)

    s = sub.add_parser("align", help="match Armenian and English categories by their data")
    s.set_defaults(func=cmd_align)

    s = sub.add_parser("collect", help="list texts that still need translation")
    s.set_defaults(func=cmd_collect)

    s = sub.add_parser("translate", help="machine-translate pending texts with an LLM API")
    s.add_argument("--backend", choices=["anthropic"], default="anthropic")
    s.add_argument("--model", default=None)
    s.add_argument("--pair", choices=["hy-en", "en-ru", "hy-ru"], action="append")
    s.add_argument("--batch-size", type=int, default=80)
    s.add_argument("--limit", type=int, default=None, help="max texts per pair")
    s.set_defaults(func=cmd_translate)

    s = sub.add_parser("import-translations",
                       help="merge translated batch files into the translation memory")
    s.add_argument("files", nargs="+")
    s.add_argument("--engine", required=True, help="engine/model name recorded in the memory")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("batches",
                       help="split pending texts into files for manual/agent translation")
    s.add_argument("--max-chars", type=int, default=30000)
    s.add_argument("--pair", choices=["hy-en", "hy-ru", "en-ru"], action="append")
    s.set_defaults(func=cmd_batches)

    s = sub.add_parser("merge-batches", help="import translated batch files (*.out.jsonl)")
    s.add_argument("--engine", required=True, help="translator/model recorded in the memory")
    s.set_defaults(func=cmd_merge_batches)

    s = sub.add_parser("build", help="build the DuckDB database")
    s.add_argument("--output", help="database file (default: build/armstat.duckdb)")
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("validate", help="run consistency checks on the database")
    s.add_argument("--database")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("qa", help="report Armenian/English label inconsistencies of Armstat")
    s.set_defaults(func=cmd_qa)

    s = sub.add_parser("docs", help="regenerate the data catalog pages in docs/")
    s.set_defaults(func=cmd_docs)

    s = sub.add_parser("release", help="prepare release assets in build/release")
    s.set_defaults(func=cmd_release)

    s = sub.add_parser("export", help="export one table as CSV/Parquet with labels")
    s.add_argument("table", help="table_id, e.g. EF-cpi-mi1")
    s.add_argument("--lang", choices=["hy", "en", "ru"], default="en")
    s.add_argument("--long", action="store_true", help="long format instead of wide")
    s.add_argument("-o", "--output", required=True, help=".csv or .parquet")
    s.set_defaults(func=cmd_export)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "lang", None) is None and args.command == "fetch":
        args.lang = ["hy"]
    if getattr(args, "tree_lang", None) is None and args.command == "fetch":
        args.tree_lang = ["hy", "en"]
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
