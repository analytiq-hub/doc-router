from fastapi import APIRouter, HTTPException, Depends, Body, BackgroundTasks, Query
from datetime import datetime, timedelta, UTC
from bson import ObjectId
import secrets
import os

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user, get_admin_user
from email_utils import get_verification_email_content, get_email_subject, get_invitation_email_content
from schemas import (
    CreateInvitationRequest,
    InvitationResponse,
    ListInvitationsResponse,
    AcceptInvitationRequest,
    User
)

account_email_router = APIRouter(
    prefix="/account/email",
    tags=["account/email"]
)

@account_email_router.post("/verification/send/{user_id}")
async def send_verification_email(
    user_id: str,
    current_user: User = Depends(get_admin_user)
):
    """Send verification email to user (admin only)"""

    db = get_async_db()
    analytiq_client = ad.get_analytiq_client()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.get("emailVerified"):
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate verification token
    token = secrets.token_urlsafe(32)
    # Ensure expiration time is stored with UTC timezone
    expires = (datetime.now(UTC) + timedelta(hours=24)).replace(tzinfo=UTC)
    
    # Store verification token
    await db.email_verifications.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "token": token,
                "expires": expires,
                "email": user["email"]
            }
        },
        upsert=True
    )
        
    # Update verification URL to use new path
    verification_url = f"{NEXTAUTH_URL}/auth/verify-email?token={token}"
    
    # Get email content from template
    html_content = get_verification_email_content(
        verification_url=verification_url,
        site_url=NEXTAUTH_URL,
        user_name=user.get("name")
    )

    # Send email using SES
    try:
        aws_client = ad.aws.get_aws_client(analytiq_client)
        ses_client = aws_client.session.client("ses", region_name=aws_client.region_name)

        ad.log.debug(f"SES_FROM_EMAIL: {SES_FROM_EMAIL}")
        ad.log.debug(f"ToAddresses: {user['email']}")
        ad.log.debug(f"Verification URL: {verification_url}")

        response = ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={
                'ToAddresses': [user["email"]]
            },
            Message={
                'Subject': {
                    'Data': get_email_subject("verification")
                },
                'Body': {
                    'Html': {
                        'Data': html_content
                    }
                }
            }
        )
        return {"message": "Verification email sent"}
    except Exception as e:
        ad.log.error(f"Failed to send email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@account_email_router.post("/verification/{token}")
async def verify_email(token: str, background_tasks: BackgroundTasks):
    """Verify email address using token"""
    ad.log.info(f"Verifying email with token: {token}")

    db = get_async_db()

    # Find verification record
    verification = await db.email_verifications.find_one({"token": token})
    if not verification:
        ad.log.info(f"No verification record found for token: {token}")
        raise HTTPException(status_code=400, detail="Invalid verification token")
        
    # Check if token expired
    # Convert stored expiration to UTC for comparison
    stored_expiry = verification["expires"].replace(tzinfo=UTC)
    if stored_expiry < datetime.now(UTC):
        ad.log.info(f"Verification token expired: {stored_expiry} < {datetime.now(UTC)}")
        raise HTTPException(status_code=400, detail="Verification token expired")
    
    # Update user's email verification status
    updated_user = await db.users.find_one_and_update(
        {"_id": ObjectId(verification["user_id"])},
        {"$set": {"emailVerified": True}},
        return_document=True
    )

    if not updated_user:
        ad.log.info(f"Failed to verify email for user {verification['user_id']}")
        raise HTTPException(status_code=404, detail="User not found")
    
    if updated_user.get("emailVerified"):
        return {"message": "Email already verified"}

    # Allow the user to re-verify their email for 1 minute
    ad.log.info(f"Scheduling deletion of verification record for token: {token}")
    async def delete_verification_later():
        await asyncio.sleep(60)  # Wait 60 seconds
        await db.email_verifications.delete_one({"token": token})
        ad.log.info(f"Deleted verification record for token: {token}")

    background_tasks.add_task(delete_verification_later)
    
    return {"message": "Email verified successfully"}

@account_email_router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    invitation: CreateInvitationRequest,
    current_user: User = Depends(get_admin_user)
):
    """Create a new invitation (admin only)"""
    db = get_async_db()
    analytiq_client = ad.get_analytiq_client()

    # Check if email already registered, if so, set user_exists to True
    existing_user = await db.users.find_one({"email": invitation.email})
    if existing_user:
        user_exists = True
    else:
        user_exists = False
    
    if user_exists:
        if invitation.organization_id:
            # Check if user is already in the organization
            org = await db.organizations.find_one({
                "_id": ObjectId(invitation.organization_id),
                "members.user_id": existing_user["_id"]
            })
            if org:
                raise HTTPException(status_code=400, detail="User is already a member of this organization")
        else:
            # User already exists, and this is not an org invitation
            raise HTTPException(status_code=400, detail="User already exists")

    if await db.users.find_one({"email": invitation.email}):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
        
    # If there's an existing pending invitation for the same organization, invalidate it
    query = {
        "email": invitation.email,
        "status": "pending",
        "expires": {"$gt": datetime.now(UTC)}
    }
    
    # Only add organization_id to query if it exists
    if invitation.organization_id:
        query["organization_id"] = invitation.organization_id
    else:
        # If this is not an org invitation, only invalidate other non-org invitations
        query["organization_id"] = {"$exists": False}

    await db.invitations.update_many(
        query,
        {"$set": {"status": "invalidated"}}
    )

    # Generate invitation token
    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=24)
    
    # Create invitation document
    invitation_doc = {
        "email": invitation.email,
        "token": token,
        "status": "pending",
        "expires": expires,
        "created_by": current_user.user_id,
        "created_at": datetime.now(UTC),
        "user_exists": user_exists
    }
    
    # Get organization name if this is an org invitation
    organization_name = None
    if invitation.organization_id:
        invitation_doc["organization_id"] = invitation.organization_id
        
        org = await db.organizations.find_one({"_id": ObjectId(invitation.organization_id)})
        if org:
            organization_name = org["name"]
    
    result = await db.invitations.insert_one(invitation_doc)
    invitation_doc["id"] = str(result.inserted_id)
    
    # Send invitation email
    invitation_url = f"{NEXTAUTH_URL}/auth/accept-invitation?token={token}"
    html_content = get_invitation_email_content(
        invitation_url=invitation_url,
        site_url=NEXTAUTH_URL,
        expires=expires,
        organization_name=organization_name
    )
    
    try:
        aws_client = ad.aws.get_aws_client(analytiq_client)
        ses_client = aws_client.session.client("ses", region_name=aws_client.region_name)
        
        response = ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={'ToAddresses': [invitation.email]},
            Message={
                'Subject': {
                    'Data': get_email_subject("invitation")
                },
                'Body': {
                    'Html': {
                        'Data': html_content
                    }
                }
            }
        )
        return InvitationResponse(**invitation_doc)
    except Exception as e:
        ad.log.error(f"Failed to send invitation email: {str(e)}")
        # Delete invitation if email fails
        await db.invitations.delete_one({"_id": result.inserted_id})
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send invitation email: {str(e)}"
        )

