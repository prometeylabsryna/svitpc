"""Align test schema with modeltranslation Brand name fields."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_search_vector"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="name_en",
            field=models.CharField(max_length=200, null=True, verbose_name="Назва"),
        ),
        migrations.AddField(
            model_name="brand",
            name="name_uk",
            field=models.CharField(max_length=200, null=True, verbose_name="Назва"),
        ),
    ]
