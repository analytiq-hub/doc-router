from __future__ import annotations

from typing import Any

RESERVED_TOP_LEVEL_KEYS = frozenset({"json", "binary", "meta", "paired_item"})
BINARY_META_KEYS = frozenset({"mime_type", "file_name", "storage_id", "file_size"})


class CodeValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        description: str | None = None,
        item_index: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.description = description
        self.item_index = item_index


def _has_reserved_key(item: dict[str, Any]) -> bool:
    return any(k in RESERVED_TOP_LEVEL_KEYS for k in item)


def normalize_output_items(items: list[Any], *, batch_has_explicit: bool) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise CodeValidationError(
                f"run() output items must be dicts; got {type(raw).__name__}",
                item_index=idx,
            )
        if _has_reserved_key(raw):
            item = dict(raw)
            if "json" not in item:
                item["json"] = {}
            normalized.append(item)
        elif batch_has_explicit:
            unknown = [k for k in raw if k not in RESERVED_TOP_LEVEL_KEYS]
            key = unknown[0] if unknown else "?"
            raise CodeValidationError(
                f"Unknown top-level key '{key}' at index {idx}. Put fields under json.",
                description='Return {"json": {...}} on every item when any item uses reserved keys.',
                item_index=idx,
            )
        else:
            normalized.append({"json": dict(raw)})
    return normalized


def validate_top_level_keys(item: dict[str, Any], item_index: int) -> None:
    keys = set(item)
    reserved = keys & RESERVED_TOP_LEVEL_KEYS
    unknown = keys - RESERVED_TOP_LEVEL_KEYS
    if reserved and unknown:
        bad = sorted(unknown)[0]
        raise CodeValidationError(
            f"Output item at index {item_index} mixes reserved key '{sorted(reserved)[0]}' "
            f"with '{bad}'.",
            description=f'Put custom fields under json, e.g. return {{"json": {{"{bad}": ...}}}}.',
            item_index=item_index,
        )


def validate_item_fields(item: dict[str, Any], item_index: int) -> None:
    json_payload = item.get("json")
    if not isinstance(json_payload, dict):
        raise CodeValidationError(
            f"'json' must be a dict at index {item_index}",
            item_index=item_index,
        )

    if "binary" in item:
        binary = item["binary"]
        if not isinstance(binary, dict):
            raise CodeValidationError(
                f"'binary' must be a dict at index {item_index}",
                item_index=item_index,
            )
        for field_name, ref in binary.items():
            if not isinstance(ref, dict):
                raise CodeValidationError(
                    f"binary['{field_name}'] must be a dict at index {item_index}",
                    item_index=item_index,
                )
            if ref.get("data") is not None:
                raise CodeValidationError(
                    f"binary['{field_name}'] must not include raw data at index {item_index}",
                    item_index=item_index,
                )
            storage_id = ref.get("storage_id")
            if not isinstance(storage_id, str) or not storage_id.strip():
                raise CodeValidationError(
                    f"binary['{field_name}'] has no storage_id at index {item_index}",
                    description="Call store_binary() to persist new blobs before returning.",
                    item_index=item_index,
                )
            extra = set(ref) - BINARY_META_KEYS
            if extra:
                bad = sorted(extra)[0]
                raise CodeValidationError(
                    f"binary['{field_name}'] has unknown key '{bad}' at index {item_index}",
                    item_index=item_index,
                )

    if "meta" in item and not isinstance(item["meta"], dict):
        raise CodeValidationError(
            f"'meta' must be a dict at index {item_index}",
            item_index=item_index,
        )

    paired = item.get("paired_item")
    if paired is not None:
        if isinstance(paired, int):
            pass
        elif isinstance(paired, list):
            if not paired or not all(isinstance(x, int) for x in paired):
                raise CodeValidationError(
                    f"Invalid paired_item at index {item_index}",
                    item_index=item_index,
                )
        else:
            raise CodeValidationError(
                f"Invalid paired_item at index {item_index}",
                item_index=item_index,
            )


def validate_code_output(items: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise CodeValidationError("run() must return a list")

    batch_has_explicit = any(isinstance(x, dict) and _has_reserved_key(x) for x in items)

    if batch_has_explicit:
        for idx, raw in enumerate(items):
            if isinstance(raw, dict):
                validate_top_level_keys(raw, idx)

    normalized = normalize_output_items(items, batch_has_explicit=batch_has_explicit)
    for idx, item in enumerate(normalized):
        validate_item_fields(item, idx)
    return normalized
