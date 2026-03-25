from pathlib import Path
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.api.public.report.dependenceis import (
    get_report_export_service,
    get_report_job_repository,
    get_storage,
)
from app.api.public.report.schema import ExportReportResponse, ReportStatusResponse
from app.application.report.export_service import ReportExportService
from app.application.report.job_repository import ReportJobRepository

from app.infra.storage.report_temp_storage import ReportTempStorage


router = APIRouter(prefix="/public/report", tags=["report"])


@router.post("/export", response_model=ExportReportResponse, status_code=status.HTTP_202_ACCEPTED)
async def export(
    file: Annotated[UploadFile, File()],
    service: Annotated[ReportExportService, Depends(get_report_export_service)],
    storage: Annotated[ReportTempStorage, Depends(get_storage)]
    ):
    job_id = uuid.uuid4().hex
    input_path = await storage.save_upload(upload=file, job_id=job_id)
    await service.create_job(job_id=job_id, input_path=input_path)

    return ExportReportResponse(
        job_id=job_id,
        status="queued"
    )


@router.get("/export/{job_id}", response_model=ReportStatusResponse)
async def get_status(
    job_id: str,
    request: Request,
    storage: Annotated[ReportTempStorage, Depends(get_storage)],
    job_repository: Annotated[ReportJobRepository, Depends(get_report_job_repository)],
):
    job = job_repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    download_url = None
    result_path = Path(job.result_path) if job.result_path is not None else storage.create_result_path(job_id)
    if job.status == "finished" and result_path.exists() and result_path.is_file():
        download_url = str(request.url_for("download", job_id=job_id))

    return ReportStatusResponse(
        job_id=job_id,
        status=job.status,
        download_url=download_url,
        error_msg=job.error_msg,
    )


@router.get("/export/{job_id}/download")
async def download(
    job_id: str,
    storage: Annotated[ReportTempStorage, Depends(get_storage)]
):
    
    result_path = storage.create_result_path(job_id)

    if not result_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result file not found")
    
    return FileResponse(
        path=result_path,
        filename=f"report_{job_id}.xlsx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    
