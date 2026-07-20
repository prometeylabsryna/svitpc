"""Shipping cost calculation services."""

from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def calc_delivery_cost(
    delivery_type: str,
    city_ref: str = "",
    warehouse_ref: str = "",
    weight_kg: float = 1.0,
    declared_value: Decimal | None = None,
) -> Decimal:
    """
    Calculate delivery cost for the given delivery type.
    Returns Decimal cost in UAH.
    """
    if delivery_type == "pickup":
        return Decimal("0")

    if delivery_type == "nova_poshta":
        return _calc_nova_poshta_cost(city_ref, warehouse_ref, weight_kg, declared_value)

    return Decimal("0")


def _calc_nova_poshta_cost(
    city_ref: str,
    warehouse_ref: str,
    weight_kg: float,
    declared_value: Decimal | None,
) -> Decimal:
    if not city_ref or not warehouse_ref:
        return Decimal("0")

    try:
        from django.conf import settings

        from apps.integrations.novaposhta.client import NovaPoshtaClient

        sender_city_ref = getattr(settings, "NP_SENDER_CITY_REF", "")
        if not settings.NOVA_POSHTA_API_KEY or not sender_city_ref:
            return Decimal("0")

        client = NovaPoshtaClient()
        resp = client._post(
            "InternetDocument",
            "getDocumentPrice",
            {
                "CitySender": sender_city_ref,
                "CityRecipient": city_ref,
                "Weight": str(round(weight_kg, 2)),
                "ServiceType": "WarehouseWarehouse",
                "Cost": str(int(declared_value or 500)),
                "CargoType": "Parcel",
                "SeatsAmount": "1",
            },
        )
        if resp.get("success") and resp.get("data"):
            cost = resp["data"][0].get("Cost") or 0
            return Decimal(str(cost))
        errors = resp.get("errors") or resp.get("warnings") or []
        if errors:
            logger.warning("Nova Poshta price API: %s", errors)
    except Exception as exc:
        logger.warning("Nova Poshta delivery price error: %s", exc)

    return Decimal("0")


def _np_city_from_api(item: dict):
    """Map searchSettlements row to city hit (name/ref/area for templates)."""
    from types import SimpleNamespace

    ref = (item.get("DeliveryCityRef") or item.get("Ref") or "").strip()
    # Use MainDescription (just city name: "Київ") not Present (full string: "м. Київ, Київська обл.")
    name = (item.get("MainDescription") or item.get("Present") or "").strip()
    area = (
        item.get("AreaDescription")
        or item.get("RegionDescription")
        or item.get("Region")
        or item.get("Area")
        or ""
    ).strip()
    if not ref or not name:
        return None
    return SimpleNamespace(name=name, ref=ref, area=area)


def _search_np_cities_term(q: str, limit: int):
    """Single-term city lookup in local DB."""
    from django.db.models import Case, IntegerField, Q, Value, When

    from apps.shipping.models import NovaPoshtaCity

    ranked = Case(
        When(name__iexact=q, then=Value(0)),
        When(name__istartswith=q, then=Value(1)),
        When(name_en__iexact=q, then=Value(2)),
        When(name_en__istartswith=q, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )

    primary = NovaPoshtaCity.objects.filter(
        Q(name__iexact=q)
        | Q(name__istartswith=q)
        | Q(name_en__iexact=q)
        | Q(name_en__istartswith=q)
    )
    if primary.exists():
        return list(primary.annotate(rank=ranked).order_by("rank", "name")[:limit])

    return list(
        NovaPoshtaCity.objects.filter(Q(name__icontains=q) | Q(name_en__icontains=q))
        .annotate(rank=ranked)
        .order_by("rank", "name")[:limit]
    )


def _search_np_cities_via_api(query: str, limit: int):
    from django.conf import settings

    from apps.integrations.novaposhta.client import NovaPoshtaClient

    if not settings.NOVA_POSHTA_API_KEY:
        return []

    try:
        items = NovaPoshtaClient().search_cities(query)
    except Exception as exc:
        logger.warning("Nova Poshta city API fallback failed: %s", exc)
        return []

    hits = []
    for item in items:
        hit = _np_city_from_api(item)
        if hit:
            hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def search_np_cities(query: str, limit: int = 10):
    """Return Nova Poshta cities matching user input, best matches first."""
    from apps.shipping.np_query import city_search_variants

    variants = city_search_variants(query)
    if not variants:
        from apps.shipping.models import NovaPoshtaCity

        return NovaPoshtaCity.objects.none()

    seen_refs: set[str] = set()
    merged: list = []

    for term in variants:
        for hit in _search_np_cities_term(term, limit):
            ref = getattr(hit, "ref", "")
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            merged.append(hit)
            if len(merged) >= limit:
                return merged

    for term in variants:
        for hit in _search_np_cities_via_api(term, limit):
            ref = getattr(hit, "ref", "")
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            merged.append(hit)
            if len(merged) >= limit:
                return merged

    return merged


def search_np_warehouses(city_ref: str, query: str = "", limit: int = 20) -> list[dict[str, str]]:
    """Return NP warehouses for checkout autocomplete."""
    from django.conf import settings

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from apps.shipping.models import NovaPoshtaWarehouse
    from apps.shipping.np_query import warehouse_search_variants

    city_ref = (city_ref or "").strip()
    if not city_ref:
        return []

    q = (query or "").strip()
    effective_limit = max(limit, 50) if not q else limit

    if settings.NOVA_POSHTA_API_KEY:
        try:
            client = NovaPoshtaClient()
            seen: set[str] = set()
            merged: list[dict[str, str]] = []
            for term in warehouse_search_variants(q):
                items = client.search_warehouses(city_ref, term, limit=effective_limit)
                for item in items:
                    ref = item.get("Ref")
                    if not ref or ref in seen:
                        continue
                    seen.add(ref)
                    merged.append({"name": item.get("Description", ""), "ref": ref})
                    if len(merged) >= effective_limit:
                        return merged
            if merged:
                return merged
        except Exception as exc:
            logger.warning("Nova Poshta warehouse API fallback to DB: %s", exc)

    qs = NovaPoshtaWarehouse.objects.filter(city__ref=city_ref)
    if q:
        from django.db.models import Q

        q_filter = Q(name__icontains=q)
        if q.isdigit():
            q_filter |= Q(number=q)
        for term in warehouse_search_variants(q)[1:]:
            q_filter |= Q(name__icontains=term)
        qs = qs.filter(q_filter)
    return [{"name": wh.name, "ref": wh.ref} for wh in qs.order_by("number", "name")[:effective_limit]]
