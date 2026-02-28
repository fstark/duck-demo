# Throughput per Constraint Hour (TPH) Analysis

## Overview

**Definition:**
```
TPH = Total Contribution Margin / Constraint Hours Used
```

**Why it matters:**
This measures economic productivity of the system bottleneck. If this number is flat while demand is rising, value is leaking via mix, scheduling, or pricing.

**What it exposes:**
- Suboptimal product mix
- Poor sequencing
- Low-margin work consuming constraint time
- Ineffective S&OP alignment

## Current System Gaps

### Missing Data
1. **Cost Data** - No variable costs tracked (materials, labor)
2. **Constraint/Resource Tracking** - No workstation capacity or bottleneck identification
3. **Margin Calculations** - Only price, no cost = no contribution margin

### Schema Enhancements Needed

```sql
-- Add cost tracking to items table
ALTER TABLE items ADD COLUMN material_cost REAL DEFAULT 0;
ALTER TABLE items ADD COLUMN labor_cost_per_hour REAL DEFAULT 0;
ALTER TABLE items ADD COLUMN variable_cost REAL DEFAULT 0;

-- Add resource/constraint tracking
CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    resource_type TEXT NOT NULL, -- 'workstation', 'machine', 'labor_pool'
    capacity_hours_per_day REAL NOT NULL,
    is_constraint BOOLEAN DEFAULT 0,
    notes TEXT
);

-- Link recipe operations to resources
ALTER TABLE recipe_operations ADD COLUMN resource_id TEXT;

-- Track actual constraint time used per production order
CREATE TABLE IF NOT EXISTS production_constraint_time (
    id TEXT PRIMARY KEY,
    production_order_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    planned_hours REAL NOT NULL,
    actual_hours REAL,
    created_at TEXT NOT NULL
);
```

## Recommended MCP Functions

### 1. Constraint Management Functions (tag: `production`)

```python
constraint_identify_bottleneck(start_date, end_date)
  """Analyzes production operations to find the constraint resource.
  
  Returns: {
    resource_id: str,
    resource_name: str,
    utilization_pct: float,
    hours_available: float,
    hours_used: float,
    hours_idle: float
  }
  """

constraint_set_resource(resource_name, capacity_hours_per_day, is_constraint)
  """Manually designate a resource as the constraint.
  
  Args:
    resource_name: Name of the resource
    capacity_hours_per_day: Available hours per day
    is_constraint: Mark as system constraint
    
  Returns: resource_id
  """
  
constraint_get_utilization(resource_name, start_date, end_date)
  """Returns constraint utilization metrics over time period.
  
  Returns: {
    resource_name: str,
    period: {start_date, end_date},
    total_hours_available: float,
    total_hours_used: float,
    utilization_pct: float,
    idle_hours: float
  }
  """
```

### 2. Cost & Margin Functions (tag: `production`)

```python
catalog_set_item_costs(item_sku, material_cost, labor_cost_per_hour)
  """Set variable costs for an item.
  
  Args:
    item_sku: Item identifier
    material_cost: Cost of materials per unit
    labor_cost_per_hour: Labor cost rate (optional)
    
  Returns: {item_sku, unit_price, material_cost, contribution_margin}
  """
  
catalog_get_item_margins(item_sku)
  """Returns pricing and margin data for an item.
  
  Returns: {
    item_sku: str,
    unit_price: float,
    variable_cost: float,
    contribution_margin: float,
    margin_pct: float
  }
  """
  
recipe_calculate_cost(recipe_id)
  """Calculates total variable cost from ingredients + operations.
  
  Returns: {
    recipe_id: str,
    output_item_sku: str,
    material_costs: float,
    labor_costs: float,
    total_variable_cost: float,
    cost_breakdown: [...]
  }
  """
```

### 3. TPH Calculation Functions (tag: `shared`)

