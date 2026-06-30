from apps.core.device import is_mobile_user_agent


def test_android_detected():
    assert is_mobile_user_agent(
        "Mozilla/5.0 (Linux; Android 11; Redmi Note 10S) AppleWebKit/537.36 Chrome/91.0 Mobile"
    )


def test_desktop_not_mobile():
    assert not is_mobile_user_agent(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0"
    )
