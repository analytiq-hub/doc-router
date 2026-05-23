from __future__ import annotations

"""Short-lived leases to dedupe overlapping trigger ticks."""

from datetime import datetime, timedelta, UTC


from pymongo.errors import DuplicateKeyError


async def acquire_tick_lease(
    db,
    *,
    flow_id: str,
    node_id: str,
    tick_key: str,
    ttl_secs: int = 120,
) -> bool:
    """
    Try to acquire an in-flight lease for ``(flow_id, node_id, tick_key)``.

    Returns True when this caller owns the tick. Expired leases may be stolen.
    """

    now = datetime.now(UTC)
    expires = now + timedelta(seconds=ttl_secs)
    lease_id = f"{flow_id}:{node_id}:{tick_key}"

    existing = await db.flow_trigger_leases.find_one({"_id": lease_id})
    if existing is None:
        try:
            await db.flow_trigger_leases.insert_one(
                {
                    "_id": lease_id,
                    "flow_id": flow_id,
                    "node_id": node_id,
                    "tick_key": tick_key,
                    "expires_at": expires,
                    "created_at": now,
                }
            )
            return True
        except DuplicateKeyError:
            existing = await db.flow_trigger_leases.find_one({"_id": lease_id})

    if not existing:
        return False

    exp = existing.get("expires_at")
    if isinstance(exp, datetime) and exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if isinstance(exp, datetime) and exp > now:
        return False

    result = await db.flow_trigger_leases.update_one(
        {"_id": lease_id, "expires_at": {"$lte": now}},
        {"$set": {"expires_at": expires, "created_at": now}},
    )
    return result.modified_count == 1
