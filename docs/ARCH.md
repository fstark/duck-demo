# Backend Architecture

## Package Structure

Three domain-based packages mirror each other:

| Package | Purpose | File suffix |
|---|---|---|
| `services/` | Business logic, DB access | `{domain}.py` |
| `mcp_tools/` | MCP tool definitions (thin wrappers over services) | `{domain}_tools.py` |
| `api_routes/` | REST endpoints (thin wrappers over services) | `{domain}_routes.py` |

Adding a new domain = one file per package + register it in that package's `__init__.py`.

## Conventions

- **Services** are stateless classes with `@staticmethod` methods. A module-level singleton (e.g. `customer_service = CustomerService()`) is the only instance.
- **Circular imports** between services are resolved with lazy imports inside method bodies, never at module top.
- **Shared helpers** live in `_common.py` (tools) or `_base.py` (services). Package-external utilities stay in top-level `utils.py`, `config.py`, `db.py`.
- **Registration**: each domain module exposes `def register(mcp)`. The package `__init__.py` calls all of them via `register_all_tools(mcp)` / `register_all_routes(mcp)`.
- **Path references**: files inside packages use `os.path.dirname(os.path.dirname(__file__))` to reach the project root (for `models/`, `mcp_apps_ui/`, `tmp/charts/`).

## Tool Tagging

Tools carry meta tags that clients filter on to build specialised agents:

| Tag | Audience |
|---|---|
| `shared` | Both agents |
| `sales` | Sales agent only |
| `production` | Production agent only |
| `internal` | MCP Apps only (hidden from agents) |

Mutating tools include a `ui` annotation pointing to `ui://generic-confirm/dialog` so the MCP App client can prompt the user before execution.

## Confirmation Flow

Mutating tools return a `structuredContent` payload instead of executing directly. The generic confirm dispatcher (`confirm_tools.py`) receives the user's decision and calls the actual service method. This keeps the confirmation UI decoupled from individual tools.
