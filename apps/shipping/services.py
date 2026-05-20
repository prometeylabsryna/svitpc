"""Shipping cost calculation services."""

from __future__ import annotations

from decimal import Decimal


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

    if delivery_type == "ukrposhta":
        # Simple flat-rate table (until UkrPoshta API is fully integrated)
        if weight_kg <= 1:
            return Decimal("60")
        elif weight_kg <= 2:
            return Decimal("75")
        elif weight_kg <= 5:
            return Decimal("100")
        return Decimal("150")

    if delivery_type == "nova_poshta":
        if not city_ref or not warehouse_ref:
            return Decimal("0")
        try:
            from apps.integrations.novaposhta.client import NovaPoshtaClient
            from django.conf import settings

            client = NovaPoshtaClient()
            resp = client._post("InternetDocument", "getDocumentPrice", {
                "CitySender": getattr(settings, "NP_SENDER_CITY_REF", ""),
                "CityRecipient": city_ref,
                "Weight": str(round(weight_kg, 2)),
                "ServiceType": "WarehouseWarehouse",
                "Cost": str(int(declared_value or 500)),
                "CargoType": "Cargo",
                "SeatsAmount": "1",
            })
            if resp.get("success") and resp.get("data"):
                cost = resp["data"][0].get("Cost") or 0
                return Decimal(str(cost))
        except Exception:
            pass
        return Decimal("0")

    return Decimal("0")
