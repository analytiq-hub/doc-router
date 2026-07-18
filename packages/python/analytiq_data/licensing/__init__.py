"""Product licensing: Ed25519-signed offline keys."""

from .claims import (
    FEATURE_DOCUMENTS,
    FEATURE_FLOWS,
    KNOWN_FEATURES,
    LicenseClaims,
    LicenseLimits,
    LicenseDeployment,
)
from .service import (
    LicenseStatus,
    evaluate_license_key,
    get_cached_status,
    get_verified_claims,
    invalidate_license_cache,
    put_license_key,
    refresh_license_state,
    start_license_checker,
    stop_license_checker,
)
from .store import (
    LICENSE_DOC_ID,
    ensure_installation_id,
    get_license_document,
    bootstrap_license_if_needed,
    clear_license_checked_at,
)
from .verifier import (
    LicenseVerifyError,
    load_public_key,
    verify_license_token,
)

__all__ = [
    "FEATURE_DOCUMENTS",
    "FEATURE_FLOWS",
    "KNOWN_FEATURES",
    "LICENSE_DOC_ID",
    "LicenseClaims",
    "LicenseDeployment",
    "LicenseLimits",
    "LicenseStatus",
    "LicenseVerifyError",
    "bootstrap_license_if_needed",
    "clear_license_checked_at",
    "ensure_installation_id",
    "evaluate_license_key",
    "get_cached_status",
    "get_license_document",
    "get_verified_claims",
    "invalidate_license_cache",
    "load_public_key",
    "put_license_key",
    "refresh_license_state",
    "start_license_checker",
    "stop_license_checker",
    "verify_license_token",
]
