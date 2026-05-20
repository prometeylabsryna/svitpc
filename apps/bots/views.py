"""Telegram webhook endpoint."""

import json
import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook_view(request: HttpRequest) -> HttpResponse:
    from django.conf import settings

    if not settings.TELEGRAM_BOT_TOKEN:
        return HttpResponse(status=503)

    try:
        import asyncio
        from aiogram import Bot, Dispatcher
        from .telegram.handlers import router

        data = json.loads(request.body)
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()
        dp.include_router(router)

        async def process():
            from aiogram.types import Update
            update = Update(**data)
            await dp.feed_update(bot, update)
            await bot.session.close()

        asyncio.run(process())
    except Exception as exc:
        logger.exception("Telegram webhook error: %s", exc)

    return HttpResponse("OK")
