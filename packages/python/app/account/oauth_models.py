from typing import Literal, Optional

from pydantic import BaseModel, Field


class OAuthAccountData(BaseModel):
    type: str = "oauth"
    access_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None


class OAuthSignInRequest(BaseModel):
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User's full name")
    email_verified: bool = Field(False, description="Whether email is verified")
    provider: Literal["google", "github"] = Field(..., description="OAuth provider")
    provider_account_id: str = Field(..., description="Provider's unique account ID")
    account: OAuthAccountData = Field(..., description="OAuth account data")
