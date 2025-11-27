# forms.py

# Standard library imports
import json
import logging
from datetime import datetime, UTC
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from bson import ObjectId

# Local imports
import analytiq_data as ad
from app.auth import get_org_user
from app.models import User

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
forms_router = APIRouter(tags=["forms"])

# Form models
class FormResponseFormat(BaseModel):
    json_formio: Optional[List[dict]] = Field(  # Changed from Optional[dict] to Optional[List[dict]]
        default=None,
        description="Form.io schema definition"
    )
    json_formio_mapping: Optional[Dict[str, dict]] = Field(
        default=None,
        description="Mapping of form fields to data extraction targets"
    )
    
    @field_validator('json_formio')
    def validate_json_formio(cls, v):
        if v is not None and not isinstance(v, list):
            raise ValueError("json_formio must be a list of form components")
        return v
    
    @field_validator('json_formio_mapping')
    def validate_json_formio_mapping(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("json_formio_mapping must be a dictionary")
        return v

class FormConfig(BaseModel):
    name: str
    response_format: FormResponseFormat
    tag_ids: List[str] = []  # Add tag_ids field with default empty list

class Form(FormConfig):
    form_revid: str # MongoDB's _id
    form_id: str    # Stable identifier
    form_version: int
    created_at: datetime
    created_by: str

class ListFormsResponse(BaseModel):
    forms: List[Form]
    total_count: int
    skip: int

# Form submission models
class FormSubmissionData(BaseModel):
    form_revid: str
    submission_data: dict
    submitted_by: Optional[str] = None

class FormSubmission(FormSubmissionData):
    id: str  # MongoDB _id converted to string
    organization_id: str
    created_at: datetime
    updated_at: datetime

# Helper functions
async def get_form_id_and_version(form_id: Optional[str] = None) -> tuple[str, int]:
    """
    Get the next version for an existing form or create a new form identifier.
    
    Args:
        form_id: Existing form ID, or None to create a new one
        
    Returns:
        Tuple of (form_id, form_version)
    """
    db = ad.common.get_async_db()

    if form_id is None:
        # Insert a placeholder document to get MongoDB-generated ID
        result = await db.forms.insert_one({
            "form_version": 1
        })
        
        # Use the MongoDB-assigned _id as our form_id
        form_id = str(result.inserted_id)
        form_version = 1
    else:
        # Get the next version for an existing form
        result = await db.forms.find_one_and_update(
            {"_id": ObjectId(form_id)},
            {"$inc": {"form_version": 1}},
            upsert=True,
            return_document=True
        )
        form_version = result["form_version"]
    
    return form_id, form_version

# Form management endpoints
@forms_router.post("/v0/orgs/{organization_id}/forms", response_model=Form)
async def create_form(
    organization_id: str,
    form: FormConfig,
    current_user: User = Depends(get_org_user)
):
    """Create a form"""
    logger.info(f"create_form() start: organization_id: {organization_id}, form: {form}")
    db = ad.common.get_async_db()

    # Check if form with this name already exists (case-insensitive)
    existing_form = await db.forms.find_one({
        "name": {"$regex": f"^{form.name}$", "$options": "i"},
        "organization_id": organization_id
    })

    # Generate form_id and version
    if existing_form:
        form_id, new_form_version = await get_form_id_and_version(str(existing_form["_id"]))
    else:
        # Generate a new form_id when creating a new form
        form_id, new_form_version = await get_form_id_and_version(None)
    
    # Update the forms collection with name and organization_id
    await db.forms.update_one(
        {"_id": ObjectId(form_id)},
        {"$set": {
            "name": form.name,
            "organization_id": organization_id,
        }},
        upsert=True
    )
    
    # Create form document for form_revisions
    form_dict = {
        "form_id": form_id,
        "response_format": form.response_format.model_dump(),
        "form_version": new_form_version,
        "tag_ids": form.tag_ids,
        "created_at": datetime.now(UTC),
        "created_by": current_user.user_id
    }
    
    # Insert into MongoDB
    result = await db.form_revisions.insert_one(form_dict)
    
    # Return complete form
    form_dict["name"] = form.name
    form_dict["form_revid"] = str(result.inserted_id)
    return Form(**form_dict)

@forms_router.get("/v0/orgs/{organization_id}/forms", response_model=ListFormsResponse)
async def list_forms(
    organization_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    tag_ids: str = Query(None, description="Comma-separated list of tag IDs to filter by"),
    current_user: User = Depends(get_org_user)
):
    """List latest form revisions within an organization, optionally filtered by tags"""
    logger.info(f"list_forms() start: organization_id: {organization_id}, skip: {skip}, limit: {limit}, tag_ids: {tag_ids}")
    db = ad.common.get_async_db()
    
    # Parse tag IDs if provided
    filter_tag_ids = []
    if tag_ids:
        filter_tag_ids = [tag_id.strip() for tag_id in tag_ids.split(',') if tag_id.strip()]
    
    # Get all forms that belong to the organization
    org_forms = await db.forms.find({"organization_id": organization_id}).to_list(None)
    
    if not org_forms:
        return ListFormsResponse(forms=[], total_count=0, skip=skip)

    logger.info(f"list_forms() org_forms: {org_forms}")
    
    # Extract form IDs
    form_ids = [form["_id"] for form in org_forms]
    form_id_to_name = {str(form["_id"]): form["name"] for form in org_forms}
    
    # Build pipeline for form_revisions with tag filtering
    pipeline = [
        {
            "$match": {"form_id": {"$in": [str(fid) for fid in form_ids]}}
        }
    ]
    
    # Add tag filtering if tag_ids are provided
    if filter_tag_ids:
        pipeline.append({
            "$match": {"tag_ids": {"$in": filter_tag_ids}}
        })
    
    # Continue with the rest of the pipeline
    pipeline.extend([
        {
            "$sort": {"_id": -1}
        },
        {
            "$group": {
                "_id": "$form_id",
                "doc": {"$first": "$$ROOT"}
            }
        },
        {
            "$replaceRoot": {"newRoot": "$doc"}
        },
        {
            "$sort": {"_id": -1}
        },
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "forms": [
                    {"$skip": skip},
                    {"$limit": limit}
                ]
            }
        }
    ])
    
    result = await db.form_revisions.aggregate(pipeline).to_list(length=1)
    result = result[0]
    
    total_count = result["total"][0]["count"] if result["total"] else 0
    forms = result["forms"]
    
    # Convert _id to id in each form and add name from forms collection
    for form in forms:
        form['form_revid'] = str(form.pop('_id'))
        form['name'] = form_id_to_name.get(form['form_id'], "Unknown")
    
    return ListFormsResponse(
        forms=forms,
        total_count=total_count,
        skip=skip
    )

