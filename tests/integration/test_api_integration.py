from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.public.report.dependenceis import (
    get_report_export_service,
    get_report_job_repository,
    get_storage,
)
from app.domain.report_job import ReportJob
from app.infra.storage.report_temp_storage import ReportTempStorage
from app.main import app


@contextmanager
def workspace_temp_dir():
    root = Path.cwd() / "tests_tmp"
    path = root / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class FakeReportExportService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Path]] = []

    async def create_job(self, job_id: str, input_path: Path) -> None:
        self.calls.append((job_id, input_path))


class FakeReportJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, ReportJob] = {}

    def create_queued(self, *, job_id: str, result_path: str) -> None:
        now = datetime.now(timezone.utc)
        self.jobs[job_id] = ReportJob(
            job_id=job_id,
            status="queued",
            result_path=result_path,
            error_msg=None,
            created_at=now,
            updated_at=now,
        )

    def mark_started(self, *, job_id: str) -> None:
        self._replace(job_id=job_id, status="started")

    def mark_finished(self, *, job_id: str, result_path: str) -> None:
        self._replace(job_id=job_id, status="finished", result_path=result_path, error_msg=None)

    def mark_failed(self, *, job_id: str, error_msg: str) -> None:
        self._replace(job_id=job_id, status="failed", error_msg=error_msg)

    def get(self, job_id: str) -> ReportJob | None:
        return self.jobs.get(job_id)

    def _replace(
        self,
        *,
        job_id: str,
        status: str,
        result_path: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        current = self.jobs.get(job_id)
        created_at = current.created_at if current is not None else now
        self.jobs[job_id] = ReportJob(
            job_id=job_id,
            status=status,
            result_path=result_path if result_path is not None else (current.result_path if current else None),
            error_msg=error_msg,
            created_at=created_at,
            updated_at=now,
        )


class ReportApiIntegrationTests(TestCase):
    def setUp(self) -> None:
        app.dependency_overrides.clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_export_accepts_file_and_enqueues_job(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            service = FakeReportExportService()

            app.dependency_overrides[get_storage] = lambda: storage
            app.dependency_overrides[get_report_export_service] = lambda: service

            with self.subTest("fixed job id"):
                from unittest.mock import patch

                with patch(
                    "app.api.public.report.router.uuid.uuid4",
                    return_value=SimpleNamespace(hex="job123"),
                ):
                    response = self.client.post(
                        "/public/report/export",
                        files={"file": ("input.txt", b"alpha beta\n", "text/plain")},
                    )

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json(), {"job_id": "job123", "status": "queued"})
            self.assertEqual(len(service.calls), 1)
            self.assertEqual(service.calls[0][0], "job123")
            self.assertTrue(service.calls[0][1].exists())
            self.assertEqual(service.calls[0][1].read_text(encoding="utf-8"), "alpha beta\n")

    def test_export_rejects_non_txt_extension(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            service = FakeReportExportService()

            app.dependency_overrides[get_storage] = lambda: storage
            app.dependency_overrides[get_report_export_service] = lambda: service

            response = self.client.post(
                "/public/report/export",
                files={"file": ("input.csv", b"alpha,beta\n", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Only .txt files are supported"})
        self.assertEqual(service.calls, [])

    def test_export_rejects_non_text_mime_type(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            service = FakeReportExportService()

            app.dependency_overrides[get_storage] = lambda: storage
            app.dependency_overrides[get_report_export_service] = lambda: service

            response = self.client.post(
                "/public/report/export",
                files={"file": ("input.txt", b"%PDF-1.7", "application/pdf")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Only text/plain .txt files are supported"})
        self.assertEqual(service.calls, [])

    def test_export_rejects_binary_payload_disguised_as_text(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            service = FakeReportExportService()

            app.dependency_overrides[get_storage] = lambda: storage
            app.dependency_overrides[get_report_export_service] = lambda: service

            response = self.client.post(
                "/public/report/export",
                files={"file": ("input.txt", b"PK\x03\x04fake-zip", "text/plain")},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Only plain text .txt files are supported"})
        self.assertEqual(service.calls, [])

    def test_status_returns_download_url_for_finished_job(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            result_path = storage.create_result_path("job123")
            result_path.write_bytes(b"xlsx-content")

            repository = FakeReportJobRepository()
            repository.create_queued(job_id="job123", result_path=str(result_path))
            repository.mark_finished(job_id="job123", result_path=str(result_path))

            app.dependency_overrides[get_storage] = lambda: storage
            app.dependency_overrides[get_report_job_repository] = lambda: repository

            response = self.client.get("/public/report/export/job123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "job_id": "job123",
                "status": "finished",
                "download_url": "http://testserver/public/report/export/job123/download",
                "error_msg": None,
            },
        )

    def test_download_returns_result_file(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            storage = ReportTempStorage(tmp_dir_path=str(tmp_dir))
            result_path = storage.create_result_path("job123")
            result_path.write_bytes(b"xlsx-content")

            app.dependency_overrides[get_storage] = lambda: storage

            response = self.client.get("/public/report/export/job123/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn('filename="report_job123.xlsx"', response.headers["content-disposition"])
        self.assertEqual(response.content, b"xlsx-content")
