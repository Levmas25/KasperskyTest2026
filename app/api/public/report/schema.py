from pydantic import BaseModel


class ExportReportResponse(BaseModel):

    job_id: str
    status: str


class ReportStatusResponse(BaseModel):

    job_id: str
    status: str
    download_url: str | None
    error_msg: str | None