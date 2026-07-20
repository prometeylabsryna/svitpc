"""Base settings — imported by all environment configs."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ── Apps ───────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.postgres",
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "mptt",
    "modeltranslation",
    "imagekit",
    "django_htmx",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "rest_framework",
    "corsheaders",
    "django_ckeditor_5",
]

LOCAL_APPS = [
    "apps.core",
    "apps.catalog",
    "apps.search",
    "apps.cart",
    "apps.checkout",
    "apps.orders",
    "apps.customers",
    "apps.wishlist",
    "apps.compare",
    "apps.reviews",
    "apps.services",
    "apps.pages",
    "apps.promotions",
    "apps.loyalty",
    "apps.notifications",
    "apps.shipping",
    "apps.payments",
    "apps.ai",
    "apps.chat",
    "apps.seo",
    "apps.analytics",
    "apps.importer",
    "apps.integrations.brain",
    "apps.integrations.kancmaster",
    "apps.integrations.novaposhta",
    "apps.integrations.vchasnokasa",
    "apps.bots",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.session_middleware.SplitSessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.core.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Templates ──────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.site_context",
                "apps.core.context_processors.device_context",
                "apps.catalog.context_processors.catalog_nav",
                "apps.cart.context_processors.cart_context",
                "apps.compare.context_processors.compare_context",
                "apps.wishlist.context_processors.wishlist_context",
                "apps.analytics.context_processors.analytics_context",
            ],
        },
    },
]

# ── Database ───────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://svitpc:svitpc@localhost:5432/svitpc"),
}
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 10}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Full-text search — 'ukrainian' is created by apps.search migration (COPY simple)
POSTGRES_FTS_CONFIG = env("POSTGRES_FTS_CONFIG", default="ukrainian")

# ── Cache ──────────────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
        },
        "TIMEOUT": 300,
        "KEY_PREFIX": "svitpc",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── Auth ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "customers.Customer"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
]
LOGIN_URL = "customers:login"
LOGIN_REDIRECT_URL = "customers:dashboard"
LOGOUT_REDIRECT_URL = "catalog:home"

# ── Passwords hashing ──────────────────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# ── Internationalization ───────────────────────────────────────────────────────
LANGUAGE_CODE = env("LANGUAGE_CODE", default="uk")
LANGUAGES = [
    ("uk", "Українська"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ── Static & Media ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Default PK ────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Celery ─────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Kyiv"
# High-priority queue for shipping (TTN) — consumed by dedicated worker (see docker-compose).
CELERY_TASK_DEFAULT_QUEUE = "celery"
CELERY_TASK_ROUTES = {
    # Priority — orders, TTN, emails (dedicated worker).
    "apps.shipping.tasks.create_ttn_for_order": {"queue": "priority"},
    "apps.notifications.tasks.notify_new_order_owner": {"queue": "priority"},
    "apps.notifications.tasks.notify_new_order_customer": {"queue": "priority"},
    "apps.notifications.tasks.notify_order_status": {"queue": "priority"},
    "apps.integrations.vchasnokasa.tasks.fiscalize_payment": {"queue": "priority"},
    # Light — frequent / chunked jobs that must not block catalog imports.
    "apps.shipping.tasks.update_delivery_statuses": {"queue": "light"},
    "catalog.flush_product_views": {"queue": "light"},
    "apps.integrations.novaposhta.tasks.sync_np_cities": {"queue": "light"},
    "apps.integrations.novaposhta.tasks.sync_np_warehouses": {"queue": "light"},
    "apps.integrations.novaposhta.tasks.sync_np_warehouses_chunk": {"queue": "light"},
    "apps.integrations.brain.tasks.sync_prices": {"queue": "light"},
    "apps.integrations.brain.tasks.sync_stock": {"queue": "light"},
    "apps.integrations.brain.tasks.reconcile_stale_stock": {"queue": "light"},
    "apps.integrations.brain.tasks.backfill_metadata": {"queue": "light"},
    # Контентні бекфіли — довгі API-цикли; на light-воркері (CPU-ліміт 0.5)
    # вони не забирають ядро у вебзапитів під час денних доганянь черги.
    "apps.integrations.brain.tasks.backfill_descriptions": {"queue": "light"},
    "apps.integrations.brain.tasks.sync_description_updates": {"queue": "light"},
    "apps.loyalty.tasks.expire_old_coins": {"queue": "light"},
    "apps.loyalty.tasks.send_birthday_greetings": {"queue": "light"},
    "catalog.warm_listing_caches": {"queue": "light"},
}
# Не резервувати пачку важких задач наперед: 1 задача на процес за раз,
# інакше воркер одразу "захоплює" весь накопичений backlog.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
from config.celery_beat_schedule import CELERY_BEAT_SCHEDULE  # noqa: E402

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@svitpc.ua")

# ── Sessions security ──────────────────────────────────────────────────────────
# Admin uses a separate session cookie so staff login does not log in on the storefront.
ADMIN_SESSION_COOKIE_NAME = "admin_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
# Store CSRF in the active session (admin_sessionid vs sessionid) so admin tabs
# do not invalidate storefront forms via a shared csrftoken cookie.
CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_TRUSTED_ORIGINS = [env("SITE_URL", default="http://localhost:8000")]

# ── Axes (brute-force protection) ─────────────────────────────────────────────
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_CALLABLE = "apps.core.utils.axes_lockout"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.customers.backends.CustomerModelBackend",
]

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
}

# ── Admin (Unfold) ─────────────────────────────────────────────────────────────
from django.templatetags.static import static  # noqa: E402
from django.urls import reverse_lazy  # noqa: E402

UNFOLD = {
    "SITE_TITLE": "СвітПК Адмін",
    "SITE_HEADER": "СвітПК",
    "SITE_SUBHEADER": "Адміністрування",
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("images/logo-admin.svg"),
        "dark": lambda request: static("images/logo-admin-dark.svg"),
    },
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "type": "image/svg+xml",
            "href": lambda request: static("images/favicon.svg"),
        },
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
            "href": lambda request: static("images/favicon-32.png"),
        },
        {
            "rel": "icon",
            "sizes": "16x16",
            "type": "image/png",
            "href": lambda request: static("images/favicon-16.png"),
        },
        {
            "rel": "apple-touch-icon",
            "sizes": "180x180",
            "href": lambda request: static("images/apple-touch-icon.png"),
        },
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "command_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Замовлення",
                "separator": False,
                "items": [
                    {
                        "title": "Замовлення",
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:orders_order_changelist"),
                    },
                    {
                        "title": "Платежі",
                        "icon": "payments",
                        "link": reverse_lazy("admin:payments_payment_changelist"),
                    },
                    {
                        "title": "Статуси замовлень",
                        "icon": "label",
                        "link": reverse_lazy("admin:orders_orderstatus_changelist"),
                    },
                ],
            },
            {
                "title": "Каталог",
                "separator": True,
                "items": [
                    {
                        "title": "Товари",
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:catalog_product_changelist"),
                    },
                    {
                        "title": "Категорії",
                        "icon": "category",
                        "link": reverse_lazy("admin:catalog_category_changelist"),
                    },
                    {
                        "title": "Бренди",
                        "icon": "verified",
                        "link": reverse_lazy("admin:catalog_brand_changelist"),
                    },
                    {
                        "title": "Атрибути",
                        "icon": "tune",
                        "link": reverse_lazy("admin:catalog_attribute_changelist"),
                    },
                    {
                        "title": "Групи атрибутів",
                        "icon": "folder",
                        "link": reverse_lazy("admin:catalog_attributegroup_changelist"),
                    },
                    {
                        "title": "Фільтри",
                        "icon": "filter_list",
                        "link": reverse_lazy("admin:catalog_filtergroup_changelist"),
                    },
                    {
                        "title": "Значення фільтрів",
                        "icon": "label",
                        "link": reverse_lazy("admin:catalog_filter_changelist"),
                    },
                ],
            },
            {
                "title": "Клієнти",
                "separator": True,
                "items": [
                    {
                        "title": "Клієнти",
                        "icon": "group",
                        "link": reverse_lazy("admin:customers_customer_changelist"),
                    },
                    {
                        "title": "Відгуки",
                        "icon": "rate_review",
                        "link": reverse_lazy("admin:reviews_review_changelist"),
                    },
                    {
                        "title": "Промокоди",
                        "icon": "confirmation_number",
                        "link": reverse_lazy("admin:loyalty_coupon_changelist"),
                    },
                    {
                        "title": "Бонусні транзакції",
                        "icon": "stars",
                        "link": reverse_lazy("admin:loyalty_bonustransaction_changelist"),
                    },
                ],
            },
            {
                "title": "Маркетинг",
                "separator": True,
                "items": [
                    {
                        "title": "Акції",
                        "icon": "local_offer",
                        "link": reverse_lazy("admin:promotions_promotion_changelist"),
                    },
                    {
                        "title": "Банери",
                        "icon": "image",
                        "link": reverse_lazy("admin:promotions_banner_changelist"),
                    },
                    {
                        "title": "Реклама на головній",
                        "icon": "view_carousel",
                        "link": reverse_lazy("admin:promotions_homeadsettings_changelist"),
                    },
                    {
                        "title": "Push-підписки",
                        "icon": "notifications",
                        "link": reverse_lazy("admin:notifications_pushsubscription_changelist"),
                    },
                    {
                        "title": "Фід Google",
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:analytics_feeds_dashboard"),
                    },
                ],
            },
            {
                "title": "Сервіс",
                "separator": True,
                "items": [
                    {
                        "title": "Заявки на сервіс",
                        "icon": "handyman",
                        "link": reverse_lazy("admin:services_servicerequest_changelist"),
                    },
                    {
                        "title": "Заявки на гарантію",
                        "icon": "verified",
                        "link": reverse_lazy("admin:services_warrantyclaim_changelist"),
                    },
                    {
                        "title": "Заявки на повернення",
                        "icon": "assignment_return",
                        "link": reverse_lazy("admin:pages_returnrequest_changelist"),
                    },
                    {
                        "title": "Послуги",
                        "icon": "build",
                        "link": reverse_lazy("admin:services_service_changelist"),
                    },
                    {
                        "title": "Категорії послуг",
                        "icon": "folder_open",
                        "link": reverse_lazy("admin:services_servicecategory_changelist"),
                    },
                    {
                        "title": "Прейскурант",
                        "icon": "payments",
                        "link": reverse_lazy("admin:services_priceitem_changelist"),
                    },
                    {
                        "title": "Серійні номери",
                        "icon": "qr_code_2",
                        "link": reverse_lazy("admin:services_productserial_changelist"),
                    },
                ],
            },
            {
                "title": "Контент",
                "separator": True,
                "items": [
                    {
                        "title": "Сторінки",
                        "icon": "article",
                        "link": reverse_lazy("admin:pages_infopage_changelist"),
                    },
                    {
                        "title": "Редиректи",
                        "icon": "alt_route",
                        "link": reverse_lazy("admin:catalog_redirect_changelist"),
                    },
                    {
                        "title": "SEO URL",
                        "icon": "link",
                        "link": reverse_lazy("admin:catalog_seourl_changelist"),
                    },
                ],
            },
            {
                "title": "Налаштування",
                "separator": True,
                "items": [
                    {
                        "title": "Контакти та сайт",
                        "icon": "store",
                        "link": reverse_lazy("admin:core_sitesettings_changelist"),
                    },
                    {
                        "title": "Знижкові правила",
                        "icon": "percent",
                        "link": reverse_lazy("admin:catalog_markuprule_changelist"),
                    },
                    {
                        "title": "Нова Пошта — міста",
                        "icon": "location_city",
                        "link": reverse_lazy("admin:shipping_novaposhtacity_changelist"),
                    },
                    {
                        "title": "Нова Пошта — відділення",
                        "icon": "local_shipping",
                        "link": reverse_lazy("admin:shipping_novaposhtawarehouse_changelist"),
                    },
                ],
            },
        ],
    },
    "STYLES": [
        lambda request: static("css/admin_extra.css"),
    ],
    "SCRIPTS": [
        lambda request: static("admin/js/admin_sidebar.js"),
    ],
}

# ── Site info ──────────────────────────────────────────────────────────────────
SITE_URL = env("SITE_URL", default="http://localhost:8000")
ADMIN_URL = env("ADMIN_URL", default="admin/")

# ── Integrations ───────────────────────────────────────────────────────────────
BRAIN_LOGIN = env("BRAIN_LOGIN", default="")
BRAIN_PASSWORD = env("BRAIN_PASSWORD", default="")
# Legacy — kept for backward compat; new code uses session auth via BRAIN_LOGIN/BRAIN_PASSWORD
BRAIN_API_URL = env("BRAIN_API_URL", default="https://api.brain.com.ua")
# Auto-hide Brain products with zero availability (is_archive)
BRAIN_HIDE_OUT_OF_STOCK = env.bool("BRAIN_HIDE_OUT_OF_STOCK", default=True)
# Brain /products limit: 100 without OWN_MODE, up to 1000 with OWN_MODE (API docs)
BRAIN_PRODUCTS_PAGE_LIMIT = env.int("BRAIN_PRODUCTS_PAGE_LIMIT", default=100)
# POST /products/content — productIDs per request (max ~100)
BRAIN_CONTENT_BATCH_SIZE = env.int("BRAIN_CONTENT_BATCH_SIZE", default=50)
# Default markup % applied on top of Brain retail price when no MarkupRule matches.
# Brain retail = max(retail_price_uah, recommendable_price, retail_price).
# 5 means: shelf_price = brain_retail * 1.05
BRAIN_DEFAULT_MARKUP_PERCENT = env.int("BRAIN_DEFAULT_MARKUP_PERCENT", default=0)
# Comma-separated top-level category slugs — Brain sync imports only these subtrees.
# Kancmaster is unaffected (separate source). Empty = built-in default list.
BRAIN_ALLOWED_CATEGORY_SLUGS = env("BRAIN_ALLOWED_CATEGORY_SLUGS", default="")

# soft_time_limit (сек) для важких нічних синків — захист від "зависання" (мертвий
# HTTP-запит, нескінченний цикл), а НЕ очікувана тривалість нормального прогону.
# ВАЖЛИВО: має лишатись помітно НИЖЧЕ heavy_catalog_sync_lock TTL (4 год = 14400с,
# apps/integrations/heavy_sync.py) — інакше лок сам протухне під час ще живої
# задачі і ДРУГИЙ синк зможе стартувати паралельно (race). Якщо реальні нічні
# прогони наближаються до цих значень — підняти тут через .env (без релізу коду),
# а не в heavy_sync.py. Перевірити фактичну тривалість на сервері:
#   docker compose logs celery_worker --since 24h | grep -E \
#     "sync_products completed|Kancmaster sync done"
BRAIN_SYNC_PRODUCTS_SOFT_TIME_LIMIT = env.int(
    "BRAIN_SYNC_PRODUCTS_SOFT_TIME_LIMIT", default=3 * 3600,
)
BRAIN_SYNC_IMAGES_SOFT_TIME_LIMIT = env.int(
    "BRAIN_SYNC_IMAGES_SOFT_TIME_LIMIT", default=2 * 3600,
)
BRAIN_SYNC_AVAILABILITY_SOFT_TIME_LIMIT = env.int(
    "BRAIN_SYNC_AVAILABILITY_SOFT_TIME_LIMIT", default=int(1.5 * 3600),
)
KANCMASTER_SYNC_ALL_SOFT_TIME_LIMIT = env.int(
    "KANCMASTER_SYNC_ALL_SOFT_TIME_LIMIT", default=3 * 3600,
)
KANCMASTER_XML_URL = env("KANCMASTER_XML_URL", default="https://kancmaster.com.ua/xml_export_request")
KANCMASTER_LOGIN = env("KANCMASTER_LOGIN", default="")
KANCMASTER_PASSWORD = env("KANCMASTER_PASSWORD", default="")
# When True (default), treat the XML price as the final retail shelf price — no markup applied.
# Set to False only if Kancmaster provides wholesale/purchase prices that require markup.
KANCMASTER_USE_FEED_PRICE_AS_RETAIL = env.bool("KANCMASTER_USE_FEED_PRICE_AS_RETAIL", default=True)
NOVA_POSHTA_API_KEY = env("NOVA_POSHTA_API_KEY", default="")
# Nova Poshta sender configuration (required for TTN creation)
NP_SENDER_REF = env("NP_SENDER_REF", default="")
NP_SENDER_CONTACT_REF = env("NP_SENDER_CONTACT_REF", default="")
NP_SENDER_PHONE = env("NP_SENDER_PHONE", default="")
NP_SENDER_CITY_REF = env("NP_SENDER_CITY_REF", default="")
NP_SENDER_WAREHOUSE_REF = env("NP_SENDER_WAREHOUSE_REF", default="")
LIQPAY_PUBLIC_KEY = env("LIQPAY_PUBLIC_KEY", default="")
LIQPAY_PRIVATE_KEY = env("LIQPAY_PRIVATE_KEY", default="")
LIQPAY_SERVER_URL = env("LIQPAY_SERVER_URL", default="")
LIQPAY_SANDBOX = env.bool("LIQPAY_SANDBOX", default=False)
WAYFORPAY_MERCHANT_ACCOUNT = env("WAYFORPAY_MERCHANT_ACCOUNT", default="")
WAYFORPAY_SECRET_KEY = env("WAYFORPAY_SECRET_KEY", default="")
MONOBANK_TOKEN = env("MONOBANK_TOKEN", default="")
VCHASNO_CASHBOX_KEY = env("VCHASNO_CASHBOX_KEY", default="")
VCHASNO_DEVICE_NAME = env("VCHASNO_DEVICE_NAME", default="SvitPC")
VCHASNO_TAX_GRP = env.int("VCHASNO_TAX_GRP", default=1)
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_ADMIN_CHAT_ID = env("TELEGRAM_ADMIN_CHAT_ID", default="")
TELEGRAM_BOT_LINK = env("TELEGRAM_BOT_LINK", default="")
LLM_API_KEY = env("LLM_API_KEY", default="")
LLM_MODEL = env("LLM_MODEL", default="gpt-4o-mini")
LLM_BASE_URL = env("LLM_BASE_URL", default="https://api.openai.com/v1")
AI_CONSULTANT_ENABLED = env.bool("AI_CONSULTANT_ENABLED", default=False)
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_CLAIMS_EMAIL = env("VAPID_CLAIMS_EMAIL", default="admin@svitpc.ua")
GOOGLE_ANALYTICS_ID = env("GOOGLE_ANALYTICS_ID", default="")
GOOGLE_TAG_MANAGER_ID = env("GOOGLE_TAG_MANAGER_ID", default="")
GOOGLE_ADS_ID = env("GOOGLE_ADS_ID", default="")
ANALYTICS_FEED_MAX_PRODUCTS = env.int("ANALYTICS_FEED_MAX_PRODUCTS", default=10000)
# Категорії (+ їх підкатегорії), з яких формується основний Google Merchant фід.
ANALYTICS_FEED_CATEGORY_SLUGS = env.list(
    "ANALYTICS_FEED_CATEGORY_SLUGS",
    default=["ноутбуки-планшети", "компютери-аксесуари", "комплектуючі-до-пк"],
)
FACEBOOK_PIXEL_ID = env("FACEBOOK_PIXEL_ID", default="")
WAYFORPAY_MERCHANT_DOMAIN = env("WAYFORPAY_MERCHANT_DOMAIN", default="")
SMS_API_KEY = env("SMS_API_KEY", default="")
SMS_SENDER = env("SMS_SENDER", default="SvitPC")
VIBER_BOT_TOKEN = env("VIBER_BOT_TOKEN", default="")

# ── CKEditor 5 ─────────────────────────────────────────────────────────────────
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": {
            "items": [
                "heading", "|", "bold", "italic", "underline", "strikethrough",
                "|", "bulletedList", "numberedList", "blockQuote",
                "|", "link", "imageUpload", "mediaEmbed",
                "|", "undo", "redo", "sourceEditing",
            ],
        },
        "language": "uk",
    },
}
CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

# ── Imagekit ───────────────────────────────────────────────────────────────────
IMAGEKIT_CACHEFILE_DIR = "cache"
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "imagekit.cachefiles.strategies.Optimistic"

# ── MPTT ───────────────────────────────────────────────────────────────────────
MPTT_DEFAULT_LEVEL_INDICATOR = "—"

# ── Modeltranslation ───────────────────────────────────────────────────────────
MODELTRANSLATION_DEFAULT_LANGUAGE = "uk"
MODELTRANSLATION_LANGUAGES = ("uk", "en")
MODELTRANSLATION_FALLBACK_LANGUAGES = ("uk",)

# ── Logging ────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/django.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
    },
}
