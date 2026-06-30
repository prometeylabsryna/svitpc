"""One-shot (or periodic) compression of home/category banner uploads."""

from __future__ import annotations

from django.core.cache import cache
from django.core.management.base import BaseCommand

from apps.catalog.home_cache import _home_cache_key
from apps.promotions.banner_image import DESKTOP_MAX_WIDTH, MOBILE_MAX_WIDTH, optimize_field_file
from apps.promotions.models import Banner


class Command(BaseCommand):
    help = "Resize and compress banner images in /media/banners/"

    def handle(self, *args, **options):
        updated = 0
        for banner in Banner.objects.iterator():
            changed = False
            if optimize_field_file(banner.image, max_width=DESKTOP_MAX_WIDTH):
                changed = True
            if optimize_field_file(banner.image_mobile, max_width=MOBILE_MAX_WIDTH):
                changed = True
            if changed:
                banner.save(update_fields=["image", "image_mobile"])
                updated += 1
                self.stdout.write(f"Optimized banner #{banner.pk}: {banner.title or banner}")

        cache.delete(_home_cache_key("banners"))
        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} banner(s)."))
