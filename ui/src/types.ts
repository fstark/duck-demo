export type Customer = {
  id: string
  name: string
  company?: string
  email?: string
  phone?: string
  address_line1?: string
  address_line2?: string
  city?: string
  postal_code?: string
  country?: string
  tax_id?: string
  payment_terms?: number
  currency?: string
  notes?: string
  created_at?: string
}

export type CustomerDetail = Customer & {
  sales_orders?: Array<{
    sales_order_id: string
    status: string
    total?: number
    currency?: string
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
  cost_price?: number
  uom?: string
  reorder_qty?: number
  default_supplier_id?: string
  image_url?: string
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
  production_orders?: ProductionOrder[]
  purchase_orders?: PurchaseOrder[]
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
  customer?: Record<string, any>
  lines: Array<{ sku: string; qty: number; unit_price?: number; line_total?: number }>
  pricing: any
  shipments: Shipment[]
}

export type Quote = {
  id: string
  customer_id: string
  customer_name?: string
  customer_company?: string
  revision_number: number
  supersedes_quote_id?: string
  status: string
  subtotal: number
  tax: number
  total: number
  valid_until?: string
  created_at?: string
  sent_at?: string
}

export type QuoteDetail = {
  quote: Record<string, any>
  lines: Array<{
    sku: string
    item_name?: string
    qty: number
    unit_price: number
    line_total: number
  }>
  newer_revision?: { id: string; ui_url?: string }
  revisions?: Array<{
    id: string
    revision_number: number
    status: string
    created_at?: string
  }>
}

export type Shipment = {
  id: string
  status: string
  ship_from_warehouse?: string
  ship_to_line1?: string
  ship_to_line2?: string
  ship_to_postal_code?: string
  ship_to_city?: string
  ship_to_country?: string
  planned_departure?: string
  planned_arrival?: string
  tracking_ref?: string
  dispatched_at?: string
  delivered_at?: string
  sales_order_id?: string
  sales_orders?: Array<{
    sales_order_id: string
    customer_id: string
    customer_name: string
    customer_company?: string
    status: string
  }>
  lines?: Array<{
    id: string
    item_id: string
    item_sku: string
    item_name: string
    uom?: string
    qty: number
  }>
}

export type ProductionOrder = {
  id: string
  item_id: string
  item_name?: string
  item_sku?: string
  item_type?: string
  recipe_id?: string
  sales_order_id?: string
  status?: string
  current_operation?: string
  qty_produced?: number
  started_at?: string
  completed_at?: string
  eta_finish?: string
  eta_ship?: string
  parent_production_order_id?: string
  notes?: string
  recipe?: Recipe
  operations?: ProductionOperation[]
}

export type ProductionOperation = {
  id: string
  production_order_id: string
  recipe_operation_id: string
  sequence_order: number
  operation_name: string
  duration_hours: number
  work_center?: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  started_at?: string
  completed_at?: string
}

export type WorkCenter = {
  id: string
  name: string
  max_concurrent: number
  description?: string
  in_progress: number
  pending: number
  completed: number
  utilization: number
  ui_url?: string
}

export type WorkCenterDetail = WorkCenter & {
  operations: Array<{
    id: string
    production_order_id: string
    operation_name: string
    duration_hours: number
    status: 'pending' | 'in_progress' | 'completed'
    started_at?: string
    completed_at?: string
    item_id: string
    item_name?: string
    item_sku?: string
    production_order_ui_url?: string
  }>
}

export type Recipe = {
  id: string
  output_item_id: string
  output_sku?: string
  output_name?: string
  output_type?: string
  output_qty: number
  output_uom?: string
  production_time_hours: number
  notes?: string
  ingredients?: RecipeIngredient[]
  operations?: RecipeOperation[]
}

export type RecipeIngredient = {
  recipe_id: string
  sequence_order: number
  input_item_id: string
  ingredient_sku?: string
  ingredient_name?: string
  ingredient_uom?: string
  input_qty: number
  input_uom: string
}

export type RecipeOperation = {
  recipe_id: string
  sequence_order: number
  operation_name: string
  duration_hours: number
  work_center?: string
}

export type Supplier = {
  id: string
  name: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  lead_time_days?: number
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
  unit_price?: number
  total?: number
  currency?: string
  status: string
  ordered_at?: string
  expected_delivery?: string
  received_at?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
}

export type Email = {
  id: string
  customer_id: string
  sales_order_id?: string
  recipient_email: string
  recipient_name?: string
  subject: string
  body: string
  status: 'draft' | 'sent'
  created_at: string
  modified_at: string
  sent_at?: string
}

export type EmailDetail = {
  email: Email
  customer?: {
    id: string
    name: string
    company?: string
    email?: string
    city?: string
    ui_url?: string
  }
  sales_order?: {
    id: string
    status?: string
    created_at?: string
    ui_url?: string
  }
}

export type QuoteOption = {
  option_id: string
  summary: string
  lines: Array<{ sku: string; qty: number; source: string }>
  can_arrive_by: string
  notes?: string
}

export type Invoice = {
  id: string
  sales_order_id: string
  customer_id: string
  customer_name?: string
  customer_company?: string
  invoice_date?: string
  due_date?: string
  subtotal: number
  discount: number
  shipping: number
  tax: number
  total: number
  currency: string
  status: 'draft' | 'issued' | 'paid' | 'overdue'
  issued_at?: string
  paid_at?: string
  created_at: string
  ui_url?: string
}

export type InvoiceDetail = {
  invoice: Invoice
  customer?: {
    id: string
    name: string
    company?: string
    email?: string
    city?: string
    ui_url?: string
  }
  sales_order?: {
    id: string
    status?: string
    created_at?: string
    ui_url?: string
  }
  lines: Array<{ sku: string; qty: number; unit_price?: number; line_total?: number }>
  payments: Array<{
    id: string
    invoice_id: string
    amount: number
    payment_method: string
    payment_date: string
    reference?: string
    notes?: string
    created_at: string
  }>
  amount_paid: number
  balance_due: number
}

// ---------------------------------------------------------------------------
// Activity Log & Dashboard
// ---------------------------------------------------------------------------

export type ActivityLogEntry = {
  id: string
  timestamp: string
  actor: string
  category: string
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown> | null
}

export type DashboardData = {
  status_distributions: Record<string, { status: string; count: number }[]>
  kpis: {
    open_orders: number
    in_progress_mos: number
    pending_shipments: number
    overdue_invoices: number
    total_revenue: number
  }
  recent_activity: ActivityLogEntry[]
  daily_volumes: { date: string; orders: number; shipped: number; invoiced: number }[]
}

