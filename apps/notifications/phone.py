"""Ukrainian phone normalization for SMS gateways."""

from __future__ import annotations

import re

_PHONE_DIGITS_RE = re.compile(r"\D+")


class InvalidPhoneError(ValueError):
    """Raised when a phone number cannot be normalized to 380XXXXXXXXX."""


def normalize_ua_phone(phone: str) -> str:
    """Return digits in TurboSMS format: 380XXXXXXXXX (12 digits)."""
    digits = _PHONE_DIGITS_RE.sub("", (phone or "").strip())
    if not digits:
        raise InvalidPhoneError("Порожній номер телефону.")

    if len(digits) == 12 and digits.startswith("380"):
        return digits
    if len(digits) == 11 and digits.startswith("80"):
        return f"3{digits}"
    if len(digits) == 10 and digits.startswith("0"):
        return f"38{digits}"
    if len(digits) == 9:
        return f"380{digits}"

    raise InvalidPhoneError(f"Некоректний формат номера: {phone}")


def clean_ua_phone_for_storage(phone: str, *, required: bool = True) -> str:
    """Normalize user input to +380XXXXXXXXX for DB/forms. Raises InvalidPhoneError if invalid."""
    raw = (phone or "").strip()
    if not raw:
        if required:
            raise InvalidPhoneError("Порожній номер телефону.")
        return ""
    return format_ua_phone_display(raw)


def format_ua_phone_display(phone: str) -> str:
    """Store/display as +380XXXXXXXXX."""
    return f"+{normalize_ua_phone(phone)}"
