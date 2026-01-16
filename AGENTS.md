# Agent Tool Filtering

This server exposes **43 MCP tools** organized by tags for client-side filtering.

## Architecture

**Single Server** → All tools with tags → **Client Filters** → Specialized Agent

## Tool Organization

### Shared Tools (13 tools) - tag: `shared`
Available to both agents:
- `get_current_user`, `get_statistics`
- `catalog_*`: get_item, search_items_basic
- `inventory_*`: list_items, get_stock_summary, check_availability
- `simulation_*`: get_time, advance_time
- `chart_generate`
- `admin_reset_database`

### Sales Tools (18 tools) - tag: `sales`
Customer relationship and order management:
- `crm_*`: find_customers, create_customer, get_customer_details
- `sales_*`: quote_options, create/price/search/get_sales_order, link_shipment
- `logistics_*`: create_shipment, get_shipment_status
- `messaging_*`: create/list/get/update/send/delete_email

### Production Tools (12 tools) - tag: `production`
Manufacturing and materials management:
- `production_*`: get_statistics, get/find/create/start/complete_order
- `recipe_*`: list, get
- `purchase_*`: create_order, restock_materials, receive_order

## Client-Side Filtering

Clients should:
1. Call `list_tools` to get all 43 tools
2. Filter by tags based on agent type:
   - **Sales agent**: `tags=['shared', 'sales']` → 31 tools
   - **Production agent**: `tags=['shared', 'production']` → 25 tools
3. Only expose filtered tools to the LLM
4. Validate tool calls match the allowed tag set

## Agent Prompts

- **Prompt_sales.md**: Instructions for sales agent (CRM, orders, shipping, emails)
- **Prompt_production.md**: Instructions for production agent (manufacturing, recipes, materials)

Both prompts should guide the LLM to use appropriate tools, with client-side filtering as the enforcement layer.

## File Structure

- `server.py`: Main server (registers all 43 tools)
- `mcp_tools.py`: All tool definitions with tags
