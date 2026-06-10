from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0005_service_show_on_home"),
    ]

    operations = [
        migrations.AddField(
            model_name="priceitem",
            name="excludes_materials",
            field=models.BooleanField(
                default=False,
                help_text="Позиція позначена * у прейскуранті — вартість робіт без матеріалів",
                verbose_name="Без матеріалів",
            ),
        ),
        migrations.AddField(
            model_name="priceitem",
            name="unit",
            field=models.CharField(
                blank=True,
                help_text="напр. шт, м, км",
                max_length=20,
                verbose_name="Одиниця",
            ),
        ),
    ]