```python
analytics_calculate_tph(start_date, end_date, constraint_resource)
  """Core TPH calculation for a time period.
  
  Args:
    start_date: Start of analysis period
    end_date: End of analysis period
    constraint_resource: Name/ID of constraint resource
    
  Returns: {
    total_contribution_margin: float,
    constraint_hours_used: float,
    constraint_hours_available: float,
    utilization_pct: float,
    tph: float,
    period: {start_date, end_date},
    units_produced: int
  }
  """

analytics_tph_by_product(start_date, end_date, group_by="item")
  """TPH breakdown by product/customer/order.
  
  Exposes: suboptimal mix, low-margin work
  
  Args:
    start_date, end_date: Analysis period
    group_by: 'item', 'customer', 'order_type'
    
  Returns: [{
    item_sku: str,
    item_name: str,
    units_produced: int,
    contribution_margin: float,
    constraint_hours: float,
    tph: float,
    rank: int
  }]
  """

analytics_tph_trend(start_date, end_date, period="month")
  """Historical TPH over time (detects if flat while demand rises).
  
  Args:
    start_date, end_date: Analysis period
    period: 'day', 'week', 'month', 'quarter'
    
  Returns: [{
    period: str,
    tph: float,
    contribution_margin: float,
    constraint_hours_used: float,
    constraint_utilization_pct: float,
    demand_units: int,
    tph_change_pct: float
  }]
  """

analytics_product_mix_optimization(target_date, available_constraint_hours)
  """Recommends optimal product mix to maximize TPH.
  
  Args:
    target_date: Planning date
    available_constraint_hours: Hours available on constraint
    
  Returns: {
    recommended_mix: [{
      item_sku: str,
      tph: float,
      recommended_units: int,
      constraint_hours_required: float,
      contribution_margin: float
    }],
    total_projected_margin: float,
    total_constraint_hours: float,
    optimization_notes: str
  }
  """
```

### 4. Production Analysis Functions (tag: `production`)

```python
production_get_constraint_schedule(start_date, end_date)
  """Shows what work is consuming constraint time.
  
  Exposes: poor sequencing, ineffective S&OP
  
  Returns: [{
    production_order_id: str,
    item_sku: str,
    customer_id: str,
    constraint_hours: float,
    start_time: str,
    end_time: str,
    tph: float,
    sequence_priority: int
  }]
  """
  
production_analyze_operations_efficiency(production_order_id)
  """Compares actual vs. planned constraint time.
  
  Identifies waste at the bottleneck.
  
  Returns: {
    production_order_id: str,
    planned_constraint_hours: float,
    actual_constraint_hours: float,
    variance_hours: float,
    efficiency_pct: float,
    waste_analysis: str
  }
  """
```

### 5. Sales Analysis Functions (tag: `sales`)

```python
sales_order_profitability(sales_order_id)
  """Calculates contribution margin and constraint hours for order.
  
  Returns: {
    sales_order_id: str,
    total_revenue: float,
    total_variable_cost: float,
    contribution_margin: float,
    constraint_hours_required: float,
    tph: float,
    recommended: bool,
    recommendation_reason: str
  }
  """

sales_customer_tph_analysis(customer_id, start_date, end_date)
  """Identifies low-TPH customers consuming constraint capacity.
  
  Returns: {
    customer_id: str,
    customer_name: str,
    total_orders: int,
    total_contribution_margin: float,
    total_constraint_hours: float,
    average_tph: float,
    vs_company_average: float,
    rank_percentile: int
  }
  """
```

## Example Usage Flow

```python
# 1. Set up costs (one-time setup per item)
result = catalog_set_item_costs("DUCK-001", material_cost=5.50, labor_cost_per_hour=25.0)
# Returns: {"item_sku": "DUCK-001", "unit_price": 15.00, "variable_cost": 5.50, "contribution_margin": 9.50}

# 2. Identify constraint
bottleneck = constraint_identify_bottleneck("2026-01-01", "2026-02-28")
# Returns: {
#   "resource": "Assembly Station", 
#   "utilization_pct": 95, 
#   "hours_available": 480,
#   "hours_used": 456
# }

# 3. Calculate current TPH
current_tph = analytics_calculate_tph("2026-02-01", "2026-02-28", "Assembly Station")
# Returns: {
#   "tph": 187.50, 
#   "contribution_margin": 45000, 
#   "constraint_hours_used": 240,
#   "utilization_pct": 87.5
# }

# 4. Analyze by product (find low-TPH items)
product_tph = analytics_tph_by_product("2026-02-01", "2026-02-28")
# Returns: [
#   {"sku": "DUCK-001", "tph": 250.00, "margin": 5000, "hours": 20, "rank": 1},
#   {"sku": "DUCK-002", "tph": 125.00, "margin": 2500, "hours": 20, "rank": 2},  # ⚠️ LOW
#   {"sku": "DUCK-003", "tph": 312.50, "margin": 6250, "hours": 20, "rank": 0}
# ]

# 5. Check TPH trend (detect if flat while demand rises)
tph_trend = analytics_tph_trend("2025-08-01", "2026-02-28", period="month")
# Returns: [
#   {"period": "2025-08", "tph": 180.00, "demand_units": 1000, "utilization": 85},
#   {"period": "2025-09", "tph": 182.50, "demand_units": 1100, "utilization": 88},
#   {"period": "2026-01", "tph": 183.00, "demand_units": 1300, "utilization": 95},  # ⚠️ FLAT TPH
#   {"period": "2026-02", "tph": 181.00, "demand_units": 1400, "utilization": 97}   # ⚠️ DECLINING
# ]
# Analysis: TPH flat/declining while demand rising = value leaking

# 6. Optimize mix
optimal_mix = analytics_product_mix_optimization("2026-03-15", available_constraint_hours=160)
# Returns: {
#   "recommended_mix": [
#     {"sku": "DUCK-003", "tph": 312.50, "units": 100, "hours": 64, "margin": 31250},
#     {"sku": "DUCK-001", "tph": 250.00, "units": 120, "hours": 48, "margin": 30000},
#     {"sku": "DUCK-002", "tph": 125.00, "units": 96, "hours": 48, "margin": 12000}
#   ],
#   "total_projected_margin": 73250,
#   "total_constraint_hours": 160,
#   "optimization_notes": "Prioritized high-TPH products. Consider reviewing DUCK-002 pricing or costs."
# }

# 7. Analyze specific customer
customer_analysis = sales_customer_tph_analysis("CUST-001", "2026-01-01", "2026-02-28")
# Returns: {
#   "customer_id": "CUST-001",
#   "customer_name": "Big Retailer",
#   "average_tph": 98.50,
#   "vs_company_average": -45.2,  # 45% below average
#   "rank_percentile": 15  # Bottom 15% of customers by TPH
# }
# Action: Discuss pricing or product mix with this customer

# 8. Review constraint schedule
schedule = production_get_constraint_schedule("2026-03-01", "2026-03-07")
# Returns: [
#   {"order": "MO-001", "item": "DUCK-002", "tph": 125, "hours": 8, "start": "2026-03-01 08:00"},
#   {"order": "MO-002", "item": "DUCK-003", "tph": 312, "hours": 12, "start": "2026-03-01 16:00"},
#   ...
# ]
# Analysis: Low-TPH work scheduled before high-TPH work = poor sequencing
```

