from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_add_product_embedding_stub"),
    ]

    operations = [
        migrations.AddField(
            model_name="filtergroup",
            name="is_brand",
            field=models.BooleanField(
                default=False,
                help_text="Приховати з фасетів — бренди вже відображаються окремим блоком",
                verbose_name="Група брендів",
            ),
        ),
    ]
