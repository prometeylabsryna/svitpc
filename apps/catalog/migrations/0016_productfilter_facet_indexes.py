from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0015_backfill_modeltranslation_uk_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="productfilter",
            index=models.Index(fields=["filter", "product"], name="catalog_pf_filter_product"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["is_visible", "sort_order"], name="catalog_prod_vis_sort"),
        ),
    ]
