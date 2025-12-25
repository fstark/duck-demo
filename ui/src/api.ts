import { Customer, Item, SalesOrder, SalesOrderDetail, Shipment, StockSummary, QuoteOption, ProductionOrder, Recipe, Supplier, PurchaseOrder } from './types'

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
  productionOrders: () => fetchJson<{ production_orders: ProductionOrder[] }>(`/production-orders?limit=100`),
  productionOrder: (id: string) => fetchJson<ProductionOrder>(`/production-orders/${encodeURIComponent(id)}`),
  quote: (sku: string, qty: number) => fetchJson<{ options: QuoteOption[] }>(`/quotes?sku=${encodeURIComponent(sku)}&qty=${qty}`),
  recipes: (outputItemSku?: string) => 
    fetchJson<{ recipes: Recipe[] }>(`/recipes${outputItemSku ? `?output_item_sku=${encodeURIComponent(outputItemSku)}` : ''}`),
  recipeDetail: (id: string) => fetchJson<Recipe>(`/recipes/${encodeURIComponent(id)}`),
  suppliers: () => fetchJson<{ suppliers: Supplier[] }>(`/suppliers`),
  supplierDetail: (id: string) => fetchJson<Supplier>(`/suppliers/${encodeURIComponent(id)}`),
  purchaseOrders: (status?: string) => 
    fetchJson<{ purchase_orders: PurchaseOrder[] }>(`/purchase-orders${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  purchaseOrderDetail: (id: string) => fetchJson<PurchaseOrder>(`/purchase-orders/${encodeURIComponent(id)}`),
}
