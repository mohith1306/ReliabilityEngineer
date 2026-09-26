"""CI failure log parsing. READ-ONLY.

Turns raw CI output (GitHub Actions, generic pytest, plain text) into a
structured failure record the investigation engine can reason over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_LOG_BYTES = 512 * 1024

# Individual failure lines common to pytest and most CI wrappers.
_FAIL_LINE = re.compile(
    r"^(?:FAIL(?:ED)?|ERROR)\s+"
    r"(?P<ref>[\w./:-]+::[\w\[\]/ .-]+)"
    r"(?:\s+-\s+(?P<reason>.+))?$",
    re.MULTILINE,
)

_SUMMARY_COUNTS = re.compile(
    r"(?P<failed>\d+)\s+failed(?:,\s+(?P<passed>\d+)\s+passed)?"
    r"(?:,\s+(?P<errors>\d+)\s+errors?)?",
    re.IGNORECASE,
)

_TRACEBACK_HEADER = re.compile(r"^=+\s*(?:short test summary info|FAILURES|=+)\s*$", re.MULTILINE)

_INDENTED_ERROR = re.compile(
    r"^(?P<ref>[\w./:-]+\.(?:py|js|ts|go|rb))[:\s]+.*?(?:Error|Exception|assert)",
    re.MULTILINE,
)


@dataclass
class CIFailure:
    """One structured failure parsed out of a CI log."""
    reference: str
    reason: str | None = None
    log_excerpt: str | None = None


@dataclass
class CIFailureRecord:
    """Structured failure record for an entire CI run."""
    source: str
    failures: list[CIFailure] = field(default_factory=list)
    failed_count: int = 0
    passed_count: int | None = None
    raw_excerpt: str = ""


class CIConnector:
    """Parses a CI failure log into a structured failure record."""

    def parse_text(self, text: str, *, source: str = "inline") -> CIFailureRecord:
        record = CIFailureRecord(source=source, raw_excerpt=text[:4000])

        seen: set[str] = set()
        for m in _FAIL_LINE.finditer(text):
            ref = m.group("ref").strip()
            if ref in seen:
                continue
            seen.add(ref)
            record.failures.append(CIFailure(reference=ref, reason=m.group("reason")))

        if not record.failures:
            for m in _INDENTED_ERROR.finditer(text):
                ref = m.group("ref").strip()
                if ref in seen:
                    continue
                seen.add(ref)
                line = m.group(0).strip()
                record.failures.append(CIFailure(reference=ref, reason=line[:300]))

        counts = _SUMMARY_COUNTS.search(text)
        if counts:
            record.failed_count = int(counts.group("failed"))
            if counts.group("passed"):
                record.passed_count = int(counts.group("passed"))
        else:
            record.failed_count = len(record.failures)

        if record.failures and not record.failures[0].log_excerpt:
            record.failures[0].log_excerpt = _excerpt_around(text, record.failures[0].reference)

        return record

    def parse_file(self, path: str) -> CIFailureRecord:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"CI log not found: {path}")
        data = p.read_bytes()[:MAX_LOG_BYTES]
        return self.parse_text(data.decode("utf-8", errors="replace"), source=str(p))


def _excerpt_around(text: str, needle: str, radius: int = 400) -> str | None:
    idx = text.find(needle)
    if idx < 0:
        return None
    start = max(0, idx - radius)
    end = min(len(text), idx + radius)
    return text[start:end]
