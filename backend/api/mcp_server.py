from typing import Optional, List, Dict, Any
from fastapi import Depends, HTTPException
from jose import JWTError
import subprocess
import os
import signal
import atexit
from datetime import datetime

import analytiq_data as ad
from mcp.server.fastmcp import FastMCP
from api.schemas import User, DocumentMetadata, DocumentResponse, Prompt


class OrganizationMCP:
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.mcp = FastMCP(f"org-{organization_id}")
        self.db = ad.common.get_async_db()
        
        # Register tools
        self.mcp.tool()(self.get_document)
        self.mcp.tool()(self.list_documents)
        self.mcp.tool()(self.get_prompt)
        self.mcp.tool()(self.list_prompts)
        self.mcp.tool()(self.get_extraction)
    
    async def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get a document by ID from this organization.
        
        Args:
            document_id: The ID of the document to retrieve
        """
        document = await self.db.documents.find_one({
            "_id": document_id,
            "organization_id": self.organization_id
        })
        
        if not document:
            return {"error": "Document not found"}
            
        return {
            "id": document["_id"],
            "name": document["document_name"],
            "content": document["content"],
            "metadata": {
                "upload_date": document["upload_date"],
                "uploaded_by": document["uploaded_by"],
                "state": document["state"],
                "tag_ids": document.get("tag_ids", [])
            }
        }
    
    async def list_documents(self, limit: int = 10, skip: int = 0, tag_ids: Optional[str] = None) -> Dict[str, Any]:
        """
        List documents in this organization.
        
        Args:
            limit: Maximum number of documents to return
            skip: Number of documents to skip
            tag_ids: Comma-separated list of tag IDs to filter by
        """
        query = {"organization_id": self.organization_id}
        
        # Add tag filter if provided
        if tag_ids:
            tag_id_list = tag_ids.split(",")
            query["tag_ids"] = {"$in": tag_id_list}
            
        # Get count first
        total_count = await self.db.documents.count_documents(query)
        
        # Then get documents with pagination
        cursor = self.db.documents.find(query).skip(skip).limit(limit)
        documents = []
        
        async for doc in cursor:
            documents.append({
                "id": doc["_id"],
                "name": doc["document_name"],
                "upload_date": doc["upload_date"],
                "state": doc["state"],
                "tag_ids": doc.get("tag_ids", [])
            })
            
        return {
            "documents": documents,
            "total_count": total_count,
            "skip": skip
        }
    
    async def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        """
        Get a prompt by ID from this organization.
        
        Args:
            prompt_id: The ID of the prompt to retrieve
        """
        prompt = await self.db.prompts.find_one({
            "prompt_id": prompt_id,
            "organization_id": self.organization_id
        })
        
        if not prompt:
            return {"error": "Prompt not found"}
            
        return {
            "id": prompt["_id"],
            "prompt_id": prompt["prompt_id"],
            "name": prompt["name"],
            "content": prompt["content"],
            "schema_id": prompt.get("schema_id"),
            "schema_version": prompt.get("schema_version"),
            "version": prompt["version"],
            "created_at": prompt["created_at"],
            "created_by": prompt["created_by"],
            "tag_ids": prompt.get("tag_ids", [])
        }
    
    async def list_prompts(self, limit: int = 10, skip: int = 0, tag_ids: Optional[str] = None) -> Dict[str, Any]:
        """
        List prompts in this organization.
        
        Args:
            limit: Maximum number of prompts to return
            skip: Number of prompts to skip
            tag_ids: Comma-separated list of tag IDs to filter by
        """
        query = {"organization_id": self.organization_id}
        
        # Add tag filter if provided
        if tag_ids:
            tag_id_list = tag_ids.split(",")
            query["tag_ids"] = {"$in": tag_id_list}
            
        # Get count first
        total_count = await self.db.prompts.count_documents(query)
        
        # Then get prompts with pagination
        cursor = self.db.prompts.find(query).skip(skip).limit(limit)
        prompts = []
        
        async for prompt in cursor:
            prompts.append({
                "id": prompt["_id"],
                "prompt_id": prompt["prompt_id"],
                "name": prompt["name"],
                "version": prompt["version"],
                "created_at": prompt["created_at"],
                "created_by": prompt["created_by"],
                "tag_ids": prompt.get("tag_ids", [])
            })
            
        return {
            "prompts": prompts,
            "total_count": total_count,
            "skip": skip
        }
    
    async def get_extraction(self, document_id: str, prompt_id: str) -> Dict[str, Any]:
        """
        Get LLM extraction results for a document using a specific prompt.
        
        Args:
            document_id: The ID of the document
            prompt_id: The ID of the prompt used for extraction
        """
        result = await self.db.llm_results.find_one({
            "document_id": document_id,
            "prompt_id": prompt_id,
            "organization_id": self.organization_id
        })
        
        if not result:
            return {"error": "Extraction not found"}
            
        return {
            "document_id": result["document_id"],
            "prompt_id": result["prompt_id"],
            "result": result["llm_result"],
            "updated_result": result.get("updated_llm_result"),
            "is_verified": result.get("is_verified", False),
            "is_edited": result.get("is_edited", False),
            "created_at": result["created_at"],
            "updated_at": result.get("updated_at")
        }
    
    def run(self, transport: str = 'stdio'):
        """Run the MCP server with the specified transport"""
        self.mcp.run(transport=transport)

    async def start(self):
        """Initialize resources or connections needed for the MCP server."""
        # Add any initialization logic here
        ad.log.info(f"Starting MCP server for organization {self.organization_id}")

    async def stop(self):
        """Clean up resources or connections when stopping the MCP server."""
        # Add any cleanup logic here
        ad.log.info(f"Stopping MCP server for organization {self.organization_id}") 