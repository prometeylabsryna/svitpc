from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_coupon"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Email"),
        ),
    ]
