"""Duck Demo Server - Manufacturing simulation with MCP and REST APIs."""

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


# HTTP-based MCP server using FastMCP with stateless JSON responses.
# Allow all hosts/origins so ngrok tunnels work (demo-only; tighten for prod).
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

# Register MCP tools (38 tools)
register_tools(mcp)

# Register REST API routes (20+ endpoints)
register_routes(mcp)


if __name__ == "__main__":
    # Run as HTTP server using the streamable-http transport
    mcp.run(transport="streamable-http")
