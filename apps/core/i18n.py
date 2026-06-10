"""Helpers for bilingual DB content (manual ``_en`` fields and modeltranslation)."""

from __future__ import annotations

from django.utils import translation

from apps.core.glossary_uk_en import localize_uk_to_en
from apps.core.text import unescape_legacy_html


def localized_field(obj: object, field: str, *, lang: str | None = None) -> str:
    """Return *field* in the active language when an English value exists."""
    if obj is None:
        return ""
    code = (lang or translation.get_language() or "uk").split("-")[0].lower()
    if code == "en":
        en_val = getattr(obj, f"{field}_en", None)
        if en_val is not None and str(en_val).strip():
            return unescape_legacy_html(str(en_val))
    val = getattr(obj, field, None)
    if val is not None and str(val).strip():
        text = unescape_legacy_html(str(val))
        if code == "en":
            return localize_uk_to_en(text)
        return text
    uk_val = getattr(obj, f"{field}_uk", None)
    if uk_val is not None and str(uk_val).strip():
        text = unescape_legacy_html(str(uk_val))
        if code == "en":
            return localize_uk_to_en(text)
        return text
    return ""
