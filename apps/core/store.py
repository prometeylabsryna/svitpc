"""Store pickup location — single source for address and map links."""

from __future__ import annotations

from urllib.parse import quote

from django.utils.translation import gettext_lazy as _

from apps.core.models import SiteSettings

# Google Maps listing: СВІТ ПК (комп'ютерна техніка, канцтовари)
STORE_MAPS_QUERY = "СВІТ ПК, проспект Незалежності 26, Південноукраїнськ"

DEFAULT_STORE_ADDRESS = _(
    "проспект Незалежності, 26, м. Південноукраїнськ, Миколаївська область, 55000"
)


def store_address(site: SiteSettings | None = None) -> str:
    """Display address: admin override or default pickup location."""
    if site is not None:
        custom = str(site.address or "").strip()
        if custom:
            return custom
    return str(DEFAULT_STORE_ADDRESS)


def _encoded_maps_query() -> str:
    return quote(STORE_MAPS_QUERY)


def store_maps_url() -> str:
    """Open the verified Google Maps listing for the store."""
    return f"https://www.google.com/maps/search/?api=1&query={_encoded_maps_query()}"


def store_maps_embed_url() -> str:
    """Embed URL for an inline map on info pages."""
    return (
        f"https://maps.google.com/maps?q={_encoded_maps_query()}"
        "&hl=uk&z=17&output=embed"
    )
