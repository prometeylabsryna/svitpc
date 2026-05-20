from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Use in-memory cache locally — no Redis needed
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

# Disable HTTPS-only in dev
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Show emails in console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Axes: relaxed in dev
AXES_ENABLED = False

# Show SQL in shell
LOGGING = {  # noqa: F405
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "DEBUG"},
    "loggers": {
        "django.db.backends": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
