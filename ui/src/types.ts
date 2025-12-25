export type Customer = {
  id: string
  name: string
  company?: string
  email?: string
  city?: string
}

export type CustomerDetail = Customer & {
  sales_orders?: Array<{
    sales_order_id: string
    status: string
    created_at?: string
    requested_delivery_date?: string
  }>
  shipments?: Array<{
    id: string
    status: string
    planned_departure?: string
    planned_arrival?: string
    sales_order_id?: string
  }>
}

export type Item = {
  id: string
  sku: string
  name: string
  type: string
  on_hand_total?: number
  reserved_total?: number
  available_total?: number
  unit_price?: number
  uom?: string
  reorder_qty?: number
  recipes?: Array<{
    id: string
    output_qty: number
    production_time_hours: number
    ingredient_count: number
    operation_count: number
  }>
  used_in_recipes?: Array<{
    recipe_id: string
    output_sku: string
    output_name: string
    qty_per_batch: number
  }>
  stock?: StockSummary
}

export type StockSummary = {
  item_id: string
  on_hand_total: number
  reserved_total: number
  available_total: number
  by_location: Array<{ id: string; warehouse: string; location: string; on_hand: number; reserved: number; available: number }>
}

export type Stock = {
  id: string
  item_id: string
  item_sku: string
  item_name: string
  item_type: string
  warehouse: string
  location: string
  on_hand: number
  reserved: number
  available: number
}

export type SalesOrder = {
  sales_order_id: string
  customer_id?: string
  customer_name?: string
  customer_company?: string
  created_at?: string
  summary: string
  fulfillment_state?: string
  lines?: Array<{ sku: string; qty: number }>
  status?: string
  total?: number
  currency?: string
}

export type SalesOrderDetail = {
  sales_order: Record<string, any>
  lines: Array<{ sku: string; qty: number }>
  pricing: any
  shipments: Shipment[]
}

export type Shipment = {
  id: string
  status: string
  planned_departure?: string
  planned_arrival?: string
  tracking_ref?: string
  sales_order_id?: string
  sales_orders?: Array<{
    sales_order_id: string
    customer_id: string
    customer_name: string
    customer_company?: string
    status: string
  }>
}

export type ProductionOrder = {
  id: string
  item_id: string
  item_name?: string
  item_sku?: string
  item_type?: string
  recipe_id?: string
  qty_planned: number
  qty_completed: number
  qty_produced?: number
  current_operation?: string
  status?: string
  eta_start?: string
  eta_finish?: string
  eta_ship?: string
  parent_production_order_id?: string
  notes?: string
  recipe?: Recipe
}

export type Recipe = {
  id: string
  output_item_id: string
  output_sku?: string
  output_name?: string
  output_type?: string
  output_qty: number
  production_time_hours: number
  ingredients?: RecipeIngredient[]
  operations?: RecipeOperation[]
}

export type RecipeIngredient = {
  recipe_id: string
  seq: number
  ingredient_item_id: string
  ingredient_sku?: string
  ingredient_name?: string
  ingredient_uom?: string
  qty_per_batch: number
}

export type RecipeOperation = {
  recipe_id: string
  seq: number
  operation_name: string
  duration_hours: number
}

export type Supplier = {
  id: string
  name: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  purchase_orders?: PurchaseOrder[]
}

export type PurchaseOrder = {
  id: string
  supplier_id: string
  supplier_name?: string
  item_id: string
  item_sku?: string
  item_name?: string
  item_type?: string
  uom?: string
  qty: number
  status: string
  expected_delivery?: string
  contact_name?: string
  contact_email?: string
}

export type QuoteOption = {
  option_id: string
  summary: string
  lines: Array<{ sku: string; qty: number; source: string }>
  can_arrive_by: string
  notes?: string
}
