# Generated manually for used-category site toggle.

from django.db import migrations, models
import django.db.models.deletion


def link_default_used_category(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Category = apps.get_model("catalog", "Category")

    used = Category.objects.filter(slug="бу").first()
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    if used and site.used_category_id is None:
        site.used_category = used
        site.save(update_fields=["used_category"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("core", "0001_sitesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="show_used_category",
            field=models.BooleanField(
                default=True,
                help_text="Вимкніть, щоб приховати категорію з меню та закрити її сторінки.",
                verbose_name="Показувати розділ Б/У на сайті",
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="used_category",
            field=models.ForeignKey(
                blank=True,
                help_text="Розділ каталогу для вживаної техніки. Зазвичай «Б/У».",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="catalog.category",
                verbose_name="Категорія Б/У",
            ),
        ),
        migrations.RunPython(link_default_used_category, migrations.RunPython.noop),
    ]
