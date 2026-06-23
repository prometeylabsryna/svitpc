"""Catalog models: Brand, Category, Product, images, attributes, filters, SEO."""

from __future__ import annotations

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit
from mptt.models import MPTTModel, TreeForeignKey

try:
    from pgvector.django import VectorField as _VectorField
    PGVECTOR_AVAILABLE = True
except ImportError:
    _VectorField = None
    PGVECTOR_AVAILABLE = False


# ── Brand ──────────────────────────────────────────────────────────────────────
class Brand(models.Model):
    name = models.CharField(_("Назва"), max_length=200)
    slug = models.SlugField(_("Slug"), max_length=200, unique=True, allow_unicode=True)
    logo = models.ImageField(_("Логотип"), upload_to="brands/", null=True, blank=True)
    description = models.TextField(_("Опис"), blank=True)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    # OpenCart FK
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)

    class Meta:
        verbose_name = _("Бренд")
        verbose_name_plural = _("Бренди")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:brand", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


# ── Category ───────────────────────────────────────────────────────────────────
class Category(MPTTModel):
    parent = TreeForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name=_("Батьківська категорія"))
    name = models.CharField(_("Назва"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True, allow_unicode=True)
    description = models.TextField(_("Опис"), blank=True)
    image = models.ImageField(_("Зображення"), upload_to="categories/", null=True, blank=True)
    icon = models.ImageField(_("Іконка"), upload_to="category_icons/", null=True, blank=True)
    is_active = models.BooleanField(_("Активна"), default=True)
    is_top = models.BooleanField(_("Показати у навігації"), default=False)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    seo_title = models.CharField(_("SEO title"), max_length=255, blank=True)
    seo_description = models.CharField(_("SEO description"), max_length=500, blank=True)
    # OpenCart FK
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)
    # Kancmaster category name (used for XML sync mapping)
    kancmaster_name = models.CharField(_("Kancmaster назва"), max_length=255, blank=True, db_index=True)

    class MPTTMeta:
        order_insertion_by = ["sort_order", "name"]

    class Meta:
        verbose_name = _("Категорія")
        verbose_name_plural = _("Категорії")

    def __str__(self) -> str:
        return self.name

    @property
    def admin_path(self) -> str:
        """Full breadcrumb for admin pickers (e.g. «Б/У › Ноутбуки»)."""
        return " › ".join(a.name for a in self.get_ancestors(include_self=True))

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", kwargs={"slug": self.slug})

    @property
    def product_count(self) -> int:
        return Product.objects.filter(categories=self, is_visible=True).count()


