import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoragePaths:
    uploads: Path
    results: Path
    work: Path


@dataclass(frozen=True, slots=True)
class RedisConfig:
    host: str
    port: int
    db: int


def get_storage_paths() -> StoragePaths:
    return StoragePaths(
        uploads=Path(os.getenv("REPORT_UPLOADS_DIR", "/data/uploads")),
        results=Path(os.getenv("REPORT_RESULTS_DIR", "/data/results")),
        work=Path(os.getenv("REPORT_WORK_DIR", "/data/work")),
    )


def get_redis_config() -> RedisConfig:
    return RedisConfig(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
    )


def get_report_queue_name() -> str:
    return os.getenv("REPORT_QUEUE_NAME", "reports")


def get_report_database_url() -> str:
    return os.getenv("REPORT_DATABASE_URL", "sqlite:///./data/report_jobs.db")


def get_rq_ttls() -> tuple[int, int, int]:
    return (
        int(os.getenv("RQ_JOB_TIMEOUT_SECONDS", "3600")),
        int(os.getenv("RQ_RESULT_TTL_SECONDS", "86400")),
        int(os.getenv("RQ_FAILURE_TTL_SECONDS", "604800")),
    )


def get_cleaner_ttls() -> tuple[timedelta, timedelta]:
    return (
        timedelta(
            hours=int(
                os.getenv(
                    "CLEANER_UPLOADS_TTL_HOURS",
                    os.getenv("REPORT_UPLOADS_TTL_HOURS", "1"),
                )
            )
        ),
        timedelta(
            hours=int(
                os.getenv(
                    "CLEANER_WORK_TTL_HOURS",
                    os.getenv("REPORT_WORK_TTL_HOURS", "1"),
                )
            )
        ),
    )
