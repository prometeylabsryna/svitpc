# Generated manually for SiteSettings singleton.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="СвітПК", max_length=120, verbose_name="Назва магазину")),
                ("name_en", models.CharField(blank=True, max_length=120, verbose_name="Назва (EN)")),
                (
                    "phone",
                    models.CharField(
                        default="+38 (044) 000-00-00",
                        help_text="Відображається у футері, на сторінці контактів та в листах.",
                        max_length=40,
                        verbose_name="Телефон",
                    ),
                ),
                ("email", models.EmailField(default="info@svitpc.ua", max_length=254, verbose_name="Email")),
                (
                    "tagline",
                    models.TextField(
                        blank=True,
                        help_text="Якщо порожньо — використовується стандартний текст перекладу.",
                        verbose_name="Короткий опис у футері",
                    ),
                ),
                ("tagline_en", models.TextField(blank=True, verbose_name="Короткий опис у футері (EN)")),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="Адреса")),
                ("facebook_url", models.URLField(blank=True, verbose_name="Facebook")),
                ("instagram_url", models.URLField(blank=True, verbose_name="Instagram")),
                (
                    "telegram_url",
                    models.URLField(
                        blank=True,
                        help_text="Посилання на канал або бот для футера (не плутати з TELEGRAM_BOT_LINK у .env).",
                        verbose_name="Telegram (посилання)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Налаштування сайту",
                "verbose_name_plural": "Налаштування сайту",
            },
        ),
    ]
