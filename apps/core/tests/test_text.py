from apps.core.text import unescape_legacy_html
from apps.core.templatetags.svitpc_tags import phone_digits, viber_chat_url


def test_unescape_legacy_html_apostrophe():
    assert unescape_legacy_html("Комп&#039;ютер") == "Комп'ютер"


def test_unescape_legacy_html_empty():
    assert unescape_legacy_html("") == ""
    assert unescape_legacy_html(None) == ""


def test_viber_chat_url_from_phone():
    assert phone_digits("096-076-30-15") == "0960763015"
    assert viber_chat_url("096-076-30-15") == "viber://chat?number=%2B380960763015"
    assert viber_chat_url("+380960763015") == "viber://chat?number=%2B380960763015"
    assert viber_chat_url("") == ""
