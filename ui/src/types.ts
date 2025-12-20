export type Customer = {
  id: string
  name: string
  company?: string
  email?: string
  city?: string
}

export type Item = {
  id: string
  sku: string
  name: string
  type: string
  available_total?: number
  unit_price?: number
}

export type StockSummary = {
  item_id: string
  on_hand_total: number
  reserved_total: number
  available_total: number
  by_location: Array<{ warehouse: string; location: string; on_hand: number; reserved: number; available: number }>
}

export type SalesOrder = {
  sales_order_id: string
  created_at?: string
  summary: string
  fulfillment_state?: string
  lines?: Array<{ sku: string; qty: number }>
  status?: string
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
}

export type QuoteOption = {
  option_id: string
  summary: string
  lines: Array<{ sku: string; qty: number; source: string }>
  can_arrive_by: string
  notes?: string
}
