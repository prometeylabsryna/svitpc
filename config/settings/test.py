from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = ["testserver"]

DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "svitpc_test",
        "USER": "svitpc",
        "PASSWORD": "svitpc",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

AXES_ENABLED = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Герметичність: локальний .env не має впливати на очікування тестів
BRAIN_DEFAULT_MARKUP_PERCENT = 0

# Тестова БД використовує справжні міграції catalog (pgvector має бути
# встановлений: локально brew/збірка, у Docker — образ pgvector/pgvector).
# Застарілий обхід migrations_no_vector видалено: він відстав від справжніх
# міграцій і ламав залежності інших apps (services.0004 → catalog.0011).
