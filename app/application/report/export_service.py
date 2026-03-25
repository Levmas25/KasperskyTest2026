from pathlib import Path

from app.application.report.job_repository import ReportJobRepository
from app.application.report.queue import ReportQueue
from app.infra.storage.report_temp_storage import ReportTempStorage


class ReportExportService:

    def __init__(
        self,
        storage: ReportTempStorage,
        queue: ReportQueue,
        job_repository: ReportJobRepository,
    ):
        self.storage = storage
        self.queue = queue
        self.job_repository = job_repository

    async def create_job(self, job_id: str, input_path: Path) -> None:
        result_path = self.storage.create_result_path(job_id)
        work_path = self.storage.create_work_path(job_id)

        self.job_repository.create_queued(
            job_id=job_id,
            result_path=str(result_path),
        )

        try:
            self.queue.enqueue(
                job_id=job_id,
                input_path=input_path,
                result_path=result_path,
                work_path=work_path,
            )
        except Exception as exc:
            self.job_repository.mark_failed(job_id=job_id, error_msg=str(exc))
            raise
