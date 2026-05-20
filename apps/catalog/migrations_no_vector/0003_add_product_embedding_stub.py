"""Stub migration for test environments without pgvector.

Adds 'embedding' column as JSONB (not vector) so the model field
references don't break INSERT/UPDATE queries in tests.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_add_category_kancmaster_name"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE catalog_product ADD COLUMN IF NOT EXISTS embedding jsonb NULL;",
            reverse_sql="ALTER TABLE catalog_product DROP COLUMN IF EXISTS embedding;",
        ),
    ]
