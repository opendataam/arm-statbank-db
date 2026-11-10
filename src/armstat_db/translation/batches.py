"""File-based translation batches for translators without API access (people or agents).

Workflow::

    armstat-db collect                    # pending/{pair}.jsonl
    armstat-db batches --max-chars 30000  # pending/batches/{pair}-NNN.jsonl
    # translator writes pending/batches/{pair}-NNN.out.jsonl: {"id": n, "target": "..."}
    armstat-db merge-batches --engine "translator name"

Batch items are grouped by their context (the source table), so that all labels of one
table are translated together and consistently.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import Paths
from .memory import PAIRS, TranslationMemory

log = logging.getLogger(__name__)

_CODE_PREFIX = re.compile(r"^\s*\(?([0-9A-Z][0-9.\-]*[0-9])\)?\s")


def alignment_score(items: dict[int, dict], results: dict[int, str]) -> tuple[int, int]:
    """Count sources that start with a numeric code and how many targets keep it.

    A low ratio means that ids of the output file do not match the input (shifted or
    taken from another batch).
    """
    total = kept = 0
    for i, it in items.items():
        m = _CODE_PREFIX.match(it["source"])
        if m and any(ch.isdigit() for ch in m.group(1)) and i in results:
            total += 1
            kept += m.group(1) in results[i][: len(m.group(1)) + 4]
    return kept, total


def _batch_dir(paths: Paths) -> Path:
    return paths.translations_dir / "pending" / "batches"


def make_batches(paths: Paths, max_chars: int = 30000, pairs=PAIRS) -> dict:
    out_dir = _batch_dir(paths)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for pair in pairs:
        for old in out_dir.glob(f"{pair}-*.jsonl"):
            if ".out" in old.name:
                raise SystemExit(f"{old} exists: run merge-batches before re-splitting {pair}")
            old.unlink()
        src = paths.translations_dir / "pending" / f"{pair}.jsonl"
        if not src.exists():
            continue
        items = [json.loads(line) for line in src.open(encoding="utf-8") if line.strip()]
        items.sort(key=lambda it: ((it.get("context") or [""])[0], it["source"]))
        batches, current, size = [], [], 0
        for it in items:
            if current and size + len(it["source"]) > max_chars:
                batches.append(current)
                current, size = [], 0
            current.append(it)
            size += len(it["source"])
        if current:
            batches.append(current)
        for n, batch in enumerate(batches, 1):
            with open(out_dir / f"{pair}-{n:03d}.jsonl", "w", encoding="utf-8") as fh:
                for i, it in enumerate(batch):
                    fh.write(json.dumps({"id": i, "pair": pair, "source": it["source"],
                                         "context": (it.get("context") or [None])[0]},
                                        ensure_ascii=False) + "\n")
        stats[pair] = len(batches)
    return stats


def merge_batches(paths: Paths, engine: str, min_alignment: float = 0.8) -> dict:
    tm = TranslationMemory(paths.translations_dir)
    added = missing = 0
    rejected: list[str] = []
    for batch in sorted(_batch_dir(paths).glob("*.jsonl")):
        if ".out" in batch.name:
            continue
        items = {json.loads(line)["id"]: json.loads(line)
                 for line in batch.open(encoding="utf-8") if line.strip()}
        results: dict[int, str] = {}
        for out in sorted(batch.parent.glob(batch.stem + ".out*.jsonl")):
            for line in out.open(encoding="utf-8"):
                if line.strip():
                    row = json.loads(line)
                    results[int(row["id"])] = row["target"]
        extra = set(results) - set(items)
        kept, total = alignment_score(items, results)
        if extra or (total >= 5 and kept < min_alignment * total):
            log.error("%s rejected: %d unknown ids, %d/%d code prefixes kept",
                      batch.name, len(extra), kept, total)
            rejected.append(batch.name)
            continue
        for i, it in items.items():
            if i in results:
                added += tm.add(it["pair"], it["source"], results[i], engine)
            else:
                missing += 1
    tm.save()
    return {"added": added, "untranslated": missing, "rejected": rejected}
