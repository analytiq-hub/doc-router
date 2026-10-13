"""Org-scoped document cases (case collation)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, UTC
from typing import Any, Awaitable, Callable

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import analytiq_data as ad

logger = logging.getLogger(__name__)

CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ASSIGN_BATCH_SIZE = 1000
CASCADE_DELETE_BATCH_SIZE = 100


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


def _unique_object_ids(document_ids: list[str]) -> list[ObjectId]:
    """Convert to ObjectIds, dropping duplicates while keeping order."""
    return list(dict.fromkeys(ObjectId(did) for did in document_ids))


async def _run_in_transaction(
    analytiq_client, fn: Callable[[Any], Awaitable[None]]
) -> None:
    """
    Run ``fn(session)`` in a transaction (retried by the driver on write conflicts).

    Standalone MongoDB (no replica set) cannot run transactions; ``fn`` then runs
    without one, and assign/delete races are no longer prevented.
    """
    client = analytiq_client.mongodb_async
    try:
        async with await client.start_session() as session:
            await session.with_transaction(fn)
    except Exception as e:
        if "Transaction numbers are only allowed" not in str(e):
            raise
        logger.warning(
            f"MongoDB is not a replica set; running case update without a transaction "
            f"(concurrent assign/delete is not protected): {e}"
        )
        await fn(None)


async def get_case(analytiq_client, organization_id: str, case_id: str) -> dict | None:
    case_id = validate_case_id(case_id)
    return await _cases_coll(analytiq_client).find_one(
        {"organization_id": organization_id, "case_id": case_id, "deleting_at": None}
    )


async def count_documents_in_cases(
    analytiq_client, organization_id: str, case_ids: list[str]
) -> dict[str, int]:
    """Document counts for several cases with one aggregation. Missing cases count 0."""
    if not case_ids:
        return {}
    rows = await _docs_coll(analytiq_client).aggregate(
        [
            {"$match": {"organization_id": organization_id, "case_id": {"$in": case_ids}}},
            {"$group": {"_id": "$case_id", "count": {"$sum": 1}}},
        ]
    ).to_list(None)
    counts = {cid: 0 for cid in case_ids}
    for row in rows:
        counts[row["_id"]] = row["count"]
    return counts


async def count_documents_in_case(
    analytiq_client, organization_id: str, case_id: str
) -> int:
    counts = await count_documents_in_cases(analytiq_client, organization_id, [case_id])
    return counts[case_id]


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
    """
    Bump ``updated_at`` on a live case, or raise ``LookupError``.

    Writing the case row (not just reading it) makes a concurrent delete, which
    also writes the row, conflict with this transaction instead of interleaving.
    """
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
            {"deleting_at": 1},
            session=session,
        )
        if row and row.get("deleting_at") is not None:
            raise LookupError("case_deleting")
        raise LookupError("unknown_case")


async def check_case_assignable(
    analytiq_client, organization_id: str, case_id: str
) -> str:
    """
    Validate a case id and check that documents can be assigned to it, without writing.

    Lets callers reject a bad case id before doing other work. The assignment itself
    re-checks inside its transaction. Returns the normalized case id.
    """
    case_id = validate_case_id(case_id)
    row = await _cases_coll(analytiq_client).find_one(
        {"organization_id": organization_id, "case_id": case_id},
        {"deleting_at": 1},
    )
    if not row:
        raise LookupError("unknown_case")
    if row.get("deleting_at") is not None:
        raise LookupError("case_deleting")
    return case_id


async def _upsert_case_for_assign(
    analytiq_client,
    organization_id: str,
    case_id: str,
    created_by: str,
    *,
    session=None,
) -> None:
    now = datetime.now(UTC)
    row = await _cases_coll(analytiq_client).find_one_and_update(
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
        return_document=ReturnDocument.AFTER,
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
    set_fields: dict[str, Any] | None = None,
) -> None:
    """
    Assign documents to a case, in transactions of up to ``ASSIGN_BATCH_SIZE`` documents.

    ``set_fields`` are written to the documents in the same transaction, so a caller
    that also changes other document fields either saves everything or nothing.

    Raises ``ValueError`` for an invalid case id and ``LookupError`` with
    ``unknown_case``, ``case_deleting`` or ``document_not_found``.
    """
    if not document_ids:
        return
    case_id = validate_case_id(case_id)
    doc_oids = _unique_object_ids(document_ids)

    for start in range(0, len(doc_oids), ASSIGN_BATCH_SIZE):
        batch = doc_oids[start:start + ASSIGN_BATCH_SIZE]

        async def _run(session, batch=batch):
            if create_case_if_missing:
                await _upsert_case_for_assign(
                    analytiq_client, organization_id, case_id, created_by, session=session
                )
            else:
                await _touch_case(analytiq_client, organization_id, case_id, session=session)

            fields = {**(set_fields or {}), "case_id": case_id, "updated_at": datetime.now(UTC)}
            result = await _docs_coll(analytiq_client).update_many(
                {"_id": {"$in": batch}, "organization_id": organization_id},
                {"$set": fields},
                session=session,
            )
            if result.matched_count != len(batch):
                raise LookupError("document_not_found")

        # Two requests creating the same case at once: one insert loses on the unique
        # index and aborts its transaction. The retry then finds the existing case.
        for attempt in (1, 2):
            try:
                await _run_in_transaction(analytiq_client, _run)
                break
            except DuplicateKeyError:
                if attempt == 2:
                    raise


async def remove_documents_from_case(
    analytiq_client,
    organization_id: str,
    document_ids: list[str],
    *,
    set_fields: dict[str, Any] | None = None,
) -> None:
    """
    Clear ``case_id`` on documents. Always succeeds for existing documents, even when
    their case is being deleted or no longer exists.

    ``set_fields`` are written to the documents in the same transaction.
    Raises ``LookupError("document_not_found")``.
    """
    if not document_ids:
        return
    doc_oids = _unique_object_ids(document_ids)

    for start in range(0, len(doc_oids), ASSIGN_BATCH_SIZE):
        batch = doc_oids[start:start + ASSIGN_BATCH_SIZE]

        async def _run(session, batch=batch):
            docs = await _docs_coll(analytiq_client).find(
                {"_id": {"$in": batch}, "organization_id": organization_id},
                {"case_id": 1},
                session=session,
            ).to_list(None)
            if len(docs) != len(batch):
                raise LookupError("document_not_found")

            now = datetime.now(UTC)
            case_ids = sorted({d["case_id"] for d in docs if d.get("case_id")})
            if case_ids:
                # Bump updated_at on whichever of these cases still exist. Not
                # filtering on deleting_at keeps removal working during a delete.
                await _cases_coll(analytiq_client).update_many(
                    {"organization_id": organization_id, "case_id": {"$in": case_ids}},
                    {"$set": {"updated_at": now}},
                    session=session,
                )
            fields = {**(set_fields or {}), "case_id": None, "updated_at": now}
            await _docs_coll(analytiq_client).update_many(
                {"_id": {"$in": batch}, "organization_id": organization_id},
                {"$set": fields},
                session=session,
            )

        await _run_in_transaction(analytiq_client, _run)


async def begin_case_delete(
    analytiq_client,
    organization_id: str,
    case_id: str,
    *,
    cascade_documents: bool,
) -> dict | None:
    """
    Mark a case as being deleted and return its row, or ``None`` if there is no case.

    A case already being deleted is returned as is, so an interrupted delete can be
    resumed by deleting again. Resuming with a different ``cascade_documents`` than
    the delete was started with raises ``LookupError("delete_mode_conflict")``.
    """
    case_id = validate_case_id(case_id)
    coll = _cases_coll(analytiq_client)
    now = datetime.now(UTC)
    row = await coll.find_one_and_update(
        {"organization_id": organization_id, "case_id": case_id, "deleting_at": None},
        {
            "$set": {
                "deleting_at": now,
                "delete_cascade": cascade_documents,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if row:
        return row

    row = await coll.find_one({"organization_id": organization_id, "case_id": case_id})
    if not row:
        return None
    if bool(row.get("delete_cascade")) != cascade_documents:
        raise LookupError("delete_mode_conflict")
    return row


async def finish_case_delete(
    analytiq_client,
    organization_id: str,
    case_id: str,
    *,
    cascade_documents: bool,
) -> None:
    """
    Clear or delete the case's documents, then delete the case row.

    Idempotent: every step re-queries what is left, so a crash or retry carries on
    where the previous run stopped. Call ``begin_case_delete`` first.
    """
    case_id = validate_case_id(case_id)
    docs = _docs_coll(analytiq_client)
    member_query = {"organization_id": organization_id, "case_id": case_id}

    if cascade_documents:
        previous_batch: list[ObjectId] = []
        while True:
            batch = [
                d["_id"]
                for d in await docs.find(member_query, {"_id": 1})
                .limit(CASCADE_DELETE_BATCH_SIZE)
                .to_list(CASCADE_DELETE_BATCH_SIZE)
            ]
            if not batch:
                break
            if batch == previous_batch:
                raise RuntimeError(
                    f"Cascade delete of case {organization_id}/{case_id} made no progress"
                )
            previous_batch = batch
            for doc_oid in batch:
                await ad.common.delete_doc(analytiq_client, str(doc_oid), organization_id)
    else:
        await docs.update_many(
            member_query,
            {"$set": {"case_id": None, "updated_at": datetime.now(UTC)}},
        )

    await _cases_coll(analytiq_client).delete_one(
        {"organization_id": organization_id, "case_id": case_id}
    )
    logger.info(
        f"Deleted case {organization_id}/{case_id} (cascade_documents={cascade_documents})"
    )


async def delete_case(
    analytiq_client,
    organization_id: str,
    case_id: str,
    *,
    cascade_documents: bool,
) -> bool:
    """Begin and finish a case delete in one call. Returns ``False`` if there is no case."""
    row = await begin_case_delete(
        analytiq_client, organization_id, case_id, cascade_documents=cascade_documents
    )
    if not row:
        return False
    await finish_case_delete(
        analytiq_client, organization_id, row["case_id"], cascade_documents=cascade_documents
    )
    return True