@forms_router.get("/v0/orgs/{organization_id}/forms/{form_revid}", response_model=Form)
async def get_form(
    organization_id: str,
    form_revid: str,
    current_user: User = Depends(get_org_user)
):
    """Get a form revision"""
    logger.info(f"get_form() start: organization_id: {organization_id}, form_revid: {form_revid}")
    db = ad.common.get_async_db()
    
    # Get the form revision
    revision = await db.form_revisions.find_one({"_id": ObjectId(form_revid)})
    if not revision:
        raise HTTPException(status_code=404, detail="Form revision not found")
    
    # Get the form name and verify organization
    form = await db.forms.find_one({
        "_id": ObjectId(revision["form_id"]),
        "organization_id": organization_id
    })
    if not form:
        raise HTTPException(status_code=404, detail="Form not found or not in this organization")
    
    # Transform the data to match Form model
    form_data = {
        "name": form["name"],
        "response_format": revision["response_format"],
        "form_revid": str(revision['_id']),
        "form_id": revision["form_id"],
        "form_version": revision["form_version"],
        "tag_ids": revision["tag_ids"],
        "created_at": revision["created_at"],
        "created_by": revision["created_by"],
    }
    
    return Form(**form_data)

@forms_router.put("/v0/orgs/{organization_id}/forms/{form_id}", response_model=Form)
async def update_form(
    organization_id: str,
    form_id: str,
    form: FormConfig,
    current_user: User = Depends(get_org_user)
):
    """Update an existing form"""
    logger.info(f"update_form() start: organization_id: {organization_id}, form_id: {form_id}")
    db = ad.common.get_async_db()

    # Get the existing form and latest revision
    existing_form = await db.forms.find_one({"_id": ObjectId(form_id), "organization_id": organization_id})
    if not existing_form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    latest_revision = await db.form_revisions.find_one(
        {"form_id": form_id},
        sort=[("form_version", -1)]
    )

    logger.info(f"update_form() latest_revision: {latest_revision}")
    
    if not latest_revision:
        raise HTTPException(status_code=404, detail="Form not found")
    
    # Check if response_format or tag_ids has actually changed
    current_response_format = latest_revision.get("response_format", {})
    new_response_format = form.response_format.model_dump()
    
    response_format_changed = current_response_format != new_response_format
    tag_ids_changed = set(latest_revision.get("tag_ids", [])) != set(form.tag_ids)

    logger.info(f"update_form() response_format_changed: {response_format_changed}")
    logger.info(f"update_form() name: {form.name}")
    logger.info(f"update_form() tag_ids: {form.tag_ids}")
    
    # Update the form metadata in the forms collection
    await db.forms.update_one(
        {"_id": ObjectId(form_id)},
        {"$set": {
            "name": form.name,
        }},
        upsert=True
    )
    
    # Only create a new revision if the response_format has changed
    if response_format_changed or tag_ids_changed:
        new_form_version = latest_revision["form_version"] + 1
        
        # Create new form revision
        new_revision = {
            "form_id": form_id,
            "response_format": new_response_format,
            "tag_ids": form.tag_ids,
            "form_version": new_form_version,
            "created_at": datetime.now(UTC),
            "created_by": current_user.user_id
        }
        
        # Insert new revision
        result = await db.form_revisions.insert_one(new_revision)

        logger.info(f"update_form() new revision: {new_revision}")
        
        # Return updated form with new revision
        return Form(
            form_revid=str(result.inserted_id),
            form_id=new_revision["form_id"],
            form_version=new_revision["form_version"],
            name=form.name,
            response_format=new_revision["response_format"],
            tag_ids=new_revision["tag_ids"],
            created_at=new_revision["created_at"],
            created_by=new_revision["created_by"],
        )
    else:
        logger.info(f"update_form() no revision change")

        # No revision change, just return the existing form with updated metadata
        return Form(
            form_revid=str(latest_revision["_id"]),
            form_id=form_id,
            name=form.name,
            response_format=form.response_format,
            form_version=latest_revision["form_version"],
            tag_ids=latest_revision["tag_ids"],
            created_at=latest_revision["created_at"],
            created_by=latest_revision["created_by"],
        )

