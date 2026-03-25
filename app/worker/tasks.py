from pathlib import Path
import traceback

from app.infra.storage.report_temp_storage import ReportTempStorage
from app.infra.nlp.pymorphy_lemmatizer import PymorphyLemmatizer
from app.infra.tokenizer.tokenizer import RegexWordTokenizer
from app.application.report.processor import ReportProcessor
from app.infra.writer.xlsx_writer import XlsxReportWriter
from app.application.report.build_service import BuildReportService
from app.config import get_report_database_url
from app.infra.logging_setup import configure_logging
from app.infra.persistence import (
    SqlAlchemyReportJobRepository,
    create_engine_for_report_jobs,
    init_report_job_schema,
)


def build_report_task(
        *,
        report_job_id: str,
        input_path: Path,
        result_path: Path,
        work_path: Path
):
    configure_logging()
    engine = create_engine_for_report_jobs(get_report_database_url())
    init_report_job_schema(engine)
    job_repository = SqlAlchemyReportJobRepository(engine)

    storage = ReportTempStorage()
    lemmatizer = PymorphyLemmatizer()
    tokenizer = RegexWordTokenizer()
    processor = ReportProcessor(tokenizer=tokenizer, lemmizer=lemmatizer)
    writer = XlsxReportWriter()

    service = BuildReportService(
        storage=storage,
        processor=processor,
        writer=writer
    )

    job_repository.mark_started(job_id=report_job_id)

    try:
        service.build(
            job_id=report_job_id,
            input_path=input_path,
            result_path=result_path,
            work_path=work_path,
        )
    except Exception:
        job_repository.mark_failed(
            job_id=report_job_id,
            error_msg=traceback.format_exc(),
        )
        raise

    job_repository.mark_finished(
        job_id=report_job_id,
        result_path=str(result_path),
    )
