from fastapi import APIRouter, HTTPException, Depends
from fastapi.encoders import jsonable_encoder
from datetime import datetime
from bson import ObjectId

import analytiq_data as ad
from setup import get_db, get_analytiq_client
from auth import get_current_user
from schemas import (
    SaveFlowRequest,
    Flow,
    ListFlowsResponse,
    FlowMetadata,
    User
)

flows_router = APIRouter(
    prefix="/flows",
    tags=["flows"]
)

@flows_router.post("")
async def create_flow(
    flow: SaveFlowRequest,
    current_user: User = Depends(get_current_user)
) -> Flow:
    try:
        flow_id = ad.common.create_id()
        flow_data = {
            "_id": ObjectId(flow_id),
            "name": flow.name,
            "description": flow.description,
            "nodes": jsonable_encoder(flow.nodes),
            "edges": jsonable_encoder(flow.edges),
            "tag_ids": flow.tag_ids,
            "version": 1,
            "created_at": datetime.utcnow(),
            "created_by": current_user.user_name
        }
        
        analytiq_client = get_analytiq_client()
        env = analytiq_client.env
        
        # Save to MongoDB
        await analytiq_client.mongodb_async[env].flows.insert_one(flow_data)
        
        # Convert _id to string for response
        flow_data["id"] = str(flow_data.pop("_id"))
        return Flow(**flow_data)
        
    except Exception as e:
        ad.log.error(f"Error creating flow: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating flow: {str(e)}"
        )

@flows_router.get("")
async def list_flows(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user)
) -> ListFlowsResponse:
    analytiq_client = get_analytiq_client()
    env = analytiq_client.env
    
    cursor = analytiq_client.mongodb_async[env].flows.find(
    ).skip(skip).limit(limit)
    
    flows = await cursor.to_list(None)
    
    total_count = await analytiq_client.mongodb_async[env].flows.count_documents(
        {"created_by": current_user.user_name}
    )
    
    # Convert MongoDB documents to Flow models
    flow_list = []
    for flow in flows:
        flow_dict = {
            "id": str(flow["_id"]),
            "name": flow["name"],
            "description": flow.get("description"),
            "nodes": flow["nodes"],
            "edges": flow["edges"],
            "tag_ids": flow.get("tag_ids", []),
            "version": flow.get("version", 1),
            "created_at": flow["created_at"],
            "created_by": flow["created_by"]
        }
        flow_list.append(FlowMetadata(**flow_dict))
    
    return ListFlowsResponse(
        flows=flow_list,
        total_count=total_count,
        skip=skip
    )

@flows_router.get("/{flow_id}")
async def get_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user)
) -> Flow:
    try:
        analytiq_client = get_analytiq_client()
        env = analytiq_client.env
        
        # Find the flow in MongoDB
        flow = await analytiq_client.mongodb_async[env].flows.find_one({
            "_id": ObjectId(flow_id),
            "created_by": current_user.user_name  # Ensure user can only access their own flows
        })
        
        if not flow:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        # Convert MongoDB _id to string id for response
        flow_dict = {
            "id": str(flow["_id"]),
            "name": flow["name"],
            "description": flow.get("description"),
            "nodes": flow["nodes"],
            "edges": flow["edges"],
            "tag_ids": flow.get("tag_ids", []),
            "version": flow.get("version", 1),
            "created_at": flow["created_at"],
            "created_by": flow["created_by"]
        }
        
        return Flow(**flow_dict)
        
    except Exception as e:
        ad.log.error(f"Error getting flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error getting flow: {str(e)}"
        )

@flows_router.delete("/{flow_id}")
async def delete_flow(
    flow_id: str,
    current_user: User = Depends(get_current_user)
) -> dict:
    try:
        analytiq_client = get_analytiq_client()
        env = analytiq_client.env
        
        # Find and delete the flow, ensuring user can only delete their own flows
        result = await analytiq_client.mongodb_async[env].flows.delete_one({
            "_id": ObjectId(flow_id),
            "created_by": current_user.user_name
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        return {"message": "Flow deleted successfully"}
        
    except Exception as e:
        ad.log.error(f"Error deleting flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting flow: {str(e)}"
        )

@flows_router.put("/{flow_id}")
async def update_flow(
    flow_id: str,
    flow: SaveFlowRequest,
    current_user: User = Depends(get_current_user)
) -> Flow:
    try:
        analytiq_client = get_analytiq_client()
        env = analytiq_client.env
        
        # Find the flow and verify ownership
        existing_flow = await analytiq_client.mongodb_async[env].flows.find_one({
            "_id": ObjectId(flow_id),
            "created_by": current_user.user_name
        })
        
        if not existing_flow:
            raise HTTPException(
                status_code=404,
                detail=f"Flow with id {flow_id} not found"
            )
        
        # Prepare update data
        update_data = {
            "name": flow.name,
            "description": flow.description,
            "nodes": jsonable_encoder(flow.nodes),
            "edges": jsonable_encoder(flow.edges),
            "tag_ids": flow.tag_ids,
            "version": existing_flow.get("version", 1) + 1,
            "updated_at": datetime.utcnow()
        }
        
        # Update the flow
        result = await analytiq_client.mongodb_async[env].flows.find_one_and_update(
            {
                "_id": ObjectId(flow_id),
                "created_by": current_user.user_name
            },
            {"$set": update_data},
            return_document=True
        )
        
        return Flow(**{
            "id": str(result["_id"]),
            "name": result["name"],
            "description": result.get("description"),
            "nodes": result["nodes"],
            "edges": result["edges"],
            "tag_ids": result.get("tag_ids", []),
            "version": result["version"],
            "created_at": result["created_at"],
            "created_by": result["created_by"]
        })
        
    except Exception as e:
        ad.log.error(f"Error updating flow {flow_id}: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=f"Error updating flow: {str(e)}"
        )
