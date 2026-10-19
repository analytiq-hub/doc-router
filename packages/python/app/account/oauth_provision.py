"""Create or link OAuth users (shared by HMAC NextAuth hook and browser OAuth callbacks)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import analytiq_data as ad
from analytiq_data.org_permissions import BUILTIN_ADMIN, build_member_entry, builtin_permission_groups_document
from app.routes.payments import sync_customer
from app.account.oauth_models import OAuthSignInRequest

logger = logging.getLogger(__name__)


async def provision_oauth_signin(oauth_request: OAuthSignInRequest) -> tuple[str, bool]:
    """
    Returns ``(user_id, is_new_user)``.
    """
    db = ad.common.get_async_db()
    existing_user = await db.users.find_one({"email": oauth_request.email})

    if existing_user:
        user_id = str(existing_user["_id"])
        is_new_user = False
        logger.info(f"Existing user found: {user_id}")

        existing_account = await db.accounts.find_one({
            "provider": oauth_request.provider,
            "providerAccountId": oauth_request.provider_account_id,
        })

        if not existing_account:
            await db.accounts.insert_one({
                "userId": user_id,
                "type": oauth_request.account.type,
                "provider": oauth_request.provider,
                "providerAccountId": oauth_request.provider_account_id,
                "access_token": oauth_request.account.access_token,
                "expires_at": oauth_request.account.expires_at,
                "token_type": oauth_request.account.token_type,
                "scope": oauth_request.account.scope,
                "id_token": oauth_request.account.id_token,
                "refresh_token": oauth_request.account.refresh_token,
            })
            logger.info(f"Linked {oauth_request.provider} account to existing user {user_id}")
        return user_id, is_new_user

    is_new_user = True
    user_result = await db.users.insert_one({
        "email": oauth_request.email,
        "name": oauth_request.name,
        "email_verified": oauth_request.email_verified,
        "created_at": datetime.now(UTC),
    })
    user_id = str(user_result.inserted_id)
    logger.info(f"Created new user: {user_id}")

    await db.accounts.insert_one({
        "userId": user_id,
        "type": oauth_request.account.type,
        "provider": oauth_request.provider,
        "providerAccountId": oauth_request.provider_account_id,
        "access_token": oauth_request.account.access_token,
        "expires_at": oauth_request.account.expires_at,
        "token_type": oauth_request.account.token_type,
        "scope": oauth_request.account.scope,
        "id_token": oauth_request.account.id_token,
        "refresh_token": oauth_request.account.refresh_token,
    })

    org_result = await db.organizations.insert_one({
        "name": oauth_request.email,
        "type": "individual",
        "permission_groups": builtin_permission_groups_document(),
        "members": [build_member_entry(user_id, permission_group_ids=[BUILTIN_ADMIN])],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    })
    org_id = str(org_result.inserted_id)
    logger.info(f"Created organization {org_id} for user {user_id}")

    try:
        await sync_customer(db=db, org_id=org_id)
    except Exception as e:
        logger.warning(f"Failed to sync organization {org_id} with Stripe: {e}")

    return user_id, is_new_user
