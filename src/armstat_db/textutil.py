"""Text helpers: script detection, normalisation and time-period parsing."""

from __future__ import annotations

import re
import unicodedata

ARMENIAN = re.compile(r"[Ա-Ֆՙ-֊ﬓ-ﬗ]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def has_armenian(text: str | None) -> bool:
    return bool(text) and bool(ARMENIAN.search(text))


def has_letters(text: str | None) -> bool:
    return bool(text) and bool(LETTER.search(text))


def normalize(text: str | None) -> str | None:
    """Canonical form used as translation-memory key: NFC, unified line breaks, trimmed."""
    if text is None:
        return None
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()
    return text or None


# Cyrillic letters that look like Latin ones; Armstat English texts sometimes contain them
# by mistake ("Тransportations" with a Cyrillic "Т").
_HOMOGLYPHS = str.maketrans("АВЕКМНОРСТХаеорсухіІ", "ABEKMHOPCTXaeopcyxiI")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def fix_homoglyphs(text: str | None) -> str | None:
    """Replace Cyrillic look-alike letters inside otherwise Latin words."""
    if not text or not CYRILLIC.search(text):
        return text

    def fix(m: re.Match) -> str:
        word = m.group(0)
        if CYRILLIC.search(word) and re.search(r"[A-Za-z]", word):
            fixed = word.translate(_HOMOGLYPHS)
            if not CYRILLIC.search(fixed):
                return fixed
        if len(word) == 1 and CYRILLIC.search(word):  # lone letter such as Cyrillic "о" in "оn"
            return word.translate(_HOMOGLYPHS)
        return word

    return _WORD.sub(fix, text)


def needs_translation(text: str | None) -> bool:
    """False for empty strings and strings without letters (years, codes, numbers)."""
    return has_letters(text)


# --------------------------------------------------------------------------- time periods

TIME_DIM_CODES = {
    "years", "year", "years*", "years**", "by year", "quarterly", "quarters", "quarter",
    "months", "month", "by months", "ըստ տարիների", "ըստ ամիսների", "ըստ եռամսյակների",
}

MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december"]

_YEAR = re.compile(r"^((?:19|20)\d{2})\s*[*¹²³]*$")
_QUARTER = re.compile(r"^((?:19|20)\d{2})\s*[-/ ]?\s*Q([1-4])$", re.I)
_YEAR_MONTH = re.compile(r"^((?:19|20)\d{2})\s*[-/ M]\s*(\d{1,2})$")


def parse_period(label: str | None) -> str | None:
    """Normalise a time label: ``'2015'``, ``'2015-Q1'``, ``'2015-03'`` or ``'--03'``.

    Returns ``None`` when the label is not a plain period (e.g. "Multiyear average values").
    """
    if not label:
        return None
    s = label.strip()
    if m := _YEAR.match(s):
        return m.group(1)
    if m := _QUARTER.match(s):
        return f"{m.group(1)}-Q{m.group(2)}"
    if m := _YEAR_MONTH.match(s):
        month = int(m.group(2))
        if 1 <= month <= 12:
            return f"{m.group(1)}-{month:02d}"
    low = s.lower()
    if low in MONTHS_EN:
        return f"--{MONTHS_EN.index(low) + 1:02d}"
    return None


def is_time_dimension(code: str, labels: list[str]) -> bool:
    if code.strip().lower() in TIME_DIM_CODES:
        return True
    if not labels:
        return False
    parsed = sum(parse_period(x) is not None for x in labels)
    return parsed >= max(2, 0.8 * len(labels))


def period_year(period: str | None) -> int | None:
    if period and period[:4].isdigit():
        return int(period[:4])
    return None
