"""Gmail poll trigger logic (``flows.trigger.gmail``)."""

from __future__ import annotations

import time
from typing import Any

import analytiq_data as ad

from .api import (
    gmail_api_request,
    resolve_oauth_access_token_for_org,
)
from .email_parse import parse_gmail_api_message
from .helpers import prepare_gmail_list_query, simplify_messages
from .operations import _fetch_label_map

LAST_TIME_CHECKED_KEY = "last_time_checked"
POSSIBLE_DUPLICATES_KEY = "possible_duplicates"


def _message_unix_seconds(message: dict[str, Any], *, fallback: int) -> int:
    internal = message.get("internalDate")
    if internal is not None and str(internal).isdigit():
        return int(str(internal)) // 1000

    for key in ("date", "Date"):
        raw = message.get(key)
        if isinstance(raw, str) and raw.strip():
            from datetime import UTC, datetime

            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return int(dt.timestamp())
            except ValueError:
                pass

    headers = message.get("headers")
    if isinstance(headers, dict):
        hdr_date = headers.get("date") or headers.get("Date")
        if isinstance(hdr_date, str) and hdr_date.strip():
            from datetime import UTC, datetime

            try:
                dt = datetime.fromisoformat(hdr_date.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return int(dt.timestamp())
            except ValueError:
                pass

    return fallback


def _should_skip_message(message: dict[str, Any], *, include_drafts: bool) -> bool:
    label_ids = message.get("labelIds")
    ids = label_ids if isinstance(label_ids, list) else []
    if not include_drafts and "DRAFT" in ids:
        return True
    if "SENT" in ids and "INBOX" not in ids:
        return True
    return False


async def _verify_gmail_credential(token: str) -> None:
    await gmail_api_request(token, "GET", "/gmail/v1/users/me/profile")


async def poll_gmail_trigger(
    context: "ad.flows.PollContext",
    node: dict[str, Any],
) -> list[list[ad.flows.FlowItem]] | None:
    """
    Poll Gmail for new messages and return one ``FlowItem`` per matching email.

    Maintains ``last_time_checked`` (unix seconds) and ``possible_duplicates`` in static data.
    """

    params = node.get("parameters") if isinstance(node.get("parameters"), dict) else {}
    simple = bool(params.get("simple", True))
    filters = dict(params.get("filters") or {}) if isinstance(params.get("filters"), dict) else {}
    options = dict(params.get("options") or {}) if isinstance(params.get("options"), dict) else {}

    manual = context.mode == "manual"
    testing = bool(context.tick_meta.get("testing"))
    node_id = str(node.get("id") or "")

    token = await resolve_oauth_access_token_for_org(context.organization_id, node)

    if testing:
        await _verify_gmail_credential(token)
        context.set_static(LAST_TIME_CHECKED_KEY, int(time.time()))
        return None

    now_secs = int(time.time())
    last_checked = context.get_static(LAST_TIME_CHECKED_KEY)
    if not manual and last_checked is None:
        context.set_static(LAST_TIME_CHECKED_KEY, now_secs)
        last_checked = now_secs
    start_date = int(last_checked) if last_checked is not None else now_secs

    list_filters = dict(filters)
    if not manual:
        list_filters["receivedAfter"] = start_date
    qs = prepare_gmail_list_query(list_filters)
    if manual:
        qs["maxResults"] = 1

    listed = await gmail_api_request(
        token,
        "GET",
        "/gmail/v1/users/me/messages",
        query=qs,
        trace_node_id=node_id or None,
    )
    stubs = listed.get("messages") if isinstance(listed, dict) else []
    if not isinstance(stubs, list) or not stubs:
        if manual:
            raise ad.flows.FlowValidationError(
                "No data with the current filter could be found"
            )
        return None

    fetch_qs: dict[str, Any] = {}
    if simple:
        fetch_qs["format"] = "metadata"
        fetch_qs["metadataHeaders"] = ["From", "To", "Cc", "Bcc", "Subject"]
    else:
        fetch_qs["format"] = "raw"

    include_drafts = bool(filters.get("includeDrafts"))
    all_fetched: list[dict[str, Any]] = []
    items: list[ad.flows.FlowItem] = []

    for stub in stubs:
        if not isinstance(stub, dict) or not stub.get("id"):
            continue
        mid = str(stub["id"])
        msg = await gmail_api_request(
            token,
            "GET",
            f"/gmail/v1/users/me/messages/{mid}",
            query=fetch_qs,
            trace_node_id=node_id or None,
        )
        if not isinstance(msg, dict):
            continue
        all_fetched.append(msg)
        if _should_skip_message(msg, include_drafts=include_drafts):
            continue

        if simple:
            items.append(
                ad.flows.FlowItem(
                    json=dict(msg),
                    binary={},
                    meta={"source_node_id": node_id, "item_index": len(items)},
                    paired_item=None,
                )
            )
        else:
            prefix = str(options.get("attachmentPrefix") or "attachment_")
            download = bool(options.get("downloadAttachments"))
            parsed, binary = parse_gmail_api_message(
                msg,
                download_attachments=download,
                attachment_prefix=prefix,
            )
            items.append(
                ad.flows.FlowItem(
                    json=parsed,
                    binary=binary,
                    meta={"source_node_id": node_id, "item_index": len(items)},
                    paired_item=None,
                )
            )

    if simple and items:
        label_map = await _fetch_label_map(None, token, node_id or None)
        simplified = await simplify_messages(
            token,
            [item.json for item in items],
            label_map=label_map,
        )
        items = [
            ad.flows.FlowItem(
                json=row,
                binary=dict(items[i].binary),
                meta={"source_node_id": node_id, "item_index": i},
                paired_item=None,
            )
            for i, row in enumerate(simplified)
        ]

    if not all_fetched:
        if manual:
            raise ad.flows.FlowValidationError(
                "No data with the current filter could be found"
            )
        return None

    invalid_date_ids: set[str] = set()
    last_email_date = 0
    for msg in all_fetched:
        mid = str(msg.get("id") or "")
        email_date = _message_unix_seconds(msg, fallback=start_date)
        if mid and email_date == start_date and not msg.get("internalDate"):
            invalid_date_ids.add(mid)
        if email_date > last_email_date:
            last_email_date = email_date

    next_duplicates: list[str] = []
    for msg in all_fetched:
        mid = str(msg.get("id") or "")
        if not mid:
            continue
        email_date = _message_unix_seconds(msg, fallback=start_date)
        if email_date <= last_email_date:
            next_duplicates.append(mid)
    next_duplicates.extend(invalid_date_ids)

    possible = set(context.get_static(POSSIBLE_DUPLICATES_KEY) or [])
    if possible:
        items = [item for item in items if str(item.json.get("id") or "") not in possible]

    context.set_static(POSSIBLE_DUPLICATES_KEY, next_duplicates)
    context.set_static(LAST_TIME_CHECKED_KEY, last_email_date or start_date)

    if not items:
        return None
    return [items]