@account_email_router.get("/invitations", response_model=ListInvitationsResponse)
async def list_invitations(
    skip: int = Query(0),
    limit: int = Query(10),
    current_user: User = Depends(get_admin_user)
):
    """List all invitations (admin only)"""
    db = get_async_db()

    query = {}
    total_count = await db.invitations.count_documents(query)
    cursor = db.invitations.find(query).skip(skip).limit(limit)
    invitations = await cursor.to_list(None)
    
    return ListInvitationsResponse(
        invitations=[
            InvitationResponse(
                id=str(inv["_id"]),
                email=inv["email"],
                status=inv["status"],
                expires=inv["expires"],
                created_by=inv["created_by"],
                created_at=inv["created_at"],
                role=inv["role"],
                organization_id=inv.get("organization_id"),
                organization_role=inv.get("organization_role")
            )
            for inv in invitations
        ],
        total_count=total_count,
        skip=skip
    )

@account_email_router.get("/invitations/{token}", response_model=InvitationResponse)
async def get_invitation(token: str):
    """Get invitation details by token"""
    db = get_async_db()

    invitation = await db.invitations.find_one({
        "token": token,
        "status": "pending"
    })
    
    if not invitation:
        raise HTTPException(
            status_code=404,
            detail="Invalid or expired invitation"
        )
        
    # Ensure both datetimes are timezone-aware for comparison
    invitation_expires = invitation["expires"].replace(tzinfo=UTC)
    if invitation_expires < datetime.now(UTC):
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired"
        )

    # Check if user already exists
    user_exists = await db.users.find_one({"email": invitation["email"]}) is not None

    # Get organization name if this is an org invitation
    organization_name = None
    if invitation.get("organization_id"):
        org = await db.organizations.find_one({"_id": ObjectId(invitation["organization_id"])})
        if org:
            organization_name = org["name"]
    
    return InvitationResponse(
        id=str(invitation["_id"]),
        email=invitation["email"],
        status=invitation["status"],
        expires=invitation["expires"],
        created_by=invitation["created_by"],
        created_at=invitation["created_at"],
        organization_id=invitation.get("organization_id"),
        organization_name=organization_name,  # Add organization name
        user_exists=user_exists  # Add user existence status
    )

