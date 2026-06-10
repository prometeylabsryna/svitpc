from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0013_product_sale_end_date"),
    ]

    operations = [
        migrations.AlterField(
            model_name="brand",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                max_length=200,
                unique=True,
                verbose_name="Slug",
            ),
        ),
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                max_length=255,
                unique=True,
                verbose_name="Slug",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="slug",
            field=models.SlugField(
                allow_unicode=True,
                max_length=500,
                unique=True,
                verbose_name="Slug",
            ),
        ),
    ]
