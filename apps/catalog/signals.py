"""Catalog signals — keep product FTS index in sync."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.catalog.pricing import enforce_retail_price, reconcile_old_price
from apps.catalog.search_index import refresh_product_search_vectors, refresh_products_for_brand


@receiver(pre_save, sender=Product)
def enforce_product_retail_floor(sender, instance: Product, **kwargs) -> None:
    """Never persist a shelf price below purchase + markup (admin, imports, legacy)."""
    if not instance.purchase_price or instance.purchase_price <= 0:
        instance.old_price = reconcile_old_price(instance.price, instance.old_price)
        return

    category_ids: list[int] = []
    if instance.pk:
        category_ids = list(instance.categories.values_list("pk", flat=True))

    instance.price = enforce_retail_price(
        instance.price,
        instance.purchase_price,
        brand_id=instance.brand_id,
        category_ids=category_ids,
    )
    instance.old_price = reconcile_old_price(instance.price, instance.old_price)


@receiver(post_save, sender=Product)
def update_product_search_vector(sender, instance: Product, **kwargs) -> None:
    from apps.integrations.heavy_sync import defer_fts_refresh

    # Під час heavy-синку — відкладаємо rebuild у батч (finally локу),
    # інакше кожен save() у синку робив би повний UPDATE вектора.
    if defer_fts_refresh(instance.pk):
        return
    refresh_product_search_vectors(Product.objects.filter(pk=instance.pk))


@receiver(post_save, sender=Brand)
def update_brand_products_search_vector(sender, instance: Brand, **kwargs) -> None:
    if instance.pk:
        refresh_products_for_brand(instance.pk)


@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
def refresh_product_display_image_flag(sender, instance: ProductImage, **kwargs) -> None:
    """Тримати денормалізований Product.has_display_image актуальним при зміні галереї."""
    from apps.catalog.gallery import recompute_has_display_image

    if instance.product_id:
        recompute_has_display_image([instance.product_id])


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_nav_on_category_change(sender, instance: Category, **kwargs) -> None:
    """Зміна категорії в адмінці одразу відображається в навігації (не чекає TTL 30 хв)."""
    from apps.catalog.admin_category_tree import invalidate_admin_category_tree_cache
    from apps.catalog.nav import invalidate_nav_cache

    invalidate_nav_cache()
    invalidate_admin_category_tree_cache()
