"""Add pg_trgm GIN indexes on catalog_product name/name_uk/sku for fast trigram search.

pg_trgm extension is already installed (CREATE EXTENSION IF NOT EXISTS pg_trgm).
These indexes make the trigram fallback in search/views.py use index scans
instead of full table scans, cutting fallback query time from ~500ms to <10ms.
"""

from django.contrib.postgres.operations import BtreeGinExtension
from django.db import migrations


class Migration(migrations.Migration):

    atomic = False  # CREATE INDEX CONCURRENTLY cannot run inside a transaction

    dependencies = [
        ("catalog", "0016_productfilter_facet_indexes"),
    ]

    operations = [
        # GIN indexes for pg_trgm — enable fast trigram_word_similar lookups
        migrations.RunSQL(
            sql=[
                "CREATE EXTENSION IF NOT EXISTS pg_trgm",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS catalog_product_name_trgm "
                "ON catalog_product USING GIN (name gin_trgm_ops)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS catalog_product_name_uk_trgm "
                "ON catalog_product USING GIN (name_uk gin_trgm_ops)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS catalog_product_sku_trgm "
                "ON catalog_product USING GIN (sku gin_trgm_ops)",
            ],
            reverse_sql=[
                "DROP INDEX CONCURRENTLY IF EXISTS catalog_product_sku_trgm",
                "DROP INDEX CONCURRENTLY IF EXISTS catalog_product_name_uk_trgm",
                "DROP INDEX CONCURRENTLY IF EXISTS catalog_product_name_trgm",
            ],
        ),
    ]
