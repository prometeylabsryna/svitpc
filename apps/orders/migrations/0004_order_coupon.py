import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loyalty", "0002_coupon_customer"),
        ("orders", "0003_add_up_barcode_postcode"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="coupon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="loyalty.coupon",
                verbose_name="Промокод",
            ),
        ),
    ]
