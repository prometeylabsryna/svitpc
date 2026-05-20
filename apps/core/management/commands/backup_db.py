"""Management command: dump PostgreSQL database to gzipped SQL backup."""

from __future__ import annotations

import gzip
import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.BASE_DIR) / "backups"
KEEP_DAYS = getattr(settings, "DB_BACKUP_KEEP_DAYS", 14)


class Command(BaseCommand):
    help = "Dump PostgreSQL database to backups/svitpc_YYYYMMDD.sql.gz"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-days",
            type=int,
            default=KEEP_DAYS,
            help="Remove backups older than N days (default: %(default)s)",
        )

    def handle(self, *args, **options):
        if not shutil.which("pg_dump"):
            self.stderr.write(self.style.ERROR("pg_dump not found in PATH"))
            return

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        db_url = settings.DATABASES["default"].get("URL") or getattr(settings, "DATABASE_URL", "")
        db = settings.DATABASES["default"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = BACKUP_DIR / f"svitpc_{timestamp}.sql.gz"

        env: dict[str, str] = {}
        cmd = ["pg_dump", "--no-owner", "--no-acl", "--clean", "--if-exists"]

        if db_url:
            parsed = urlparse(db_url)
            cmd += [
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "svitpc",
                parsed.path.lstrip("/"),
            ]
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
        else:
            cmd += [
                "-h", db.get("HOST", "localhost"),
                "-p", str(db.get("PORT", 5432)),
                "-U", db.get("USER", "svitpc"),
                db.get("NAME", "svitpc"),
            ]
            if db.get("PASSWORD"):
                env["PGPASSWORD"] = db["PASSWORD"]

        self.stdout.write(f"Dumping database → {out_path} …")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                env={**__import__("os").environ, **env},
                check=True,
            )
            with gzip.open(out_path, "wb") as gz:
                gz.write(result.stdout)
            size_mb = out_path.stat().st_size / 1_048_576
            self.stdout.write(self.style.SUCCESS(f"Backup saved: {out_path} ({size_mb:.1f} MB)"))
        except subprocess.CalledProcessError as exc:
            self.stderr.write(self.style.ERROR(f"pg_dump failed: {exc.stderr.decode()[:500]}"))
            return

        keep_days = options["keep_days"]
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0
        for f in BACKUP_DIR.glob("svitpc_*.sql.gz"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                removed += 1
        if removed:
            self.stdout.write(f"Removed {removed} old backup(s) (>{keep_days} days)")
