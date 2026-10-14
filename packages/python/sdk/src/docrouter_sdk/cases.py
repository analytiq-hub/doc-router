import json
from typing import Any, Dict, List, Optional, Union

from .documents import encode_metadata_search
from .models.case import CaseOut, ListCasesResponse
from .models.case_llm import CaseLlmResultsResponse, CaseLlmRunStartResponse


class CasesAPI:
    def __init__(self, client):
        self.client = client

    def create(self, organization_id: str, body: Dict[str, Any]) -> CaseOut:
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/cases",
            json=body,
        )
        return CaseOut(**data)

    def list(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 50,
        case_id_search: Optional[str] = None,
        tag_ids: Optional[List[str]] = None,
        metadata_search: Optional[Dict[str, str]] = None,
        updated_after: Optional[str] = None,
        updated_before: Optional[str] = None,
        sort: Optional[Union[str, List[Dict[str, Any]]]] = None,
        filters: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> ListCasesResponse:
        """List cases. ``tag_ids`` and ``metadata_search`` take the same types as ``documents.list``."""
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if case_id_search:
            params["case_id_search"] = case_id_search
        if tag_ids:
            params["tag_ids"] = ",".join(tag_ids)
        if metadata_search:
            params["metadata_search"] = encode_metadata_search(metadata_search)
        if updated_after:
            params["updated_after"] = updated_after
        if updated_before:
            params["updated_before"] = updated_before
        if sort is not None:
            params["sort"] = sort if isinstance(sort, str) else json.dumps(sort)
        if filters is not None:
            params["filters"] = filters if isinstance(filters, str) else json.dumps(filters)
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/cases",
            params=params,
        )
        return ListCasesResponse(**data)

    def get(self, organization_id: str, case_id: str) -> CaseOut:
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/cases/{case_id}",
        )
        return CaseOut(**data)

    def update(self, organization_id: str, case_id: str, body: Dict[str, Any]) -> CaseOut:
        data = self.client.request(
            "PUT",
            f"/v0/orgs/{organization_id}/cases/{case_id}",
            json=body,
        )
        return CaseOut(**data)

    def delete(
        self, organization_id: str, case_id: str, *, cascade: bool = False
    ) -> Dict[str, str]:
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/cases/{case_id}",
            params={"cascade": cascade},
        )

    def assign_documents(
        self,
        organization_id: str,
        case_id: str,
        document_ids: List[str],
        create_case_if_missing: bool = False,
    ) -> Dict[str, Any]:
        return self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/cases/{case_id}/documents",
            json={
                "document_ids": document_ids,
                "create_case_if_missing": create_case_if_missing,
            },
        )

    def remove_document(
        self, organization_id: str, case_id: str, document_id: str
    ) -> Dict[str, str]:
        return self.client.request(
            "DELETE",
            f"/v0/orgs/{organization_id}/cases/{case_id}/documents/{document_id}",
        )

    def start_llm_run(
        self, organization_id: str, case_id: str, prompt_id: str
    ) -> CaseLlmRunStartResponse:
        """Queue a case-scoped LLM run (HTTP 202)."""
        data = self.client.request(
            "POST",
            f"/v0/orgs/{organization_id}/cases/{case_id}/runs",
            json={"prompt_id": prompt_id},
        )
        return CaseLlmRunStartResponse(**data)

    def get_llm_results(
        self, organization_id: str, case_id: str, prompt_id: str
    ) -> CaseLlmResultsResponse:
        data = self.client.request(
            "GET",
            f"/v0/orgs/{organization_id}/cases/{case_id}/results",
            params={"prompt_id": prompt_id},
        )
        return CaseLlmResultsResponse(**data)
