from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, insert, select, update
from sqlalchemy.engine import Engine

from app.config import get_report_database_url
from app.domain.report_job import ReportJob


metadata = MetaData()

report_jobs = Table(
    "report_jobs",
    metadata,
    Column("job_id", String(64), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("result_path", Text, nullable=True),
    Column("error_msg", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def create_engine_for_report_jobs(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_report_database_url(), future=True)


def init_report_job_schema(engine: Engine) -> None:
    metadata.create_all(engine)


class SqlAlchemyReportJobRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def create_queued(self, *, job_id: str, result_path: str) -> None:
        now = datetime.now(timezone.utc)
        with self._engine.begin() as connection:
            connection.execute(
                insert(report_jobs).values(
                    job_id=job_id,
                    status="queued",
                    result_path=result_path,
                    error_msg=None,
                    created_at=now,
                    updated_at=now,
                )
            )

    def mark_started(self, *, job_id: str) -> None:
        self._update_status(job_id=job_id, status="started")

    def mark_finished(self, *, job_id: str, result_path: str) -> None:
        self._update_status(job_id=job_id, status="finished", result_path=result_path, error_msg=None)

    def mark_failed(self, *, job_id: str, error_msg: str) -> None:
        self._update_status(job_id=job_id, status="failed", error_msg=error_msg)

    def get(self, job_id: str) -> ReportJob | None:
        with self._engine.begin() as connection:
            row = connection.execute(
                select(
                    report_jobs.c.job_id,
                    report_jobs.c.status,
                    report_jobs.c.result_path,
                    report_jobs.c.error_msg,
                    report_jobs.c.created_at,
                    report_jobs.c.updated_at,
                ).where(report_jobs.c.job_id == job_id)
            ).mappings().first()

        if row is None:
            return None

        return ReportJob(
            job_id=row["job_id"],
            status=row["status"],
            result_path=row["result_path"],
            error_msg=row["error_msg"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _update_status(
        self,
        *,
        job_id: str,
        status: str,
        result_path: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        values = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if result_path is not None:
            values["result_path"] = result_path
        if error_msg is not None or status == "finished":
            values["error_msg"] = error_msg

        with self._engine.begin() as connection:
            result = connection.execute(
                update(report_jobs)
                .where(report_jobs.c.job_id == job_id)
                .values(**values)
            )
            if result.rowcount:
                return

            now = values["updated_at"]
            connection.execute(
                insert(report_jobs).values(
                    job_id=job_id,
                    status=status,
                    result_path=result_path,
                    error_msg=error_msg,
                    created_at=now,
                    updated_at=now,
                )
            )
