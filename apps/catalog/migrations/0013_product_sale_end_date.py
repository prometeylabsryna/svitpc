from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_remove_product_catalog_product_name_trgm_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sale_end_date",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Дата завершення акції. Таймер на картці та сторінці товару; "
                    "автоматично створює запис у розділі «Акції»."
                ),
                null=True,
                verbose_name="Кінець акції (таймер)",
            ),
        ),
    ]
