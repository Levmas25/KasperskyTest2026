import logging
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Iterable

import xlsxwriter

from app.infra.writer.report_row import ReportRow


EXCEL_CELL_LIMIT = 32767


class XlsxReportWriter:
    HEADERS = (
        "словоформа",
        "кол-во во всём документе",
        "вхождения по строкам",
    )

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        progress_log_every_rows: int = 100,
    ):
        self.logger = logger or logging.getLogger("app.builder")
        self.progress_log_every_rows = progress_log_every_rows

    def write(self, rows: Iterable[ReportRow], out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        workbook = xlsxwriter.Workbook(
            str(out_path),
            {"constant_memory": True},
        )
        worksheet = workbook.add_worksheet("report")

        try:
            for col, value in enumerate(self.HEADERS):
                worksheet.write(0, col, value)

            row_index = 1
            started_at = perf_counter()
            for row in rows:
                worksheet.write(row_index, 0, row.lemma)
                worksheet.write(row_index, 1, row.total_count)

                for chunk_index, chunk in enumerate(self._iter_per_line_count_chunks(row.per_line_counts)):
                    worksheet.write(row_index, 2 + chunk_index, chunk)

                if self.progress_log_every_rows > 0 and row_index % self.progress_log_every_rows == 0:
                    self.logger.info(
                        "write progress written_rows=%d current_lemma=%s elapsed=%.3fs",
                        row_index,
                        row.lemma,
                        perf_counter() - started_at,
                    )

                row_index += 1

        finally:
            workbook.close()

        return out_path

    def _iter_per_line_count_chunks(self, per_line_counts: str | StringIO):
        if isinstance(per_line_counts, StringIO):
            per_line_counts.seek(0)
            while chunk := per_line_counts.read(EXCEL_CELL_LIMIT):
                yield chunk
            return

        if not per_line_counts:
            yield ""
            return

        for start in range(0, len(per_line_counts), EXCEL_CELL_LIMIT):
            yield per_line_counts[start:start + EXCEL_CELL_LIMIT]
