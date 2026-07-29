"""Django sitemaps for SvitPC."""

from django.contrib.sitemaps import Sitemap

from apps.catalog.models import Brand, Category, Product
from apps.services.models import Service
from apps.pages.models import InfoPage


class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9
    i18n = True

    def items(self):
        return Product.objects.filter(is_visible=True).only("slug", "date_modified")

    def lastmod(self, obj):
        return obj.date_modified

    def location(self, obj):
        return obj.get_absolute_url()


class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    i18n = True

    def items(self):
        """Тільки категорії, які реально відкриваються (не 404).

        `catalog.views.category_view` ховає (404) категорію без жодного
        видимого товару в піддереві — і окремо приховану гілку «Б/У»
        (`is_used_category_branch`). Раніше сюди потрапляли ВСІ активні
        категорії незалежно від джерела товарів (Brain/Kancmaster/manual),
        тому sitemap.xml містив тисячі посилань на неіснуючі сторінки.
        Той самий фільтр застосовуємо тут — БЕЗ прив'язки до Brain-вайтліста
        (`apps.integrations.brain.category_filter`), інакше з sitemap
        зникли б цілком легітимні Kancmaster/manual категорії (напр. «Б/У»),
        які не мають стосунку до Brain, але мають реальні товари й сторінки.
        """
        from apps.catalog.nav import get_subtree_product_counts
        from apps.core.used_category import hidden_used_category_pks

        hidden_pks = hidden_used_category_pks()
        candidates = list(
            Category.objects.filter(is_active=True)
            .exclude(pk__in=hidden_pks)
            .only("slug", "lft", "rght", "tree_id", "level"),
        )
        counts = get_subtree_product_counts({c.pk for c in candidates})
        return [c for c in candidates if counts.get(c.pk, 0) > 0]

    def location(self, obj):
        return obj.get_absolute_url()


class BrandSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return (
            Brand.objects
            .filter(products__is_visible=True)
            .distinct()
            .only("slug")
        )

    def location(self, obj):
        return obj.get_absolute_url()


class ServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Service.objects.filter(is_active=True).only("slug")

    def location(self, obj):
        return obj.get_absolute_url()


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return InfoPage.objects.filter(is_active=True).only("slug", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()
