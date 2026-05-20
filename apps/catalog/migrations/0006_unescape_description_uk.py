import html

from django.db import migrations


def unescape_description_uk(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    batch_size = 2000
    qs = Product.objects.filter(description_uk__contains="&lt;")
    total = qs.count()
    updated = 0
    while updated < total:
        chunk = list(qs[updated : updated + batch_size])
        if not chunk:
            break
        for product in chunk:
            product.description_uk = html.unescape(product.description_uk)
        Product.objects.bulk_update(chunk, ["description_uk"])
        updated += len(chunk)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_mark_brand_filter_groups"),
    ]

    operations = [
        migrations.RunPython(unescape_description_uk, noop),
    ]
