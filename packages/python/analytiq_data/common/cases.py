"""Org-scoped document cases (case collation)."""

from __future__ import annotations

import re
from datetime import datetime, UTC
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

import analytiq_data as ad

CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ASSIGN_BATCH_SIZE = 1000


def validate_case_id(case_id: str) -> str:
    case_id = case_id.strip()
    if not CASE_ID_PATTERN.match(case_id):
        raise ValueError(
            "case_id must be 1–128 characters: letters, digits, and . _ : - only"
        )
    return case_id


def normalize_case_metadata(metadata: dict[str, str] | None) -> dict[str, str]:
    if not metadata:
        return {}
    out: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        trimmed = value.strip()
        if trimmed:
            out[key.strip()] = trimmed
    return out


async def _validate_tag_ids(db, organization_id: str, tag_ids: list[str]) -> None:
    if not tag_ids:
        return
    existing = await db.tags.find(
        {
            "_id": {"$in": [ObjectId(tid) for tid in tag_ids]},
            "organization_id": organization_id,
        },
        {"_id": 1},
    ).to_list(None)
    existing_ids = {str(t["_id"]) for t in existing}
    missing = set(tag_ids) - existing_ids
    if missing:
        raise ValueError(f"Invalid tag IDs: {sorted(missing)}")


def _cases_coll(analytiq_client):
    return analytiq_client.mongodb_async[analytiq_client.env]["cases"]


def _docs_coll(analytiq_client):
    return analytiq_client.mongodb_async[analytiq_client.env]["docs"]


async def get_case(analytiq_client, organization_id: str, case_id: str) -> dict | None:
    case_id = validate_case_id(case_id)
    return await _cases_coll(analytiq_client).find_one(
        {"organization_id": organization_id, "case_id": case_id, "deleting_at": None}
    )


async def count_documents_in_case(
    analytiq_client, organization_id: str, case_id: str
) -> int:
    return await _docs_coll(analytiq_client).count_documents(
        {"organization_id": organization_id, "case_id": case_id}
    )


