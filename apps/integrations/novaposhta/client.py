"""Nova Poshta API client."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)
NP_API_URL = "https://api.novaposhta.ua/v2.0/json/"

# NP status code → human-readable Ukrainian mapping
NP_STATUS_MAP: dict[str, str] = {
    "1": "Відправлення створено",
    "2": "Видалено",
    "3": "Не знайдено",
    "4": "Відправлення у місті відправника",
    "5": "Відправлено",
    "6": "У місті",
    "7": "Прибуло у відділення",
    "8": "Прийняте",
    "9": "Відмова. Повернення грошей на карту",
    "10": "Відмова. Готівка на повернення",
    "11": "Повернення грошей",
    "12": "Доставлено",
    "14": "Відправлення не знайдено",
    "41": "Пошукова робота",
    "101": "На шляху до одержувача",
    "102": "Відмова від отримання",
    "103": "Пошкоджено",
    "108": "Не виїхало",
}
DELIVERED_CODES = {"12"}
IN_TRANSIT_CODES = {"5", "6", "7", "101"}


class NovaPoshtaClient:
    def __init__(self) -> None:
        self._key = settings.NOVA_POSHTA_API_KEY

    def _post(self, model_name: str, method: str, props: dict | None = None) -> dict:
        try:
            resp = httpx.post(NP_API_URL, json={
                "apiKey": self._key,
                "modelName": model_name,
                "calledMethod": method,
                "methodProperties": props or {},
            }, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("NovaPoshta API error %s/%s: %s", model_name, method, exc)
            return {"success": False, "data": []}

    def search_cities(self, query: str) -> list[dict]:
        resp = self._post("Address", "searchSettlements", {"CityName": query, "Limit": 10})
        addresses = resp.get("data", [{}])
        return addresses[0].get("Addresses", []) if addresses else []

    def get_warehouses(self, city_ref: str, query: str = "") -> list[dict]:
        resp = self._post("AddressGeneral", "getWarehouses", {
            "CityRef": city_ref,
            "FindByString": query,
            "Limit": 50,
        })
        return resp.get("data", [])

    def create_ttn(self, order) -> str | None:
        """Create TTN (waybill) for an order. Returns IntDocNumber or None."""
        if not self._key:
            logger.warning("NP create_ttn: NOVA_POSHTA_API_KEY not configured")
            return None

        sender_ref = getattr(settings, "NP_SENDER_REF", "")
        contact_ref = getattr(settings, "NP_SENDER_CONTACT_REF", "")
        sender_phone = getattr(settings, "NP_SENDER_PHONE", "")
        sender_city_ref = getattr(settings, "NP_SENDER_CITY_REF", "")
        sender_wh_ref = getattr(settings, "NP_SENDER_WAREHOUSE_REF", "")

        if not all([sender_ref, contact_ref, sender_phone, sender_city_ref, sender_wh_ref]):
            logger.warning("NP create_ttn: sender settings not configured (NP_SENDER_*)")
            return None

        # Calculate weight/cost from order items
        total = float(order.total)
        weight = sum(
            float(getattr(item.product, "weight", 0) or 0.5)
            for item in order.items.select_related("product").all()
        ) or 0.5

        props = {
            "PayerType": "Recipient",
            "PaymentMethod": "Cash" if order.payment_method == "cod" else "NonCash",
            "CargoType": "Parcel",
            "Weight": str(round(weight, 2)),
            "SeatsAmount": "1",
            "Description": f"Замовлення #{order.pk}",
            "Cost": str(int(total)),
            "CitySender": sender_city_ref,
            "Sender": sender_ref,
            "SenderAddress": sender_wh_ref,
            "ContactSender": contact_ref,
            "SendersPhone": sender_phone,
            "CityRecipient": order.city_ref,
            "RecipientAddress": order.warehouse_ref,
            "RecipientsPhone": order.phone,
            "Recipient": {
                "FirstName": order.first_name,
                "LastName": order.last_name,
                "Phone": order.phone,
            },
        }
        resp = self._post("InternetDocument", "save", props)
        if resp.get("success") and resp.get("data"):
            ttn = resp["data"][0].get("IntDocNumber")
            logger.info("NP TTN created: %s for order #%s", ttn, order.pk)
            return ttn
        errors = resp.get("errors", [])
        logger.error("NP create_ttn failed for order #%s: %s", order.pk, errors)
        return None

    def track_ttn(self, ttn: str) -> dict | None:
        resp = self._post("TrackingDocument", "getStatusDocuments", {"Documents": [{"DocumentNumber": ttn}]})
        data = resp.get("data", [])
        return data[0] if data else None

    def sync_cities_to_db(self) -> int:
        """Download all cities and save to NovaPoshtaCity model."""
        from apps.shipping.models import NovaPoshtaCity
        resp = self._post("Address", "getCities", {"Page": 1, "Limit": 50000})
        cities = resp.get("data", [])
        objs = [
            NovaPoshtaCity(
                name=c.get("Description", ""),
                name_en=c.get("DescriptionRu", ""),
                ref=c["Ref"],
                area=c.get("AreaDescription", ""),
            )
            for c in cities if c.get("Ref")
        ]
        NovaPoshtaCity.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=["name", "name_en", "area"],
            unique_fields=["ref"],
        )
        return len(objs)
