import { Customer, Item, SalesOrder, SalesOrderDetail, Shipment, StockSummary, QuoteOption } from './types'

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
  items: (inStockOnly = false) =>
    fetchJson<{ items: Item[] }>(`/items${inStockOnly ? '?in_stock_only=1' : ''}`),
  stock: (sku: string) => fetchJson<StockSummary>(`/items/${encodeURIComponent(sku)}/stock`),
  salesOrders: () => fetchJson<{ sales_orders: SalesOrder[] }>(`/sales-orders?limit=50`),
  salesOrder: (id: string) => fetchJson<SalesOrderDetail>(`/sales-orders/${encodeURIComponent(id)}`),
  shipment: (id: string) => fetchJson<Shipment>(`/shipments/${encodeURIComponent(id)}`),
  shipments: () => fetchJson<{ shipments: Shipment[] }>(`/shipments`),
  quote: (sku: string, qty: number) => fetchJson<{ options: QuoteOption[] }>(`/quotes?sku=${encodeURIComponent(sku)}&qty=${qty}`),
}
