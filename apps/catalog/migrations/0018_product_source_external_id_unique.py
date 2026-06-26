"""Deduplicate integration products and enforce unique (source, external_id)."""

from django.db import migrations, models
from django.db.models import Q


def dedupe_integration_products(apps, schema_editor):
    from apps.catalog.product_dedup import dedupe_all_integration_products

    removed = dedupe_all_integration_products()
    if removed:
        print(f"catalog 0018: merged {removed} duplicate integration product(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0017_trgm_search_indexes"),
    ]

    operations = [
        migrations.RunPython(dedupe_integration_products, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=~Q(external_id=""),
                name="catalog_product_source_external_id_uniq",
            ),
        ),
    ]
