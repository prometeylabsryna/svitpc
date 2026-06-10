"""Verify TurboSMS API key and optionally send a test message."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.notifications import turbosms
from apps.notifications.phone import InvalidPhoneError, normalize_ua_phone


class Command(BaseCommand):
    help = "Перевірити SMS_API_KEY (ping) і за потреби надіслати тестове SMS."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "phone",
            nargs="?",
            help="Номер у форматі +380..., 380... або 0XX...",
        )
        parser.add_argument(
            "--ping-only",
            action="store_true",
            help="Лише перевірити ключ (auth/ping), без відправки SMS.",
        )

    def handle(self, *args, **options) -> None:
        if not turbosms.is_configured():
            raise CommandError(
                "SMS_API_KEY не задано в .env. Додайте ключ з кабінету TurboSMS (HTTP API)."
            )

        try:
            data = turbosms.ping()
        except turbosms.TurboSmsError as exc:
            raise CommandError(f"Ping не вдався: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"TurboSMS OK: {data.get('response_status')}"))

        if options["ping_only"]:
            return

        phone_raw = options.get("phone")
        if not phone_raw:
            raise CommandError("Вкажіть номер телефону або використайте --ping-only.")

        try:
            normalized = normalize_ua_phone(phone_raw)
        except InvalidPhoneError as exc:
            raise CommandError(str(exc)) from exc

        text = "СвітПК: тестове SMS. Ключ TurboSMS підключено успішно."
        try:
            result = turbosms.send_sms(phone_raw, text)
        except turbosms.TurboSmsError as exc:
            raise CommandError(
                f"Відправка не вдалась: {exc}. Перевірте SMS_SENDER у .env "
                f"(зараз: має збігатися з альфа-іменем у кабінеті TurboSMS)."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"SMS надіслано на {normalized}, статус: {result.get('response_status')}"
            )
        )
