"""Shipping cost calculation services."""

from __future__ import annotations

import logging
from decimal import Decimal

from apps.shipping.helpers import DEFAULT_PARCEL_HEIGHT_CM, DEFAULT_PARCEL_LENGTH_CM, DEFAULT_PARCEL_WIDTH_CM

logger = logging.getLogger(__name__)


def calc_delivery_cost(
    delivery_type: str,
    city_ref: str = "",
    warehouse_ref: str = "",
    postcode: str = "",
    weight_kg: float = 1.0,
    declared_value: Decimal | None = None,
) -> Decimal:
    """
    Calculate delivery cost for the given delivery type.
    Returns Decimal cost in UAH.
    """
    if delivery_type == "pickup":
        return Decimal("0")

    if delivery_type == "ukrposhta":
        return _calc_ukrposhta_cost(postcode, weight_kg, declared_value)

    if delivery_type == "nova_poshta":
        return _calc_nova_poshta_cost(city_ref, warehouse_ref, weight_kg, declared_value)

    return Decimal("0")


def _calc_ukrposhta_cost(
    postcode: str,
    weight_kg: float,
    declared_value: Decimal | None,
) -> Decimal:
    postcode = (postcode or "").strip()
    if not postcode:
        return Decimal("0")

    try:
        from apps.integrations.ukrposhta.client import UkrPoshtaClient

        client = UkrPoshtaClient()
        price = client.calc_delivery_price(
            recipient_postcode=postcode,
            weight_kg=weight_kg,
            declared_value=int(declared_value or 500),
        )
        if price is not None:
            return price
    except Exception as exc:
        logger.warning("Ukrposhta delivery price fallback: %s", exc)

    return _ukrposhta_flat_rate(weight_kg)


def _ukrposhta_flat_rate(weight_kg: float) -> Decimal:
    if weight_kg <= 1:
        return Decimal("60")
    if weight_kg <= 2:
        return Decimal("75")
    if weight_kg <= 5:
        return Decimal("100")
    return Decimal("150")


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
    name = (item.get("Present") or item.get("MainDescription") or "").strip()
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
    from django.db.models import Case, IntegerField, Q, Value, When

    from apps.shipping.models import NovaPoshtaCity

    q = (query or "").strip()
    if len(q) < 2:
        return NovaPoshtaCity.objects.none()

    ranked = Case(
        When(name__iexact=q, then=Value(0)),
        When(name__istartswith=q, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )

    primary = NovaPoshtaCity.objects.filter(Q(name__iexact=q) | Q(name__istartswith=q))
    if primary.exists():
        return list(primary.annotate(rank=ranked).order_by("rank", "name")[:limit])

    db_results = list(
        NovaPoshtaCity.objects.filter(name__icontains=q)
        .annotate(rank=ranked)
        .order_by("rank", "name")[:limit]
    )
    if db_results:
        return db_results

    return _search_np_cities_via_api(q, limit)


def search_np_warehouses(city_ref: str, query: str = "", limit: int = 20) -> list[dict[str, str]]:
    """Return NP warehouses for checkout autocomplete."""
    from django.conf import settings

    from apps.integrations.novaposhta.client import NovaPoshtaClient
    from apps.shipping.models import NovaPoshtaWarehouse

    city_ref = (city_ref or "").strip()
    if not city_ref:
        return []

    q = (query or "").strip()
    effective_limit = max(limit, 50) if not q else limit

    if settings.NOVA_POSHTA_API_KEY:
        try:
            items = NovaPoshtaClient().search_warehouses(city_ref, q, limit=effective_limit)
            warehouses = [
                {"name": item.get("Description", ""), "ref": item["Ref"]}
                for item in items
                if item.get("Ref")
            ]
            if warehouses:
                return warehouses
        except Exception as exc:
            logger.warning("Nova Poshta warehouse API fallback to DB: %s", exc)

    qs = NovaPoshtaWarehouse.objects.filter(city__ref=city_ref)
    if q:
        qs = qs.filter(name__icontains=q)
    return [{"name": wh.name, "ref": wh.ref} for wh in qs.order_by("number", "name")[:effective_limit]]
