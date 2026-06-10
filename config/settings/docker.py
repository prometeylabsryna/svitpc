"""Production settings for Docker (nginx terminates TLS)."""

from .production import *  # noqa: F401, F403

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# TLS завершується в nginx; Gunicorn слухає HTTP (healthcheck без 301)
SECURE_SSL_REDIRECT = False

# nginx віддає static/media — WhiteNoise не потрібен
MIDDLEWARE = [m for m in MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"]  # noqa: F405

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
