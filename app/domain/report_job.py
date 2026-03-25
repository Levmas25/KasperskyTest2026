from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReportJob:
    job_id: str
    status: str
    result_path: str | None
    error_msg: str | None
    created_at: datetime
    updated_at: datetime
