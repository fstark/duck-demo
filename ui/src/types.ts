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
  qty_planned: number
  qty_completed: number
  current_operation?: string
  eta_finish?: string
  eta_ship?: string
}

export type QuoteOption = {
  option_id: string
  summary: string
  lines: Array<{ sku: string; qty: number; source: string }>
  can_arrive_by: string
  notes?: string
}
