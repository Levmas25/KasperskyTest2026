from typing import Protocol


class ReportQueue(Protocol):
    def enqueue(
            self,
            *,
            job_id: str,
            input_path: str,
            result_path: str,
            work_path: str
        ) -> str:
        ...