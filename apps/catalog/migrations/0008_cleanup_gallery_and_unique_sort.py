from django.db import migrations, models


def cleanup_gallery(apps, schema_editor):
    from apps.catalog.gallery import cleanup_product_gallery

    # recompute_flags=False: колонка has_display_image з'являється лише в 0020
    cleanup_product_gallery(dry_run=False, recompute_flags=False)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_unescape_description_uk_remaining"),
    ]

    operations = [
        migrations.RunPython(cleanup_gallery, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                fields=("product", "sort_order"),
                name="catalog_productimage_product_sort_uniq",
            ),
        ),
    ]
