"""Management command: register Telegram bot webhook URL."""

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Register or delete Telegram bot webhook. Usage: manage.py setup_telegram_webhook <url>"

    def add_arguments(self, parser):
        parser.add_argument(
            "webhook_url",
            nargs="?",
            default="",
            help="Full HTTPS URL for the webhook endpoint (e.g. https://svitpc.ua/bot/webhook/). "
                 "Leave empty to delete current webhook.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete the current webhook.",
        )
        parser.add_argument(
            "--info",
            action="store_true",
            help="Show current webhook info.",
        )

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set in settings/.env")

        base = f"https://api.telegram.org/bot{token}"

        if options["info"]:
            resp = httpx.get(f"{base}/getWebhookInfo", timeout=10)
            self.stdout.write(str(resp.json()))
            return

        if options["delete"] or not options["webhook_url"]:
            resp = httpx.post(f"{base}/deleteWebhook", timeout=10)
            data = resp.json()
            if data.get("ok"):
                self.stdout.write(self.style.SUCCESS("Webhook deleted."))
            else:
                raise CommandError(f"Failed to delete webhook: {data}")
            return

        url = options["webhook_url"]
        if not url.startswith("https://"):
            raise CommandError("Webhook URL must start with https://")

        resp = httpx.post(
            f"{base}/setWebhook",
            json={"url": url, "allowed_updates": ["message", "callback_query"]},
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            self.stdout.write(self.style.SUCCESS(f"Webhook set: {url}"))
        else:
            raise CommandError(f"Telegram API error: {data}")
