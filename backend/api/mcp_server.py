from mcp.server.fastmcp import FastMCP

# Create a standalone MCP server
mcp = FastMCP("Analytiq MCP Server")

@mcp.tool()
async def handle_get_status(message):
    return {"status": "ok", "version": "1.0.0"}

@mcp.tool()
async def handle_perform_action(message):
    action = message.get("action")
    parameters = message.get("parameters", {})
    return {"success": True, "action": action}

# Export the SSE app for mounting
sse_app = mcp.sse_app()