from collections import Counter
from dataclasses import dataclass
from io import StringIO
import logging
from pathlib import Path
import sqlite3
from time import perf_counter

from app.infra.storage.report_temp_storage import ReportTempStorage
from app.infra.writer.report_row import ReportRow
from app.infra.writer.xlsx_writer import XlsxReportWriter
from .processor import ReportProcessor


@dataclass(slots=True)
class BuildCollectionStats:
    total_lines: int = 0
    non_empty_lines: int = 0
    total_tokens: int = 0
    total_line_stats: int = 0
    flushes: int = 0


class BuildReportService:

    def __init__(
            self,
            storage: ReportTempStorage,
            processor: ReportProcessor,
            writer: XlsxReportWriter,
            buffer_size: int = 50_000,
            progress_log_every_lines: int = 10_000,
            logger: logging.Logger | None = None,
        ):
        self.storage = storage
        self.processor = processor
        self.writer = writer
        self.buffer_size = buffer_size
        self.progress_log_every_lines = progress_log_every_lines
        self.logger = logger or logging.getLogger("app.builder")

    def build(
            self,
            job_id: str,
            input_path: Path,
            result_path: Path,
            work_path: Path
        ) -> Path:
        build_started_at = perf_counter()
        self.logger.info(
            "build started job_id=%s input_path=%s result_path=%s work_path=%s buffer_size=%d",
            job_id,
            input_path,
            result_path,
            work_path,
            self.buffer_size,
        )

        work_path.parent.mkdir(parents=True, exist_ok=True)
        if work_path.exists():
            work_path.unlink()

        collect_started_at = perf_counter()
        stats = self._collect_stats(job_id=job_id, input_path=input_path, work_path=work_path)
        collect_elapsed = perf_counter() - collect_started_at
        total_lemmas = self._count_total_lemmas(work_path)
        self.logger.info(
            "stats collected job_id=%s total_lines=%d non_empty_lines=%d total_tokens=%d total_line_stats=%d total_lemmas=%d flushes=%d elapsed=%.3fs",
            job_id,
            stats.total_lines,
            stats.non_empty_lines,
            stats.total_tokens,
            stats.total_line_stats,
            total_lemmas,
            stats.flushes,
            collect_elapsed,
        )

        lemmatizer = getattr(self.processor, "lemmizer", None)
        cache_info = getattr(lemmatizer, "cache_info", None)
        if callable(cache_info):
            info = cache_info()
            self.logger.info(
                "lemmatizer cache job_id=%s hits=%d misses=%d current_size=%d",
                job_id,
                info.hits,
                info.misses,
                info.currsize,
            )

        avg_non_zero_entries = stats.total_line_stats / total_lemmas if total_lemmas else 0.0
        self.logger.info(
            "write phase estimate job_id=%s total_lemmas=%d total_non_zero_entries=%d avg_non_zero_entries_per_lemma=%.2f",
            job_id,
            total_lemmas,
            stats.total_line_stats,
            avg_non_zero_entries,
        )

        write_started_at = perf_counter()
        rows = self._iter_rows(work_path=work_path)
        output_path = self.writer.write(rows, result_path)
        write_elapsed = perf_counter() - write_started_at

        self.logger.info(
            "build finished job_id=%s total_lines=%d total_tokens=%d total_lemmas=%d collect_elapsed=%.3fs write_elapsed=%.3fs total_elapsed=%.3fs output_path=%s",
            job_id,
            stats.total_lines,
            stats.total_tokens,
            total_lemmas,
            collect_elapsed,
            write_elapsed,
            perf_counter() - build_started_at,
            output_path,
        )

        return output_path

    def _collect_stats(self, *, job_id: str, input_path: Path, work_path: Path) -> BuildCollectionStats:
        if not input_path.exists() or not input_path.is_file():
            raise ValueError("input_path must be existing file")

        conn = sqlite3.connect(work_path)

        try:
            self._configure_db(conn)
            self._init_db(conn)

            stats = BuildCollectionStats()
            total_buffer: Counter[str] = Counter()
            line_buffer: list[tuple[str, int, int]] = []
            last_progress_log_line = 0

            with input_path.open("r", encoding="utf-8", errors="ignore", buffering=1024 * 1024) as file:
                for line_no, line in enumerate(file, start=1):
                    stats.total_lines = line_no
                    line_counts = self.processor.process_line(line)

                    if line_counts:
                        stats.non_empty_lines += 1
                        stats.total_tokens += sum(line_counts.values())
                        stats.total_line_stats += len(line_counts)

                        total_buffer.update(line_counts)
                        line_buffer.extend(
                            (lemma, line_no, count)
                            for lemma, count in line_counts.items()
                        )

                    if len(line_buffer) >= self.buffer_size:
                        self._flush_buffers(
                            job_id=job_id,
                            conn=conn,
                            total_buffer=total_buffer,
                            line_buffer=line_buffer,
                            stats=stats,
                        )

                    if self.progress_log_every_lines > 0 and line_no - last_progress_log_line >= self.progress_log_every_lines:
                        last_progress_log_line = line_no
                        self.logger.info(
                            "collect progress job_id=%s processed_lines=%d non_empty_lines=%d total_tokens=%d buffered_line_stats=%d flushes=%d",
                            job_id,
                            stats.total_lines,
                            stats.non_empty_lines,
                            stats.total_tokens,
                            len(line_buffer),
                            stats.flushes,
                        )

            self._flush_buffers(
                job_id=job_id,
                conn=conn,
                total_buffer=total_buffer,
                line_buffer=line_buffer,
                stats=stats,
            )
            return stats
        finally:
            conn.close()

    def _configure_db(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA journal_mode = MEMORY;
            PRAGMA synchronous = OFF;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = -131072;
            PRAGMA locking_mode = EXCLUSIVE;
            """
        )

    def _init_db(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS total_counts(
                lemma TEXT PRIMARY KEY,
                total INTEGER NOT NULL
            ) WITHOUT ROWID;

            CREATE TABLE IF NOT EXISTS line_counts(
                lemma TEXT NOT NULL,
                line_no INTEGER NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY(lemma, line_no)
            ) WITHOUT ROWID;
            """
        )

    def _flush_buffers(
            self,
            *,
            job_id: str,
            conn: sqlite3.Connection,
            total_buffer: Counter[str],
            line_buffer: list[tuple[str, int, int]],
            stats: BuildCollectionStats,
        ) -> None:
        if not total_buffer and not line_buffer:
            return

        flush_started_at = perf_counter()
        buffered_total_counts = len(total_buffer)
        buffered_line_stats = len(line_buffer)

        with conn:
            conn.executemany(
                """
                INSERT INTO total_counts(lemma, total)
                VALUES (?, ?)
                ON CONFLICT(lemma) DO UPDATE
                SET total = total + excluded.total
                """,
                total_buffer.items(),
            )

            conn.executemany(
                """
                INSERT INTO line_counts(lemma, line_no, count)
                VALUES (?, ?, ?)
                ON CONFLICT(lemma, line_no) DO UPDATE
                SET count = count + excluded.count
                """,
                line_buffer,
            )

        stats.flushes += 1
        self.logger.info(
            "sqlite flush job_id=%s flush_no=%d buffered_total_counts=%d buffered_line_stats=%d total_tokens=%d total_lines=%d elapsed=%.3fs",
            job_id,
            stats.flushes,
            buffered_total_counts,
            buffered_line_stats,
            stats.total_tokens,
            stats.total_lines,
            perf_counter() - flush_started_at,
        )

        total_buffer.clear()
        line_buffer.clear()

    def _count_total_lemmas(self, work_path: Path) -> int:
        conn = sqlite3.connect(work_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM total_counts")
            result = cursor.fetchone()
            return int(result[0]) if result is not None else 0
        finally:
            conn.close()

    def _iter_rows(self, work_path: Path):
        conn = sqlite3.connect(work_path)

        try:
            cursor = conn.execute(
                """
                SELECT total_counts.lemma, total_counts.total, line_counts.line_no, line_counts.count
                FROM total_counts
                LEFT JOIN line_counts ON line_counts.lemma = total_counts.lemma
                ORDER BY total_counts.lemma, line_counts.line_no
                """
            )

            current_lemma: str | None = None
            current_total = 0
            first = True
            buffer: StringIO | None = None

            for lemma, total_count, line_no, count in cursor:
                if lemma != current_lemma:
                    if current_lemma is not None and buffer is not None:
                        buffer.seek(0)
                        yield ReportRow(
                            lemma=current_lemma,
                            total_count=current_total,
                            per_line_counts=buffer,
                        )

                    current_lemma = lemma
                    current_total = total_count
                    first = True
                    buffer = StringIO()

                if line_no is None or buffer is None:
                    continue

                self._write_sparse_count(buffer, line_no, count, first)
                first = False

            if current_lemma is not None and buffer is not None:
                buffer.seek(0)
                yield ReportRow(
                    lemma=current_lemma,
                    total_count=current_total,
                    per_line_counts=buffer,
                )
        finally:
            conn.close()

    def _write_sparse_count(self, buffer: StringIO, line_no: int, count: int, first: bool) -> None:
        if not first:
            buffer.write(",")
        buffer.write(f"{line_no}:{count}")