# ── Attribute ──────────────────────────────────────────────────────────────────
class AttributeGroup(models.Model):
    name = models.CharField(_("Назва"), max_length=200)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)

    class Meta:
        verbose_name = _("Група атрибутів")
        verbose_name_plural = _("Групи атрибутів")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Attribute(models.Model):
    group = models.ForeignKey(AttributeGroup, on_delete=models.CASCADE, related_name="attributes", verbose_name=_("Група"))
    name = models.CharField(_("Назва"), max_length=200)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)

    class Meta:
        verbose_name = _("Атрибут")
        verbose_name_plural = _("Атрибути")
        ordering = ["group__sort_order", "sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.group.name} / {self.name}"


# ── Filters ────────────────────────────────────────────────────────────────────
class FilterGroup(models.Model):
    name = models.CharField(_("Назва"), max_length=200)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)
    is_brand = models.BooleanField(
        _("Група брендів"),
        default=False,
        help_text=_("Приховати з фасетів — бренди вже відображаються окремим блоком"),
    )

    class Meta:
        verbose_name = _("Група фільтрів")
        verbose_name_plural = _("Групи фільтрів")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Filter(models.Model):
    group = models.ForeignKey(FilterGroup, on_delete=models.CASCADE, related_name="filters", verbose_name=_("Група"))
    name = models.CharField(_("Назва"), max_length=200)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)

    class Meta:
        verbose_name = _("Фільтр")
        verbose_name_plural = _("Фільтри")
        ordering = ["group__sort_order", "sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.group.name}: {self.name}"


# ── Markup Rules ───────────────────────────────────────────────────────────────
class MarkupRule(models.Model):
    """Price markup rules for Brain/Kancmaster products."""

    name = models.CharField(_("Назва"), max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Бренд"))
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Категорія"))
    markup_percent = models.DecimalField(_("Націнка %"), max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(_("Активне"), default=True)
    priority = models.PositiveSmallIntegerField(_("Пріоритет"), default=0, help_text=_("Вищий = важливіший"))

    class Meta:
        verbose_name = _("Правило націнки")
        verbose_name_plural = _("Правила націнки")
        ordering = ["-priority"]

    def __str__(self) -> str:
        return self.name

    def apply(self, base_price: "Decimal") -> "Decimal":  # type: ignore[name-defined]
        from decimal import Decimal

        multiplier = Decimal("1") + self.markup_percent / Decimal("100")
        return (base_price * multiplier).quantize(Decimal("0.01"))


# ── Product ────────────────────────────────────────────────────────────────────
class Product(models.Model):
    SOURCE_BRAIN = "brain"
    SOURCE_KANCMASTER = "kancmaster"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = [
        (SOURCE_BRAIN, "Brain API"),
        (SOURCE_KANCMASTER, "Kancmaster XML"),
        (SOURCE_MANUAL, _("Вручну")),
    ]

    # Identification
    external_id = models.CharField(_("Зовнішній ID"), max_length=100, blank=True, db_index=True)
    source = models.CharField(_("Джерело"), max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    sku = models.CharField(_("Артикул"), max_length=100, blank=True, db_index=True)
    model = models.CharField(_("Модель"), max_length=200, blank=True)
    oc_id = models.PositiveIntegerField(_("OC ID"), null=True, blank=True, unique=True)

    # Relations
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name=_("Бренд"))
    categories = models.ManyToManyField(Category, related_name="products", blank=True, verbose_name=_("Категорії"))

    # Content (translated via django-modeltranslation: name_uk, name_en, etc.)
    name = models.CharField(_("Назва"), max_length=500)
    description = models.TextField(_("Опис"), blank=True)
    short_description = models.TextField(_("Короткий опис"), blank=True)

    # SEO
    slug = models.SlugField(_("Slug"), max_length=500, unique=True, allow_unicode=True)
    seo_title = models.CharField(_("SEO title"), max_length=255, blank=True)
    seo_description = models.CharField(_("SEO description"), max_length=500, blank=True)

    # Pricing
    price = models.DecimalField(_("Ціна"), max_digits=12, decimal_places=2)
    old_price = models.DecimalField(_("Стара ціна"), max_digits=12, decimal_places=2, null=True, blank=True)
    purchase_price = models.DecimalField(_("Закупівельна ціна"), max_digits=12, decimal_places=2, null=True, blank=True)

    # Stock
    stock = models.IntegerField(_("Залишок"), default=0)
    is_visible = models.BooleanField(_("Показувати"), default=True)
    hide_if_out_of_stock = models.BooleanField(_("Приховати без залишку"), default=False)

    # Flags
    is_new = models.BooleanField(_("Новинка"), default=False)
    is_hit = models.BooleanField(_("Хіт продажів"), default=False)
    sale_end_date = models.DateTimeField(
        _("Кінець акції (таймер)"),
        null=True,
        blank=True,
        help_text=_(
            "Дата завершення акції. Таймер на картці та сторінці товару; "
            "автоматично створює запис у розділі «Акції»."
        ),
    )

    # Image
    image = models.ImageField(_("Основне фото"), upload_to="products/", null=True, blank=True)
    image_url = models.URLField(_("URL фото (зовнішній)"), max_length=500, blank=True)
    image_thumb = ImageSpecField(
        source="image",
        processors=[ResizeToFit(300, 300)],
        format="WEBP",
        options={"quality": 82},
    )

    # Timestamps
    date_added = models.DateTimeField(_("Дата додавання"), auto_now_add=True, db_index=True)
    date_modified = models.DateTimeField(_("Дата оновлення"), auto_now=True)
    viewed = models.PositiveIntegerField(_("Переглядів"), default=0)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)

    # AI embedding vector (pgvector, 1536 dims for text-embedding-3-small)
    embedding = (_VectorField(dimensions=1536, null=True, blank=True) if PGVECTOR_AVAILABLE else models.JSONField(null=True, blank=True, help_text="pgvector not available — stored as JSON"))

    # Precomputed FTS (GIN-indexed) — see apps.catalog.search_index
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        verbose_name = _("Товар")
        verbose_name_plural = _("Товари")
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["source", "external_id"]),
            models.Index(fields=["is_visible", "stock"]),
            models.Index(fields=["is_new"]),
            models.Index(fields=["is_hit"]),
            GinIndex(fields=["search_vector"], name="catalog_product_search_gin"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:product", kwargs={"slug": self.slug})

    @property
    def is_available(self) -> bool:
        return self.stock > 0

    @property
    def sale_timer_active(self) -> bool:
        from django.utils import timezone

        return bool(self.sale_end_date and self.sale_end_date > timezone.now())

    @property
    def main_image_url(self) -> str:
        from apps.catalog.gallery import resolve_product_image_url

        return resolve_product_image_url(self)

    @property
    def avg_rating(self) -> float | None:
        # Use queryset annotation when available (avoids N+1 on list pages).
        ann = self.__dict__.get("avg_rating_ann")
        if ann is not None:
            return round(ann, 1)
        agg = self.reviews.filter(is_approved=True).aggregate(avg=models.Avg("rating"))
        return round(agg["avg"], 1) if agg["avg"] else None

    @property
    def review_count(self) -> int:
        ann = self.__dict__.get("review_count_ann")
        if ann is not None:
            return ann
        return self.reviews.filter(is_approved=True).count()

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base = slugify(self.name, allow_unicode=True)
            self.slug = f"{base}-{self.oc_id or self.pk or ''}"
        if self.hide_if_out_of_stock and self.stock <= 0:
            self.is_visible = False
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name=_("Товар"))
    image = models.ImageField(_("Зображення"), upload_to="products/gallery/", null=True, blank=True)
    image_url = models.URLField(_("URL (зовнішній)"), max_length=500, blank=True)
    alt = models.CharField(_("Alt"), max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    thumb = ImageSpecField(
        source="image",
        processors=[ResizeToFit(80, 80)],
        format="WEBP",
        options={"quality": 80},
    )

    class Meta:
        verbose_name = _("Фото товару")
        verbose_name_plural = _("Фото товару")
        ordering = ["sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "sort_order"],
                name="catalog_productimage_product_sort_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} [{self.sort_order}]"

    @property
    def url(self) -> str:
        if self.image:
            return self.image.url
        return self.image_url


class ProductAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="attributes", verbose_name=_("Товар"))
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, verbose_name=_("Атрибут"))
    value = models.TextField(_("Значення"))

    class Meta:
        verbose_name = _("Атрибут товару")
        verbose_name_plural = _("Атрибути товару")
        unique_together = [("product", "attribute")]

    def __str__(self) -> str:
        return f"{self.attribute.name}: {self.value}"


class ProductFilter(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="filters", verbose_name=_("Товар"))
    filter = models.ForeignKey(Filter, on_delete=models.CASCADE, verbose_name=_("Фільтр"))

    class Meta:
        verbose_name = _("Фільтр товару")
        verbose_name_plural = _("Фільтри товару")
        unique_together = [("product", "filter")]


# ── SEO URL (legacy redirect support) ─────────────────────────────────────────
class SeoUrl(models.Model):
    """Maps OpenCart query strings to slugs (preserved for 301 redirects)."""

    language_code = models.CharField(_("Мова"), max_length=5, default="uk")
    query = models.CharField(_("OC query"), max_length=255, db_index=True)  # e.g. "product_id=123"
    keyword = models.SlugField(_("Keyword"), max_length=500)  # OC slug
    oc_id = models.PositiveIntegerField(_("OC seo_url_id"), null=True, blank=True)

    class Meta:
        verbose_name = _("SEO URL (OC)")
        verbose_name_plural = _("SEO URLs (OC)")
        unique_together = [("language_code", "query")]

    def __str__(self) -> str:
        return f"{self.query} → {self.keyword}"


class Redirect(models.Model):
    """301/302 redirects — populated from OpenCart SEO URLs during import."""

    old_path = models.CharField(_("Старий шлях"), max_length=500, unique=True, db_index=True)
    new_path = models.CharField(_("Новий шлях"), max_length=500)
    status_code = models.PositiveSmallIntegerField(_("Статус"), default=301, choices=[(301, "301"), (302, "302")])
    is_active = models.BooleanField(_("Активний"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Редірект")
        verbose_name_plural = _("Редіректи")

    def __str__(self) -> str:
        return f"{self.old_path} → {self.new_path} [{self.status_code}]"

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        from apps.core.redirect_cache import invalidate_redirect_cache

        invalidate_redirect_cache()

    def delete(self, *args, **kwargs) -> None:
        super().delete(*args, **kwargs)
        from apps.core.redirect_cache import invalidate_redirect_cache

        invalidate_redirect_cache()
