from typing import Any

from app.application.report.queue import ReportQueue
from app.worker.tasks import build_report_task


class RqReportQueue:

    def __init__(
            self,
            queue: Any,
            *,
            job_timeout: int = 60 * 60,
            result_ttl: int = 24 * 60 * 60,
            failure_ttl: int = 7 * 24 * 60 * 60
    ):
        self._queue = queue
        self._job_timeout = job_timeout
        self._result_ttl = result_ttl
        self._failure_ttl = failure_ttl

    def enqueue(
            self,
            *,
            job_id: str,
            input_path: str,
            result_path: str,
            work_path: str
    ) -> str:
        job = self._queue.enqueue(
            build_report_task,
            report_job_id=job_id,
            job_id=job_id,
            input_path=input_path,
            result_path=result_path,
            work_path=work_path,
            job_timeout=self._job_timeout,
            result_ttl=self._result_ttl,
            failure_ttl=self._failure_ttl,
        )
        return job.id
