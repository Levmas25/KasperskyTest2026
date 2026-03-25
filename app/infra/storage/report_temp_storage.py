from pathlib import Path
from fastapi import UploadFile

from app.config import get_storage_paths


class ReportTempStorage:
    ALLOWED_REPORT_MEDIA_TYPES = {
        "",
        "application/octet-stream",
        "text/plain",
    }
    BINARY_SIGNATURES = (
        b"%PDF-",
        b"PK\x03\x04",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
        b"GIF87a",
        b"GIF89a",
        b"MZ",
        b"\x7fELF",
    )
    TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251")

    def __init__(
        self,
        tmp_dir_path: str | None = None,
        *,
        uploads_dir: str | Path | None = None,
        results_dir: str | Path | None = None,
        work_dir: str | Path | None = None,
    ):
        if any(value is not None for value in (uploads_dir, results_dir, work_dir)):
            env_paths = get_storage_paths()
            self.uploads = Path(uploads_dir) if uploads_dir is not None else env_paths.uploads
            self.results = Path(results_dir) if results_dir is not None else env_paths.results
            self.work = Path(work_dir) if work_dir is not None else env_paths.work
        elif tmp_dir_path is not None:
            base_dir = Path(tmp_dir_path)
            self.uploads = base_dir / "uploads"
            self.results = base_dir / "results"
            self.work = base_dir / "work"
        else:
            paths = get_storage_paths()
            self.uploads = paths.uploads
            self.results = paths.results
            self.work = paths.work

        self.uploads.mkdir(exist_ok=True, parents=True)
        self.results.mkdir(exist_ok=True, parents=True)
        self.work.mkdir(exist_ok=True, parents=True)

    async def save_upload(
        self,
        upload: UploadFile,
        job_id: str,
        chunk_size: int = 1024 * 1024,
    ) -> Path:
        original_name = Path(upload.filename or "input.txt").name
        path = self.uploads / f"{job_id}_{original_name}"
        first_chunk = b""

        try:
            self._validate_upload_metadata(upload)
            first_chunk = await upload.read(chunk_size)
            self._validate_upload_content(first_chunk)

            with path.open("wb") as out:
                if first_chunk:
                    out.write(first_chunk)

                while chunk := await upload.read(chunk_size):
                    out.write(chunk)
        except Exception:
            if path.exists():
                path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        return path

    def create_result_path(self, job_id: str) -> Path:
        return self.results / f"{job_id}.xlsx"

    def create_work_path(self, job_id: str) -> Path:
        return self.work / f"{job_id}.sqlite3"

    def delete(self, path: str | Path) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()

    def _validate_upload_metadata(self, upload: UploadFile) -> None:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix != ".txt":
            raise ValueError("Only .txt files are supported")

        content_type = (upload.content_type or "").lower()
        if content_type not in self.ALLOWED_REPORT_MEDIA_TYPES:
            raise ValueError("Only text/plain .txt files are supported")

    def _validate_upload_content(self, first_chunk: bytes) -> None:
        if not first_chunk:
            return

        if first_chunk.startswith(self.BINARY_SIGNATURES):
            raise ValueError("Only plain text .txt files are supported")

        if b"\x00" in first_chunk:
            raise ValueError("Only plain text .txt files are supported")

        if any(byte < 32 and byte not in (9, 10, 13) for byte in first_chunk):
            raise ValueError("Only plain text .txt files are supported")

        for encoding in self.TEXT_ENCODINGS:
            try:
                first_chunk.decode(encoding)
                return
            except UnicodeDecodeError:
                continue

        raise ValueError("Only plain text .txt files are supported")
