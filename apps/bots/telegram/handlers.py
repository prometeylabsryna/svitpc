"""Aiogram handlers — /start, /order, /repair, /contact, /message + free-text relay."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Вітаємо в <b>СвітПК</b>!\n\n"
        "Доступні команди:\n"
        "/order &lt;номер&gt; — статус замовлення\n"
        "/repair &lt;ID&gt; — статус гарантійного ремонту\n"
        "/contact — зв'язатися з магазином\n\n"
        "Або просто напишіть нам — ми передамо ваше повідомлення менеджеру.",
        parse_mode="HTML",
    )


@router.message(Command("order"))
async def cmd_order(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Вкажіть номер замовлення: /order 12345")
        return

    from asgiref.sync import sync_to_async

    @sync_to_async
    def get_order(pk: int):
        from apps.orders.models import Order
        try:
            return Order.objects.select_related("status").get(pk=pk)
        except Order.DoesNotExist:
            return None

    order = await get_order(int(args[1].strip()))
    if order:
        ttn_line = f"\n🚚 ТТН: <b>{order.ttn}</b>" if getattr(order, "ttn", None) else ""
        await message.answer(
            f"📦 Замовлення #{order.pk}: <b>{order.status.name}</b>\n"
            f"💰 Сума: {order.total} ₴"
            f"{ttn_line}",
            parse_mode="HTML",
        )
    else:
        await message.answer("Замовлення не знайдено.")


@router.message(Command("repair"))
async def cmd_repair(message: Message) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Вкажіть ID заявки: /repair 12345")
        return

    from asgiref.sync import sync_to_async

    @sync_to_async
    def get_repair(pk: int):
        from apps.services.models import ServiceRequest
        try:
            return ServiceRequest.objects.select_related("service").get(pk=pk)
        except ServiceRequest.DoesNotExist:
            return None

    req = await get_repair(int(args[1].strip()))
    if req:
        status_label = req.get_status_display_uk()
        cost_info = ""
        if req.final_cost is not None:
            cost_info = f"\n💰 Вартість: <b>{req.final_cost} ₴</b>"
        elif req.estimated_cost is not None:
            cost_info = f"\n💰 Орієнтовна: <b>{req.estimated_cost} ₴</b>"
        await message.answer(
            f"🔧 Заявка #{req.pk}\n"
            f"Пристрій: {req.device}\n"
            f"Статус: <b>{status_label}</b>"
            f"{cost_info}",
            parse_mode="HTML",
        )
    else:
        await message.answer("Заявку не знайдено.")


@router.message(Command("contact"))
async def cmd_contact(message: Message) -> None:
    from apps.core.models import SiteSettings

    site = SiteSettings.load()
    await message.answer(
        f"📞 <b>{site.name}</b>\n"
        f"Телефон: {site.phone}\n"
        f"Email: {site.email}\n\n"
        f"Або просто напишіть тут — менеджер відповість найближчим часом.",
        parse_mode="HTML",
    )


@router.message(Command("message"))
async def cmd_message(message: Message) -> None:
    """Admin command: /message <chat_id> <text> — send message to a customer."""
    from django.conf import settings

    admin_chat = str(getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", ""))
    if str(message.chat.id) != admin_chat:
        await message.answer("Ця команда доступна тільки адміністратору.")
        return

    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /message &lt;chat_id&gt; &lt;текст&gt;", parse_mode="HTML")
        return

    _, target_id, text = parts
    try:
        await message.bot.send_message(chat_id=int(target_id), text=text)
        await message.answer(f"✅ Повідомлення надіслано клієнту {target_id}.")
    except Exception as exc:
        await message.answer(f"❌ Помилка: {exc}")


@router.message(F.text & ~F.text.startswith("/"))
async def relay_to_admin(message: Message) -> None:
    """Forward any plain text from customers to the admin chat."""
    from django.conf import settings

    admin_chat = getattr(settings, "TELEGRAM_ADMIN_CHAT_ID", "")
    if not admin_chat or str(message.chat.id) == str(admin_chat):
        return

    sender = message.from_user
    name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Невідомий"
    username = f" (@{sender.username})" if sender.username else ""
    try:
        await message.bot.send_message(
            chat_id=int(admin_chat),
            text=(
                f"💬 <b>Повідомлення від клієнта</b>\n"
                f"👤 {name}{username}\n"
                f"🆔 chat_id: <code>{message.chat.id}</code>\n\n"
                f"{message.text}"
            ),
            parse_mode="HTML",
        )
        await message.answer("✅ Ваше повідомлення передано менеджеру. Очікуйте відповіді.")
    except Exception:
        await message.answer("Вибачте, виникла помилка. Будь ласка, зателефонуйте нам.")
