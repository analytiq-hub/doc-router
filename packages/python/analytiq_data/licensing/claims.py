"""License claim models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

FEATURE_DOCUMENTS = "documents"
FEATURE_FLOWS = "flows"
KNOWN_FEATURES = frozenset({FEATURE_DOCUMENTS, FEATURE_FLOWS})

PRODUCT_NAME = "docrouter"
DEFAULT_GRACE_DAYS = 7


class LicenseLimits(BaseModel):
    """Quantitative caps (accepted in v1; not enforced yet)."""

    users: Optional[int] = None
    workspaces: Optional[int] = None

    model_config = {"extra": "allow"}


class LicenseDeployment(BaseModel):
    installation_id: Optional[str] = None

    model_config = {"extra": "allow"}


class LicenseClaims(BaseModel):
    license_id: str
    customer_id: str
    customer_name: str
    product: str = PRODUCT_NAME
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    grace_days: int = DEFAULT_GRACE_DAYS
    features: list[str] = Field(default_factory=list)
    limits: LicenseLimits = Field(default_factory=LicenseLimits)
    deployment: LicenseDeployment = Field(default_factory=LicenseDeployment)

    model_config = {"extra": "allow"}

    def recognized_features(self) -> list[str]:
        return sorted(f for f in self.features if f in KNOWN_FEATURES)

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def limits_dict(self) -> dict[str, Any]:
        data = self.limits.model_dump(exclude_none=True)
        return data
