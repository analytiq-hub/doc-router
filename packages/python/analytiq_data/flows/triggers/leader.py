from __future__ import annotations

"""MongoDB-based leader election for the flow trigger scheduler."""

import logging
import os
import socket
from datetime import datetime, timedelta, UTC

from pymongo.errors import DuplicateKeyError


logger = logging.getLogger(__name__)


def default_holder_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class FlowSchedulerLeader:
    """
    Single-leader lease stored in ``flow_scheduler_leader``.

    Only the holder should execute cron/poll ticks (mirrors n8n ``isLeader`` gate).
    """

    def __init__(self, db, *, holder_id: str | None = None, ttl_secs: int = 30) -> None:
        self._db = db
        self._holder_id = holder_id or default_holder_id()
        self._ttl_secs = max(5, int(ttl_secs))
        self.is_leader = False

    @property
    def holder_id(self) -> str:
        return self._holder_id

    async def renew(self) -> bool:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=self._ttl_secs)
        coll = self._db.flow_scheduler_leader
        doc = await coll.find_one({"_id": "leader"})

        if doc is None:
            try:
                await coll.insert_one(
                    {
                        "_id": "leader",
                        "holder": self._holder_id,
                        "expires_at": expires,
                        "updated_at": now,
                    }
                )
                self.is_leader = True
                return True
            except DuplicateKeyError:
                doc = await coll.find_one({"_id": "leader"})

        if doc and doc.get("holder") == self._holder_id:
            await coll.update_one(
                {"_id": "leader", "holder": self._holder_id},
                {"$set": {"expires_at": expires, "updated_at": now}},
            )
            self.is_leader = True
            return True

        exp = doc.get("expires_at") if doc else None
        if isinstance(exp, datetime) and exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if doc and isinstance(exp, datetime) and exp <= now:
            result = await coll.update_one(
                {"_id": "leader", "expires_at": {"$lte": now}},
                {"$set": {"holder": self._holder_id, "expires_at": expires, "updated_at": now}},
            )
            self.is_leader = result.modified_count == 1
            return self.is_leader

        self.is_leader = False
        return False

    async def release(self) -> None:
        await self._db.flow_scheduler_leader.update_one(
            {"_id": "leader", "holder": self._holder_id},
            {"$set": {"expires_at": datetime.now(UTC)}},
        )
        self.is_leader = False
