"""Duck Demo Server - Manufacturing simulation with MCP and REST APIs.

Single MCP server with all 53 tools, organized by tags:
  - 'shared' tools (14): Available to both agents - user, stats, catalog (items + inspect + recipes), inventory, simulation, charts, admin
  - 'sales' tools (29): Sales agent - CRM, orders, shipping, emails, invoices, quotes
  - 'production' tools (9): Production agent - manufacturing, materials
  - 'internal' tools (1): Only callable by MCP Apps, not exposed to agents - customer confirmation

Clients filter tools by tag to create specialized agents:
  - Sales agent: Uses Prompt_sales.md, filters to 'shared' + 'sales' tags (43 tools)
  - Production agent: Uses Prompt_production.md, filters to 'shared' + 'production' tags (23 tools)
  
MCP Apps: Interactive UI components served via ui:// scheme for human-in-the-loop workflows.
"""

import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from db import init_db
from mcp_tools import register_tools
from api_routes import register_routes
import config


# Basic logging setup with timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger("duck-demo")


# Single MCP server with ALL tools
mcp = FastMCP(
    "duck-demo",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    ),
)

# Register all tools with tags:
#   - shared (14) + sales (29) + production (9) + internal (1) = 53 tools total
#   - Agents see: sales=43 tools, production=23 tools (internal excluded)
register_tools(mcp)

# Register REST API routes (for UI compatibility)
register_routes(mcp)

# Register MCP App UI resources
@mcp.resource("ui://generic-confirm/dialog", mime_type="text/html;profile=mcp-app")
def get_generic_confirm_ui() -> str:
    """Serves the generic confirmation MCP App UI."""
    ui_path = os.path.join(os.path.dirname(__file__), "mcp_apps_ui", "generic-confirm.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        logger.warning(f"MCP App UI not found at {ui_path}. Run 'cd ui && npm run build:mcp-app' to build it.")
        return "<html><body><p>MCP App UI not built yet. Please run: cd ui && npm run build:mcp-app</p></body></html>"

@mcp.resource("ui://item-inspect/viewer", mime_type="text/html;profile=mcp-app")
def get_item_inspect_ui() -> str:
    """Serves the 3D item inspector MCP App UI."""
    ui_path = os.path.join(os.path.dirname(__file__), "mcp_apps_ui", "item-inspect.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        logger.warning(f"MCP App UI not found at {ui_path}. Run 'cd ui && npm run build:mcp-app' to build it.")
        return "<html><body><p>MCP App UI not built yet. Please run: cd ui && npm run build:mcp-app</p></body></html>"

logger.info("Duck Demo MCP Server ready (53 tools)")


if __name__ == "__main__":
    import sys
    
    # Check for --stdio flag
    if "--stdio" in sys.argv:
        logger.info("Starting Duck Demo MCP Server in STDIO mode")
        mcp.run(transport="stdio")
    else:
        import uvicorn
        from uvicorn.config import LOGGING_CONFIG as UVICORN_DEFAULT_CONFIG
        
        # Add timestamps to uvicorn's log formats
        UVICORN_DEFAULT_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelname)s %(message)s"
        UVICORN_DEFAULT_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%dT%H:%M:%S"
        UVICORN_DEFAULT_CONFIG["formatters"]["access"]["fmt"] = '%(asctime)s %(levelname)s %(client_addr)s - "%(request_line)s" %(status_code)s'
        UVICORN_DEFAULT_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%dT%H:%M:%S"
        
        mcp.run(transport="streamable-http")
