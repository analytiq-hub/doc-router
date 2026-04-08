"""Display-only masking for secrets returned in admin APIs (same rules as LLM provider tokens)."""


def mask_secret_plaintext(plaintext: str) -> str | None:
    """
    First 16 characters + ``******``, or ``******`` for shorter non-empty secrets.
    Empty input returns ``None`` (matches list_llm_providers behavior).
    """
    if not plaintext:
        return None
    if len(plaintext) > 16:
        return plaintext[:16] + "******"
    return "******"
