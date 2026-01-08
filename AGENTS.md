# Duck Demo Project - Context Summary

## Project Overview
Manufacturing simulation demo for rubber duck production with:
- **Backend**: Python FastAPI server + FastMCP (MCP tools)
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite with comprehensive manufacturing schema
- **Domain**: Customer orders → Sales orders → Production orders → Production operations → Stock → Shipments

## Key Components

### Database Schema
- `simulation_state`: Single-row table (id=1) tracking simulated time
- `items`: Products (finished goods, components, raw materials)
- `recipes`: Bill of materials with `recipe_ingredients` (sequence_order, input_qty, input_uom)
- `production_orders`: Manufacturing orders with status tracking
- `production_operations`: Individual manufacturing steps with start/complete times and duration_hours
- `sales_orders`, `shipments`, `purchase_orders`, `customers`, `stock`

### Simulation Framework (Current Focus)
**Purpose**: "Build a robust framework to simulate production"

**Implemented**:
- `simulation_state` table with `sim_time` column (TEXT, format: 'YYYY-MM-DD HH:MM:SS')
- Initial time: **2025-12-24 08:30:00** (fixed for reproducibility)
- MCP tools:
  - `simulation_get_time()`: Returns current simulation time
  - `simulation_advance_time(hours/days/to_time)`: Advances or sets time
- REST API: `/api/simulation/time`
- UI: Layout component displays "Simulation Time: 12/24/2025, 8:30:00 AM" in dark header

### Production Model
- Single-batch operations: Each production_operation has `actual_quantity` (not qty_per_batch)
- Operations track: start_time, complete_time, duration_hours, status
- Item detail page shows related production_orders and purchase_orders

## User Preferences
- **Fixed times** for reproducibility (no `datetime('now')`)
- **No defensive code** that masks design issues
- **Terse commit messages**

## File Locations
- schema.sql: Database structure
- seed_demo.py: Populate demo data with fixed starting time
- server.py: FastAPI routes + MCP tools (simulation_get_time, simulation_advance_time)
- Layout.tsx: Displays simulation time
- api.ts: API client with simulationTime() method
- Scripts: backend.sh, frontend.sh, tunnel.sh

## Next Steps (Likely)
- Advance simulation time and complete production operations based on duration
- Auto-update production order statuses when operations finish
- Simulate purchase order arrivals after lead time
- Add UI controls for time advancement
- Trigger time-based events in the simulation

## Technical Notes
- SQLite datetime format: 'YYYY-MM-DD HH:MM:SS'
- JS Date parsing: Convert space to 'T' for ISO format
- Database path: demo.db in project root
- Virtual env: python -m venv venv
