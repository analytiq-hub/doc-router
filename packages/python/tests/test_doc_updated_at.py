"""Document ``updated_at`` on write paths used for case-run staleness."""

import pytest
from bson import ObjectId

import analytiq_data as ad
from tests.conftest_utils import TEST_ORG_ID


@pytest.mark.asyncio
async def test_update_doc_state_sets_updated_at(test_db, mock_auth, setup_test_models):
    org_id = TEST_ORG_ID
    doc_id = ObjectId()
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
