"""Unit tests for CasesAPI and document case_id helpers (mocked HTTP)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from docrouter_sdk.cases import CasesAPI
from docrouter_sdk.documents import DocumentsAPI
from docrouter_sdk.models.case import CaseOut, ListCasesResponse


ORG = "org-123"
NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _case_payload(case_id: str = "CLM-1") -> dict:
    return {
        "case_id": case_id,
        "display_name": case_id,
        "tag_ids": [],
        "metadata": {},
        "document_count": 0,
        "created_by": "user-1",
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cases_api(mock_client):
    return CasesAPI(mock_client)


@pytest.fixture
def documents_api(mock_client):
    return DocumentsAPI(mock_client)


class TestCasesAPI:
    def test_create_posts_json(self, cases_api, mock_client):
        mock_client.request.return_value = _case_payload()
        out = cases_api.create(ORG, {"case_id": "CLM-1", "display_name": "Claim"})
        mock_client.request.assert_called_once_with(
            "POST",
            f"/v0/orgs/{ORG}/cases",
            json={"case_id": "CLM-1", "display_name": "Claim"},
        )
        assert isinstance(out, CaseOut)
        assert out.case_id == "CLM-1"

    def test_list_passes_search_params(self, cases_api, mock_client):
        mock_client.request.return_value = {"cases": [], "total_count": 0, "skip": 0}
        cases_api.list(
            ORG,
            skip=10,
            limit=25,
            case_id_search="CLM",
            tag_ids=["t1", "t2"],
            metadata_search={"k": "v w"},
        )
        mock_client.request.assert_called_once_with(
            "GET",
            f"/v0/orgs/{ORG}/cases",
            params={
                "skip": 10,
                "limit": 25,
                "case_id_search": "CLM",
                "tag_ids": "t1,t2",
                "metadata_search": "k=v%20w",
            },
        )
        assert isinstance(ListCasesResponse(**mock_client.request.return_value), ListCasesResponse)

    def test_list_passes_grid_and_updated_range_params(self, cases_api, mock_client):
        mock_client.request.return_value = {"cases": [], "total_count": 0, "skip": 0}
        sort = [{"field": "updated_at", "sort": "desc"}]
        filters = {"items": [], "logicOperator": "and"}
        cases_api.list(
            ORG,
            updated_after="2026-01-01T00:00:00Z",
            updated_before="2026-12-31T23:59:59Z",
            sort=sort,
            filters=filters,
        )
        mock_client.request.assert_called_once_with(
            "GET",
            f"/v0/orgs/{ORG}/cases",
            params={
                "skip": 0,
                "limit": 50,
                "updated_after": "2026-01-01T00:00:00Z",
                "updated_before": "2026-12-31T23:59:59Z",
                "sort": '[{"field": "updated_at", "sort": "desc"}]',
                "filters": '{"items": [], "logicOperator": "and"}',
            },
        )

    def test_get_case_path(self, cases_api, mock_client):
        mock_client.request.return_value = _case_payload("A:B")
        cases_api.get(ORG, "A:B")
        mock_client.request.assert_called_once_with(
            "GET",
            f"/v0/orgs/{ORG}/cases/A:B",
        )

    def test_update_puts_body(self, cases_api, mock_client):
        mock_client.request.return_value = _case_payload()
        cases_api.update(ORG, "CLM-1", {"display_name": "New name"})
        mock_client.request.assert_called_once_with(
            "PUT",
            f"/v0/orgs/{ORG}/cases/CLM-1",
            json={"display_name": "New name"},
        )

    def test_delete_cascade_param(self, cases_api, mock_client):
        mock_client.request.return_value = {"message": "Case delete started"}
        cases_api.delete(ORG, "CLM-1", cascade=True)
        mock_client.request.assert_called_once_with(
            "DELETE",
            f"/v0/orgs/{ORG}/cases/CLM-1",
            params={"cascade": True},
        )

    def test_assign_documents(self, cases_api, mock_client):
        mock_client.request.return_value = {"message": "ok", "count": 2}
        cases_api.assign_documents(
            ORG, "CLM-1", ["d1", "d2"], create_case_if_missing=True
        )
        mock_client.request.assert_called_once_with(
            "POST",
            f"/v0/orgs/{ORG}/cases/CLM-1/documents",
            json={
                "document_ids": ["d1", "d2"],
                "create_case_if_missing": True,
            },
        )

    def test_remove_document(self, cases_api, mock_client):
        mock_client.request.return_value = {"message": "ok"}
        cases_api.remove_document(ORG, "CLM-1", "doc-9")
        mock_client.request.assert_called_once_with(
            "DELETE",
            f"/v0/orgs/{ORG}/cases/CLM-1/documents/doc-9",
        )


class TestDocumentsAPICaseFields:
    def test_list_includes_case_id_param(self, documents_api, mock_client):
        mock_client.request.return_value = {"documents": [], "total_count": 0, "skip": 0}
        documents_api.list(ORG, case_id="CLM-99")
        mock_client.request.assert_called_once_with(
            "GET",
            f"/v0/orgs/{ORG}/documents",
            params={"skip": 0, "limit": 10, "case_id": "CLM-99"},
        )

    def test_update_sends_case_id_and_create_flag(self, documents_api, mock_client):
        mock_client.request.return_value = {"message": "ok"}
        documents_api.update(
            ORG,
            "doc-1",
            case_id=None,
            create_case_if_missing=True,
        )
        mock_client.request.assert_called_once_with(
            "PUT",
            f"/v0/orgs/{ORG}/documents/doc-1",
            json={"case_id": None, "create_case_if_missing": True},
        )

    def test_upload_passes_through_json_documents(self, documents_api, mock_client):
        mock_client.request.return_value = {"documents": []}
        payload = [
            {
                "name": "f.pdf",
                "content": "abc",
                "case_id": "CLM-1",
                "create_case_if_missing": False,
            }
        ]
        documents_api.upload(ORG, payload)
        mock_client.request.assert_called_once_with(
            "POST",
            f"/v0/orgs/{ORG}/documents",
            json={"documents": payload},
        )


def test_document_update_dump_leaves_out_unset_fields():
    from docrouter_sdk.models import DocumentUpdate

    assert DocumentUpdate(tag_ids=["t1"]).model_dump() == {"tag_ids": ["t1"]}
    assert DocumentUpdate(case_id=None).model_dump() == {"case_id": None}
    assert DocumentUpdate(tag_ids=["t1"]).model_dump(exclude_unset=False)["case_id"] is None


def test_case_models_exported():
    from docrouter_sdk.models import CaseCreate, CaseUpdate, CaseOut, ListCasesResponse  # noqa: F401
