from __future__ import annotations

from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def migrate_old_promotions(apps, schema_editor) -> None:
    Promotion = apps.get_model("promotions", "Promotion")
    now = timezone.now()
    default_end = now + timedelta(days=7)

    for promo in list(Promotion.objects.all()):
        product_ids = list(promo.products.values_list("pk", flat=True))
        if not product_ids:
            promo.delete()
            continue

        start = promo.date_start or now
        end = promo.date_end or default_end
        shared = {
            "title_uk": promo.name or "",
            "title_en": promo.name_en or "",
            "description_uk": promo.description or "",
            "description_en": promo.description_en or "",
            "is_active": promo.is_active,
            "start_date": start,
            "end_date": end,
            "auto_synced": False,
        }

        promo.product_id = product_ids[0]
        for field, value in shared.items():
            setattr(promo, field, value)
        promo.save()

        for product_id in product_ids[1:]:
            Promotion.objects.create(product_id=product_id, **shared)


def noop(apps, schema_editor) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0013_product_sale_end_date"),
        ("promotions", "0002_homeadsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="promotion",
            name="product",
            field=models.ForeignKey(
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="promotions",
                to="catalog.product",
                verbose_name="Товар",
            ),
        ),
        migrations.AddField(
            model_name="promotion",
            name="title_uk",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
                verbose_name="Підзаголовок акції",
            ),
        ),
        migrations.AddField(
            model_name="promotion",
            name="title_en",
            field=models.CharField(
                blank=True,
                default="",
                max_length=200,
                verbose_name="Підзаголовок акції",
            ),
        ),
        migrations.AddField(
            model_name="promotion",
            name="auto_synced",
            field=models.BooleanField(
                default=False,
                help_text="Встановлено автоматично з поля «Кінець акції (таймер)» товару.",
                verbose_name="Авто-синхронізовано",
            ),
        ),
        migrations.AddField(
            model_name="promotion",
            name="start_date",
            field=models.DateTimeField(null=True, verbose_name="Початок"),
        ),
        migrations.AddField(
            model_name="promotion",
            name="end_date",
            field=models.DateTimeField(null=True, verbose_name="Кінець"),
        ),
        migrations.RenameField(
            model_name="promotion",
            old_name="description",
            new_name="description_uk",
        ),
        migrations.RunPython(migrate_old_promotions, noop),
        migrations.RemoveField(model_name="promotion", name="name"),
        migrations.RemoveField(model_name="promotion", name="name_en"),
        migrations.RemoveField(model_name="promotion", name="slug"),
        migrations.RemoveField(model_name="promotion", name="image"),
        migrations.RemoveField(model_name="promotion", name="date_start"),
        migrations.RemoveField(model_name="promotion", name="date_end"),
        migrations.RemoveField(model_name="promotion", name="sort_order"),
        migrations.RemoveField(model_name="promotion", name="products"),
        migrations.AlterField(
            model_name="promotion",
            name="product",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="promotions",
                to="catalog.product",
                verbose_name="Товар",
            ),
        ),
        migrations.AlterField(
            model_name="promotion",
            name="start_date",
            field=models.DateTimeField(verbose_name="Початок"),
        ),
        migrations.AlterField(
            model_name="promotion",
            name="end_date",
            field=models.DateTimeField(verbose_name="Кінець"),
        ),
        migrations.AlterModelOptions(
            name="promotion",
            options={
                "ordering": ["-end_date"],
                "verbose_name": "Акція",
                "verbose_name_plural": "Акції",
            },
        ),
    ]
