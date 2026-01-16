"""Duck Demo Server - Manufacturing simulation with MCP and REST APIs.

Single MCP server with all 43 tools, organized by tags:
  - 'shared' tools (13): Available to both agents - catalog, inventory, simulation, charts, etc.
  - 'sales' tools (18): Sales agent - CRM, orders, shipping, emails
  - 'production' tools (12): Production agent - manufacturing, recipes, materials

Clients filter tools by tag to create specialized agents:
  - Sales agent: Uses Prompt_sales.md, filters to 'shared' + 'sales' tags (31 tools)
  - Production agent: Uses Prompt_production.md, filters to 'shared' + 'production' tags (25 tools)
"""

import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from db import init_db
from mcp_tools import register_tools
from api_routes import register_routes
import config


# Logging setup - console and file
log_format = logging.Formatter(
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)

# File handler
file_handler = logging.FileHandler(config.LOG_FILE)
file_handler.setFormatter(log_format)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],
)
logger = logging.getLogger("duck-demo")
logger.info(f"Logging to console and {config.LOG_FILE}")


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

# Register all tools with tags: shared (13) + sales (18) + production (12) = 43 tools
register_tools(mcp)

# Register REST API routes (for UI compatibility)
register_routes(mcp)

logger.info("Starting Duck Demo MCP Server (43 tools)")
logger.info("  Shared tools (13): catalog_*, inventory_*, simulation_*, chart_*, get_*, admin_*")
logger.info("  Sales tools (18): crm_*, sales_*, logistics_*, messaging_*")
logger.info("  Production tools (12): production_*, recipe_*, purchase_*")
logger.info("")
logger.info("Client-side agent filtering by tag:")
logger.info("  - Sales agent (Prompt_sales.md): tags=['shared', 'sales'] → 31 tools")
logger.info("  - Production agent (Prompt_production.md): tags=['shared', 'production'] → 25 tools")


if __name__ == "__main__":
    # Run as HTTP server using the streamable-http transport
    mcp.run(transport="streamable-http")
