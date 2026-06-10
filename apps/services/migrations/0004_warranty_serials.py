# Generated manually for warranty / serial number control

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0011_unescape_catalog_text_fields"),
        ("services", "0003_description_ckeditor"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductSerial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("serial_number", models.CharField(db_index=True, max_length=128, unique=True, verbose_name="Серійний номер")),
                ("product_name", models.CharField(blank=True, max_length=500, verbose_name="Назва товару")),
                ("product_code", models.CharField(blank=True, max_length=100, verbose_name="Код товару")),
                ("articul", models.CharField(blank=True, max_length=100, verbose_name="Артикул")),
                ("sale_document", models.CharField(blank=True, max_length=100, verbose_name="Документ продажу")),
                ("sale_date", models.DateField(blank=True, null=True, verbose_name="Дата продажу")),
                ("warranty_until", models.DateField(blank=True, null=True, verbose_name="Гарантія до")),
                ("warranty_months", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Гарантія, міс")),
                (
                    "source",
                    models.CharField(
                        choices=[("brain", "Brain API"), ("manual", "Вручну"), ("order", "Замовлення")],
                        default="manual",
                        max_length=20,
                        verbose_name="Джерело",
                    ),
                ),
                ("brain_order_id", models.CharField(blank=True, max_length=50, verbose_name="ID замовлення Brain")),
                ("notes", models.TextField(blank=True, verbose_name="Примітки")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="serials",
                        to="catalog.product",
                        verbose_name="Товар",
                    ),
                ),
            ],
            options={
                "verbose_name": "Серійний номер",
                "verbose_name_plural": "Серійні номери",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="WarrantyClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rma_number", models.CharField(blank=True, db_index=True, max_length=20, unique=True, verbose_name="№ RMA")),
                ("serial_number", models.CharField(blank=True, db_index=True, max_length=128, verbose_name="Серійний номер")),
                ("without_serial_number", models.BooleanField(default=False, verbose_name="Без серійного номера")),
                ("product_name", models.CharField(max_length=500, verbose_name="Товар")),
                ("product_code", models.CharField(blank=True, max_length=100, verbose_name="Код товару")),
                ("articul", models.CharField(blank=True, max_length=100, verbose_name="Артикул")),
                ("sale_document", models.CharField(blank=True, max_length=100, verbose_name="Документ продажу")),
                ("sale_date", models.DateField(blank=True, null=True, verbose_name="Дата продажу")),
                ("warranty_until", models.DateField(blank=True, null=True, verbose_name="Гарантія до")),
                ("is_under_warranty", models.BooleanField(blank=True, null=True, verbose_name="Гарантійний")),
                ("defect_description", models.CharField(max_length=60, verbose_name="Опис дефекту")),
                ("client_name", models.CharField(blank=True, max_length=200, verbose_name="ПІБ клієнта")),
                ("client_phone", models.CharField(blank=True, max_length=20, verbose_name="Телефон клієнта")),
                ("client_email", models.EmailField(blank=True, max_length=254, verbose_name="Email клієнта")),
                ("client_address", models.CharField(blank=True, max_length=500, verbose_name="Адреса клієнта")),
                (
                    "delivery_service",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("nova_poshta", "Нова Пошта"),
                            ("ukrposhta", "Укрпошта"),
                            ("other", "Інша"),
                        ],
                        max_length=20,
                        verbose_name="Служба доставки",
                    ),
                ),
                ("waybill_number", models.CharField(blank=True, max_length=100, verbose_name="Номер накладної СД")),
                ("waybill_date", models.DateField(blank=True, null=True, verbose_name="Дата накладної СД")),
                ("comment", models.CharField(blank=True, max_length=250, verbose_name="Коментар")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Чернетка"),
                            ("submitted", "Відправлена"),
                            ("in_progress", "В обробці"),
                            ("done", "Завершена"),
                            ("cancelled", "Скасована"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата відправки")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="warranty_claims",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Створив",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="warranty_claims",
                        to="catalog.product",
                        verbose_name="Товар",
                    ),
                ),
                (
                    "product_serial",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claims",
                        to="services.productserial",
                        verbose_name="Запис серійного номера",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заявка на гарантію",
                "verbose_name_plural": "Заявки на гарантію",
                "ordering": ["-created_at"],
            },
        ),
    ]
