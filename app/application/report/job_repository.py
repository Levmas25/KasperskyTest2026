from typing import Protocol

from app.domain.report_job import ReportJob


class ReportJobRepository(Protocol):
    def create_queued(self, *, job_id: str, result_path: str) -> None:
        ...

    def mark_started(self, *, job_id: str) -> None:
        ...

    def mark_finished(self, *, job_id: str, result_path: str) -> None:
        ...

    def mark_failed(self, *, job_id: str, error_msg: str) -> None:
        ...

    def get(self, job_id: str) -> ReportJob | None:
        ...
