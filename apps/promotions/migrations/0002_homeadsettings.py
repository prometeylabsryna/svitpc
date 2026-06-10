from django.db import migrations, models


def create_default_settings(apps, schema_editor):
    HomeAdSettings = apps.get_model("promotions", "HomeAdSettings")
    HomeAdSettings.objects.get_or_create(pk=1, defaults={"visible_columns": 4})


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeAdSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "visible_columns",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "1"), (2, "2"), (3, "3"), (4, "4")],
                        default=4,
                        help_text=(
                            "Скільки рекламних зображень показувати одночасно "
                            "на головній сторінці (десктоп)."
                        ),
                        verbose_name="Кількість банерів у рядку",
                    ),
                ),
            ],
            options={
                "verbose_name": "Реклама на головній",
                "verbose_name_plural": "Реклама на головній",
            },
        ),
        migrations.RunPython(create_default_settings, migrations.RunPython.noop),
    ]
