"""
Extract descriptions for Brain products from the OpenCart SQL dump.

The SQL dump contains oc_product_description with descriptions for all products
that were in the old OpenCart store, including Brain products (identified by apiplus_id).
This command matches Brain products by external_id == apiplus_id and
imports their descriptions into description_uk.

Usage:
    python manage.py import_brain_descriptions_from_sql --dry-run
    python manage.py import_brain_descriptions_from_sql
    python manage.py import_brain_descriptions_from_sql --file data/svitpc_2023-02-28_15-47-34_backup.sql
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

logger = logging.getLogger(__name__)

DEFAULT_SQL = Path("data/svitpc_2023-02-28_15-47-34_backup.sql")
# OpenCart language IDs: 1=Russian, 2=Ukrainian
LANG_UK = "2"
LANG_RU = "1"

RE_INSERT = re.compile(r"^INSERT INTO `([^`]+)` \(([^)]+)\) VALUES (.+);$")


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


def _parse_rows(values_str: str) -> list[list]:
    rows: list[list] = []
    current_row: list = []
    current_val: list = []
    in_str = False
    str_char = ""
    escape = False
    i = 0
    while i < len(values_str):
        ch = values_str[i]
        if escape:
            current_val.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
            current_val.append(ch)
        elif in_str:
            if ch == str_char:
                in_str = False
            current_val.append(ch)
        elif ch in ("'", '"'):
            in_str = True
            str_char = ch
            current_val.append(ch)
        elif ch == "(":
            current_val = []
            current_row = []
        elif ch == ",":
            current_row.append(_cast("".join(current_val).strip()))
            current_val = []
        elif ch == ")":
            current_row.append(_cast("".join(current_val).strip()))
            rows.append(current_row)
            current_row = []
            current_val = []
        else:
            current_val.append(ch)
        i += 1
    return rows


def stream_table(filepath: Path, table: str):
    with filepath.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = RE_INSERT.match(line)
            if not m or m.group(1) != table:
                continue
            columns = [c.strip().strip("`") for c in m.group(2).split(",")]
            for row in _parse_rows(m.group(3)):
                yield dict(zip(columns, row))


class Command(BaseCommand):
    help = "Імпортувати описи Brain-товарів з OpenCart SQL-дампу в description_uk"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            default=str(DEFAULT_SQL),
            help=f"Шлях до SQL-дампу (default: {DEFAULT_SQL})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показати кількість збігів — нічого не писати",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.catalog.models import Product
        from apps.catalog.ru_localization import localize_ru_to_uk

        filepath = Path(options["file"])
        dry_run: bool = options["dry_run"]

        if not filepath.exists():
            self.stderr.write(f"SQL file not found: {filepath}")
            return

        self.stdout.write(f"[import_brain_descriptions_from_sql] file={filepath} dry_run={dry_run}")

        # Крок 1: Збудуємо карту {oc_product_id -> apiplus_id}
        self.stdout.write("Читаємо apiplus_id з oc_product...")
        oc_to_brain: dict[int, str] = {}
        for row in stream_table(filepath, "oc_product"):
            apiplus_id = (row.get("apiplus_id") or "").strip()
            if apiplus_id and apiplus_id != "0":
                try:
                    oc_id = int(row["product_id"])
                    oc_to_brain[oc_id] = apiplus_id
                except (KeyError, TypeError, ValueError):
                    pass
        self.stdout.write(f"  Brain продуктів в дампі: {len(oc_to_brain)}")

        # Крок 2: Збудуємо карту {apiplus_id -> description_uk}
        self.stdout.write("Читаємо описи з oc_product_description...")
        # {oc_id: {lang: description}}
        desc_map: dict[int, dict[str, str]] = {}
        for row in stream_table(filepath, "oc_product_description"):
            try:
                oc_id = int(row["product_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if oc_id not in oc_to_brain:
                continue
            lang = str(row.get("language_id", ""))
            desc = (row.get("description") or "").strip()
            if desc:
                desc_map.setdefault(oc_id, {})[lang] = desc

        # Крок 3: Для кожного Brain product_id знаходимо опис (UA > RU)
        brain_id_to_desc: dict[str, str] = {}
        for oc_id, apiplus_id in oc_to_brain.items():
            if oc_id not in desc_map:
                continue
            langs = desc_map[oc_id]
            desc = langs.get(LANG_UK) or langs.get(LANG_RU) or ""
            if desc:
                if langs.get(LANG_RU) and not langs.get(LANG_UK):
                    desc = localize_ru_to_uk(desc, allow_api=False)
                brain_id_to_desc[apiplus_id] = desc

        self.stdout.write(f"  Описів знайдено в дампі: {len(brain_id_to_desc)}")

        if not brain_id_to_desc:
            self.stdout.write(self.style.WARNING("Жодного опису не знайдено. Перевірте файл."))
            return

        # Крок 4: Знаходимо поточні Brain-продукти в нашій БД
        current_brain = {
            p.external_id: p.pk
            for p in Product.objects.filter(
                source=Product.SOURCE_BRAIN,
                external_id__gt="",
                description_uk="",
            ).only("pk", "external_id")
        }
        self.stdout.write(f"  Brain-продукти без опису в БД: {len(current_brain)}")

        matches = {
            ext_id: (pk, brain_id_to_desc[ext_id])
            for ext_id, pk in current_brain.items()
            if ext_id in brain_id_to_desc
        }
        self.stdout.write(f"  Збігів: {len(matches)}")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n[DRY RUN] Буде оновлено {len(matches)} товарів. Запусти без --dry-run."))
            # Показуємо приклади
            for ext_id, (pk, desc) in list(matches.items())[:3]:
                self.stdout.write(f"  pk={pk} ext_id={ext_id}: {repr(desc[:80])}")
            return

        if not matches:
            self.stdout.write(self.style.WARNING("Збігів не знайдено — всі Brain-продукти вже мають опис або не знайдені в дампі."))
            return

        # Крок 5: Оновлюємо description_uk в БД
        self.stdout.write(f"Оновлюємо description_uk для {len(matches)} товарів...")
        from django.db import connection

        BATCH = 500
        items = list(matches.values())
        updated = 0
        for i in range(0, len(items), BATCH):
            batch = items[i:i + BATCH]
            with connection.cursor() as cur:
                for pk, desc in batch:
                    cur.execute(
                        "UPDATE catalog_product SET description_uk=%s WHERE id=%s AND (description_uk IS NULL OR description_uk='')",
                        [desc, pk],
                    )
                    updated += cur.rowcount

            if i % (BATCH * 5) == 0 and i > 0:
                self.stdout.write(f"  ...{updated} оновлено")

        self.stdout.write(self.style.SUCCESS(f"\nГотово. Оновлено description_uk для {updated} Brain-товарів."))
        logger.info("import_brain_descriptions_from_sql: updated=%d matched=%d", updated, len(matches))
