"""Turn official (Armenian, English) text pairs into final trilingual values.

Rules (applied to every human-readable field):

1. Armenian is always the official Armstat text (or NULL when the API has none).
2. English is the official Armstat text when it exists and contains no Armenian script.
   Otherwise it is translated from Armenian (``hy-en`` memory) and flagged as machine.
3. Russian is always a machine translation: from the official English when available
   (``en-ru``), otherwise directly from Armenian (``hy-ru``). An ``hy-ru`` entry for the
   Armenian text, when present, takes precedence over ``en-ru`` (used for corrections
   where Armstat's English is ambiguous or wrong).
4. Texts without letters (years, numbers, codes) are copied unchanged to all languages.
5. Cyrillic look-alike letters inside Latin words of English texts are replaced
   (source typos such as a Cyrillic "Т" in "Тransportations").

Texts not yet in the translation memory are recorded in :attr:`Resolver.missing`; they
become the input of ``armstat-db translate`` / batch translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..textutil import fix_homoglyphs, has_armenian, needs_translation, normalize
from .memory import TranslationMemory


@dataclass
class Resolved:
    hy: str | None
    en: str | None
    ru: str | None
    en_machine: bool


@dataclass
class Resolver:
    tm: TranslationMemory
    # pair -> source -> list of contexts
    missing: dict[str, dict[str, list[str]]] = field(
        default_factory=lambda: {"hy-en": {}, "hy-ru": {}, "en-ru": {}})

    def _lookup(self, pair: str, source: str, context: str | None) -> str | None:
        target = self.tm.get(pair, source)
        if target is None:
            ctx = self.missing[pair].setdefault(source, [])
            if context and context not in ctx and len(ctx) < 3:
                ctx.append(context)
        return target

    def resolve(self, hy: str | None, en: str | None, context: str | None = None) -> Resolved:
        hy, en = normalize(hy), fix_homoglyphs(normalize(en))
        if en is not None and has_armenian(en):
            # English slot holds Armenian text: treat it as Armenian source.
            hy = hy or en
            en = None
        if hy is not None and en is None and not has_armenian(hy) and not needs_translation(hy):
            # Armenian slot holds a code or number only.
            return Resolved(hy, hy, hy, False)
        if en is not None:
            if not needs_translation(en):
                return Resolved(hy or en, en, en, False)
            # an hy-ru entry for the Armenian text overrides en-ru: it corrects cases where
            # Armstat's English is ambiguous (e.g. one English word for two Armenian terms)
            ru = self.tm.get("hy-ru", hy) if has_armenian(hy) else None
            if ru is None:
                ru = self._lookup("en-ru", en, context)
            return Resolved(hy, en, ru, False)
        if hy is None:
            return Resolved(None, None, None, False)
        if not needs_translation(hy):
            return Resolved(hy, hy, hy, False)
        return Resolved(hy, self._lookup("hy-en", hy, context),
                        self._lookup("hy-ru", hy, context), True)

    @property
    def n_missing(self) -> int:
        return sum(len(v) for v in self.missing.values())
