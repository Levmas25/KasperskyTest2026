from dataclasses import dataclass
from io import StringIO


@dataclass(frozen=True, slots=True)
class ReportRow:
    lemma: str
    total_count: int
    per_line_counts: str | StringIO
