from fastapi import APIRouter
from mcp.server.fastmcp import FastMCP

router = APIRouter(prefix="/v0/mcp", tags=["mcp"])
mcp = FastMCP(router=router)

@mcp.tool()
async def handle_get_status(message):
    return {"status": "ok", "version": "1.0.0"}

@mcp.tool()
async def handle_perform_action(message):
    action = message.get("action")
    parameters = message.get("parameters", {})
    return {"success": True, "action": action}