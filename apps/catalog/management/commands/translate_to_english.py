"""Management command: translate catalog DB content to English.

Backends:
  - google  : unofficial Google Translate (free, no key needed) — default
  - llm     : configured LLM provider (needs LLM_API_KEY in .env)

Usage:
    python manage.py translate_to_english
    python manage.py translate_to_english --what=categories
    python manage.py translate_to_english --what=products --batch=40
    python manage.py translate_to_english --backend=llm
    python manage.py translate_to_english --dry-run --limit=10
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.content_translation import run_catalog_translation


class Command(BaseCommand):
    help = "Translate catalog and site content (names, descriptions) to English."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--what",
            choices=[
                "all",
                "catalog",
                "site",
                "categories",
                "brands",
                "filtergroups",
                "filters",
                "attributegroups",
                "attributes",
                "products",
                "productattrs",
            ],
            # productattrs: ~1M+ rows — use only with --with-attribute-values or what=productattrs
            default="all",
        )
        parser.add_argument(
            "--with-attribute-values",
            action="store_true",
            help="Also translate product attribute values (~millions of rows; very slow)",
        )
        parser.add_argument(
            "--backend",
            choices=["google", "llm"],
            default="google",
            help="Translation backend (default: google — free, no key needed)",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--skip-descriptions",
            action="store_true",
            help="Skip long HTML/text descriptions (faster)",
        )
        parser.add_argument("--limit", type=int, default=0, help="Limit items per job (testing)")

    def handle(self, *args, **options) -> None:
        if options["backend"] == "llm":
            from django.conf import settings

            if not getattr(settings, "LLM_API_KEY", ""):
                raise CommandError("LLM_API_KEY is not set. Use --backend=google or add the key to .env")

        if options["dry_run"]:
            from apps.catalog.content_translation import (
                catalog_translation_jobs,
                missing_en_q,
                site_content_translation_jobs,
            )

            what = options["what"]
            jobs = []
            if what in (
                "all",
                "catalog",
                "categories",
                "brands",
                "filtergroups",
                "filters",
                "attributegroups",
                "attributes",
                "products",
                "productattrs",
            ):
                jobs.extend(
                    catalog_translation_jobs(
                        with_descriptions=not options["skip_descriptions"],
                        with_attribute_values=options["with_attribute_values"],
                    )
                )
            if what in ("all", "site"):
                jobs.extend(site_content_translation_jobs())
            for job in jobs:
                pending = job.model.objects.filter(missing_en_q(job.dst_field)).count()
                self.stdout.write(f"  {job.label}: ~{pending} pending")
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] No changes written."))
            return

        def on_progress(label: str, saved: int, total: int) -> None:
            pct = min(100, int(saved / total * 100)) if total else 100
            self.stdout.write(f"  {label}: {pct:3d}% ({saved}/{total})")

        total = run_catalog_translation(
            what=options["what"],
            backend=options["backend"],
            with_descriptions=not options["skip_descriptions"],
            with_attribute_values=options["with_attribute_values"],
            limit=options["limit"],
            on_progress=on_progress,
        )
        self.stdout.write(self.style.SUCCESS(f"\nDone. Total fields updated: {total}"))
