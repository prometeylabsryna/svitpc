from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loyalty", "0002_coupon_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="bonustransaction",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Діє до"),
        ),
        migrations.AddField(
            model_name="bonustransaction",
            name="is_expired",
            field=models.BooleanField(default=False, verbose_name="Протерміновано"),
        ),
        migrations.AddField(
            model_name="coupon",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Загальний / адмін"),
                    ("birthday", "День народження"),
                    ("coin_reward", "Нагорода за монети"),
                ],
                default="manual",
                max_length=20,
                verbose_name="Джерело",
            ),
        ),
        migrations.AlterField(
            model_name="bonustransaction",
            name="amount",
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Монети"),
        ),
        migrations.AlterField(
            model_name="bonustransaction",
            name="transaction_type",
            field=models.CharField(
                choices=[
                    ("earn", "Нарахування"),
                    ("spend", "Списання"),
                    ("adjust", "Коригування"),
                    ("birthday", "Бонус ДН"),
                    ("redeem", "Обмін на купон"),
                    ("expire", "Протерміновано"),
                ],
                max_length=10,
            ),
        ),
    ]
