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
        return Category.objects.filter(is_active=True).only("slug", "lft", "rght", "tree_id", "level")

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
