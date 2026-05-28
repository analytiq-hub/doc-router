from __future__ import annotations

"""In-memory registry of active flows with scheduled/poll trigger jobs."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

import analytiq_data as ad

from ..flow_settings import resolve_flow_timezone
from .cron_exprs import (
    CronExpressionError,
    TriggerScheduleSpec,
    parse_schedule_anchor,
    poll_times_to_specs,
    schedule_params_to_specs,
)
from .enqueue import enqueue_scheduled_flow_run
from .registrations import delete_trigger_registrations, upsert_trigger_registrations
from .leases import acquire_tick_lease
from .poll_context import PollContext, require_poll_context
from .poll_defaults import resolve_poll_times
from .scheduler import FlowScheduler
from .static_data import load_node_static_data, save_node_static_data


logger = logging.getLogger(__name__)

SCHEDULE_ANCHORS_KEY = "schedule_anchors"


@dataclass
class _RegisteredTrigger:
    organization_id: str
    flow_id: str
    flow_revid: str
    node: dict[str, Any]
    node_type_key: str
    timezone: str = "UTC"
    specs: list[TriggerScheduleSpec] = field(default_factory=list)


class ActiveFlowRegistry:
    """Maps active flows to cron jobs and executes ticks on the leader."""

    def __init__(
        self,
        analytiq_client,
        scheduler: FlowScheduler,
        *,
        leader_check: Any,
        lease_ttl_secs: int = 120,
    ) -> None:
        self._client = analytiq_client
        self._db = ad.common.get_async_db(analytiq_client)
        self._scheduler = scheduler
        self._leader_check = leader_check
        self._lease_ttl_secs = lease_ttl_secs
        self._triggers: dict[str, list[_RegisteredTrigger]] = {}

    async def register_flow(
        self,
        organization_id: str,
        flow_id: str,
        flow_revid: str,
        revision: dict[str, Any],
        *,
        run_immediately: bool = False,
    ) -> None:
        await self.deregister_flow(flow_id)
        nodes = revision.get("nodes") or []
        ad.flows.ensure_builtin_keys_for_revision(revision)
        timezone = resolve_flow_timezone(revision.get("settings"))
        registered: list[_RegisteredTrigger] = []

        for node in nodes:
            if node.get("disabled"):
                continue
            node_type_key = node.get("type") or ""
            try:
                nt = ad.flows.get(node_type_key)
            except KeyError:
                continue

            params = node.get("parameters") or {}
            specs: list[TriggerScheduleSpec] = []
            trigger_kind = ""

            if node_type_key == "flows.trigger.schedule":
                try:
                    specs = schedule_params_to_specs(params)
                except CronExpressionError as e:
                    raise ad.flows.FlowValidationError(
                        f"Schedule trigger {ad.flows.node_name(node)}: {e}"
                    ) from e
                trigger_kind = "schedule"
            elif getattr(nt, "polling", False):
                try:
                    specs = poll_times_to_specs(resolve_poll_times(params))
                except CronExpressionError as e:
                    raise ad.flows.FlowValidationError(
                        f"Poll trigger {ad.flows.node_name(node)}: {e}"
                    ) from e
                trigger_kind = "poll"
            else:
                continue

            anchors = await self._resolve_schedule_anchors(
                flow_id=flow_id,
                node_id=node["id"],
                specs=specs,
                reset=run_immediately,
            )

            reg = _RegisteredTrigger(
                organization_id=organization_id,
                flow_id=flow_id,
                flow_revid=flow_revid,
                node=node,
                node_type_key=node_type_key,
                timezone=timezone,
                specs=specs,
            )
            registered.append(reg)

            for spec in specs:
                job_id = self._job_id(flow_id, node["id"], spec.rule_index)
                tick = self._make_tick(reg, spec.rule_index, trigger_kind)
                if spec.kind == "interval":
                    anchor = anchors.get(spec.rule_index) or datetime.now(UTC)
                    await self._scheduler.register_interval(
                        job_id,
                        spec.interval_secs or 0.0,
                        tick,
                        anchor=anchor,
                        run_immediately=run_immediately,
                    )
                else:
                    await self._scheduler.register_cron(
                        job_id,
                        spec.cron_expr or "",
                        tick,
                        timezone=timezone,
                        run_immediately=run_immediately,
                    )

            await upsert_trigger_registrations(
                self._db,
                organization_id=organization_id,
                flow_id=flow_id,
                flow_revid=flow_revid,
                node_id=node["id"],
                trigger_kind=trigger_kind,
                timezone=timezone,
                specs=specs,
                anchors=anchors,
            )

        if registered:
            self._triggers[flow_id] = registered
            logger.info(
                f"Registered {len(registered)} trigger node(s) for active flow {flow_id!r}"
            )

    async def _resolve_schedule_anchors(
        self,
        *,
        flow_id: str,
        node_id: str,
        specs: list[TriggerScheduleSpec],
        reset: bool,
    ) -> dict[int, datetime]:
        interval_indices = [s.rule_index for s in specs if s.kind == "interval"]
        if not interval_indices:
            return {}

        now = datetime.now(UTC)
        static_data = await load_node_static_data(self._db, flow_id, node_id)
        raw_anchors = static_data.get(SCHEDULE_ANCHORS_KEY)
        stored: dict[str, str] = raw_anchors if isinstance(raw_anchors, dict) else {}

        anchors: dict[int, datetime] = {}
        for rule_index in interval_indices:
            key = str(rule_index)
            if reset:
                anchors[rule_index] = now
                stored[key] = now.isoformat()
                continue
            parsed = parse_schedule_anchor(stored.get(key))
            anchors[rule_index] = parsed or now

        if reset:
            static_data[SCHEDULE_ANCHORS_KEY] = stored
            await save_node_static_data(self._db, flow_id, node_id, static_data)

        return anchors

    async def deregister_flow(self, flow_id: str) -> None:
        self._triggers.pop(flow_id, None)
        await self._scheduler.deregister_prefix(f"{flow_id}:")
        await delete_trigger_registrations(self._db, flow_id=flow_id)

    def _job_id(self, flow_id: str, node_id: str, rule_index: int) -> str:
        return f"{flow_id}:{node_id}:{rule_index}"

    def _make_tick(
        self,
        reg: _RegisteredTrigger,
        rule_index: int,
        trigger_kind: str,
    ):
        async def _tick() -> None:
            if not self._leader_check():
                return
            tick_key = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")
            node_id = reg.node["id"]
            if not await acquire_tick_lease(
                self._db,
                flow_id=reg.flow_id,
                node_id=node_id,
                tick_key=tick_key,
                ttl_secs=self._lease_ttl_secs,
            ):
                logger.debug(
                    f"Skipping duplicate tick flow={reg.flow_id!r} node={node_id!r} key={tick_key!r}"
                )
                return
            try:
                await self._run_tick(reg, rule_index, tick_key, trigger_kind)
            except Exception:
                logger.exception(
                    f"Trigger tick failed flow={reg.flow_id!r} node={node_id!r} kind={trigger_kind!r}"
                )

        return _tick

    async def _run_tick(
        self,
        reg: _RegisteredTrigger,
        rule_index: int,
        tick_key: str,
        trigger_kind: str,
    ) -> None:
        nt = ad.flows.get(reg.node_type_key)
        node_id = reg.node["id"]
        static_data = await load_node_static_data(self._db, reg.flow_id, node_id)
        ctx = PollContext(
            organization_id=reg.organization_id,
            flow_id=reg.flow_id,
            flow_revid=reg.flow_revid,
            node_id=node_id,
            mode="schedule",
            analytiq_client=self._client,
            tick_meta={"rule_index": rule_index, "tick_key": tick_key},
            static_data=static_data,
        )

        require_poll_context(ctx)

        items: list[list[ad.flows.FlowItem]] | None = None
        if trigger_kind == "schedule":
            on_tick = getattr(nt, "on_schedule_tick", None)
            if on_tick is None:
                logger.warning(f"Node type {reg.node_type_key!r} has no on_schedule_tick")
                return
            items = await on_tick(ctx, reg.node)
        elif trigger_kind == "poll":
            poll_fn = getattr(nt, "poll", None)
            if poll_fn is None:
                logger.warning(f"Node type {reg.node_type_key!r} has no poll")
                return
            items = await poll_fn(ctx, reg.node)

        if ctx.data_changed:
            await save_node_static_data(self._db, reg.flow_id, node_id, ctx.static_data)

        if not items:
            return
        if all(not lane for lane in items):
            return

        await enqueue_scheduled_flow_run(
            self._client,
            organization_id=reg.organization_id,
            flow_id=reg.flow_id,
            flow_revid=reg.flow_revid,
            trigger_node_id=node_id,
            trigger_type=trigger_kind,
            items=items,
            tick_key=tick_key,
            rule_index=rule_index,
        )
        logger.info(
            f"Enqueued scheduled flow run flow={reg.flow_id!r} node={node_id!r} tick={tick_key!r}"
        )
