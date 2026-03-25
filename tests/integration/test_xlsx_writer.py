from contextlib import contextmanager
from io import StringIO
from pathlib import Path
import shutil
from unittest import TestCase
from uuid import uuid4
from xml.etree import ElementTree
import zipfile

from app.infra.writer.report_row import ReportRow
from app.infra.writer.xlsx_writer import EXCEL_CELL_LIMIT, XlsxReportWriter


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


class XlsxWriterTests(TestCase):
    def test_writes_long_per_line_counts_into_continuation_columns(self) -> None:
        writer = XlsxReportWriter()
        long_counts = "1" * (EXCEL_CELL_LIMIT + 5)

        with workspace_temp_dir() as tmp_dir:
            out_path = tmp_dir / "report.xlsx"
            writer.write(
                [
                    ReportRow(
                        lemma="lemma",
                        total_count=1,
                        per_line_counts=StringIO(long_counts),
                    )
                ],
                out_path,
            )

            cells = read_sheet_cells(out_path)

        self.assertEqual(cells["C2"], "1" * EXCEL_CELL_LIMIT)
        self.assertEqual(cells["D2"], "1" * 5)
