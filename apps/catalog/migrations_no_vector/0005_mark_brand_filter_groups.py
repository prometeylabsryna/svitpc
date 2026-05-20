from django.db import migrations

_BRAND_GROUP_NAMES = {"Виробник", "Производитель"}


def mark_brand_groups(apps, schema_editor):
    FilterGroup = apps.get_model("catalog", "FilterGroup")
    FilterGroup.objects.filter(name__in=_BRAND_GROUP_NAMES).update(is_brand=True)


def unmark_brand_groups(apps, schema_editor):
    FilterGroup = apps.get_model("catalog", "FilterGroup")
    FilterGroup.objects.filter(name__in=_BRAND_GROUP_NAMES).update(is_brand=False)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_add_filtergroup_is_brand"),
    ]

    operations = [
        migrations.RunPython(mark_brand_groups, reverse_code=unmark_brand_groups),
    ]
