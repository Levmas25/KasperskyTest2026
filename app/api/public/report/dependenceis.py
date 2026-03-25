from typing import Annotated

from fastapi import Depends
from redis import Redis
from app.config import get_redis_config, get_report_queue_name, get_report_database_url, get_rq_ttls
from app.application.report.export_service import ReportExportService
from app.application.report.job_repository import ReportJobRepository
from app.infra.storage.report_temp_storage import ReportTempStorage
from app.infra.persistence import (
    SqlAlchemyReportJobRepository,
    create_engine_for_report_jobs,
    init_report_job_schema,
)
from app.infra.rq.rq_queue import RqReportQueue


def get_redis_conn() -> Redis:
    config = get_redis_config()
    return Redis(host=config.host, port=config.port, db=config.db)


def get_storage() -> ReportTempStorage:
    return ReportTempStorage()


def get_report_job_repository() -> ReportJobRepository:
    engine = create_engine_for_report_jobs(get_report_database_url())
    init_report_job_schema(engine)
    return SqlAlchemyReportJobRepository(engine)


def get_report_export_service(
        storage: Annotated[ReportTempStorage, Depends(get_storage)],
        redis_conn: Annotated[Redis, Depends(get_redis_conn)],
        job_repository: Annotated[ReportJobRepository, Depends(get_report_job_repository)],
        ) -> ReportExportService:
    from rq import Queue

    rq_queue = Queue(get_report_queue_name(), connection=redis_conn)
    job_timeout, result_ttl, failure_ttl = get_rq_ttls()
    queue = RqReportQueue(
        rq_queue,
        job_timeout=job_timeout,
        result_ttl=result_ttl,
        failure_ttl=failure_ttl,
    )

    return ReportExportService(
        storage=storage,
        queue=queue,
        job_repository=job_repository,
    )
