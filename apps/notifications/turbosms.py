"""TurboSMS HTTP API client."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from .phone import InvalidPhoneError, normalize_ua_phone

logger = logging.getLogger(__name__)

API_BASE = "https://api.turbosms.ua"


class TurboSmsError(Exception):
    """TurboSMS API error with provider status details."""

    def __init__(self, message: str, *, response_code: int | None = None, response_status: str = "") -> None:
        self.response_code = response_code
        self.response_status = response_status
        super().__init__(message)


def is_configured() -> bool:
    return bool(getattr(settings, "SMS_API_KEY", ""))


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.SMS_API_KEY}"}


def _request(method: str, path: str, *, json: dict | None = None) -> dict[str, Any]:
    url = f"{API_BASE}/{path}"
    try:
        with httpx.Client(timeout=20.0) as client:
            if method.upper() == "GET":
                resp = client.get(url, headers=_auth_headers())
            else:
                resp = client.post(url, headers=_auth_headers(), json=json or {})
    except httpx.HTTPError as exc:
        raise TurboSmsError(f"Помилка з'єднання з TurboSMS: {exc}") from exc

    if resp.status_code != 200:
        raise TurboSmsError(f"TurboSMS HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise TurboSmsError("TurboSMS повернув некоректний JSON.") from exc

    if not isinstance(data, dict):
        raise TurboSmsError("TurboSMS повернув неочікувану відповідь.")
    return data


def ping() -> dict[str, Any]:
    """Verify API key and connectivity. response_code=1 means PONG."""
    data = _request("GET", "auth/ping.json")
    if data.get("response_code") != 1 or data.get("response_status") != "PONG":
        raise TurboSmsError(
            f"TurboSMS ping failed: {data.get('response_status')}",
            response_code=data.get("response_code"),
            response_status=str(data.get("response_status", "")),
        )
    return data


def _recipient_succeeded(entry: dict[str, Any]) -> bool:
    return entry.get("response_code") == 0 and bool(entry.get("message_id"))


def send_sms(phone: str, text: str, *, sender: str | None = None) -> dict[str, Any]:
    """Send one SMS. Returns TurboSMS response payload."""
    if not is_configured():
        raise TurboSmsError("SMS_API_KEY не налаштовано.")

    try:
        recipient = normalize_ua_phone(phone)
    except InvalidPhoneError as exc:
        raise TurboSmsError(str(exc)) from exc

    sender_name = sender or getattr(settings, "SMS_SENDER", "SvitPC")
    payload = {
        "recipients": [recipient],
        "sms": {
            "sender": sender_name,
            "text": text,
        },
    }
    data = _request("POST", "message/send.json", json=payload)

    results = data.get("response_result")
    if isinstance(results, list) and results:
        if any(_recipient_succeeded(item) for item in results if isinstance(item, dict)):
            return data
        first = results[0] if results else {}
        status = first.get("response_status", data.get("response_status", "UNKNOWN"))
        code = first.get("response_code", data.get("response_code"))
        raise TurboSmsError(
            f"TurboSMS: {status}",
            response_code=code,
            response_status=str(status),
        )

    if data.get("response_code") == 0:
        return data

    raise TurboSmsError(
        f"TurboSMS: {data.get('response_status', 'UNKNOWN')}",
        response_code=code,
        response_status=str(data.get("response_status", "")),
    )
