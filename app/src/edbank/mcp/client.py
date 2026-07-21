"""
MCP client: fetches tool schemas and calls tools via Streamable HTTP.
One short-lived connection per operation — safe for single-user PoC.
"""
import json
import logging
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from edbank.config import settings

logger = logging.getLogger(__name__)


async def list_tools() -> list[dict]:
    """Return all tools from the MCP server in OpenAI function-calling format."""
    async with streamablehttp_client(
        url=settings.mcp_server_url,
        timeout=settings.mcp_timeout_seconds,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

    openai_tools = []
    for tool in result.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        })
    logger.info("mcp list_tools count=%d", len(openai_tools))
    return openai_tools


async def call_tool(name: str, arguments: dict) -> dict:
    """Call one MCP tool and return the result as a dict."""
    async with streamablehttp_client(
        url=settings.mcp_server_url,
        timeout=settings.mcp_timeout_seconds,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)

    # MCP returns a list of content objects; we extract text or forward as-is
    if result.isError:
        raise RuntimeError(f"MCP tool error: {result.content}")

    parts = []
    for item in result.content:
        if hasattr(item, "text"):
            parts.append(item.text)
    raw = "\n".join(parts) if parts else ""

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {"raw": raw}
