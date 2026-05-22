"""Ensure PostgreSQL text search config 'ukrainian' exists (copy of simple)."""

from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_catalog.pg_ts_config WHERE cfgname = 'ukrainian'
                ) THEN
                    CREATE TEXT SEARCH CONFIGURATION ukrainian (COPY = simple);
                END IF;
            END $$;
            """,
            reverse_sql="DROP TEXT SEARCH CONFIGURATION IF EXISTS ukrainian;",
        ),
    ]
