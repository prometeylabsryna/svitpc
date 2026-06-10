"""Copy legacy catalog text into modeltranslation ``*_uk`` columns."""

from django.db import migrations


def backfill_uk_fields(apps, schema_editor):
    from apps.core.modeltranslation_sync import backfill_uk_from_legacy

    backfill_uk_from_legacy()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_slug_allow_unicode"),
    ]

    operations = [
        migrations.RunPython(backfill_uk_fields, noop),
    ]
