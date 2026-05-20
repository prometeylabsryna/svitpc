"""Telegram bot via aiogram 3."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def get_bot():
    from aiogram import Bot

    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


async def send_message(chat_id: str, text: str) -> bool:
    bot = get_bot()
    if not bot:
        return False
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        return True
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)
        return False
    finally:
        await bot.session.close()
