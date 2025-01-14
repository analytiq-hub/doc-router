from fastapi import APIRouter, HTTPException, Depends, Body
from datetime import datetime, timedelta, UTC
from bson import ObjectId
import secrets

import analytiq_data as ad
from setup import get_async_db
from auth import get_current_user
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

@account_email_router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    request: CreateInvitationRequest,
    current_user: User = Depends(get_current_user)
):
    """Create an invitation"""
    db = get_async_db()
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists"
        )
    
    # Check if there's a pending invitation
    existing_invitation = await db.invitations.find_one({
        "email": request.email,
        "status": "pending"
    })
    if existing_invitation:
        raise HTTPException(
            status_code=400,
            detail="Pending invitation already exists for this email"
        )
    
    # Create invitation
    token = secrets.token_urlsafe(32)
    invitation = {
        "email": request.email,
        "token": token,
        "status": "pending",
        "expires": datetime.now(UTC) + timedelta(days=7),
        "created_by": current_user.user_id,
        "created_at": datetime.now(UTC),
        "organization_id": request.organization_id
    }
    
    result = await db.invitations.insert_one(invitation)
    invitation["id"] = str(result.inserted_id)
    
    # Get organization name if this is an org invitation
    organization_name = None
    if request.organization_id:
        org = await db.organizations.find_one({"_id": ObjectId(request.organization_id)})
        if org:
            organization_name = org["name"]
    
    # Send invitation email
    subject = get_email_subject("invitation")
    content = get_invitation_email_content(token)
    # TODO: Send email using your email service
    
    return InvitationResponse(
        id=str(result.inserted_id),
        email=request.email,
        status="pending",
        expires=invitation["expires"],
        created_by=current_user.user_id,
        created_at=invitation["created_at"],
        organization_id=request.organization_id,
        organization_name=organization_name,
        user_exists=False
    )

@account_email_router.get("/invitations", response_model=ListInvitationsResponse)
async def list_invitations(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """List invitations"""
    db = get_async_db()
    
    # Get total count
    total_count = await db.invitations.count_documents({
        "created_by": current_user.user_id
    })
    
    # Get paginated invitations
    cursor = db.invitations.find({
        "created_by": current_user.user_id
    }).sort("_id", -1).skip(skip).limit(limit)
    
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
                organization_id=inv.get("organization_id")
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
        organization_name=organization_name,
        user_exists=user_exists
    )

@account_email_router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    data: AcceptInvitationRequest = Body(...)
):
    """Accept an invitation and create user account if needed"""
    db = get_async_db()
    
    ad.log.info(f"Accepting invitation with token: {token}")
    
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