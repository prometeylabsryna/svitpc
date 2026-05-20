"""
Stream-parse a 994MB OpenCart MySQL dump and import into Django models.

Usage:
    python manage.py import_opencart_sql --file data/svitpc_2023-02-28_15-47-34_backup.sql
    python manage.py import_opencart_sql --file data/... --steps brands,categories,products
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Iterator

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils.text import slugify

logger = logging.getLogger(__name__)

BATCH_SIZE = 500

RE_INSERT = re.compile(r"^INSERT INTO `([^`]+)` \(([^)]+)\) VALUES (.+);$")

# OpenCart language IDs in this dump: 1 = Russian, 2 = Ukrainian.
# Per TZ: site supports uk + en only; Russian is NOT needed.
# Strategy: import lang_id=2 as Ukrainian. lang_id=1 (RU) is used ONLY as fallback
#           when Ukrainian text is missing for a given record.
LANG_MAP = {"1": "ru", "2": "uk"}
PRIMARY_LANG = "uk"
FALLBACK_LANG = "ru"

BRAIN_IMG_BASE = "https://opt.brain.com.ua/"

# How many products to auto-flag after import (TZ §4: новинки, хіти продажів)
AUTO_NEW_LIMIT = 100
AUTO_HIT_LIMIT = 100


def parse_values(values_str: str) -> list[list[str | None]]:
    """
    Parse MySQL VALUES clause into list of row-lists.
    Handles multi-row inserts and quoted strings with escaped chars.
    """
    rows: list[list[str | None]] = []
    current_row: list[str | None] = []
    current_val: list[str] = []
    in_str = False
    str_char = ""
    escape = False
    i = 0

    while i < len(values_str):
        ch = values_str[i]

        if escape:
            current_val.append(ch)
            escape = False
            i += 1
            continue

        if ch == "\\":
            escape = True
            current_val.append(ch)
            i += 1
            continue

        if in_str:
            if ch == str_char:
                in_str = False
            current_val.append(ch)
            i += 1
            continue

        if ch in ("'", '"'):
            in_str = True
            str_char = ch
            current_val.append(ch)
            i += 1
            continue

        if ch == "(":
            current_val = []
            current_row = []
            i += 1
            continue

        if ch == ",":
            val = "".join(current_val).strip()
            current_row.append(_cast(val))
            current_val = []
            i += 1
            continue

        if ch == ")":
            val = "".join(current_val).strip()
            current_row.append(_cast(val))
            rows.append(current_row)
            current_row = []
            current_val = []
            i += 1
            continue

        current_val.append(ch)
        i += 1

    return rows


def _cast(val: str) -> str | None:
    if val.upper() == "NULL":
        return None
    if val.startswith("'") and val.endswith("'"):
        return (
            val[1:-1]
            .replace("\\'", "'")
            .replace("\\n", "\n")
            .replace("\\r", "")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
    return val


def stream_table(filepath: Path, table: str) -> Iterator[dict]:
    """Yield rows from a specific table as dicts, streaming the file."""
    with filepath.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = RE_INSERT.match(line)
            if not m:
                continue
            tbl = m.group(1)
            if tbl != table:
                continue
            columns = [c.strip().strip("`") for c in m.group(2).split(",")]
            rows = parse_values(m.group(3))
            for row in rows:
                yield dict(zip(columns, row))


def collect_table(filepath: Path, table: str) -> list[dict]:
    """Collect all rows from a table (used for small tables)."""
    return list(stream_table(filepath, table))


def _pick(desc: dict, *fields: str) -> str:
    """Return first non-empty value for `fields` from primary lang, else fallback lang."""
    for lang in (PRIMARY_LANG, FALLBACK_LANG):
        bucket = desc.get(lang) or {}
        for f in fields:
            v = bucket.get(f) or ""
            if v.strip():
                return v
    return ""


def _normalize_image_url(image: str) -> str:
    """Return absolute image URL. Brain images are remote; everything else is relative
    to OpenCart `image/` folder which is no longer available — keep raw path so admin
    can re-upload, but expose Brain images directly."""
    if not image:
        return ""
    image = image.strip()
    if image.startswith("http://") or image.startswith("https://"):
        return image
    if image.startswith("apiplus/"):
        return BRAIN_IMG_BASE + image
    # Native OC images are no longer reachable; return empty so the placeholder is shown.
    return ""


class Command(BaseCommand):
    help = "Import data from OpenCart SQL backup into SvitPC Django models"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", required=True, help="Path to .sql backup file")
        parser.add_argument(
            "--steps",
            default="brands,categories,attrs,filters,products,images,seo,reviews,flags",
            help="Comma-separated steps to run",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to DB")

    def handle(self, *args, **options) -> None:
        filepath = Path(options["file"])
        if not filepath.exists():
            self.stderr.write(f"File not found: {filepath}")
            return

        steps = [s.strip() for s in options["steps"].split(",")]
        dry_run: bool = options["dry_run"]

        log_file = Path("logs/import_opencart.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        self._log_fh = log_file.open("a", encoding="utf-8")
        self._dry_run = dry_run
        self._filepath = filepath

        self.stdout.write(self.style.SUCCESS(f"Starting import from {filepath} (dry_run={dry_run})"))
        t0 = time.time()

        step_funcs = {
            "brands": self._import_brands,
            "categories": self._import_categories,
            "attrs": self._import_attrs,
            "filters": self._import_filters,
            "products": self._import_products,
            "images": self._import_images,
            "seo": self._import_seo,
            "reviews": self._import_reviews,
            "flags": self._auto_flags,
        }

        for step in steps:
            if step not in step_funcs:
                self.stdout.write(self.style.WARNING(f"Unknown step: {step}"))
                continue
            self.stdout.write(f"→ {step}...")
            try:
                step_funcs[step]()
                self.stdout.write(self.style.SUCCESS(f"  ✓ {step} done"))
            except Exception as exc:
                self.stderr.write(f"  ✗ {step} failed: {exc}")
                self._log({"step": step, "error": str(exc)})
                logger.exception("Step %s failed", step)

        elapsed = time.time() - t0
        self.stdout.write(self.style.SUCCESS(f"\nDone in {elapsed:.1f}s"))
        self._log_fh.close()

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _log(self, data: dict) -> None:
        self._log_fh.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _make_unique_slug(self, base: str, existing: set[str], oc_id: int | None = None) -> str:
        """Generate slug, ensuring uniqueness via existing-set; falls back to OC id suffix."""
        slug = slugify(base, allow_unicode=True)[:200] or f"item-{oc_id or 0}"
        if slug not in existing:
            existing.add(slug)
            return slug
        if oc_id:
            candidate = f"{slug}-{oc_id}"
            if candidate not in existing:
                existing.add(candidate)
                return candidate
        counter = 1
        while True:
            candidate = f"{slug}-{counter}"
            if candidate not in existing:
                existing.add(candidate)
                return candidate
            counter += 1

    # ── Step implementations ────────────────────────────────────────────────────

    def _import_brands(self) -> None:
        from apps.catalog.models import Brand

        rows = collect_table(self._filepath, "oc_manufacturer")
        self.stdout.write(f"  {len(rows)} brands found")
        if self._dry_run:
            return

        existing_slugs: set[str] = set(Brand.objects.values_list("slug", flat=True))
        existing_oc: set[int] = set(Brand.objects.filter(oc_id__isnull=False).values_list("oc_id", flat=True))
        to_create: list[Brand] = []
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            oc_id = int(row["manufacturer_id"])
            if oc_id in existing_oc:
                continue
            slug = self._make_unique_slug(name, existing_slugs, oc_id)
            to_create.append(Brand(
                name=name,
                slug=slug,
                sort_order=int(row.get("sort_order") or 0),
                oc_id=oc_id,
            ))

        Brand.objects.bulk_create(to_create, ignore_conflicts=True, batch_size=BATCH_SIZE)
        self.stdout.write(f"  Created {len(to_create)} brands")

    def _import_categories(self) -> None:
        from apps.catalog.models import Category

        cat_rows = collect_table(self._filepath, "oc_category")
        desc_rows = collect_table(self._filepath, "oc_category_description")

        # Build desc lookup: {oc_id: {lang: {field: value}}}
        desc_map: dict[int, dict] = {}
        for d in desc_rows:
            cid = int(d["category_id"])
            lang = LANG_MAP.get(str(d.get("language_id", "")), "")
            if not lang:
                continue
            desc_map.setdefault(cid, {})[lang] = {
                "name": d.get("name") or "",
                "description": d.get("description") or "",
                "seo_title": d.get("meta_title") or "",
                "seo_description": d.get("meta_description") or "",
            }

        if self._dry_run:
            self.stdout.write(f"  {len(cat_rows)} categories (dry-run)")
            return

        existing_slugs: set[str] = set(Category.objects.values_list("slug", flat=True))
        oc_id_to_pk: dict[int, int] = {
            c.oc_id: c.pk for c in Category.objects.filter(oc_id__isnull=False).only("pk", "oc_id")
        }

        # Process roots first, then descendants (so parent_pk is already known).
        created = 0
        for row in sorted(cat_rows, key=lambda r: int(r.get("parent_id") or 0)):
            oc_id = int(row["category_id"])
            if oc_id in oc_id_to_pk:
                continue

            desc = desc_map.get(oc_id, {})
            name = _pick(desc, "name") or f"Категорія {oc_id}"

            parent_oc = int(row.get("parent_id") or 0)
            parent_pk = oc_id_to_pk.get(parent_oc) if parent_oc else None
            slug = self._make_unique_slug(name, existing_slugs, oc_id)

            try:
                with transaction.atomic():
                    cat = Category.objects.create(
                        parent_id=parent_pk,
                        name=name,
                        description=_pick(desc, "description"),
                        seo_title=_pick(desc, "seo_title")[:255],
                        seo_description=_pick(desc, "seo_description")[:500],
                        slug=slug,
                        is_active=bool(int(row.get("status") or 1)),
                        is_top=bool(int(row.get("top") or 0)),
                        sort_order=int(row.get("sort_order") or 0),
                        oc_id=oc_id,
                    )
                    oc_id_to_pk[oc_id] = cat.pk
                    created += 1
            except Exception as e:
                self._log({"step": "categories", "oc_id": oc_id, "error": str(e)})

        Category.objects.rebuild()
        self.stdout.write(f"  Created {created} categories")

    def _import_attrs(self) -> None:
        from apps.catalog.models import Attribute, AttributeGroup

        groups = collect_table(self._filepath, "oc_attribute_group")
        group_descs = collect_table(self._filepath, "oc_attribute_group_description")
        attrs = collect_table(self._filepath, "oc_attribute")
        attr_descs = collect_table(self._filepath, "oc_attribute_description")

        if self._dry_run:
            return

        gd_map: dict[int, dict[str, str]] = {}
        for d in group_descs:
            lang = LANG_MAP.get(str(d.get("language_id", "")), "")
            if not lang:
                continue
            gd_map.setdefault(int(d["attribute_group_id"]), {})[lang] = d.get("name") or ""

        oc_group_to_pk: dict[int, int] = {}
        for g in groups:
            oc_id = int(g["attribute_group_id"])
            names = gd_map.get(oc_id, {})
            name = names.get(PRIMARY_LANG) or names.get(FALLBACK_LANG) or f"Group {oc_id}"
            obj, _ = AttributeGroup.objects.update_or_create(
                oc_id=oc_id, defaults={"name": name, "sort_order": int(g.get("sort_order") or 0)}
            )
            oc_group_to_pk[oc_id] = obj.pk

        ad_map: dict[int, dict[str, str]] = {}
        for d in attr_descs:
            lang = LANG_MAP.get(str(d.get("language_id", "")), "")
            if not lang:
                continue
            ad_map.setdefault(int(d["attribute_id"]), {})[lang] = d.get("name") or ""

        for a in attrs:
            oc_id = int(a["attribute_id"])
            group_pk = oc_group_to_pk.get(int(a.get("attribute_group_id") or 0))
            if not group_pk:
                continue
            names = ad_map.get(oc_id, {})
            name = names.get(PRIMARY_LANG) or names.get(FALLBACK_LANG) or f"Attr {oc_id}"
            Attribute.objects.update_or_create(
                oc_id=oc_id,
                defaults={"group_id": group_pk, "name": name, "sort_order": int(a.get("sort_order") or 0)},
            )

        self.stdout.write(f"  {len(attrs)} attributes processed")

    def _import_filters(self) -> None:
        from apps.catalog.models import Filter, FilterGroup

        groups = collect_table(self._filepath, "oc_filter_group")
        group_descs = collect_table(self._filepath, "oc_filter_group_description")
        filters_ = collect_table(self._filepath, "oc_filter")
        filter_descs = collect_table(self._filepath, "oc_filter_description")

        if self._dry_run:
            return

        def lang_pick(rows, key_id: str, value_field: str) -> dict[int, str]:
            tmp: dict[int, dict[str, str]] = {}
            for d in rows:
                lang = LANG_MAP.get(str(d.get("language_id", "")), "")
                if not lang:
                    continue
                tmp.setdefault(int(d[key_id]), {})[lang] = d.get(value_field) or ""
            return {k: (v.get(PRIMARY_LANG) or v.get(FALLBACK_LANG) or "") for k, v in tmp.items()}

        gd_map = lang_pick(group_descs, "filter_group_id", "name")
        fg_map: dict[int, int] = {}
        for g in groups:
            oc_id = int(g["filter_group_id"])
            obj, _ = FilterGroup.objects.update_or_create(
                oc_id=oc_id,
                defaults={"name": gd_map.get(oc_id) or f"FG{oc_id}", "sort_order": int(g.get("sort_order") or 0)},
            )
            fg_map[oc_id] = obj.pk

        fd_map = lang_pick(filter_descs, "filter_id", "name")
        for f in filters_:
            oc_id = int(f["filter_id"])
            group_pk = fg_map.get(int(f.get("filter_group_id") or 0))
            if not group_pk:
                continue
            Filter.objects.update_or_create(
                oc_id=oc_id,
                defaults={
                    "group_id": group_pk,
                    "name": fd_map.get(oc_id) or f"F{oc_id}",
                    "sort_order": int(f.get("sort_order") or 0),
                },
            )

        self.stdout.write(f"  {len(filters_)} filters processed")

    def _import_products(self) -> None:
        from apps.catalog.models import (
            Attribute,
            Brand,
            Category,
            Product,
            ProductAttribute,
            ProductFilter,
        )
        from apps.catalog.models import Filter as FilterModel

        self.stdout.write("  Loading reference maps...")
        brand_map = {b.oc_id: b.pk for b in Brand.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}
        cat_map = {c.oc_id: c.pk for c in Category.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}
        attr_map = {a.oc_id: a.pk for a in Attribute.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}
        filter_map = {f.oc_id: f.pk for f in FilterModel.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}

        existing_oc_ids: set[int] = set(Product.objects.filter(oc_id__isnull=False).values_list("oc_id", flat=True))
        existing_slugs: set[str] = set(Product.objects.values_list("slug", flat=True))

        # ── Pre-collect SEO URL keywords (preserve original OC SEO URLs per TZ §15) ──
        self.stdout.write("  Collecting SEO URL keywords...")
        seo_keyword_map: dict[int, str] = {}
        for r in stream_table(self._filepath, "oc_seo_url"):
            q = r.get("query") or ""
            if not q.startswith("product_id="):
                continue
            lang = LANG_MAP.get(str(r.get("language_id", "")), "")
            if lang != PRIMARY_LANG:
                # prefer Ukrainian; if missing, allow Russian fallback
                if int(q.split("=", 1)[1]) in seo_keyword_map:
                    continue
            try:
                pid = int(q.split("=", 1)[1])
            except (ValueError, IndexError):
                continue
            kw = (r.get("keyword") or "").strip()
            if kw and (lang == PRIMARY_LANG or pid not in seo_keyword_map):
                seo_keyword_map[pid] = kw

        # ── Descriptions ──
        self.stdout.write("  Collecting descriptions...")
        desc_map: dict[int, dict] = {}
        for d in stream_table(self._filepath, "oc_product_description"):
            pid = int(d["product_id"])
            lang = LANG_MAP.get(str(d.get("language_id", "")), "")
            if not lang:
                continue
            desc_map.setdefault(pid, {})[lang] = {
                "name": d.get("name") or "",
                "description": d.get("description") or "",
                "short_description": d.get("description_short") or "",
                "seo_title": d.get("meta_title") or "",
                "seo_description": d.get("meta_description") or "",
            }

        # ── Categories M2M map ──
        self.stdout.write("  Collecting product-category links...")
        prod_cats: dict[int, list[int]] = {}
        for row in stream_table(self._filepath, "oc_product_to_category"):
            pid = int(row["product_id"])
            cid = int(row["category_id"])
            if cat_map.get(cid):
                prod_cats.setdefault(pid, []).append(cat_map[cid])

        # ── Attributes ──
        self.stdout.write("  Collecting product attributes...")
        prod_attrs: dict[int, list[tuple[int, str]]] = {}
        for row in stream_table(self._filepath, "oc_product_attribute"):
            pid = int(row["product_id"])
            aid = attr_map.get(int(row["attribute_id"]))
            lang = LANG_MAP.get(str(row.get("language_id", "")), "")
            if aid and lang == PRIMARY_LANG:
                prod_attrs.setdefault(pid, []).append((aid, row.get("text") or ""))

        # ── Filters ──
        self.stdout.write("  Collecting product filters...")
        prod_filters: dict[int, list[int]] = {}
        for row in stream_table(self._filepath, "oc_product_filter"):
            pid = int(row["product_id"])
            fid = filter_map.get(int(row["filter_id"]))
            if fid:
                prod_filters.setdefault(pid, []).append(fid)

        if self._dry_run:
            return

        # ── Stream products ──
        self.stdout.write("  Creating products...")
        batch: list[Product] = []
        count = 0

        for row in stream_table(self._filepath, "oc_product"):
            try:
                oc_id = int(row["product_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if oc_id in existing_oc_ids:
                continue

            desc = desc_map.get(oc_id, {})
            name = _pick(desc, "name") or f"Товар {oc_id}"

            seo_kw = seo_keyword_map.get(oc_id, "").strip()
            slug_base = seo_kw or name
            slug = self._make_unique_slug(slug_base, existing_slugs, oc_id)

            brand_pk = brand_map.get(int(row.get("manufacturer_id") or 0))

            try:
                price = float(row.get("price") or 0)
            except (TypeError, ValueError):
                price = 0.0
            try:
                purchase = float(row.get("price_zak") or 0) or None
            except (TypeError, ValueError):
                purchase = None

            apiplus_id = (row.get("apiplus_id") or "").strip()
            source = Product.SOURCE_BRAIN if apiplus_id else Product.SOURCE_MANUAL

            product = Product(
                oc_id=oc_id,
                external_id=apiplus_id,
                source=source,
                sku=(row.get("model") or row.get("sku") or "")[:100],
                model=(row.get("model") or "")[:200],
                brand_id=brand_pk,
                name=name[:500],
                description=_pick(desc, "description"),
                short_description=_pick(desc, "short_description"),
                seo_title=_pick(desc, "seo_title")[:255],
                seo_description=_pick(desc, "seo_description")[:500],
                slug=slug,
                price=price,
                purchase_price=purchase,
                stock=int(row.get("quantity") or 0),
                is_visible=bool(int(row.get("status") or 0)),
                image_url=_normalize_image_url(row.get("image") or ""),
                sort_order=int(row.get("sort_order") or 0),
                viewed=int(row.get("viewed") or 0),
            )
            batch.append(product)

            if len(batch) >= BATCH_SIZE:
                Product.objects.bulk_create(batch, ignore_conflicts=True, batch_size=BATCH_SIZE)
                count += len(batch)
                batch = []
                if count % (BATCH_SIZE * 10) == 0:
                    self.stdout.write(f"  ... {count} products processed")

        if batch:
            Product.objects.bulk_create(batch, ignore_conflicts=True, batch_size=BATCH_SIZE)
            count += len(batch)

        self.stdout.write(f"  {count} products created")

        # ── M2M links ──
        self.stdout.write("  Linking categories, attrs, filters...")
        prod_map = {p.oc_id: p.pk for p in Product.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}
        M2M_cat = Product.categories.through

        cat_m2m = []
        for oc_id, cat_pks in prod_cats.items():
            pk = prod_map.get(oc_id)
            if not pk:
                continue
            for cpk in cat_pks:
                cat_m2m.append(M2M_cat(product_id=pk, category_id=cpk))
        M2M_cat.objects.bulk_create(cat_m2m, ignore_conflicts=True, batch_size=2000)

        attr_objs = []
        for oc_id, items in prod_attrs.items():
            pk = prod_map.get(oc_id)
            if not pk:
                continue
            for aid, val in items:
                attr_objs.append(ProductAttribute(product_id=pk, attribute_id=aid, value=val))
        ProductAttribute.objects.bulk_create(attr_objs, ignore_conflicts=True, batch_size=2000)

        filter_objs = []
        for oc_id, fids in prod_filters.items():
            pk = prod_map.get(oc_id)
            if not pk:
                continue
            for fid in fids:
                filter_objs.append(ProductFilter(product_id=pk, filter_id=fid))
        ProductFilter.objects.bulk_create(filter_objs, ignore_conflicts=True, batch_size=2000)
        self.stdout.write("  Categories/attrs/filters linked")

    def _import_images(self) -> None:
        from apps.catalog.models import Product, ProductImage

        if self._dry_run:
            return

        prod_map = {p.oc_id: p.pk for p in Product.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}
        images: list[ProductImage] = []
        count = 0

        for row in stream_table(self._filepath, "oc_product_image"):
            pid = prod_map.get(int(row["product_id"]))
            url = _normalize_image_url(row.get("image") or "")
            if not pid or not url:
                continue
            images.append(ProductImage(
                product_id=pid,
                image_url=url,
                sort_order=int(row.get("sort_order") or 0),
            ))
            count += 1
            if len(images) >= BATCH_SIZE:
                ProductImage.objects.bulk_create(images, ignore_conflicts=True, batch_size=BATCH_SIZE)
                images = []

        if images:
            ProductImage.objects.bulk_create(images, ignore_conflicts=True, batch_size=BATCH_SIZE)
        self.stdout.write(f"  {count} product images processed")

    def _import_seo(self) -> None:
        from apps.catalog.models import Category, Product, Redirect, SeoUrl

        if self._dry_run:
            return

        seo_rows = collect_table(self._filepath, "oc_seo_url")
        prod_map = {p.oc_id: p for p in Product.objects.filter(oc_id__isnull=False).only("pk", "oc_id", "slug")}
        cat_map = {c.oc_id: c for c in Category.objects.filter(oc_id__isnull=False).only("pk", "oc_id", "slug")}

        seo_objs: list[SeoUrl] = []
        seen_redirect_paths: set[str] = set()
        redirects: list[Redirect] = []

        for row in seo_rows:
            lang_id = str(row.get("language_id", "1"))
            lang_code = LANG_MAP.get(lang_id, PRIMARY_LANG)
            query = row.get("query") or ""
            keyword = row.get("keyword") or ""
            try:
                oc_seo_id = int(row.get("seo_url_id") or 0)
            except (TypeError, ValueError):
                oc_seo_id = 0

            seo_objs.append(SeoUrl(
                language_code=lang_code,
                query=query,
                keyword=keyword,
                oc_id=oc_seo_id,
            ))

            old_path = f"/{keyword}"
            if old_path in seen_redirect_paths:
                continue

            new_path: str | None = None
            if query.startswith("product_id="):
                try:
                    prod = prod_map.get(int(query.split("=", 1)[1]))
                except ValueError:
                    prod = None
                if prod:
                    new_path = prod.get_absolute_url()
            elif query.startswith("category_id="):
                try:
                    cat = cat_map.get(int(query.split("=", 1)[1]))
                except ValueError:
                    cat = None
                if cat:
                    new_path = cat.get_absolute_url()

            if new_path and new_path != old_path:
                seen_redirect_paths.add(old_path)
                redirects.append(Redirect(old_path=old_path, new_path=new_path, status_code=301))

        SeoUrl.objects.bulk_create(seo_objs, ignore_conflicts=True, batch_size=BATCH_SIZE)
        Redirect.objects.bulk_create(redirects, ignore_conflicts=True, batch_size=BATCH_SIZE)
        self.stdout.write(f"  {len(seo_objs)} SEO URLs, {len(redirects)} redirects")

    def _import_reviews(self) -> None:
        if self._dry_run:
            return

        from apps.catalog.models import Product
        from apps.reviews.models import Review

        review_rows = collect_table(self._filepath, "oc_review")
        prod_map = {p.oc_id: p.pk for p in Product.objects.filter(oc_id__isnull=False).only("pk", "oc_id")}

        objs: list[Review] = []
        for row in review_rows:
            try:
                pid = prod_map.get(int(row.get("product_id") or 0))
            except (TypeError, ValueError):
                pid = None
            if not pid:
                continue
            try:
                rating = min(5, max(1, int(row.get("rating") or 5)))
            except (TypeError, ValueError):
                rating = 5
            objs.append(Review(
                product_id=pid,
                author_name=(row.get("author") or "Анонім")[:200],
                rating=rating,
                text=row.get("text") or "",
                is_approved=bool(int(row.get("status") or 0)),
            ))

        Review.objects.bulk_create(objs, ignore_conflicts=True, batch_size=BATCH_SIZE)
        self.stdout.write(f"  {len(objs)} reviews processed")

    def _auto_flags(self) -> None:
        """Auto-flag products as Новинки/Хіти продажів for empty home page (TZ §4)."""
        if self._dry_run:
            return

        from apps.catalog.models import Product

        new_pks = list(
            Product.objects.filter(is_visible=True, stock__gt=0)
            .order_by("-oc_id")
            .values_list("pk", flat=True)[:AUTO_NEW_LIMIT]
        )
        if new_pks:
            Product.objects.filter(pk__in=new_pks).update(is_new=True)

        hit_pks = list(
            Product.objects.filter(is_visible=True, stock__gt=0, viewed__gt=0)
            .order_by("-viewed")
            .values_list("pk", flat=True)[:AUTO_HIT_LIMIT]
        )
        if hit_pks:
            Product.objects.filter(pk__in=hit_pks).update(is_hit=True)

        self.stdout.write(
            f"  Flagged {len(new_pks)} as Новинки, {len(hit_pks)} as Хіти продажів"
        )
