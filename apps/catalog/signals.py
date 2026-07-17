"""Catalog signals — keep product FTS index in sync."""

from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
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


def _invalidate_nav_unless_heavy_sync() -> None:
    """Дешеве скидання nav-кешу (кілька cache.delete, без rewarm/delete_pattern).

    Під час важкого нічного синку (heavy_catalog_sync_lock) навмисно
    пропускаємо: там пишуться тисячі товарів підряд і синк сам одноразово
    викликає invalidate_catalog_listing_caches() у finally. Без цього гейта
    кожен save()/зміна categories під час синку зайво скидала б nav —
    той самий N-запис-N-інвалідацій паттерн, який ми вже прибрали для FTS
    (див. defer_fts_refresh).
    """
    from apps.integrations.heavy_sync import is_heavy_sync_running

    if is_heavy_sync_running():
        return
    from apps.catalog.nav import invalidate_nav_cache

    invalidate_nav_cache()


@receiver(post_save, sender=Product)
def invalidate_nav_on_product_change(sender, instance: Product, **kwargs) -> None:
    """Товар вручну доданий/змінений в адмінці — категорія має з'явитись у навігації одразу.

    Ловить, зокрема, перший товар у раніше порожній категорії (напр. «Б/У»):
    без цього нав-кеш (TTL 30 хв) продовжував би ховати її як «без товарів».
    """
    _invalidate_nav_unless_heavy_sync()


@receiver(m2m_changed, sender=Product.categories.through)
def invalidate_nav_on_product_categories_change(sender, instance, action, **kwargs) -> None:
    """Зміна прив'язки товару до категорій (форма адмінки: поле «Категорії»)."""
    if action in ("post_add", "post_remove", "post_clear"):
        _invalidate_nav_unless_heavy_sync()
