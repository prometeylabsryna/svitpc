from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_sitesettings_used_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="viber_phone",
            field=models.CharField(
                blank=True,
                help_text="Номер для чату у Viber. Якщо порожньо — використовується основний телефон.",
                max_length=40,
                verbose_name="Viber (телефон)",
            ),
        ),
    ]
