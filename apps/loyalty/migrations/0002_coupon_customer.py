import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loyalty", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="coupon",
            name="customer",
            field=models.ForeignKey(
                blank=True,
                help_text="Порожньо — промокод для всіх; заповнено — лише для цього клієнта",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="coupons",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Покупець",
            ),
        ),
    ]
