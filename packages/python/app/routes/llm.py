# llm.py

# Standard library imports
import json
import logging
from datetime import datetime, UTC
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response
from bson import ObjectId

# Local imports
import analytiq_data as ad
from app.auth import get_org_user, get_current_user, get_admin_user
from app.models import User
from app.routes.payments import SPUCreditException

# Configure logger
logger = logging.getLogger(__name__)

# Initialize FastAPI router
llm_router = APIRouter(tags=["llm"])

# LLM models
class LLMModel(BaseModel):
    litellm_model: str
    litellm_provider: str
    max_input_tokens: int
    max_output_tokens: int
    input_cost_per_token: float
    output_cost_per_token: float

class ListLLMModelsResponse(BaseModel):
    models: List[LLMModel]

class LLMToken(BaseModel):
    id: str
    user_id: str
    llm_vendor: Literal["OpenAI", "Anthropic", "Gemini", "Groq", "Mistral", "xAI"]
    token: str
    created_at: datetime

class LLMProvider(BaseModel):
    name: str
    display_name: str
    litellm_provider: str
    litellm_models_available: List[str]
    litellm_models_enabled: List[str]
    enabled: bool = False
    token: str | None = None
    token_created_at: datetime | None = None

class ListLLMProvidersResponse(BaseModel):
    providers: List[LLMProvider]

class SetLLMProviderConfigRequest(BaseModel):
    litellm_models_enabled: List[str] | None = None
    enabled: bool | None = None
    token: str | None = None

class LLMRunResponse(BaseModel):
    status: str
    result: dict

class LLMResult(BaseModel):
    prompt_revid: str
    prompt_id: str
    prompt_version: int
    document_id: str
    llm_result: dict
    updated_llm_result: dict
    is_edited: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

class UpdateLLMResultRequest(BaseModel):
    updated_llm_result: dict
    is_verified: bool = False

class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Content of the message")

class LLMPromptRequest(BaseModel):
    model: str = Field(..., description="The LLM model to use (e.g., 'gpt-4o-mini')")
    messages: List[LLMMessage] = Field(..., description="Array of messages for the conversation")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, description="Sampling temperature (0.0 to 2.0)")
    stream: Optional[bool] = Field(default=False, description="Whether to stream the response")

class LLMStreamResponse(BaseModel):
    chunk: str
    done: bool = False

# Organization-level LLM routes
@llm_router.post("/v0/orgs/{organization_id}/llm/run/{document_id}", response_model=LLMRunResponse)
async def run_llm_analysis(
    organization_id: str,
    document_id: str,
    prompt_revid: str = Query(default="default", description="The prompt revision ID to use"),
    force: bool = Query(default=False, description="Force new run even if result exists"),
    current_user: User = Depends(get_org_user)
):
    """
    Run LLM on a document, with optional force refresh.
    """
    logger.info(f"run_llm_analysis(): doc_id/prompt_revid {document_id}/{prompt_revid}, force: {force}")
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify OCR is complete only if the document requires OCR
    file_name = document.get("user_file_name", "")
    if ad.common.doc.ocr_supported(file_name):
        ocr_metadata = await ad.common.get_ocr_metadata(analytiq_client, document_id)
        if ocr_metadata is None:
            raise HTTPException(status_code=404, detail="OCR metadata not found")

    try:
        result = await ad.llm.run_llm(
            analytiq_client,
            document_id=document_id,
            prompt_revid=prompt_revid,
            force=force
        )
        
        # Update state to LLM completed
        await ad.common.doc.update_doc_state(analytiq_client, document_id, ad.common.doc.DOCUMENT_STATE_LLM_COMPLETED)
        
        return LLMRunResponse(
            status="success",
            result=result
        )
        
    except SPUCreditException as e:
        logger.warning(f"{document_id}/{prompt_revid}: SPU credit exhausted in LLM run: {str(e)}")
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient SPU credits: {str(e)}"
        )
    except Exception as e:
        logger.error(f"{document_id}/{prompt_revid}: Error in LLM run: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )

@llm_router.post("/v0/orgs/{organization_id}/llm/run")
async def run_llm_chat_org(
    organization_id: str,
    request: LLMPromptRequest,
    current_user: User = Depends(get_admin_user)
):
    """
    Test LLM with arbitrary prompt (admin or org admin) - Organization level.
    Supports both streaming and non-streaming responses.
    """
    return await ad.llm.run_llm_chat(request, current_user)

@llm_router.get("/v0/orgs/{organization_id}/llm/result/{document_id}", response_model=LLMResult)
async def get_llm_result(
    organization_id: str,
    document_id: str,
    prompt_revid: str = Query(default="default", description="The prompt revision ID to retrieve"),
    fallback: bool = Query(default=False, description="Whether to fallback to the most recent available prompt revision result"),
    current_user: User = Depends(get_org_user)
):
    """
    Retrieve existing LLM results for a document.
    """
    logger.debug(f"get_llm_result() start: document_id: {document_id}, prompt_revid: {prompt_revid}")
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    llm_result = await ad.llm.get_llm_result(analytiq_client, document_id, prompt_revid, fallback)
    if not llm_result:
        raise HTTPException(
            status_code=404,
            detail=f"LLM result not found for document_id: {document_id} prompt_revid: {prompt_revid} fallback: {fallback}"
        )
    
    return llm_result

@llm_router.put("/v0/orgs/{organization_id}/llm/result/{document_id}", response_model=LLMResult)
async def update_llm_result(
    organization_id: str,
    document_id: str,
    prompt_revid: str = Query(..., description="The prompt revision ID to update"),
    update: UpdateLLMResultRequest = Body(..., description="The update request"),
    current_user: User = Depends(get_org_user)
):
    """
    Update LLM results with user edits and verification status.
    """
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        await ad.llm.update_llm_result(
            analytiq_client,
            document_id=document_id,
            prompt_revid=prompt_revid,
            updated_llm_result=update.updated_llm_result,
            is_verified=update.is_verified
        )
        
        return await ad.llm.get_llm_result(analytiq_client, document_id, prompt_revid)
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating LLM result: {str(e)}"
        )

