from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0004_warranty_serials"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="show_on_home",
            field=models.BooleanField(
                default=False,
                help_text="Показувати картку послуги в блоці «Сервісний центр» на головній",
                verbose_name="На головній",
            ),
        ),
        migrations.AlterModelOptions(
            name="priceitem",
            options={
                "ordering": ["sort_order"],
                "verbose_name": "Прайс-позиція",
                "verbose_name_plural": "Прайс-позиції",
            },
        ),
    ]
