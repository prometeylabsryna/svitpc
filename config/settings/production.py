from .base import *  # noqa: F401, F403

DEBUG = False
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

# ── Content Security Policy (no unsafe-inline) ─────────────────────────────
# Nonces are handled by django-csp middleware (add django-csp to deps if needed).
# These sources cover: GTM, GA4, LiqPay, Facebook Pixel, Monobank, WayForPay,
# fonts (Google), HTMX, push service worker.
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "https://www.googletagmanager.com",
    "https://www.google-analytics.com",
    "https://www.googleadservices.com",
    "https://www.gstatic.com",
    "https://connect.facebook.net",
    # LiqPay checkout
    "https://www.liqpay.ua",
    # Monobank
    "https://pay.mbnk.biz",
    # WayForPay
    "https://secure.wayforpay.com",
)
CSP_SCRIPT_SRC_ELEM = CSP_SCRIPT_SRC  # required for modern browsers
CSP_STYLE_SRC = (
    "'self'",
    "https://fonts.googleapis.com",
)
CSP_FONT_SRC = (
    "'self'",
    "https://fonts.gstatic.com",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "https:",
    "blob:",
)
CSP_CONNECT_SRC = (
    "'self'",
    "https://www.google-analytics.com",
    "https://analytics.google.com",
    "https://api.novaposhta.ua",
    "https://chatapi.viber.com",
    "https://api.telegram.org",
    "https://api.monobank.ua",
    "https://api.wayforpay.com",
)
CSP_WORKER_SRC = ("'self'",)  # service worker
CSP_MANIFEST_SRC = ("'self'",)
CSP_FRAME_SRC = (
    "https://www.liqpay.ua",
    "https://pay.mbnk.biz",
    "https://secure.wayforpay.com",
)
CSP_FORM_ACTION = ("'self'", "https://www.liqpay.ua", "https://secure.wayforpay.com")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
