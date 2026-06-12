"""Legal entity fields for LiqPay / storefront compliance."""

from django.db import migrations, models


def backfill_legal_info(apps, schema_editor) -> None:
    SiteSettings = apps.get_model("core", "SiteSettings")
    SiteSettings.objects.filter(pk=1).update(
        legal_entity="ФОП",
        legal_name="ІГНАТЕНКО СЕРГІЙ ВОЛОДИМИРОВИЧ",
        tax_id="3180319112",
        legal_address=(
            "56501, Миколаївська обл., Вознесенський р-н, "
            "м. Вознесенськ, вул. Щаслива, буд. 14"
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_sitesettings_viber_phone"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="legal_address",
            field=models.CharField(
                blank=True,
                help_text="Адреса реєстрації з податкової або виписки.",
                max_length=500,
                verbose_name="Юридична адреса",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="legal_entity",
            field=models.CharField(
                blank=True,
                default="ФОП",
                help_text="Напр.: ФОП або ТОВ — для блоку юридичної інформації на сайті.",
                max_length=20,
                verbose_name="Форма суб'єкта",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="legal_name",
            field=models.CharField(
                blank=True,
                help_text="Як у документах для LiqPay та податкової (ПІБ ФОП або повна назва ТОВ).",
                max_length=255,
                verbose_name="ПІБ / назва юрособи",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="tax_id",
            field=models.CharField(
                blank=True,
                help_text="ІПН для ФОП або ЄДРПОУ для ТОВ.",
                max_length=20,
                verbose_name="РНОКПП / ЄДРПОУ",
            ),
        ),
        migrations.RunPython(backfill_legal_info, migrations.RunPython.noop),
    ]
