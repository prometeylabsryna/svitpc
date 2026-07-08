from .base import *  # noqa: F401, F403

DEBUG = False

CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[env("SITE_URL", default="https://svitpc.com.ua")],  # noqa: F405
)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# CSP: константи CSP_* видалено — пакет django-csp не встановлений, тому вони
# були мертвим кодом (жоден middleware їх не читав). При потребі CSP:
# додати django-csp у requirements + CONTENT_SECURITY_POLICY dict за
# документацією пакета (джерела: GTM, GA4, LiqPay, Monobank, WayForPay, fonts).

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
