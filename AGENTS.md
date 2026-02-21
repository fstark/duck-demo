# Agent Tool Filtering

This server exposes **39 MCP tools** organized by tags for client-side filtering.

## Architecture

**Single Server** → All tools with tags → **Client Filters** → Specialized Agent

## Tool Organization

> 🔧 = mutating tool (writes to database)

### Shared Tools (13 tools) - tag: `shared`
Available to both agents:
- `user_get_current`
- `stats_get_summary`
- `catalog_get_item`, `catalog_search_items`
- `catalog_list_recipes`, `catalog_get_recipe`
- `inventory_list_items`, `inventory_get_stock`, `inventory_check_availability`
- `simulation_get_time`, `simulation_advance_time`
- `chart_generate`
- `admin_reset_database`

### Sales Tools (17 tools) - tag: `sales`
Customer relationship and order management:
- `crm_search_customers`, 🔧 `crm_create_customer`, 🔧 `crm_update_customer`, `crm_get_customer`
- `sales_get_quote_options`, `sales_price_order`, `sales_search_orders`, `sales_get_order`, 🔧 `sales_link_shipment`
- 🔧 `logistics_create_shipment`, `logistics_get_shipment`
- `messaging_create_email`, `messaging_list_emails`, `messaging_get_email`, `messaging_update_email`, `messaging_send_email`, `messaging_delete_email`
- 🔧 `invoice_create`, `invoice_get`, `invoice_list`, 🔧 `invoice_issue`, 🔧 `invoice_record_payment`
- 🔧 `quote_create`, `quote_get`, `quote_list`, 🔧 `quote_send`, 🔧 `quote_accept`, 🔧 `quote_reject`, 🔧 `quote_revise`

### Production Tools (9 tools) - tag: `production`
Manufacturing and materials management:
- `production_get_dashboard`, `production_get_order`, `production_search_orders`, 🔧 `production_create_order`, 🔧 `production_start_order`, 🔧 `production_complete_order`
- 🔧 `purchase_create_order`, 🔧 `purchase_restock_materials`, 🔧 `purchase_receive_order`

## Client-Side Filtering

Clients should:
1. Call `list_tools` to get all 39 tools
2. Filter by tags based on agent type:
   - **Sales agent**: `tags=['shared', 'sales']` → 30 tools
   - **Production agent**: `tags=['shared', 'production']` → 22 tools
3. Only expose filtered tools to the LLM
4. Validate tool calls match the allowed tag set

## Agent Prompts

- **Prompt_sales.md**: Instructions for sales agent (CRM, orders, shipping, emails, invoices, quotes)
- **Prompt_production.md**: Instructions for production agent (manufacturing, recipes, materials)

Both prompts should guide the LLM to use appropriate tools, with client-side filtering as the enforcement layer.

## File Structure

- `server.py`: Main server (registers all 39 tools)
- `mcp_tools.py`: All tool definitions with tags

