from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path
from time import perf_counter

from app.config import get_cleaner_ttls, get_storage_paths
from app.infra.logging_setup import configure_logging


logger = logging.getLogger("app.cleaner")


def clean_temp_files(
        base_dir: str | Path | None = None,
        uploads_dir: str | Path | None = None,
        work_dir: str | Path | None = None,
        uploads_ttl: timedelta | None = None,
        work_ttl: timedelta | None = None,
    ) -> None:
    started_at = perf_counter()
    now = datetime.now()

    uploads_path, work_path = _resolve_cleaner_paths(
        base_dir=base_dir,
        uploads_dir=uploads_dir,
        work_dir=work_dir,
    )
    default_uploads_ttl, default_work_ttl = get_cleaner_ttls()
    effective_uploads_ttl = uploads_ttl or default_uploads_ttl
    effective_work_ttl = work_ttl or default_work_ttl

    logger.info(
        "cleaner started uploads_dir=%s work_dir=%s uploads_ttl=%s work_ttl=%s",
        uploads_path,
        work_path,
        effective_uploads_ttl,
        effective_work_ttl,
    )

    cleaned_uploads = clean_dir(now, uploads_path, effective_uploads_ttl, directory_label="uploads")
    cleaned_work = clean_dir(now, work_path, effective_work_ttl, directory_label="work")

    logger.info(
        "cleaner finished uploads_cleaned=%d work_cleaned=%d total_cleaned=%d elapsed=%.3fs",
        len(cleaned_uploads),
        len(cleaned_work),
        len(cleaned_uploads) + len(cleaned_work),
        perf_counter() - started_at,
    )


def _resolve_cleaner_paths(
        *,
        base_dir: str | Path | None,
        uploads_dir: str | Path | None,
        work_dir: str | Path | None,
    ) -> tuple[Path, Path]:
    if any(value is not None for value in (uploads_dir, work_dir)):
        env_paths = get_storage_paths()
        uploads_path = Path(uploads_dir) if uploads_dir is not None else env_paths.uploads
        work_path = Path(work_dir) if work_dir is not None else env_paths.work
        return uploads_path, work_path

    if base_dir is not None:
        root = Path(base_dir)
        return root / "uploads", root / "work"

    paths = get_storage_paths()
    return paths.uploads, paths.work


def clean_dir(now: datetime, directory: Path, ttl: timedelta, *, directory_label: str) -> list[str]:
    if not directory.exists():
        return []

    cleaned_files: list[str] = []

    for item in directory.iterdir():
        if not item.is_file():
            continue

        modified = datetime.fromtimestamp(item.stat().st_mtime)
        if now - modified > ttl:
            item.unlink(missing_ok=True)
            cleaned_files.append(item.name)
            logger.info(
                "cleaner removed file directory=%s filename=%s modified_at=%s",
                directory_label,
                item.name,
                modified.isoformat(timespec="seconds"),
            )

    return cleaned_files


def main() -> None:
    configure_logging()
    clean_temp_files()


if __name__ == "__main__":
    main()
