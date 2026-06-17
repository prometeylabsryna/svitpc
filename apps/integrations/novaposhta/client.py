"""Nova Poshta API client."""

from __future__ import annotations

import logging
import re

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


def _normalize_np_phone(phone: str) -> str:
    """Return phone in 380XXXXXXXXX format for Nova Poshta API."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("380"):
        return digits
    if digits.startswith("80"):
        return f"3{digits}"
    if digits.startswith("0"):
        return f"38{digits}"
    if len(digits) == 9:
        return f"380{digits}"
    return digits


_LATIN_DIGRAPHS = (
    ("shch", "щ"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "є"),
    ("yi", "ї"),
)
_LATIN_SINGLES = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г",
    "h": "г", "i": "і", "j": "й", "k": "к", "l": "л", "m": "м", "n": "н",
    "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
    "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з",
}


def _latin_to_ukrainian(text: str) -> str:
    """Rough Latin→Ukrainian transliteration for NP name fields."""
    text = (text or "").lower()
    result: list[str] = []
    idx = 0
    while idx < len(text):
        matched = False
        for latin, cyrillic in _LATIN_DIGRAPHS:
            if text.startswith(latin, idx):
                result.append(cyrillic)
                idx += len(latin)
                matched = True
                break
        if matched:
            continue
        char = text[idx]
        if char in _LATIN_SINGLES:
            result.append(_LATIN_SINGLES[char])
        elif char in " -'":
            result.append(char)
        idx += 1
    return "".join(result)


def _np_name_part(value: str, *, fallback: str) -> str:
    """Return Cyrillic-safe name fragment for Nova Poshta API."""
    value = (value or "").strip()
    if not value:
        return fallback
    if re.search(r"[а-яА-ЯіІїЇєЄґҐ]", value):
        return value
    transliterated = _latin_to_ukrainian(value)
    return transliterated or fallback


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

    def search_warehouses(self, city_ref: str, query: str = "", limit: int = 20) -> list[dict]:
        """Fetch warehouses for autocomplete (single API page)."""
        city_ref = (city_ref or "").strip()
        if not city_ref or not self._key:
            return []

        props: dict = {"CityRef": city_ref, "Limit": str(limit), "Page": "1"}
        if query:
            props["FindByString"] = query
        resp = self._post("AddressGeneral", "getWarehouses", props)
        return resp.get("data", [])[:limit]

    def get_warehouses(self, city_ref: str, query: str = "") -> list[dict]:
        if query:
            return self.search_warehouses(city_ref, query, limit=500)

        props: dict = {"CityRef": city_ref, "Limit": "500", "Page": "1"}
        warehouses: list[dict] = []
        while True:
            resp = self._post("AddressGeneral", "getWarehouses", props)
            batch = resp.get("data", [])
            if not batch:
                break
            warehouses.extend(batch)
            if len(batch) < int(props["Limit"]):
                break
            props["Page"] = str(int(props["Page"]) + 1)
        return warehouses

    def _ensure_recipient(self, order) -> tuple[str, str] | None:
        """Create or reuse NP recipient counterparty. Returns (recipient_ref, contact_ref)."""
        phone = _normalize_np_phone(order.phone)
        first_name = _np_name_part(order.first_name, fallback="Клієнт")
        last_name = _np_name_part(order.last_name, fallback="")
        if not last_name:
            last_name = first_name
        if not phone:
            logger.warning("NP create_ttn: order #%s has no phone", order.pk)
            return None

        resp = self._post(
            "Counterparty",
            "save",
            {
                "FirstName": first_name,
                "LastName": last_name,
                "Phone": phone,
                "Email": (order.email or "").strip(),
                "CounterpartyType": "PrivatePerson",
                "CounterpartyProperty": "Recipient",
            },
        )
        if not resp.get("success") or not resp.get("data"):
            logger.error(
                "NP ensure_recipient failed for order #%s: %s",
                order.pk,
                resp.get("errors", []),
            )
            return None

        item = resp["data"][0]
        recipient_ref = item.get("Ref", "")
        contact_person = item.get("ContactPerson") or {}
        contacts = contact_person.get("data") or []
        contact_ref = contacts[0].get("Ref", "") if contacts else ""
        if not recipient_ref or not contact_ref:
            logger.error("NP ensure_recipient missing refs for order #%s", order.pk)
            return None
        return recipient_ref, contact_ref

    def _payment_props(self, order) -> dict[str, str]:
        """Map order payment to NP payer settings (Cash-only for private senders)."""
        if order.payment_method == "cod":
            return {"PayerType": "Recipient", "PaymentMethod": "Cash"}
        return {"PayerType": "Sender", "PaymentMethod": "Cash"}

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

        if not order.city_ref or not order.warehouse_ref:
            logger.warning("NP create_ttn: order #%s missing city_ref/warehouse_ref", order.pk)
            return None

        recipient = self._ensure_recipient(order)
        if not recipient:
            return None
        recipient_ref, recipient_contact_ref = recipient
        recipient_phone = _normalize_np_phone(order.phone)

        total = float(order.total)
        weight = sum(
            float(getattr(item.product, "weight", 0) or 0.5)
            for item in order.items.select_related("product").all()
        ) or 0.5

        props = {
            **self._payment_props(order),
            "CargoType": "Parcel",
            "Weight": str(round(weight, 2)),
            "SeatsAmount": "1",
            "Description": f"Замовлення #{order.pk}",
            "Cost": str(int(total)),
            "ServiceType": "WarehouseWarehouse",
            "CitySender": sender_city_ref,
            "Sender": sender_ref,
            "SenderAddress": sender_wh_ref,
            "ContactSender": contact_ref,
            "SendersPhone": _normalize_np_phone(sender_phone),
            "CityRecipient": order.city_ref,
            "Recipient": recipient_ref,
            "RecipientAddress": order.warehouse_ref,
            "ContactRecipient": recipient_contact_ref,
            "RecipientsPhone": recipient_phone,
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
        resp = self._post("Address", "getCities", {"Page": "1", "Limit": "50000"})
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
