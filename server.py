"""Duck Demo Server - Manufacturing simulation with MCP and REST APIs.

Single MCP server with all 39 tools, organized by tags:
  - 'shared' tools (13): Available to both agents - user, stats, catalog (items + recipes), inventory, simulation, charts, admin
  - 'sales' tools (17): Sales agent - CRM, orders, shipping, emails
  - 'production' tools (9): Production agent - manufacturing, materials

Clients filter tools by tag to create specialized agents:
  - Sales agent: Uses Prompt_sales.md, filters to 'shared' + 'sales' tags (30 tools)
  - Production agent: Uses Prompt_production.md, filters to 'shared' + 'production' tags (22 tools)
"""

import logging

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

# Register all tools with tags: shared (13) + sales (17) + production (9) = 39 tools
register_tools(mcp)

# Register REST API routes (for UI compatibility)
register_routes(mcp)

logger.info("Starting Duck Demo MCP Server (39 tools)")
logger.info("  Shared tools (13): user_*, stats_*, catalog_* (items + recipes), inventory_*, simulation_*, chart_*, admin_*")
logger.info("  Sales tools (17): crm_*, sales_*, logistics_*, messaging_*")
logger.info("  Production tools (9): production_*, purchase_*")
logger.info("")
logger.info("Client-side agent filtering by tag:")
logger.info("  - Sales agent (Prompt_sales.md): tags=['shared', 'sales'] → 30 tools")
logger.info("  - Production agent (Prompt_production.md): tags=['shared', 'production'] → 22 tools")


if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG as UVICORN_DEFAULT_CONFIG
    
    # Add timestamps to uvicorn's log formats
    UVICORN_DEFAULT_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelname)s %(message)s"
    UVICORN_DEFAULT_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%dT%H:%M:%S"
    UVICORN_DEFAULT_CONFIG["formatters"]["access"]["fmt"] = '%(asctime)s %(levelname)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    UVICORN_DEFAULT_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%dT%H:%M:%S"
    
    mcp.run(transport="streamable-http")
