import { Customer, Item, SalesOrder, SalesOrderDetail, Shipment, StockSummary, QuoteOption, ProductionOrder, Recipe, Supplier, PurchaseOrder, Email, EmailDetail, Invoice, InvoiceDetail, Quote, QuoteDetail, WorkCenter, WorkCenterDetail, ActivityLogEntry, DashboardData } from './types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  const text = await res.text()
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${text || ''}`)
  }
  if (!text) {
    throw new Error('Empty response')
  }
  try {
    return JSON.parse(text)
  } catch (err) {
    throw new Error(`Invalid JSON: ${text.slice(0, 200)}`)
  }
}

export const api = {
  customers: (q?: { name?: string }) =>
    fetchJson<{ customers: Customer[] }>(`/customers${q?.name ? `?name=${encodeURIComponent(q.name)}` : ''}`),
  customerDetail: (id: string) => fetchJson<import('./types').CustomerDetail>(`/customers/${encodeURIComponent(id)}`),
  items: (inStockOnly = false) =>
    fetchJson<{ items: Item[] }>(`/items${inStockOnly ? '?in_stock_only=1' : ''}`),
  itemDetail: (sku: string) => fetchJson<Item>(`/items/${encodeURIComponent(sku)}`),
  stock: (sku: string) => fetchJson<StockSummary>(`/items/${encodeURIComponent(sku)}/stock`),
  stockList: () => fetchJson<{ stock: import('./types').Stock[] }>(`/stock`),
  stockDetail: (id: string) => fetchJson<import('./types').Stock>(`/stock/${encodeURIComponent(id)}`),
  salesOrders: () => fetchJson<{ sales_orders: SalesOrder[] }>(`/sales-orders?limit=50`),
  salesOrder: (id: string) => fetchJson<SalesOrderDetail>(`/sales-orders/${encodeURIComponent(id)}`),
  shipment: (id: string) => fetchJson<Shipment>(`/shipments/${encodeURIComponent(id)}`),
  shipments: () => fetchJson<{ shipments: Shipment[] }>(`/shipments`),
  productionOrders: (q?: { sales_order_id?: string }) => {
    const params = new URLSearchParams()
    params.set('limit', '100')
    if (q?.sales_order_id) params.set('sales_order_id', q.sales_order_id)
    const query = params.toString()
    return fetchJson<{ production_orders: ProductionOrder[] }>(`/production-orders?${query}`)
  },
  productionOrder: (id: string) => fetchJson<ProductionOrder>(`/production-orders/${encodeURIComponent(id)}`),
  workCenters: () => fetchJson<{ work_centers: WorkCenter[] }>(`/work-centers`),
  workCenterDetail: (id: string) => fetchJson<WorkCenterDetail>(`/work-centers/${encodeURIComponent(id)}`),
  quote: (sku: string, qty: number) => fetchJson<{ options: QuoteOption[] }>(`/quote-options?sku=${encodeURIComponent(sku)}&qty=${qty}`),
  recipes: (outputItemSku?: string) =>
    fetchJson<{ recipes: Recipe[] }>(`/recipes${outputItemSku ? `?output_item_sku=${encodeURIComponent(outputItemSku)}` : ''}`),
  recipeDetail: (id: string) => fetchJson<Recipe>(`/recipes/${encodeURIComponent(id)}`),
  suppliers: () => fetchJson<{ suppliers: Supplier[] }>(`/suppliers`),
  supplierDetail: (id: string) => fetchJson<Supplier>(`/suppliers/${encodeURIComponent(id)}`),
  purchaseOrders: (status?: string) =>
    fetchJson<{ purchase_orders: PurchaseOrder[] }>(`/purchase-orders${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  purchaseOrderDetail: (id: string) => fetchJson<PurchaseOrder>(`/purchase-orders/${encodeURIComponent(id)}`),
  simulationTime: () => fetchJson<{ current_time: string }>(`/simulation/time`),
  emails: (q?: { customer_id?: string; sales_order_id?: string; status?: string }) => {
    const params = new URLSearchParams()
    if (q?.customer_id) params.set('customer_id', q.customer_id)
    if (q?.sales_order_id) params.set('sales_order_id', q.sales_order_id)
    if (q?.status) params.set('status', q.status)
    const query = params.toString()
    return fetchJson<{ emails: Email[] }>(`/emails${query ? `?${query}` : ''}`)
  },
  emailDetail: (id: string) => fetchJson<EmailDetail>(`/emails/${encodeURIComponent(id)}`),
  invoices: (q?: { customer_id?: string; sales_order_id?: string; status?: string }) => {
    const params = new URLSearchParams()
    if (q?.customer_id) params.set('customer_id', q.customer_id)
    if (q?.sales_order_id) params.set('sales_order_id', q.sales_order_id)
    if (q?.status) params.set('status', q.status)
    const query = params.toString()
    return fetchJson<{ invoices: Invoice[] }>(`/invoices${query ? `?${query}` : ''}`)
  },
  invoiceDetail: (id: string) => fetchJson<InvoiceDetail>(`/invoices/${encodeURIComponent(id)}`),
  quotes: (q?: { customer_id?: string; status?: string; show_superseded?: boolean }) => {
    const params = new URLSearchParams()
    if (q?.customer_id) params.set('customer_id', q.customer_id)
    if (q?.status) params.set('status', q.status)
    if (q?.show_superseded) params.set('show_superseded', 'true')
    const query = params.toString()
    return fetchJson<{ quotes: Quote[] }>(`/quotes${query ? `?${query}` : ''}`)
  },
  quoteDetail: (id: string) => fetchJson<QuoteDetail>(`/quotes/${encodeURIComponent(id)}`),
  spotlight: () => fetchJson<{
    customers: { label: string; sublabel: string; href: string }[]
    quotes: { label: string; sublabel: string; href: string }[]
    sales_orders: { label: string; sublabel: string; href: string }[]
    shipments: { label: string; sublabel: string; href: string }[]
    invoices: { label: string; sublabel: string; href: string }[]
    emails: { label: string; sublabel: string; href: string }[]
    stock: { label: string; sublabel: string; href: string }[]
    production_orders: { label: string; sublabel: string; href: string }[]
    purchase_orders: { label: string; sublabel: string; href: string }[]
  }>(`/stats/spotlight`),
  activityLog: (params?: { limit?: number; offset?: number; category?: string; action?: string; entity_type?: string; entity_id?: string; since?: string; until?: string }) => {
    const p = new URLSearchParams()
    if (params?.limit) p.set('limit', String(params.limit))
    if (params?.offset) p.set('offset', String(params.offset))
    if (params?.category) p.set('category', params.category)
    if (params?.action) p.set('action', params.action)
    if (params?.entity_type) p.set('entity_type', params.entity_type)
    if (params?.entity_id) p.set('entity_id', params.entity_id)
    if (params?.since) p.set('since', params.since)
    if (params?.until) p.set('until', params.until)
    const q = p.toString()
    return fetchJson<{ entries: ActivityLogEntry[]; total: number; limit: number; offset: number }>(`/activity-log${q ? `?${q}` : ''}`)
  },
  activitySummary: (params?: { since?: string; until?: string }) => {
    const p = new URLSearchParams()
    if (params?.since) p.set('since', params.since)
    if (params?.until) p.set('until', params.until)
    const q = p.toString()
    return fetchJson<{ date: string; category: string; action: string; count: number }[]>(`/activity-log/summary${q ? `?${q}` : ''}`)
  },
  dashboard: (params?: { since?: string; until?: string }) => {
    const p = new URLSearchParams()
    if (params?.since) p.set('since', params.since)
    if (params?.until) p.set('until', params.until)
    const q = p.toString()
    return fetchJson<DashboardData>(`/dashboard${q ? `?${q}` : ''}`)
  },
}
