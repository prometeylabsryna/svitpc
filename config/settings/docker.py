"""Production settings for Docker (nginx terminates TLS)."""

from .production import *  # noqa: F401, F403

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# TLS завершується в nginx; Gunicorn слухає HTTP (healthcheck без 301)
SECURE_SSL_REDIRECT = False

# nginx віддає static/media — WhiteNoise не потрібен
MIDDLEWARE = [
    m
    for m in MIDDLEWARE  # noqa: F405
    if m
    not in (
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "django.middleware.gzip.GZipMiddleware",
        "apps.core.middleware_debug_i18n.DebugI18nMiddleware",
    )
]

DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=600)  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[env("SITE_URL", default="https://svitpc.com.ua")],  # noqa: F405
)

# У контейнері логи → docker logs (без файлу logs/django.log)
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
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
