from __future__ import annotations

"""Process-wide flow trigger scheduler service (leader + registry + startup reload)."""

import asyncio
import logging
import os
from typing import Any

from bson import ObjectId

import analytiq_data as ad

from .leader import FlowSchedulerLeader
from .registry import ActiveFlowRegistry
from .scheduler import FlowScheduler


logger = logging.getLogger(__name__)

_service: "FlowTriggerService | None" = None


def get_flow_trigger_service() -> "FlowTriggerService | None":
    return _service


class FlowTriggerService:
    """Leader-elected trigger runner bound to one MongoDB client."""

    def __init__(
        self,
        analytiq_client,
        *,
        leader_ttl_secs: int | None = None,
        lease_ttl_secs: int = 120,
        holder_id: str | None = None,
    ) -> None:
        self._client = analytiq_client
        self._db = ad.common.get_async_db(analytiq_client)
        ttl = leader_ttl_secs
        if ttl is None:
            ttl = int(os.getenv("FLOW_SCHEDULER_LEADER_TTL_SECS", "30"))
        self._leader = FlowSchedulerLeader(self._db, holder_id=holder_id, ttl_secs=ttl)
        self._scheduler = FlowScheduler()
        self._registry = ActiveFlowRegistry(
            analytiq_client,
            self._scheduler,
            leader_check=lambda: self._leader.is_leader,
            lease_ttl_secs=lease_ttl_secs,
        )
        self._renew_task: asyncio.Task | None = None

    @property
    def registry(self) -> ActiveFlowRegistry:
        return self._registry

    @property
    def leader(self) -> FlowSchedulerLeader:
        return self._leader

    async def start(self) -> None:
        await self._leader.renew()
        self._renew_task = asyncio.create_task(self._leader_renew_loop(), name="flow_scheduler_leader")
        await self._reload_active_flows()
        logger.info(
            f"Flow trigger service started holder={self._leader.holder_id!r} leader={self._leader.is_leader}"
        )

    async def stop(self) -> None:
        if self._renew_task:
            self._renew_task.cancel()
            try:
                await self._renew_task
            except asyncio.CancelledError:
                pass
            self._renew_task = None
        for flow_id in list(self._registry._triggers.keys()):
            await self._registry.deregister_flow(flow_id)
        await self._scheduler.shutdown()
        await self._leader.release()

    async def _leader_renew_loop(self) -> None:
        interval = max(1.0, self._leader._ttl_secs / 3.0)
        while True:
            try:
                was_leader = self._leader.is_leader
                await self._leader.renew()
                if self._leader.is_leader and not was_leader:
                    logger.info("Became flow scheduler leader; reloading active flows")
                    await self._reload_active_flows()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Flow scheduler leader renewal failed")
            await asyncio.sleep(interval)

    async def _reload_active_flows(self) -> None:
        if not self._leader.is_leader:
            return
        cursor = self._db.flows.find({"active": True, "active_flow_revid": {"$ne": None}})
        async for header in cursor:
            flow_id = str(header["_id"])
            rev_id = header.get("active_flow_revid")
            if not rev_id:
                continue
            revision = await self._db.flow_revisions.find_one(
                {"_id": ObjectId(str(rev_id)), "flow_id": flow_id}
            )
            if not revision:
                logger.warning(f"Active flow {flow_id!r} missing revision {rev_id!r}")
                continue
            org_id = header.get("organization_id") or ""
            try:
                await self._registry.register_flow(org_id, flow_id, str(rev_id), revision)
            except ad.flows.FlowValidationError as e:
                logger.error(f"Failed to register triggers for flow {flow_id!r}: {e}")

    async def register_flow(
        self,
        organization_id: str,
        flow_id: str,
        flow_revid: str,
        revision: dict[str, Any],
        *,
        run_immediately: bool = False,
    ) -> None:
        await self._registry.register_flow(
            organization_id,
            flow_id,
            flow_revid,
            revision,
            run_immediately=run_immediately,
        )

    async def deregister_flow(self, flow_id: str) -> None:
        await self._registry.deregister_flow(flow_id)


async def ensure_flow_trigger_indexes(analytiq_client) -> None:
    db = ad.common.get_async_db(analytiq_client)
    await db.flow_static_data.create_index(
        [("flow_id", 1), ("node_id", 1)],
        unique=True,
        name="flow_static_data_flow_node_unique",
    )
    await db.flow_trigger_leases.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="flow_trigger_leases_expires_at_ttl",
    )
    await db.flow_trigger_registrations.create_index(
        [("flow_id", 1), ("node_id", 1), ("rule_index", 1)],
        unique=True,
        name="flow_trigger_registrations_flow_node_rule_unique",
    )
    await db.flow_trigger_registrations.create_index(
        [("flow_id", 1)],
        name="flow_trigger_registrations_flow_id",
    )
    await db.flow_executions.create_index(
        "trigger.dedupe_key",
        unique=True,
        sparse=True,
        name="flow_executions_trigger_dedupe_key_unique",
    )

    await ad.docrouter_flows.ensure_docrouter_flow_trigger_indexes(db)
    await ad.docrouter_flows.ensure_flow_results_indexes(db)


async def start_flow_trigger_service(analytiq_client, **kwargs: Any) -> FlowTriggerService:
    global _service
    if _service is not None:
        return _service
    await ensure_flow_trigger_indexes(analytiq_client)
    _service = FlowTriggerService(analytiq_client, **kwargs)
    await _service.start()
    return _service


async def stop_flow_trigger_service() -> None:
    global _service
    if _service is None:
        return
    await _service.stop()
    _service = None
