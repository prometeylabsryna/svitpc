"""Management command: translate catalog DB content to English.

Backends:
  - google  : unofficial Google Translate (free, no key needed) — default
  - llm     : configured LLM provider (needs LLM_API_KEY in .env)

Usage:
    python manage.py translate_to_english
    python manage.py translate_to_english --what=categories
    python manage.py translate_to_english --what=products --batch=40
    python manage.py translate_to_english --backend=llm --what=categories
    python manage.py translate_to_english --dry-run --limit=10
"""

from __future__ import annotations

import json
import time
import logging
import urllib.parse
from typing import Sequence

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# ─── Google Translate (unofficial, no key required) ───────────────────────────

_GT_URL = "https://translate.googleapis.com/translate_a/single"
_GT_SEPARATOR = "\n\n||||\n\n"


def _google_translate_batch(texts: list[str], src: str = "auto", tgt: str = "en") -> list[str]:
    """Translate a list of strings via unofficial Google Translate."""
    import httpx

    joined = _GT_SEPARATOR.join(t.strip() for t in texts)
    params = {
        "client": "gtx",
        "sl": src,
        "tl": tgt,
        "dt": "t",
        "q": joined,
    }
    resp = httpx.get(_GT_URL, params=params, timeout=30)
    resp.raise_for_status()

    # Response: [[["translated", "original", null, null, 1], ...], ...]
    data = resp.json()
    translated_full = "".join(part[0] for part in data[0] if part[0])

    parts = translated_full.split(_GT_SEPARATOR.strip())
    # Normalise count
    if len(parts) != len(texts):
        # Try alternative separator Google may output
        parts = translated_full.split("||||\n\n")
        if len(parts) != len(texts):
            parts = translated_full.split("||||")
        if len(parts) != len(texts):
            # Fall back to individual calls
            results = []
            for t in texts:
                results.append(_google_translate_single(t, src, tgt))
                time.sleep(0.1)
            return results
    return [p.strip() for p in parts]


