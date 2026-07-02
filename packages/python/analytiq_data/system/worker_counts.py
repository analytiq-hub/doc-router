"""Per-queue asyncio worker pool sizes (deployment-wide)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

WORKER_COUNT_DEFAULT = 4
WORKER_COUNT_MIN = 0
WORKER_COUNT_MAX = 256

QUEUE_WORKER_FIELDS: tuple[str, ...] = (
    "n_ocr_workers",
    "n_llm_workers",
    "n_kb_index_workers",
    "n_webhook_workers",
    "n_flow_run_workers",
)

QUEUE_TYPE_BY_FIELD: dict[str, str] = {
    "n_ocr_workers": "ocr",
    "n_llm_workers": "llm",
    "n_kb_index_workers": "kb_index",
    "n_webhook_workers": "webhook",
    "n_flow_run_workers": "flow_run",
}

FIELD_BY_QUEUE_TYPE: dict[str, str] = {v: k for k, v in QUEUE_TYPE_BY_FIELD.items()}


@dataclass(frozen=True)
class WorkerCounts:
    n_ocr_workers: int = WORKER_COUNT_DEFAULT
    n_llm_workers: int = WORKER_COUNT_DEFAULT
    n_kb_index_workers: int = WORKER_COUNT_DEFAULT
    n_webhook_workers: int = WORKER_COUNT_DEFAULT
    n_flow_run_workers: int = WORKER_COUNT_DEFAULT

    def as_dict(self) -> dict[str, int]:
        return {field: getattr(self, field) for field in QUEUE_WORKER_FIELDS}

    def count_for_queue(self, queue_type: str) -> int:
        field = FIELD_BY_QUEUE_TYPE.get(queue_type)
        if field is None:
            raise KeyError(f"Unknown queue type: {queue_type}")
        return getattr(self, field)

    def total_queue_workers(self) -> int:
        return sum(self.as_dict().values())

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WorkerCounts:
        defaults = default_worker_counts()
        values: dict[str, int] = {}
        for field in QUEUE_WORKER_FIELDS:
            raw = (data or {}).get(field, getattr(defaults, field))
            values[field] = clamp_worker_count(raw)
        return cls(**values)


def _read_env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def clamp_worker_count(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return WORKER_COUNT_DEFAULT
    return max(WORKER_COUNT_MIN, min(WORKER_COUNT_MAX, n))


def default_worker_counts() -> WorkerCounts:
    """Bootstrap values when no ``system_settings`` document exists."""
    legacy = _read_env_int("N_DOCROUTER_WORKERS")
    if legacy is not None:
        value = clamp_worker_count(legacy)
        return WorkerCounts(
            n_ocr_workers=value,
            n_llm_workers=value,
            n_kb_index_workers=value,
            n_webhook_workers=value,
            n_flow_run_workers=value,
        )

    per_queue: dict[str, int] = {}
    for field, queue_type in QUEUE_TYPE_BY_FIELD.items():
        env_name = f"N_{queue_type.upper()}_WORKERS"
        env_value = _read_env_int(env_name)
        per_queue[field] = clamp_worker_count(env_value) if env_value is not None else WORKER_COUNT_DEFAULT
    return WorkerCounts(**per_queue)
