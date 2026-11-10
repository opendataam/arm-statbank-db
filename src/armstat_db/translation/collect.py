"""Write the texts that are not yet in the translation memory to ``pending/{pair}.jsonl``."""

from __future__ import annotations

import json

from ..config import Paths


def collect_pending(paths: Paths) -> dict:
    from ..build import collect_missing  # local import: build imports this package

    resolver, _ = collect_missing(paths)
    out_dir = paths.translations_dir / "pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for pair, items in resolver.missing.items():
        path = out_dir / f"{pair}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for source in sorted(items):
                fh.write(json.dumps({"pair": pair, "source": source,
                                     "context": items[source]}, ensure_ascii=False) + "\n")
        stats[pair] = {"texts": len(items), "chars": sum(len(s) for s in items),
                       "file": str(path)}
    return stats
