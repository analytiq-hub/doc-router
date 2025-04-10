from mcp.server.fastmcp import FastMCP
import analytiq_data as ad

# Create a standalone MCP server
mcp = FastMCP("Analytiq MCP Server")

@mcp.tool()
async def handle_get_status(message):
    ad.log.info(f"Received message: {message}")
    return {"status": "ok", "version": "1.0.0"}

@mcp.tool()
async def handle_perform_action(message):
    ad.log.info(f"Received message: {message}")
    action = message.get("action")
    parameters = message.get("parameters", {})
    return {"success": True, "action": action}

# Add MCP functionality with decorators
@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    ad.log.info(f"Received resource message: {message}")
    return f"Resource echo: {message}"


@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    ad.log.info(f"Received tool message: {message}")
    return f"Tool echo: {message}"


@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    ad.log.info(f"Received prompt message: {message}")
    return f"Please process this message: {message}"

# Export the SSE app for mounting
sse_app = mcp.sse_app()