## Key Questions TPH Analysis Answers

1. **"What's our current TPH?"**
   - Use: `analytics_calculate_tph()`
   - Baseline metric for system productivity

2. **"Which products have the highest TPH?"**
   - Use: `analytics_tph_by_product()`
   - Identify products to prioritize in production

3. **"Is our TPH improving or declining?"**
   - Use: `analytics_tph_trend()`
   - Detect value leakage over time

4. **"Which customers are consuming constraint time with low-margin orders?"**
   - Use: `sales_customer_tph_analysis()`
   - Guide pricing negotiations and customer mix

5. **"What's the optimal product mix to maximize throughput?"**
   - Use: `analytics_product_mix_optimization()`
   - Drive S&OP decisions

6. **"Are we scheduling work efficiently at the bottleneck?"**
   - Use: `production_get_constraint_schedule()`
   - Identify sequencing improvements

7. **"Is this sales order worth accepting?"**
   - Use: `sales_order_profitability()`
   - Real-time decision support for sales team

## Implementation Priority

### Phase 1 (Core Foundation)
**Goal: Calculate basic TPH**
- Schema changes (resources, costs, constraint tracking)
- `constraint_identify_bottleneck`
- `catalog_set_item_costs`
- `catalog_get_item_margins`
- `analytics_calculate_tph`

### Phase 2 (Analysis)
**Goal: Identify improvement opportunities**
- `analytics_tph_by_product`
- `analytics_tph_trend`
- `production_get_constraint_schedule`
- `sales_order_profitability`

### Phase 3 (Optimization)
**Goal: Actionable recommendations**
- `analytics_product_mix_optimization`
- `sales_customer_tph_analysis`
- `production_analyze_operations_efficiency`

## Integration with Existing MCP Tools

### Data Sources
- `production_get_order` - Extract constraint time from operations
- `catalog_get_item` - Enrich with pricing data
- `sales_get_order` - Link revenue to constraint usage
- `stats_get_summary` - Aggregate production volumes

### Agent Prompts
**Sales Agent:**
- Use `sales_order_profitability()` before quoting
- Alert on low-TPH customers via `sales_customer_tph_analysis()`

**Production Agent:**
- Prioritize high-TPH work via `production_get_constraint_schedule()`
- Report TPH trends to identify process degradation

## Expected Outcomes

1. **Visibility**: Clear metric showing bottleneck productivity
2. **Mix Optimization**: Data-driven product prioritization
3. **Pricing Insights**: Identify underpriced products consuming constraint time
4. **Customer Analysis**: Focus on high-value customers
5. **S&OP Alignment**: Link production planning to financial impact
6. **Early Warning**: Detect value leakage before it impacts bottom line

---

**Document Status:** Proposal  
**Created:** 2026-02-28  
**Next Steps:** Review with team, prioritize implementation phases
