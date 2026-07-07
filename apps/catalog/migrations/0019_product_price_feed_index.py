"""Add composite index (is_visible, price) for price-tier feed queries."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0018_product_source_external_id_unique"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["is_visible", "price"],
                name="catalog_product_visible_price_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["is_visible", "stock", "price"],
                name="catalog_product_visible_stock_price_idx",
            ),
        ),
    ]
