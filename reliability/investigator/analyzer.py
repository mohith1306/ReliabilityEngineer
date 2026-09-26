"""TaskAnalyzer: classify an incident and name candidate components/topics.

Contract (reliability/investigator/__init__.py):
    TaskAnalyzer.analyze(incident) -> IncidentTask
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "was", "were", "has",
    "have", "had", "not", "but", "are", "its", "it's", "into", "when", "then",
    "than", "after", "before", "during", "while", "failed", "failure", "error",
    "test", "tests", "failed.", "exception", "assert", "assertion",
}

# metadata keys whose values are treated as raw error text
ERROR_KEYS = ("error", "message", "traceback", "stderr", "failure", "log", "detail")

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_TOKEN = re.compile(r"[A-Za-z0-9_.]+")


@dataclass
class IncidentTask:
    """What the investigation should look for."""
    incident_id: str
    incident_type: str
    description: str
    error_text: str
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def search_blob(self) -> str:
        return f"{self.description} {self.error_text}".strip()


class TaskAnalyzer:
    """Classifies the incident and names candidate components (topics)."""

    def analyze(self, incident) -> IncidentTask:
        description = incident.description or ""
        metadata = dict(incident.metadata or {})

        error_parts = []
        for key in ERROR_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value:
                error_parts.append(value)
        error_text = "\n".join(error_parts)

        keywords = self._keywords(description, error_text, metadata)
        topics = self._topics(description, error_text)

        return IncidentTask(
            incident_id=incident.id,
            incident_type=str(getattr(incident, "type", "unknown")),
            description=description,
            error_text=error_text,
            keywords=keywords,
            topics=topics,
            metadata=metadata,
        )

    def _keywords(self, *texts_and_meta) -> list[str]:
        description, error_text = texts_and_meta[0], texts_and_meta[1]
        metadata = texts_and_meta[2]
        raw = " ".join([description, error_text])
        if isinstance(metadata.get("repository"), str):
            raw += " " + metadata["repository"]

        seen: list[str] = []
        for token in _TOKEN.findall(raw):
            for piece in _CAMEL.split(token):
                piece = piece.strip("._-").lower()
                if len(piece) < 3 or piece in STOPWORDS or piece.isdigit():
                    continue
                if piece not in seen:
                    seen.append(piece)
        return seen

    def _topics(self, description: str, error_text: str) -> list[str]:
        """Component-like identifiers: CamelCase or snake_case names."""
        blob = f"{description} {error_text}"
        topics: list[str] = []
        for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b", blob):
            name = match.group(0)
            if name.lower() in STOPWORDS:
                continue
            if name not in topics:
                topics.append(name)
        return topics
