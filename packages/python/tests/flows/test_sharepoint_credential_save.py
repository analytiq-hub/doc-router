from __future__ import annotations

import analytiq_data as ad
from analytiq_data.flows.credential_fields import (
    apply_credential_kind_defaults,
    coerce_credential_fields,
    credential_validation_schema,
    normalize_credential_fields_for_kind,
)
from jsonschema import Draft7Validator


def test_sharepoint_credential_save_without_subdomain_passes_schema() -> None:
    """Saving without subdomain must not 422; OAuth connect validates scope separately."""

    kind = ad.flows.get_credential_kind("microsoftSharePointOAuth2Api")
    schema = credential_validation_schema(kind)
    assert schema is not None
    fields = apply_credential_kind_defaults(
        kind,
        {"clientId": "cid", "clientSecret": "sec"},
    )
    fields = normalize_credential_fields_for_kind(kind, fields)
    fields = coerce_credential_fields(schema, fields)
    Draft7Validator(schema).validate(fields)


def test_sharepoint_credential_normalizes_subdomain_hostname() -> None:
    kind = ad.flows.get_credential_kind("microsoftSharePointOAuth2Api")
    fields = normalize_credential_fields_for_kind(
        kind,
        {"subdomain": "https://contoso.sharepoint.com"},
    )
    assert fields["subdomain"] == "contoso"