@forms_router.delete("/v0/orgs/{organization_id}/forms/{form_id}")
async def delete_form(
    organization_id: str,
    form_id: str,
    current_user: User = Depends(get_org_user)
):
    """Delete a form"""
    logger.info(f"delete_form() start: organization_id: {organization_id}, form_id: {form_id}")

    db = ad.common.get_async_db()
    
    # Get the form and verify organization
    form = await db.forms.find_one({
        "_id": ObjectId(form_id),
        "organization_id": organization_id
    })
    if not form:
        raise HTTPException(status_code=404, detail="Form not found or not in this organization")

    # Check for dependent prompts by form_id
    dependent_prompts = await db.prompt_revisions.find({
        "form_id": form_id
    }).to_list(None)
    
    if dependent_prompts:
        # Get names from prompts collection
        prompt_names = {}
        for prompt_revision in dependent_prompts:
            prompt = await db.prompts.find_one({"_id": ObjectId(prompt_revision["prompt_id"])})
            if prompt:
                prompt_names[str(prompt_revision["_id"])] = prompt["name"]
        
        # Format the list of dependent prompts
        prompt_list = [
            {
                "name": prompt_names.get(str(p["_id"]), "Unknown"), 
                "form_version": p["form_version"]
            } 
            for p in dependent_prompts
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete form because it has dependent prompts:{json.dumps(prompt_list)}"
        )
    
    # If no dependent prompts, proceed with deletion
    result = await db.form_revisions.delete_many({
        "form_id": form_id
    })
    
    # Delete the form entry
    await db.forms.delete_one({"_id": ObjectId(form_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No form revisions found")
        
    return {"message": "Form deleted successfully"}

# Form submission endpoints
@forms_router.post("/v0/orgs/{organization_id}/forms/submissions/{document_id}", response_model=FormSubmission)
async def submit_form(
    organization_id: str,
    document_id: str,
    submission: FormSubmissionData,
    current_user: User = Depends(get_org_user)
):
    """Submit a form for a specific document - updates existing submission if found"""
    logger.info(f"submit_form() start: organization_id: {organization_id}, document_id: {document_id}, form_revid: {submission.form_revid}")
    db = ad.common.get_async_db()
    
    # Verify the form revision exists
    form_revision = await db.form_revisions.find_one({"_id": ObjectId(submission.form_revid)})
    if not form_revision:
        raise HTTPException(status_code=404, detail="Form revision not found")
    
    # Verify the form belongs to the organization
    form = await db.forms.find_one({
        "_id": ObjectId(form_revision["form_id"]),
        "organization_id": organization_id
    })
    if not form:
        raise HTTPException(status_code=404, detail="Form not found or not in this organization")

    # Verify the document exists and belongs to the organization
    document = await db.docs.find_one({
        "_id": ObjectId(document_id),
        "organization_id": organization_id
    })
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or not in this organization")
    
    # Check if a submission already exists for this form/document combination
    existing_submission = await db.form_submissions.find_one({
        "form_revid": submission.form_revid,
        "document_id": document_id,
        "organization_id": organization_id
    })
    
    now = datetime.now(UTC)
    
    if existing_submission:
        # Update existing submission
        update_data = {
            "submission_data": submission.submission_data,
            "submitted_by": submission.submitted_by or current_user.user_id,
            "updated_at": now
        }
        
        await db.form_submissions.update_one(
            {"_id": existing_submission["_id"]},
            {"$set": update_data}
        )
        
        # Return updated submission
        updated_submission = await db.form_submissions.find_one({"_id": existing_submission["_id"]})
        updated_submission["id"] = str(updated_submission.pop('_id'))
        return FormSubmission(**updated_submission)
    else:
        # Create new submission
        submission_doc = {
            "form_revid": submission.form_revid,
            "document_id": document_id,
            "organization_id": organization_id,
            "submission_data": submission.submission_data,
            "submitted_by": submission.submitted_by or current_user.user_id,
            "created_at": now,
            "updated_at": now
        }
        
        result = await db.form_submissions.insert_one(submission_doc)
        
        # Return the created submission
        submission_doc["id"] = str(result.inserted_id)
        return FormSubmission(**submission_doc)

@forms_router.get("/v0/orgs/{organization_id}/forms/submissions/{document_id}", response_model=Optional[FormSubmission])
async def get_form_submission(
    organization_id: str,
    document_id: str,
    form_revid: str = Query(..., description="The form revision ID"),
    current_user: User = Depends(get_org_user)
):
    """Get the form submission for a specific document and form combination"""
    logger.info(f"get_form_submission() start: organization_id: {organization_id}, document_id: {document_id}, form_revid: {form_revid}")
    db = ad.common.get_async_db()
    
    submission = await db.form_submissions.find_one({
        "document_id": document_id,
        "form_revid": form_revid,
        "organization_id": organization_id
    })
    
    if submission:
        submission["id"] = str(submission.pop('_id'))
        return FormSubmission(**submission)
    
    return None

@forms_router.delete("/v0/orgs/{organization_id}/forms/submissions/{document_id}")
async def delete_form_submission(
    organization_id: str,
    document_id: str,
    form_revid: str = Query(..., description="The form revision ID"),
    current_user: User = Depends(get_org_user)
):
    """Delete a form submission"""
    logger.info(f"delete_form_submission() start: organization_id: {organization_id}, document_id: {document_id}, form_revid: {form_revid}")
    db = ad.common.get_async_db()
    
    result = await db.form_submissions.delete_one({
        "document_id": document_id,
        "form_revid": form_revid,
        "organization_id": organization_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Form submission not found")
    
    return {"message": "Form submission deleted successfully"}
