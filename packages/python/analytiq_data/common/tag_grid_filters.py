"""
Resolve MUI grid filter values for ``tag_ids`` columns: values may be Mongo id strings
or human-readable tag names (case-insensitive exact match per value).
"""

from __future__ import annotations

import re
from typing import Any

from bson import ObjectId


async def resolve_tag_filter_values_to_ids(
    db: Any,
    organization_id: str,
    values: list[str],
) -> list[str]:
    """Each entry is either a valid ``ObjectId`` string or a tag ``name`` (exact, case-insensitive)."""
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        s = str(v).strip()
        if not s:
            continue
        if ObjectId.is_valid(s):
            tid = str(ObjectId(s))
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
            continue
        doc = await db["tags"].find_one(
            {
                "organization_id": organization_id,
                "name": {"$regex": f"^{re.escape(s)}$", "$options": "i"},
            },
            {"_id": 1},
        )
        if doc:
            tid = str(doc["_id"])
            if tid not in seen:
                seen.add(tid)
                out.append(tid)
    return out
