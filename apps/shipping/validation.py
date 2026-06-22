"""Checkout delivery field validation."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.orders.models import Order


def validate_checkout_step1(data: dict) -> list[str]:
    """Return a list of user-facing validation error messages."""
    errors: list[str] = []

    if not (data.get("first_name") or "").strip():
        errors.append(_("Вкажіть ім'я."))
    if not (data.get("last_name") or "").strip():
        errors.append(_("Вкажіть прізвище."))

    phone_raw = (data.get("phone") or "").strip()
    if not phone_raw:
        errors.append(_("Вкажіть телефон."))
    else:
        from apps.notifications.phone import InvalidPhoneError, clean_ua_phone_for_storage

        try:
            data["phone"] = clean_ua_phone_for_storage(phone_raw)
        except InvalidPhoneError:
            errors.append(_("Введіть коректний номер телефону (+380…)."))

    delivery_type = (data.get("delivery_type") or Order.DELIVERY_NP).strip()

    if delivery_type == Order.DELIVERY_NP:
        if not (data.get("city") or "").strip():
            errors.append(_("Оберіть місто доставки."))
        if not (data.get("city_ref") or "").strip():
            errors.append(_("Оберіть місто зі списку підказок."))
        if not (data.get("warehouse_ref") or "").strip():
            errors.append(_("Оберіть відділення Нової Пошти."))
    elif delivery_type == Order.DELIVERY_UP:
        if not (data.get("city") or "").strip():
            errors.append(_("Вкажіть місто доставки."))
        postcode = (data.get("postcode") or "").strip()
        if not postcode:
            errors.append(_("Вкажіть поштовий індекс відділення Укрпошти."))
        elif not postcode.isdigit() or len(postcode) != 5:
            errors.append(_("Індекс має містити 5 цифр."))
    elif delivery_type != Order.DELIVERY_PICKUP:
        errors.append(_("Оберіть спосіб доставки."))

    return errors
