"""Machine translation of pending texts with the Claude API.

Requires the optional dependency ``anthropic`` (``pip install -e '.[translate]'``) and an
API credential (``ANTHROPIC_API_KEY`` or an ``ant auth login`` profile).

The model receives batches of numbered source strings plus a short context (the table
title the string comes from) and the project glossary, and returns a JSON object
``{"translations": [{"id": n, "text": "..."}]}``. Results go straight into the
translation memory, so an interrupted run can simply be restarted.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from ..config import Paths
from .memory import TranslationMemory

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
LANG_NAMES = {"hy": "Armenian", "en": "English", "ru": "Russian"}

SYSTEM_PROMPT = """\
You translate metadata of official statistics published by the Statistical Committee of the
Republic of Armenia (Armstat): table titles, dimension names, category labels, units of
measure, footnotes and source names.

Rules:
- Translate faithfully and completely; do not summarise, explain or add anything.
- Use the standard terminology of official statistics (SNA 2008, NACE/ISIC, COICOP, HS,
  ILO) and of Russian/English-language statistical yearbooks of the CIS countries.
- Follow the glossary exactly when a term from it occurs.
- Keep numbers, years, codes, abbreviations of classifications, footnote markers (*, **, ¹),
  punctuation and capitalisation pattern of the source. Keep line breaks.
- Armenian administrative units: "մարզ" -> "marz" (en) / "марз" (ru); keep proper names
  in the conventional transliteration given in the glossary.
- Russian: use correct grammatical case and agreement; units like "հազ. դրամ" ->
  "тыс. драмов", "մլն դրամ" -> "млн драмов", "%" stays "%".
- Each item has an id; return every id exactly once.
"""


def load_glossary(directory: Path) -> list[dict]:
    path = directory / "glossary.tsv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return [row for row in csv.DictReader(fh, delimiter="\t")]


def _glossary_text(glossary: list[dict], src: str, tgt: str) -> str:
    lines = [f"{g[src]} => {g[tgt]}" for g in glossary if g.get(src) and g.get(tgt)]
    return "\n".join(lines)


def _read_pending(paths: Paths, pair: str) -> list[dict]:
    path = paths.translations_dir / "pending" / f"{pair}.jsonl"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _translate_batch(client, model: str, pair: str, items: list[dict], glossary: str) -> dict:
    src, tgt = pair.split("-")
    payload = [{"id": i, "text": it["source"], "context": (it.get("context") or [None])[0]}
               for i, it in enumerate(items)]
    user = (
        f"Translate from {LANG_NAMES[src]} to {LANG_NAMES[tgt]}.\n\n"
        f"Glossary ({LANG_NAMES[src]} => {LANG_NAMES[tgt]}):\n{glossary or '(none)'}\n\n"
        "Items (JSON). `context` is the statistical table the text belongs to; "
        "do not translate it.\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=0)}\n\n"
        'Answer with JSON only: {"translations": [{"id": 0, "text": "..."}, ...]}'
    )
    with client.beta.messages.stream(
        model=model,
        max_tokens=64000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": user}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        raise RuntimeError(f"model refused batch ({pair}, {len(items)} items)")
    text = "".join(b.text for b in message.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {int(t["id"]): t["text"] for t in data.get("translations", [])}


def translate_pending(paths: Paths, backend: str = "anthropic", model: str | None = None,
                      batch_size: int = 80, limit: int | None = None,
                      pair: list[str] | None = None) -> dict:
    if backend != "anthropic":
        raise ValueError(f"unsupported backend {backend!r}")
    import anthropic  # optional dependency

    client = anthropic.Anthropic()
    model = model or DEFAULT_MODEL
    engine = f"anthropic:{model}"
    tm = TranslationMemory(paths.translations_dir)
    glossary = load_glossary(paths.translations_dir)
    stats = {}
    for p in pair or ["hy-en", "hy-ru", "en-ru"]:
        items = [it for it in _read_pending(paths, p) if tm.get(p, it["source"]) is None]
        if limit:
            items = items[:limit]
        gloss = _glossary_text(glossary, *p.split("-"))
        done = 0
        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]
            try:
                result = _translate_batch(client, model, p, batch, gloss)
            except (anthropic.APIError, json.JSONDecodeError, RuntimeError) as exc:
                log.error("%s batch %d failed: %s", p, start // batch_size, exc)
                continue
            for i, it in enumerate(batch):
                if result.get(i):
                    done += tm.add(p, it["source"], result[i], engine)
            tm.save()
            log.info("%s: %d/%d", p, min(start + batch_size, len(items)), len(items))
        stats[p] = {"pending": len(items), "translated": done}
    return stats
