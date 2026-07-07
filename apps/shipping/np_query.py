"""Nova Poshta autocomplete — Latin/English query helpers."""

from __future__ import annotations

import re

_LATIN_QUERY_RE = re.compile(r"^[a-zA-Z0-9\s\-'.]+$")

# Strip Ukrainian locality type prefixes: "м.", "м-ко", "смт.", "с.", "міс."
_CITY_PREFIX_RE = re.compile(
    r"^(м-ко|смт|міс|м|с)\.?\s+",
    re.IGNORECASE | re.UNICODE,
)
# Strip trailing region suffix: ", Київська обл." or "Київська обл."
_CITY_SUFFIX_RE = re.compile(
    r",?\s+\S+\s+обл\.?.*$",
    re.IGNORECASE | re.UNICODE,
)

# Common English / Latin spellings → Ukrainian city name (NP DB `name` field).
_CITY_EN_ALIASES: dict[str, str] = {
    "kyiv": "Київ",
    "kiev": "Київ",
    "lviv": "Львів",
    "lwow": "Львів",
    "odesa": "Одеса",
    "odessa": "Одеса",
    "kharkiv": "Харків",
    "kharkov": "Харків",
    "dnipro": "Дніпро",
    "dnepr": "Дніпро",
    "dnepropetrovsk": "Дніпро",
    "zaporizhzhia": "Запоріжжя",
    "zaporizhia": "Запоріжжя",
    "mykolaiv": "Миколаїв",
    "nikolaev": "Миколаїв",
    "vinnytsia": "Вінниця",
    "vinnitsa": "Вінниця",
    "chernihiv": "Чернігів",
    "cherkasy": "Черкаси",
    "poltava": "Полтава",
    "ivano-frankivsk": "Івано-Франківськ",
    "uzhhorod": "Ужгород",
    "uzhgorod": "Ужгород",
    "ternopil": "Тернопіль",
    "lutsk": "Луцьк",
    "rivne": "Рівне",
    "rovno": "Рівне",
    "zhytomyr": "Житомир",
    "sumy": "Суми",
    "khmelnytskyi": "Хмельницький",
    "khmelnitsky": "Хмельницький",
    "kryvyi rih": "Кривий Ріг",
    "krivoy rog": "Кривий Ріг",
    "mariupol": "Маріуполь",
    "chernivtsi": "Чернівці",
    "chernevtsy": "Чернівці",
}


def is_latin_query(text: str) -> bool:
    raw = (text or "").strip()
    return bool(raw) and bool(_LATIN_QUERY_RE.match(raw))


def _normalize_city_query(raw: str) -> str:
    """Strip Ukrainian locality prefixes (м., смт.) and region suffixes (Київська обл.)."""
    normalized = _CITY_PREFIX_RE.sub("", raw).strip()
    normalized = _CITY_SUFFIX_RE.sub("", normalized).strip()
    normalized = normalized.strip(",").strip()
    return normalized


def city_search_variants(query: str) -> list[str]:
    """Return search terms to try (original, normalized, UA alias, transliteration)."""
    raw = (query or "").strip()
    if len(raw) < 2:
        return []

    variants: list[str] = []

    def add(value: str) -> None:
        value = (value or "").strip()
        if value and len(value) >= 2 and value not in variants:
            variants.append(value)

    add(raw)

    normalized = _normalize_city_query(raw)
    add(normalized)

    for term in (raw.lower(), normalized.lower()):
        alias = _CITY_EN_ALIASES.get(term)
        if alias:
            add(alias)

    for term in (normalized, raw):
        if is_latin_query(term):
            from apps.integrations.novaposhta.client import _latin_to_ukrainian

            add(_latin_to_ukrainian(term))
            break

    return variants


def warehouse_search_variants(query: str) -> list[str]:
    """Latin warehouse hints (street/number) → also try rough UA transliteration."""
    raw = (query or "").strip()
    if not raw:
        return [""]
    variants = [raw]
    if is_latin_query(raw):
        from apps.integrations.novaposhta.client import _latin_to_ukrainian

        translit = _latin_to_ukrainian(raw)
        if translit and translit not in variants:
            variants.append(translit)
    return variants
