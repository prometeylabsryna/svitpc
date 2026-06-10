"""Home page advertising: layout constants and queryset helpers."""

from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Banner, HomeAdSettings

# Match --container-max and layout gutters in static CSS.
CONTENT_MAX_WIDTH = 1280
CONTAINER_PAD = 16
SLOT_GAP = 12

# Portrait tiles in a row (ITbox-style).
ASPECT_BY_COLUMNS: dict[int, tuple[int, int]] = {
    2: (3, 4),
    3: (3, 4),
    4: (3, 4),
}

# One full-width banner: same width as the block, height ≈ one 4-col row + ~8%.
SINGLE_COL_ASPECT = (20, 7)
SINGLE_ROW_HEIGHT_FACTOR = 1.08

# Mobile (multi-column layouts collapsed to one column).
MOBILE_ASPECT = (3, 4)


def _clamp_columns(columns: int) -> int:
    return max(1, min(4, columns))


def _four_column_tile_height() -> int:
    w = slot_width(4)
    ratio_w, ratio_h = ASPECT_BY_COLUMNS[4]
    return round(w * ratio_h / ratio_w)


def _single_column_height() -> int:
    return round(_four_column_tile_height() * SINGLE_ROW_HEIGHT_FACTOR)


def aspect_ratio_for(columns: int) -> tuple[int, int]:
    cols = _clamp_columns(columns)
    if cols == 1:
        return (slot_width(1), _single_column_height())
    return ASPECT_BY_COLUMNS[cols]


def aspect_ratio_label(columns: int) -> str:
    if _clamp_columns(columns) == 1:
        w, h = SINGLE_COL_ASPECT
        return f"{w}:{h}"
    ratio_w, ratio_h = aspect_ratio_for(columns)
    return f"{ratio_w}:{ratio_h}"


def slot_width(columns: int) -> int:
    """Pixel width of one banner slot on desktop."""
    cols = _clamp_columns(columns)
    inner = CONTENT_MAX_WIDTH - 2 * CONTAINER_PAD
    gaps = (cols - 1) * SLOT_GAP
    return max(1, (inner - gaps) // cols)


def recommended_banner_size(columns: int) -> tuple[int, int]:
    """Recommended upload size (width, height) for the given column count."""
    width = slot_width(columns)
    ratio_w, ratio_h = aspect_ratio_for(columns)
    height = round(width * ratio_h / ratio_w)
    return width, height


def all_recommended_sizes() -> dict[int, tuple[int, int]]:
    return {n: recommended_banner_size(n) for n in range(1, 5)}


def all_aspect_labels() -> dict[int, str]:
    return {n: aspect_ratio_label(n) for n in range(1, 5)}


def get_home_ad_settings() -> HomeAdSettings:
    return HomeAdSettings.load()


def active_home_banners() -> QuerySet[Banner]:
    now = timezone.now()
    return (
        Banner.objects.filter(position=Banner.POSITION_HOME, is_active=True)
        .filter(Q(date_start__isnull=True) | Q(date_start__lte=now))
        .filter(Q(date_end__isnull=True) | Q(date_end__gte=now))
        .order_by("sort_order", "pk")
    )