async def create_case(
    analytiq_client,
    organization_id: str,
    *,
    case_id: str | None,
    display_name: str | None,
    tag_ids: list[str] | None,
    metadata: dict[str, str] | None,
    created_by: str,
) -> dict:
    db = analytiq_client.mongodb_async[analytiq_client.env]
    if case_id is None or not str(case_id).strip():
        case_id = f"DR-{ad.common.create_id()}"
    case_id = validate_case_id(case_id)
    tag_ids = tag_ids or []
    metadata = normalize_case_metadata(metadata)

    await _validate_tag_ids(db, organization_id, tag_ids)

    now = datetime.now(UTC)
    doc = {
        "organization_id": organization_id,
        "case_id": case_id,
        "display_name": (display_name or "").strip() or case_id,
        "tag_ids": tag_ids,
        "metadata": metadata,
        "deleting_at": None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    try:
        await _cases_coll(analytiq_client).insert_one(doc)
    except DuplicateKeyError as e:
        raise ValueError(f"Case {case_id} already exists") from e
    return doc


async def update_case(
    analytiq_client,
    organization_id: str,
    case_id: str,
    *,
    display_name: str | None = None,
    tag_ids: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> dict | None:
    case_id = validate_case_id(case_id)
    db = analytiq_client.mongodb_async[analytiq_client.env]
    update: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if display_name is not None:
        update["display_name"] = display_name.strip() or case_id
    if tag_ids is not None:
        await _validate_tag_ids(db, organization_id, tag_ids)
        update["tag_ids"] = tag_ids
    if metadata is not None:
        update["metadata"] = normalize_case_metadata(metadata)

    return await _cases_coll(analytiq_client).find_one_and_update(
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "deleting_at": None,
        },
        {"$set": update},
        return_document=True,
    )


async def build_cases_match_query(
    organization_id: str,
    *,
    case_id_search: str | None = None,
    tag_ids: list[str] | None = None,
    metadata_search: dict[str, str] | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {
        "organization_id": organization_id,
        "deleting_at": None,
    }
    if case_id_search:
        query["case_id"] = {"$regex": re.escape(case_id_search.strip()), "$options": "i"}
    if tag_ids:
        query["tag_ids"] = {"$all": tag_ids}
    if metadata_search:
        for key, value in metadata_search.items():
            query[f"metadata.{key}"] = value
    return query


async def list_cases(
    analytiq_client,
    organization_id: str,
    *,
    skip: int = 0,
    limit: int = 50,
    case_id_search: str | None = None,
    tag_ids: list[str] | None = None,
    metadata_search: dict[str, str] | None = None,
    sort_field: str = "updated_at",
    sort_dir: int = -1,
) -> tuple[list[dict], int]:
    coll = _cases_coll(analytiq_client)
    query = await build_cases_match_query(
        organization_id,
        case_id_search=case_id_search,
        tag_ids=tag_ids,
        metadata_search=metadata_search,
    )
    total = await coll.count_documents(query)
    cursor = (
        coll.find(query)
        .sort(sort_field, sort_dir)
        .skip(skip)
        .limit(limit)
    )
    cases = await cursor.to_list(length=limit)
    return cases, total


async def _touch_case(
    analytiq_client, organization_id: str, case_id: str, *, session=None
) -> None:
    result = await _cases_coll(analytiq_client).update_one(
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "deleting_at": None,
        },
        {"$set": {"updated_at": datetime.now(UTC)}},
        session=session,
    )
    if result.matched_count == 0:
        row = await _cases_coll(analytiq_client).find_one(
            {"organization_id": organization_id, "case_id": case_id},
            session=session,
        )
        if not row:
            raise LookupError("unknown_case")
        if row.get("deleting_at") is not None:
            raise LookupError("case_deleting")
        raise LookupError("unknown_case")


async def _upsert_case_for_assign(
    analytiq_client,
    organization_id: str,
    case_id: str,
    created_by: str,
    *,
    session=None,
) -> None:
    now = datetime.now(UTC)
    await _cases_coll(analytiq_client).update_one(
        {"organization_id": organization_id, "case_id": case_id},
        {
            "$setOnInsert": {
                "organization_id": organization_id,
                "case_id": case_id,
                "display_name": case_id,
                "tag_ids": [],
                "metadata": {},
                "deleting_at": None,
                "created_by": created_by,
                "created_at": now,
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
        session=session,
    )
    row = await _cases_coll(analytiq_client).find_one(
        {"organization_id": organization_id, "case_id": case_id},
        session=session,
    )
    if row and row.get("deleting_at") is not None:
        raise LookupError("case_deleting")


async def assign_documents_to_case(
    analytiq_client,
    organization_id: str,
    document_ids: list[str],
    case_id: str,
    *,
    create_case_if_missing: bool,
    created_by: str,
) -> None:
    if not document_ids:
        return
    case_id = validate_case_id(case_id)
    doc_oids = [ObjectId(did) for did in document_ids]

    async def _run(session):
        if create_case_if_missing:
            try:
                await _upsert_case_for_assign(
                    analytiq_client, organization_id, case_id, created_by, session=session
                )
            except DuplicateKeyError:
                pass
        else:
            await _touch_case(analytiq_client, organization_id, case_id, session=session)

        now = datetime.now(UTC)
        result = await _docs_coll(analytiq_client).update_many(
            {
                "_id": {"$in": doc_oids},
                "organization_id": organization_id,
            },
            {"$set": {"case_id": case_id, "updated_at": now}},
            session=session,
        )
        if result.matched_count != len(doc_oids):
            raise LookupError("document_not_found")

    client = analytiq_client.mongodb_async
    for attempt in (1, 2):
        try:
            async with await client.start_session() as session:
                await session.with_transaction(_run)
            return
        except DuplicateKeyError:
            if attempt == 2:
                raise
        except Exception as e:
            if "Transaction numbers are only allowed" in str(e):
                await _run(None)
                return
            raise


async def remove_documents_from_case(
    analytiq_client,
    organization_id: str,
    document_ids: list[str],
) -> None:
    if not document_ids:
        return
    doc_oids = [ObjectId(did) for did in document_ids]
    docs = await _docs_coll(analytiq_client).find(
        {"_id": {"$in": doc_oids}, "organization_id": organization_id},
        {"case_id": 1},
    ).to_list(None)
    if len(docs) != len(doc_oids):
        raise LookupError("document_not_found")

    case_ids = {d["case_id"] for d in docs if d.get("case_id")}
    now = datetime.now(UTC)

    async def _run(session):
        for cid in case_ids:
            await _touch_case(analytiq_client, organization_id, cid, session=session)
        await _docs_coll(analytiq_client).update_many(
            {"_id": {"$in": doc_oids}, "organization_id": organization_id},
            {"$set": {"case_id": None, "updated_at": now}},
            session=session,
        )

    client = analytiq_client.mongodb_async
    try:
        async with await client.start_session() as session:
            await session.with_transaction(_run)
    except Exception as e:
        if "Transaction numbers are only allowed" in str(e):
            await _run(None)
        else:
            raise


async def delete_case(
    analytiq_client,
    organization_id: str,
    case_id: str,
    *,
    cascade_documents: bool,
) -> bool:
    case_id = validate_case_id(case_id)
    coll = _cases_coll(analytiq_client)
    now = datetime.now(UTC)
    row = await coll.find_one_and_update(
        {
            "organization_id": organization_id,
            "case_id": case_id,
            "deleting_at": None,
        },
        {"$set": {"deleting_at": now, "updated_at": now}},
        return_document=True,
    )
    if not row:
        return False

    if cascade_documents:
        # Phase 1: synchronous batch delete; worker queue can follow for large cases.
        while True:
            docs = await _docs_coll(analytiq_client).find(
                {"organization_id": organization_id, "case_id": case_id},
                {"_id": 1},
            ).limit(100).to_list(100)
            if not docs:
                break
            for doc in docs:
                await ad.common.delete_doc(
                    analytiq_client, str(doc["_id"]), organization_id
                )
    else:
        await _docs_coll(analytiq_client).update_many(
            {"organization_id": organization_id, "case_id": case_id},
            {"$set": {"case_id": None, "updated_at": now}},
        )

    await coll.delete_one({"organization_id": organization_id, "case_id": case_id})
    return True
