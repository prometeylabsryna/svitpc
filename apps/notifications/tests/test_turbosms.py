"""TurboSMS client and phone normalization tests."""

from unittest.mock import MagicMock, patch

import pytest

from apps.notifications.phone import format_ua_phone_display, normalize_ua_phone, InvalidPhoneError
from apps.notifications.turbosms import TurboSmsError, ping, send_sms


def test_normalize_ua_phone_formats():
    assert normalize_ua_phone("+380 (50) 123-45-67") == "380501234567"
    assert normalize_ua_phone("0501234567") == "380501234567"
    assert format_ua_phone_display("0501234567") == "+380501234567"


def test_clean_ua_phone_for_storage():
    from apps.notifications.phone import clean_ua_phone_for_storage

    assert clean_ua_phone_for_storage("0501234567") == "+380501234567"
    # За замовчуванням телефон обов'язковий (checkout validation покладається на це)
    assert clean_ua_phone_for_storage("", required=False) == ""
    with pytest.raises(InvalidPhoneError):
        clean_ua_phone_for_storage("", required=True)
    with pytest.raises(InvalidPhoneError):
        clean_ua_phone_for_storage("12345", required=True)


@pytest.mark.django_db
def test_ping_success(settings):
    settings.SMS_API_KEY = "test-token"
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"response_code": 1, "response_status": "PONG", "response_result": None}

    with patch("apps.notifications.turbosms.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        data = ping()
    assert data["response_status"] == "PONG"


@pytest.mark.django_db
def test_send_sms_success(settings):
    settings.SMS_API_KEY = "test-token"
    settings.SMS_SENDER = "SvitPC"
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "response_code": 0,
        "response_status": "OK",
        "response_result": [
            {"phone": "380501234567", "response_code": 0, "message_id": "uuid-1", "response_status": "OK"},
        ],
    }

    with patch("apps.notifications.turbosms.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        data = send_sms("+380501234567", "Тест")
    assert data["response_code"] == 0


@pytest.mark.django_db
def test_send_sms_recipient_error(settings):
    settings.SMS_API_KEY = "test-token"
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "response_code": 802,
        "response_status": "SUCCESS_MESSAGE_PARTIAL_ACCEPTED",
        "response_result": [
            {"phone": "380501234567", "response_code": 305, "message_id": None, "response_status": "INVALID_PHONE"},
        ],
    }

    with patch("apps.notifications.turbosms.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
        with pytest.raises(TurboSmsError, match="INVALID_PHONE"):
            send_sms("+380501234567", "Тест")
