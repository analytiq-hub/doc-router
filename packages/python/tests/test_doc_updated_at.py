"""Document ``updated_at`` on write paths used for case-run staleness."""

from datetime import datetime, UTC

import pytest
from bson import ObjectId

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@pytest.mark.asyncio
async def test_update_doc_state_sets_updated_at(test_db, mock_auth, setup_test_models):
    org_id = TEST_ORG_ID
    doc_id = ObjectId()
    before = datetime.now(UTC)
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": org_id,
            "user_file_name": "t.pdf",
            "state": ad.common.doc.DOCUMENT_STATE_UPLOADED,
            "tag_ids": [],
        }
    )
    aq = ad.common.get_analytiq_client()
    await ad.common.update_doc_state(aq, str(doc_id), ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED)
    row = await test_db.docs.find_one({"_id": doc_id})
    assert row["state"] == ad.common.doc.DOCUMENT_STATE_OCR_COMPLETED
    assert row.get("updated_at") is not None
    assert _utc(row["updated_at"]) >= before


@pytest.mark.asyncio
async def test_bump_doc_updated_at(test_db, mock_auth, setup_test_models):
    org_id = TEST_ORG_ID
    doc_id = ObjectId()
    old = datetime(2020, 1, 1, tzinfo=UTC)
    await test_db.docs.insert_one(
        {
            "_id": doc_id,
            "organization_id": org_id,
            "user_file_name": "t.pdf",
            "updated_at": old,
        }
    )
    aq = ad.common.get_analytiq_client()
    await ad.common.bump_doc_updated_at(aq, str(doc_id), org_id)
    row = await test_db.docs.find_one({"_id": doc_id})
    assert _utc(row["updated_at"]) > old
