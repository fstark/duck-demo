# Agent Tool Filtering

This server exposes **53 MCP tools** organized by tags for client-side filtering.

## Architecture

**Single Server** → All tools with tags → **Client Filters** → Specialized Agent

## Tool Organization

> 🔧 = mutating tool (writes to database)

### Shared Tools (14 tools) - tag: `shared`
Available to both agents:
- `user_get_current`
- `stats_get_summary`
- `catalog_get_item`, `catalog_inspect_item`, `catalog_search_items`
- `catalog_list_recipes`, `catalog_get_recipe`
- `inventory_list_items`, `inventory_get_stock`, `inventory_check_availability`
- `simulation_get_time`, `simulation_advance_time`
- `chart_generate`
- `admin_reset_database`

### Sales Tools (29 tools) - tag: `sales`
Customer relationship and order management:
- `crm_search_customers`, 🔧 `crm_create_customer` (MCP App), 🔧 `crm_update_customer`, `crm_get_customer`
- `sales_get_quote_options`, `sales_price_order`, `sales_search_orders`, `sales_get_order`, 🔧 `sales_link_shipment`
- 🔧 `logistics_create_shipment`, `logistics_get_shipment`
- `messaging_create_email`, `messaging_list_emails`, `messaging_get_email`, `messaging_update_email`, `messaging_send_email`, `messaging_delete_email`
- 🔧 `invoice_create`, `invoice_get`, `invoice_list`, 🔧 `invoice_issue`, 🔧 `invoice_record_payment`
- 🔧 `quote_create`, `quote_get`, `quote_list`, 🔧 `quote_send`, 🔧 `quote_accept`, 🔧 `quote_reject`, 🔧 `quote_revise`

### Internal Tools (1 tool) - no tags
Tools only callable by MCP Apps, not exposed to agents:
- 🔧 `generic_confirm_action` - Generic dispatcher for confirmed actions, called by confirmation dialogs after user approval

### Production Tools (9 tools) - tag: `production`
Manufacturing and materials management:
- `production_get_dashboard`, `production_get_order`, `production_search_orders`, 🔧 `production_create_order`, 🔧 `production_start_order`, 🔧 `production_complete_order`
- 🔧 `purchase_create_order`, 🔧 `purchase_restock_materials`, 🔧 `purchase_receive_order`

## Client-Side Filtering

Clients should:
1. Call `list_tools` to get all 53 tools
2. Filter by tags based on agent type:
   - **Sales agent**: `tags=['shared', 'sales']` → 43 tools (29 sales + 14 shared)
   - **Production agent**: `tags=['shared', 'production']` → 23 tools (9 production + 14 shared)
   - **Internal tools** with empty tags are excluded from agent contexts but remain callable by MCP Apps
3. Only expose filtered tools to the LLM
4. Validate tool calls match the allowed tag set

## Agent Prompts

- **Prompt_sales.md**: Instructions for sales agent (CRM, orders, shipping, emails, invoices, quotes)
- **Prompt_production.md**: Instructions for production agent (manufacturing, recipes, materials)

Both prompts should guide the LLM to use appropriate tools, with client-side filtering as the enforcement layer.

## MCP Apps (UI Extensions)

The server includes MCP App support for interactive human-in-the-loop workflows using a **unified confirmation system**:

### Generic Confirmation Dialog
All 20+ mutating tools (marked with 🔧) now use a generic confirmation dialog system that:
- **Gateway tools** return standardized confirmation metadata (field definitions, action details, original arguments)
- **Single MCP App UI** (`ui://generic-confirm/dialog`) renders any confirmation based on field metadata
- **Single hidden dispatcher** (`generic_confirm_action`) routes confirmations to appropriate service methods
- **Field metadata** defines how each parameter should be displayed (label, type, grouping, validation)

### Confirmed Actions
All mutating tools trigger confirmation dialogs before execution:
- **Customer Management**: `crm_create_customer`, `crm_update_customer`
- **Quote Management**: `quote_create`, `quote_send`, `quote_accept`, `quote_reject`, `quote_revise`
- **Invoice & Payment**: `invoice_create`, `invoice_issue`, `invoice_record_payment`
- **Order & Shipping**: `sales_link_shipment`, `logistics_create_shipment`
- **Production**: `production_create_order`, `production_start_order`, `production_complete_order`
- **Purchasing**: `purchase_create_order`, `purchase_restock_materials`, `purchase_receive_order`
- **Messaging**: `messaging_send_email`, `messaging_delete_email`

### Other MCP Apps
- **Item Inspector**: `catalog_inspect_item` returns an interactive 3D wireframe viewer with mouse-controlled rotation for examining catalog items

### Build Instructions
- Build MCP App UIs: `cd ui && npm run build:mcp-app`
- UI resources served via `ui://` scheme (e.g., `ui://generic-confirm/dialog`, `ui://item-inspect/viewer`)

## File Structure

- `server.py`: Main server (registers all 53 tools + MCP App resources)
- `mcp_tools.py`: All tool definitions with tags + confirmation metadata system
- `ui/src/mcp-apps/`: MCP App UI components
  - `GenericConfirmDialog.tsx`: Universal confirmation UI
  - `ItemInspectViewer.tsx`: 3D item inspector

