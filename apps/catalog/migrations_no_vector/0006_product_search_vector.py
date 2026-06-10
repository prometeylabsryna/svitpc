"""Product.search_vector for test DB (same as 0010, without pgvector deps)."""

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations
from django.db.models import F


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_mark_brand_filter_groups"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddField(
            model_name="product",
            name="search_vector",
            field=SearchVectorField(editable=False, null=True),
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(fields=["search_vector"], name="catalog_product_search_gin"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                OpClass(F("name"), name="gin_trgm_ops"),
                name="catalog_product_name_trgm",
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                OpClass(F("sku"), name="gin_trgm_ops"),
                name="catalog_product_sku_trgm",
            ),
        ),
    ]
