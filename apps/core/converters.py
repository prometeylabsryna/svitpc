"""URL converters for SvitPC.

`UnicodeSlugConverter` accepts Unicode word characters (e.g. Cyrillic)
in slugs, which Django's default `slug` converter forbids.
This is required because we store SEO-friendly Cyrillic slugs imported
from the legacy OpenCart store (see TZ §15: SEO URL preservation).
"""

from __future__ import annotations


class UnicodeSlugConverter:
    """Slug converter that allows letters from any language plus `-`, `_`."""

    regex = r"[-\w]+"

    def to_python(self, value: str) -> str:
        return value

    def to_url(self, value: str) -> str:
        return value
