"""Nova Poshta autocomplete — Latin/English query helpers."""

from __future__ import annotations

import re

_LATIN_QUERY_RE = re.compile(r"^[a-zA-Z0-9\s\-'.]+$")

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


def city_search_variants(query: str) -> list[str]:
    """Return search terms to try (original, UA alias, transliteration)."""
    raw = (query or "").strip()
    if len(raw) < 2:
        return []

    variants: list[str] = []

    def add(value: str) -> None:
        value = (value or "").strip()
        if value and value not in variants:
            variants.append(value)

    add(raw)
    alias = _CITY_EN_ALIASES.get(raw.lower())
    if alias:
        add(alias)
    if is_latin_query(raw):
        from apps.integrations.novaposhta.client import _latin_to_ukrainian

        add(_latin_to_ukrainian(raw))
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
