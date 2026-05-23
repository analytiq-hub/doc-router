from __future__ import annotations

"""Activation-time poll smoke test (n8n-style)."""

import analytiq_data as ad

from .poll_context import PollContext
from .static_data import load_node_static_data, save_node_static_data


async def run_poll_activation_tests(
    analytiq_client,
    *,
    organization_id: str,
    flow_id: str,
    flow_revid: str,
    revision: dict,
) -> None:
    """
    Run each poll trigger once with ``tick_meta.testing=True``.

    Raises ``FlowValidationError`` when ``poll()`` raises. Empty poll output is allowed.
    Static data mutations during the test are persisted (cursor initialization, etc.).
    """

    db = ad.common.get_async_db(analytiq_client)
    nodes = revision.get("nodes") or []

    for node in nodes:
        if node.get("disabled"):
            continue
        node_type_key = node.get("type") or ""
        try:
            nt = ad.flows.get(node_type_key)
        except KeyError:
            continue
        if not getattr(nt, "polling", False):
            continue

        poll_fn = getattr(nt, "poll", None)
        if poll_fn is None:
            raise ad.flows.FlowValidationError(
                f"Poll trigger {ad.flows.node_name(node)} has no poll() implementation"
            )

        node_id = node["id"]
        static_data = await load_node_static_data(db, flow_id, node_id)
        ctx = PollContext(
            organization_id=organization_id,
            flow_id=flow_id,
            flow_revid=flow_revid,
            node_id=node_id,
            mode="schedule",
            analytiq_client=analytiq_client,
            tick_meta={"testing": True, "rule_index": 0, "tick_key": "activation"},
            static_data=static_data,
        )
        try:
            await poll_fn(ctx, node)
        except Exception as e:
            raise ad.flows.FlowValidationError(
                f"Poll trigger {ad.flows.node_name(node)} activation test failed: {e}"
            ) from e

        if ctx.data_changed:
            await save_node_static_data(db, flow_id, node_id, ctx.static_data)
