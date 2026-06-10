"""Text helpers for legacy OpenCart HTML entities in catalog content."""

from __future__ import annotations

import html


def unescape_legacy_html(value: str | None) -> str:
    """Decode ``&#039;``, ``&amp;``, etc. left over from OpenCart import."""
    if not value:
        return ""
    return html.unescape(str(value))
