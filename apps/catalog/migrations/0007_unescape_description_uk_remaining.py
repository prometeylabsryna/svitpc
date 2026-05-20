import html

from django.db import migrations


def unescape_description_uk(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    batch_size = 2000
    while True:
        chunk = list(
            Product.objects.filter(description_uk__contains="&lt;")
            .only("pk", "description_uk")[:batch_size]
        )
        if not chunk:
            break
        for product in chunk:
            product.description_uk = html.unescape(product.description_uk)
        Product.objects.bulk_update(chunk, ["description_uk"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_unescape_description_uk"),
    ]

    operations = [
        migrations.RunPython(unescape_description_uk, noop),
    ]