@account_email_router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    data: AcceptInvitationRequest = Body(...)  # Change to use AcceptInvitationRequest
):
    """Accept an invitation and create user account if needed"""
    ad.log.info(f"Accepting invitation with token: {token}")

    db = get_async_db()

    # Find and validate invitation
    invitation = await db.invitations.find_one({
        "token": token,
        "status": "pending"
    })
    
    if not invitation:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired invitation"
        )
        
    # Ensure both datetimes are timezone-aware for comparison
    invitation_expires = invitation["expires"].replace(tzinfo=UTC)
    if invitation_expires < datetime.now(UTC):
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=400,
            detail="Invitation has expired"
        )
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": invitation["email"]})
    
    if existing_user:
        user_id = str(existing_user["_id"])
        
        # If this is an organization invitation, add user to the organization
        if invitation.get("organization_id"):
            # Check if user is already in the organization
            org = await db.organizations.find_one({
                "_id": ObjectId(invitation["organization_id"]),
                "members.user_id": user_id
            })
            
            if org:
                raise HTTPException(
                    status_code=400,
                    detail="User is already a member of this organization"
                )
            
            # Add user to organization
            await db.organizations.update_one(
                {"_id": ObjectId(invitation["organization_id"])},
                {
                    "$push": {
                        "members": {
                            "user_id": user_id,
                            "role": "user"  # Default all invited users to regular member role
                        }
                    }
                }
            )
        
        # Mark invitation as accepted
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "accepted"}}
        )
        
        return {"message": "User added to organization successfully"}
    
    # Create new user account if they don't exist
    if not data.name or not data.password:
        raise HTTPException(
            status_code=400,
            detail="Name and password are required for new accounts"
        )

    hashed_password = hashpw(data.password.encode(), gensalt(12))
    user_doc = {
        "email": invitation["email"],
        "name": data.name,
        "password": hashed_password.decode(),
        "role": "user",  # Default all invited users to regular user role
        "emailVerified": True,  # Auto-verify since it's from invitation
        "createdAt": datetime.now(UTC)
    }
    
    try:
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        # If organization invitation, add to organization
        if invitation.get("organization_id"):
            await db.organizations.update_one(
                {"_id": ObjectId(invitation["organization_id"])},
                {
                    "$push": {
                        "members": {
                            "user_id": user_id,
                            "role": "user"  # Default all invited users to regular member role
                        }
                    }
                }
            )
        else:
            # Create default individual organization
            await db.organizations.insert_one({
                "_id": result.inserted_id,
                "name": invitation["email"],
                "members": [{
                    "user_id": user_id,
                    "role": "admin"  # User is admin of their individual org
                }],
                "type": "individual",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
        
        # Mark invitation as accepted
        await db.invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "accepted"}}
        )
        
        return {"message": "Account created successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create account: {str(e)}"
        )
