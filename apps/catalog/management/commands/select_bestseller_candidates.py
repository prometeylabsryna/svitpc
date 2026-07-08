"""
Analyze products in target categories and select the best-selling candidates
for a curated feed, based on real purchase history and engagement signals.

Scoring combines (highest weight first):
  1. Actual sales — sum of OrderItem.qty across all orders (strongest signal:
     proven that customers actually bought this exact product).
  2. Approved reviews — count * average rating (social proof).
  3. is_hit flag — manually curated "bestseller" marker.
  4. Page views — log-scaled so high-traffic outliers don't dominate.
  5. Active discount (old_price > price) — promo pull tends to convert.
  6. Known brand — trust signal vs no-name goods.
  7. Non-empty description — content completeness helps conversion & feed compliance.

Hard requirements (must pass to be eligible at all):
  - is_visible=True, stock>0 (must be actually purchasable right now)
  - price <= --max-price
  - has_display_image=True (no placeholder/stale photo — required for any ad feed)
  - belongs to one of the target category subtrees

Usage:
    python manage.py select_bestseller_candidates
    python manage.py select_bestseller_candidates --max-price 30000 --limit 10000
    python manage.py select_bestseller_candidates --output data/bestseller_feed_pks.json
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import (
    Avg,
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Ln

DEFAULT_CATEGORY_SLUGS = [
    "ноутбуки-планшети",
    "компютери-аксесуари",
    "комплектуючі-до-пк",
    "периферія-оргтехніка",
    "kantseliarski-tovary",
]

CATEGORY_LABELS = {
    "ноутбуки-планшети": "Ноутбуки, планшети",
    "компютери-аксесуари": "Комп'ютери, аксесуари",
    "комплектуючі-до-пк": "Комплектуючі до ПК",
    "периферія-оргтехніка": "Периферія, оргтехніка",
    "kantseliarski-tovary": "Канцелярські товари",
}

# Scoring weights — tuned so real sales dominate, then social proof, then
# curated/engagement/quality signals act as tie-breakers.
W_SOLD_QTY = 100.0
W_REVIEW = 20.0
W_IS_HIT = 500.0
W_VIEWED_LOG = 10.0
W_DISCOUNT = 50.0
W_BRAND = 20.0
W_DESCRIPTION = 30.0


class Command(BaseCommand):
    help = "Score and select top-N best-selling candidate products within budget/category constraints."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--max-price", type=str, default="30000", help="Maximum price (UAH), default 30000.")
        parser.add_argument("--limit", type=int, default=10000, help="Number of products to select, default 10000.")
        parser.add_argument(
            "--categories",
            type=str,
            default=",".join(DEFAULT_CATEGORY_SLUGS),
            help="Comma-separated category slugs (top-level, subtree included).",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="data/bestseller_feed_pks.json",
            help="Path to write the selected product PKs as JSON (relative to project root).",
        )
        parser.add_argument("--top-examples", type=int, default=15, help="How many top-scored examples to print.")

    def handle(self, *args, **options) -> None:
        from apps.catalog.models import Category, Product
        from apps.orders.models import OrderItem
        from apps.reviews.models import Review

        max_price = Decimal(options["max_price"])
        limit = options["limit"]
        slugs = [s.strip() for s in options["categories"].split(",") if s.strip()]

        # ── Resolve category subtree ────────────────────────────────────────
        subtree_pks: set[int] = set()
        cat_by_slug: dict[str, "Category"] = {}
        for slug in slugs:
            cat = Category.objects.filter(slug=slug).first()
            if not cat:
                self.stdout.write(self.style.WARNING(f"  NOT FOUND: {slug}"))
                continue
            cat_by_slug[slug] = cat
            subtree_pks.update(cat.get_descendants(include_self=True).values_list("pk", flat=True))

        if not subtree_pks:
            self.stdout.write(self.style.ERROR("No valid categories resolved — aborting."))
            return

        # ── Base eligible queryset (hard requirements) ──────────────────────
        base_qs = (
            Product.objects.filter(
                is_visible=True,
                stock__gt=0,
                price__lte=max_price,
                has_display_image=True,
                categories__in=subtree_pks,
            )
            .distinct()
        )
        eligible_count = base_qs.count()

        # ── Scoring subqueries (avoid join fan-out from M2M/reverse FK) ─────
        sold_qty_sq = (
            OrderItem.objects.filter(product_id=OuterRef("pk"))
            .values("product_id")
            .annotate(s=Sum("qty"))
            .values("s")
        )
        review_count_sq = (
            Review.objects.filter(product_id=OuterRef("pk"), is_approved=True)
            .values("product_id")
            .annotate(c=Count("id"))
            .values("c")
        )
        review_avg_sq = (
            Review.objects.filter(product_id=OuterRef("pk"), is_approved=True)
            .values("product_id")
            .annotate(a=Avg("rating"))
            .values("a")
        )

        # NOTE: annotation names are prefixed with `bs_` — Product already defines
        # `review_count` / `avg_rating` as @property (reading *_ann attrs), so
        # reusing those names raises "property has no setter" when Django tries
        # to set the annotated column value on the instance.
        scored = base_qs.annotate(
            bs_sold_qty=Coalesce(Subquery(sold_qty_sq, output_field=IntegerField()), Value(0)),
            bs_review_count=Coalesce(Subquery(review_count_sq, output_field=IntegerField()), Value(0)),
            bs_review_avg=Coalesce(Subquery(review_avg_sq, output_field=FloatField()), Value(0.0)),
        ).annotate(
            score=ExpressionWrapper(
                F("bs_sold_qty") * W_SOLD_QTY
                + F("bs_review_count") * F("bs_review_avg") * W_REVIEW
                + Case(When(is_hit=True, then=Value(W_IS_HIT)), default=Value(0.0), output_field=FloatField())
                + Ln(F("viewed") + 1) * W_VIEWED_LOG
                + Case(
                    When(old_price__gt=F("price"), then=Value(W_DISCOUNT)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
                + Case(
                    When(brand__isnull=False, then=Value(W_BRAND)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
                + Case(
                    When(~Q(short_description="") | ~Q(description=""), then=Value(W_DESCRIPTION)),
                    default=Value(0.0),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            )
        ).order_by("-score", "-viewed", "-stock", "pk")

        selected = list(scored[:limit])
        selected_pks = [p.pk for p in selected]

        # ── Per-category breakdown of the final selection ───────────────────
        self.stdout.write(self.style.SUCCESS(f"\nЕligible universe (before scoring): {eligible_count} товарів\n"))
        self.stdout.write(f"Selected: {len(selected_pks)} / {limit} requested\n")

        self.stdout.write("\n=== Розподіл по категоріях (може бути перетин) ===")
        for slug in slugs:
            cat = cat_by_slug.get(slug)
            if not cat:
                continue
            cat_pks = set(cat.get_descendants(include_self=True).values_list("pk", flat=True))
            # Single aggregate query per category instead of N+1 over selected products.
            cnt = Product.objects.filter(pk__in=selected_pks, categories__in=cat_pks).distinct().count()
            self.stdout.write(f"  {CATEGORY_LABELS.get(slug, slug)}: {cnt}")

        with_sales = sum(1 for p in selected if getattr(p, "bs_sold_qty", 0) > 0)
        with_reviews = sum(1 for p in selected if getattr(p, "bs_review_count", 0) > 0)
        is_hit_count = sum(1 for p in selected if p.is_hit)

        self.stdout.write("\n=== Якість вибірки ===")
        self.stdout.write(f"  Мають реальні продажі (OrderItem): {with_sales} ({with_sales * 100 // max(len(selected), 1)}%)")
        self.stdout.write(f"  Мають відгуки: {with_reviews}")
        self.stdout.write(f"  Позначені як 'Хіт продажів': {is_hit_count}")

        if selected:
            scores = [p.score for p in selected]
            self.stdout.write(f"  Score діапазон: {scores[-1]:.1f} (найнижчий у вибірці) — {scores[0]:.1f} (найвищий)")

        top_n = options["top_examples"]
        self.stdout.write(f"\n=== Топ-{top_n} товарів за скором ===")
        for p in selected[:top_n]:
            self.stdout.write(
                f"  [{p.pk}] {p.name[:60]!r} — {p.price} грн, score={p.score:.1f}, "
                f"продано={getattr(p, 'bs_sold_qty', 0)}, перегляди={p.viewed}, хіт={p.is_hit}"
            )

        # ── Persist selection ─────────────────────────────────────────────
        output_path = Path(options["output"])
        if not output_path.is_absolute():
            from django.conf import settings

            output_path = Path(settings.BASE_DIR) / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(selected_pks, ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f"\nЗбережено {len(selected_pks)} PK у {output_path}"))