def _google_translate_single(text: str, src: str = "auto", tgt: str = "en") -> str:
    import httpx

    params = {"client": "gtx", "sl": src, "tl": tgt, "dt": "t", "q": text.strip()}
    resp = httpx.get(_GT_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return "".join(part[0] for part in data[0] if part[0]).strip()


# ─── LLM backend ──────────────────────────────────────────────────────────────

_LLM_SYSTEM = (
    "You are a professional translator for an e-commerce computer and electronics store. "
    "Translate product catalog texts from Ukrainian or Russian to English. "
    "Keep brand names, model numbers, and technical abbreviations unchanged. "
    "Return ONLY a valid JSON array of strings — the same count as the input, in the same order. "
    "No extra text, no markdown, no commentary."
)


def _llm_translate_batch(texts: list[str]) -> list[str]:
    from apps.ai.services.llm import get_llm

    llm = get_llm()
    raw = llm.complete(json.dumps(texts, ensure_ascii=False), system=_LLM_SYSTEM).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    if len(result) != len(texts):
        raise ValueError(f"LLM returned {len(result)} items, expected {len(texts)}")
    return result


# ─── Command ──────────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Translate catalog content (names, descriptions) to English."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--what",
            choices=[
                "categories", "filtergroups", "filters",
                "attributegroups", "attributes", "products", "all",
            ],
            default="all",
        )
        parser.add_argument(
            "--backend",
            choices=["google", "llm"],
            default="google",
            help="Translation backend (default: google — free, no key needed)",
        )
        parser.add_argument("--batch", type=int, default=40)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--with-descriptions",
            action="store_true",
            help="Also translate product descriptions (very slow)",
        )
        parser.add_argument("--limit", type=int, default=0, help="Limit items for testing")

    # ------------------------------------------------------------------ #

    def _translate(self, texts: list[str], backend: str) -> list[str]:
        """Dispatch to the selected backend, with per-item fallback."""
        if not texts:
            return []
        try:
            if backend == "llm":
                return _llm_translate_batch(texts)
            else:
                return _google_translate_batch(texts)
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f"  Batch failed ({exc}). Retrying in 3 s…"))
            time.sleep(3)
            try:
                if backend == "llm":
                    return _llm_translate_batch(texts)
                else:
                    return _google_translate_batch(texts)
            except Exception as exc2:
                self.stderr.write(self.style.ERROR(f"  Retry failed: {exc2}. Translating individually…"))
                results = []
                for t in texts:
                    try:
                        if backend == "llm":
                            results.append(_llm_translate_batch([t])[0])
                        else:
                            results.append(_google_translate_single(t))
                    except Exception:
                        results.append(t)  # keep original on failure
                    time.sleep(0.2)
                return results

    # ------------------------------------------------------------------ #

    def _process(
        self,
        label: str,
        qs: QuerySet,
        src_field: str,
        dst_field: str,
        batch_size: int,
        backend: str,
        dry_run: bool,
        limit: int,
    ) -> int:
        total = qs.count()
        if total == 0:
            self.stdout.write(f"  {label}: up to date ✓")
            return 0

        effective = min(total, limit) if limit else total
        self.stdout.write(f"\n{self.style.MIGRATE_HEADING(label)}: {effective} items  (batch={batch_size})")

        items = list(qs[:limit] if limit else qs)
        saved = 0

        for start in range(0, len(items), batch_size):
            chunk = items[start : start + batch_size]
            texts = [getattr(obj, src_field) or "" for obj in chunk]
            non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]

            if not non_empty:
                continue

            indices, raw_texts = zip(*non_empty)

            if dry_run:
                self.stdout.write(f"  [DRY-RUN] {len(raw_texts)} items — e.g. {raw_texts[0][:80]!r}")
                continue

            translations = self._translate(list(raw_texts), backend)

            to_update = []
            for idx, translation in zip(indices, translations):
                obj = chunk[idx]
                setattr(obj, dst_field, translation)
                to_update.append(obj)

            with transaction.atomic():
                qs.model.objects.bulk_update(to_update, [dst_field])

            saved += len(to_update)
            pct = min(100, int((start + len(chunk)) / len(items) * 100))
            sample = translations[0][:60] if translations else ""
            self.stdout.write(f"  {pct:3d}%  [{saved}/{effective}]  → {sample!r}")

            time.sleep(0.2)  # polite rate-limit

        return saved

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options) -> None:  # noqa: C901
        from apps.catalog.models import (
            Attribute, AttributeGroup, Category,
            Filter, FilterGroup, Product,
        )

        what = options["what"]
        backend = options["backend"]
        batch = options["batch"]
        dry_run = options["dry_run"]
        with_desc = options["with_descriptions"]
        limit = options["limit"]

        if backend == "llm":
            from django.conf import settings
            if not getattr(settings, "LLM_API_KEY", ""):
                raise CommandError("LLM_API_KEY is not set. Use --backend=google or add the key to .env")

        run_all = what == "all"
        total_saved = 0

        # ── Categories ────────────────────────────────────────────────────
        if run_all or what == "categories":
            total_saved += self._process(
                "Categories › name",
                Category.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )
            total_saved += self._process(
                "Categories › description",
                Category.objects.filter(
                    description_en__isnull=True,
                    description_uk__isnull=False,
                ).exclude(description_uk="").order_by("id"),
                "description_uk", "description_en", min(batch, 10), backend, dry_run, limit,
            )
            total_saved += self._process(
                "Categories › seo_title",
                Category.objects.filter(
                    seo_title_en__isnull=True,
                    seo_title_uk__isnull=False,
                ).exclude(seo_title_uk="").order_by("id"),
                "seo_title_uk", "seo_title_en", batch, backend, dry_run, limit,
            )
            total_saved += self._process(
                "Categories › seo_description",
                Category.objects.filter(
                    seo_description_en__isnull=True,
                    seo_description_uk__isnull=False,
                ).exclude(seo_description_uk="").order_by("id"),
                "seo_description_uk", "seo_description_en", min(batch, 10), backend, dry_run, limit,
            )

        # ── Filter groups + Filters ───────────────────────────────────────
        if run_all or what == "filtergroups":
            total_saved += self._process(
                "FilterGroups › name",
                FilterGroup.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )

        if run_all or what == "filters":
            total_saved += self._process(
                "Filters › name",
                Filter.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )

        # ── Attribute groups + Attributes ─────────────────────────────────
        if run_all or what == "attributegroups":
            total_saved += self._process(
                "AttributeGroups › name",
                AttributeGroup.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )

        if run_all or what == "attributes":
            total_saved += self._process(
                "Attributes › name",
                Attribute.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )

        # ── Products ──────────────────────────────────────────────────────
        if run_all or what == "products":
            total_saved += self._process(
                "Products › name",
                Product.objects.filter(name_en__isnull=True).order_by("id"),
                "name_uk", "name_en", batch, backend, dry_run, limit,
            )
            total_saved += self._process(
                "Products › short_description",
                Product.objects.filter(
                    short_description_en__isnull=True,
                    short_description_uk__isnull=False,
                ).exclude(short_description_uk="").order_by("id"),
                "short_description_uk", "short_description_en", min(batch, 20), backend, dry_run, limit,
            )
            if with_desc:
                total_saved += self._process(
                    "Products › description",
                    Product.objects.filter(
                        description_en__isnull=True,
                        description_uk__isnull=False,
                    ).exclude(description_uk="").order_by("id"),
                    "description_uk", "description_en", 5, backend, dry_run, limit,
                )

        mode = "[DRY-RUN] " if dry_run else ""
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style(f"\n{mode}Done. Total saved: {total_saved}"))
