from __future__ import annotations

"""Document lifecycle event names wired to ``docrouter.trigger``."""

DOCROUTER_EVENT_TYPES: tuple[str, ...] = (
    "document.uploaded",
    "document.error",
    "llm.completed",
    "llm.error",
)

DOCROUTER_LLM_EVENT_TYPES: frozenset[str] = frozenset({"llm.completed", "llm.error"})
