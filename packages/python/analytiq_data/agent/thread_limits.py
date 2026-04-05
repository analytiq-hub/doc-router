"""Pure helpers for chat thread message limits (no DB / heavy deps)."""

MAX_STORED_MESSAGES = 25


def trim_stored_messages(messages: list[dict]) -> list[dict]:
    """Keep only the last MAX_STORED_MESSAGES messages."""
    if len(messages) <= MAX_STORED_MESSAGES:
        return messages
    return messages[-MAX_STORED_MESSAGES:]
