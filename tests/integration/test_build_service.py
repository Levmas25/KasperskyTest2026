from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import shutil
from unittest import TestCase
from uuid import uuid4
from xml.etree import ElementTree
import zipfile

from app.application.report.build_service import BuildReportService
from app.infra.storage.report_temp_storage import ReportTempStorage
from app.infra.writer.xlsx_writer import XlsxReportWriter


@contextmanager
def workspace_temp_dir():
    root = Path.cwd() / "tests_tmp"
    path = root / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def read_sheet_cells(xlsx_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(xlsx_path) as archive:
        sheet_xml = archive.read("xl/worksheets/sheet1.xml")

    root = ElementTree.fromstring(sheet_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    cells: dict[str, str] = {}

    for cell in root.findall(".//x:c", namespace):
        ref = cell.attrib["r"]
        inline_text = cell.find(".//x:t", namespace)
        if inline_text is not None:
            cells[ref] = inline_text.text or ""
            continue

        value = cell.find("x:v", namespace)
        cells[ref] = value.text if value is not None else ""

    return cells


class StubProcessor:
    def __init__(self, responses: list[Counter[str]]):
        self._responses = iter(responses)

    def process_line(self, line: str) -> Counter[str]:
        return next(self._responses)


class BuildReportServiceTests(TestCase):
    def test_build_writes_sparse_per_line_counts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_path = tmp_dir / "input.txt"
            input_path.write_text("line1\nline2\nline3\n", encoding="utf-8")

            service = BuildReportService(
                storage=ReportTempStorage(tmp_dir_path=str(tmp_dir)),
                processor=StubProcessor(
                    [
                        Counter({"alpha": 1, "beta": 1}),
                        Counter({"beta": 1}),
                        Counter({"alpha": 2}),
                    ]
                ),
                writer=XlsxReportWriter(progress_log_every_rows=0),
            )

            result_path = tmp_dir / "report.xlsx"
            service.build(
                job_id="job123",
                input_path=input_path,
                result_path=result_path,
                work_path=tmp_dir / "work.sqlite3",
            )

            cells = read_sheet_cells(result_path)

        self.assertEqual(cells["A2"], "alpha")
        self.assertEqual(cells["B2"], "3")
        self.assertEqual(cells["C2"], "1:1,3:2")
        self.assertEqual(cells["A3"], "beta")
        self.assertEqual(cells["B3"], "2")
        self.assertEqual(cells["C3"], "1:1,2:1")
