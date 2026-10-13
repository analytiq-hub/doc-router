from typing import Any, Dict, List, Optional

from .models.case import CaseOut, ListCasesResponse


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
        tag_ids: Optional[str] = None,
        metadata_search: Optional[str] = None,
    ) -> ListCasesResponse:
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if case_id_search:
            params["case_id_search"] = case_id_search
        if tag_ids:
            params["tag_ids"] = tag_ids
        if metadata_search:
            params["metadata_search"] = metadata_search
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
