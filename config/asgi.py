import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.develop")

# Channels/WebSocket прибрано: пакета channels немає в залежностях, а
# websocket-роутинг чату порожній. Якщо WebSocket знадобиться — додати
# channels у requirements і повернути ProtocolTypeRouter.
application = get_asgi_application()