@llm_router.delete("/v0/orgs/{organization_id}/llm/result/{document_id}")
async def delete_llm_result(
    organization_id: str,
    document_id: str,
    prompt_revid: str = Query(..., description="The prompt revision ID to delete"),
    current_user: User = Depends(get_org_user)
):
    """
    Delete LLM results for a specific document and prompt.
    """
    logger.debug(f"delete_llm_result() start: document_id: {document_id}, prompt_revid: {prompt_revid}")
    analytiq_client = ad.common.get_analytiq_client()
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    deleted = await ad.llm.delete_llm_result(analytiq_client, document_id, prompt_revid)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"LLM result not found for document_id: {document_id} and prompt_revid: {prompt_revid}"
        )
    
    return {"status": "success", "message": "LLM result deleted"}

@llm_router.get("/v0/orgs/{organization_id}/llm/results/{document_id}/download")
async def download_all_llm_results(
    organization_id: str,
    document_id: str,
    current_user: User = Depends(get_org_user)
):
    """
    Download all LLM results for a document as a JSON file.
    """
    logger.debug(f"download_all_llm_results() start: document_id: {document_id}")
    analytiq_client = ad.common.get_analytiq_client()
    
    # Verify document exists and user has access
    document = await ad.common.get_doc(analytiq_client, document_id, organization_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all LLM results for this document
    db = ad.common.get_async_db(analytiq_client)
    llm_results = await db.llm_runs.find({
        "document_id": document_id
    }).to_list(None)
    
    if not llm_results:
        raise HTTPException(
            status_code=404,
            detail="No LLM results found for this document"
        )
    
    # Get prompts information for context
    prompt_ids = list(set(result["prompt_revid"] for result in llm_results))
    # Filter out non-ObjectId prompt IDs (like "default")
    valid_prompt_ids = []
    for pid in prompt_ids:
        try:
            valid_prompt_ids.append(ObjectId(pid))
        except:
            # Skip invalid ObjectIds like "default"
            continue
    
    prompts = await db.prompt_revisions.find({
        "_id": {"$in": valid_prompt_ids}
    }).to_list(None)
    
    prompt_map = {str(p["_id"]): p for p in prompts}
    
    # Prepare download data
    download_data = {
        "document_id": document_id,
        "organization_id": organization_id,
        "document_name": document.get("user_file_name", "Unknown"),
        "extraction_date": datetime.now(UTC).isoformat(),
        "results": []
    }
    
    for result in llm_results:
        prompt_info = prompt_map.get(result["prompt_revid"], {})
        # Handle special case for "default" prompt
        if result["prompt_revid"] == "default":
            prompt_name = "Default Prompt"
        else:
            prompt_name = prompt_info.get("content", "Unknown")[:100] + "..." if len(prompt_info.get("content", "")) > 100 else prompt_info.get("content", "Unknown")
        
        download_data["results"].append({
            "prompt_revid": result["prompt_revid"],
            "prompt_name": prompt_name,
            "prompt_version": result.get("prompt_version", 0),
            "extraction_result": result["updated_llm_result"],
            "metadata": {
                "created_at": result["created_at"].isoformat() if result.get("created_at") else None,
                "updated_at": result["updated_at"].isoformat() if result.get("updated_at") else None,
                "is_edited": result.get("is_edited", False),
                "is_verified": result.get("is_verified", False)
            }
        })
    
    # Create JSON response
    json_content = json.dumps(download_data, indent=2, default=str)
    
    # Return as downloadable file
    return Response(
        content=json_content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=extractions_{document_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
        }
    )

# Account-level LLM routes
@llm_router.post("/v0/account/llm/run")
async def run_llm_chat_account(
    request: LLMPromptRequest,
    current_user: User = Depends(get_admin_user)
):
    """
    Test LLM with arbitrary prompt (admin only) - Account level.
    Supports both streaming and non-streaming responses.
    """
    return await ad.llm.run_llm_chat(request, current_user)

@llm_router.get("/v0/account/llm/models", response_model=ListLLMModelsResponse)
async def list_llm_models(
    current_user: User = Depends(get_current_user),
    provider_name: str | None = Query(None, description="Filter models by provider name"),
    provider_enabled: bool | None = Query(None, description="Filter models by provider enabled status"),
    llm_enabled: bool | None = Query(True, description="Filter models by enabled status"),
):
    """List all supported LLM models"""
    # Import litellm here to avoid event loop warnings
    import litellm
    
    db = ad.common.get_async_db()

    # Retrieve providers from MongoDB
    cursor = db.llm_providers.find({})

    # Get all enabled providers
    providers = await cursor.to_list(length=None)

    # Get all available models for each provider
    llm_models = []
    for provider in providers:
        # Skip disabled providers
        if provider_enabled and not provider["enabled"]:
            continue

        if provider_name and provider_name != provider["litellm_provider"]:
            continue

        # Which models to return?
        if llm_enabled:
            models = provider["litellm_models_enabled"]
        else:
            models = provider["litellm_models_available"]

        # Get the max input and output tokens for each model
        for model in models:
            max_input_tokens = 0
            max_output_tokens = 0
            input_cost_per_token = 0
            output_cost_per_token = 0
            
            if model in litellm.model_cost:
                max_input_tokens = litellm.model_cost[model].get("max_input_tokens", 0)
                max_output_tokens = litellm.model_cost[model].get("max_output_tokens", 0)
                input_cost_per_token = litellm.model_cost[model].get("input_cost_per_token", 0)
                output_cost_per_token = litellm.model_cost[model].get("output_cost_per_token", 0)

            llm_model = LLMModel(
                litellm_model=model,
                litellm_provider=provider["litellm_provider"],
                max_input_tokens=max_input_tokens,
                max_output_tokens=max_output_tokens,
                input_cost_per_token=input_cost_per_token,
                output_cost_per_token=output_cost_per_token,
            )
            llm_models.append(llm_model)
            logger.info(f"llm_model: {llm_model}")

    return ListLLMModelsResponse(models=llm_models)

@llm_router.get("/v0/account/llm/providers", response_model=ListLLMProvidersResponse)
async def list_llm_providers(
    current_user: User = Depends(get_admin_user)
):
    """List all supported LLM providers"""
    db = ad.common.get_async_db()
    
    # Retrieve models from MongoDB
    cursor = db.llm_providers.find({})
    providers = await cursor.to_list(length=None)
    
    # Convert MongoDB documents to LLMModel instances
    llm_providers = []
    for provider in providers:
        logger.info(f"provider: {provider}")

        token = provider["token"]
        if len(token) > 0:
            token = ad.crypto.decrypt_token(token)
            if len(token) > 16:
                token = token[:16] + "******"
            elif len(token) > 0:
                token = "******"
        else:
            token = None

        llm_providers.append(LLMProvider(
            name=provider["name"],
            display_name=provider["display_name"],
            litellm_provider=provider["litellm_provider"],
            litellm_models_enabled=provider["litellm_models_enabled"],
            litellm_models_available=provider["litellm_models_available"],
            enabled=provider["enabled"],
            token=token,
            token_created_at=provider["token_created_at"]
        ))
    
    return ListLLMProvidersResponse(providers=llm_providers)

@llm_router.put("/v0/account/llm/provider/{provider_name}")
async def set_llm_provider_config(
    provider_name: str,
    request: SetLLMProviderConfigRequest,
    current_user: User = Depends(get_admin_user)
):
    """Set LLM provider config"""

    db = ad.common.get_async_db()

    if provider_name is None:
        raise HTTPException(status_code=400, detail="Provider name is required")

    # Get the litellm_provider from the name
    elem = await db.llm_providers.find_one({"name": provider_name})
    if elem is None:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' not found")
    litellm_provider = elem["litellm_provider"]
    
    if request.litellm_models_enabled is not None:
        if len(request.litellm_models_enabled) > 0:
            for model in request.litellm_models_enabled:
                if model not in elem["litellm_models_available"]:
                    raise HTTPException(status_code=400, detail=f"Model '{model}' is not available for provider '{provider_name}'")
        
        # Reorder the list
        litellm_models_enabled_ordered = sorted(request.litellm_models_enabled,
                                                key=lambda x: elem["litellm_models_available"].index(x))
    
        # Save the reordered list
        elem["litellm_models_enabled"] = litellm_models_enabled_ordered

    if request.enabled is not None:
        elem["enabled"] = request.enabled
    if request.token is not None:
        if len(request.token) > 0:
            elem["token"] = ad.crypto.encrypt_token(request.token)
            elem["token_created_at"] = datetime.now(UTC)
        else:
            elem["token_created_at"] = None

    # Save the updated provider
    await db.llm_providers.update_one(
        {"name": provider_name},
        {"$set": elem}
    )

    return {"message": "LLM provider config updated successfully"}
