import { useEffect, useState } from 'react'
import './index.css'
import { Layout } from './components/Layout'
import { Card } from './components/Card'
import { Table } from './components/Table'
import { Badge } from './components/Badge'
import { api } from './api'
import { Customer, Item, SalesOrder, SalesOrderDetail, StockSummary, Shipment, QuoteOption } from './types'

function SectionHeading({ id, title }: { id: string; title: string }) {
  return (
    <div id={id} className="flex items-center justify-between">
      <div className="text-lg font-semibold text-slate-800">{title}</div>
    </div>
  )
}

type ViewPage = 'home' | 'customers' | 'items' | 'orders' | 'shipments' | 'quotes'
type ViewState = { page: ViewPage; id?: string }

function parseHash(): ViewState {
  if (typeof window === 'undefined') return { page: 'home' }
  const hash = window.location.hash.replace(/^#/, '')
  const parts = hash.split('/').filter(Boolean)
  const page = (parts[0] as ViewPage) || 'home'
  const id = parts[1] ? decodeURIComponent(parts.slice(1).join('/')) : undefined
  const allowed: ViewPage[] = ['home', 'customers', 'items', 'orders', 'shipments', 'quotes']
  return { page: allowed.includes(page) ? page : 'home', id }
}

function setHash(page: ViewPage, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

export default function App() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [orders, setOrders] = useState<SalesOrder[]>([])
  const [selectedOrder, setSelectedOrder] = useState<SalesOrderDetail | null>(null)
  const [stock, setStock] = useState<StockSummary | null>(null)
  const [shipments, setShipments] = useState<Shipment[]>([])
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null)
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)
  const [quoteOptions, setQuoteOptions] = useState<QuoteOption[] | null>(null)
  const [quoteSku, setQuoteSku] = useState('ELVIS-DUCK-20CM')
  const [quoteQty, setQuoteQty] = useState(24)
  const [view, setView] = useState<ViewState>(() => parseHash())
  const [apiError, setApiError] = useState<string | null>(null)

  const handleApiError = (err: unknown) => {
    console.error(err)
    setApiError('API unavailable. Start the backend on http://127.0.0.1:8000 and refresh.')
  }

  useEffect(() => {
    api.customers().then((res) => setCustomers(res.customers || [])).catch(handleApiError)
    api.items(true).then((res) => setItems(res.items || [])).catch(handleApiError)
    api.salesOrders().then((res) => setOrders(res.sales_orders || [])).catch(handleApiError)
    api.shipments().then((res) => setShipments(res.shipments || [])).catch(handleApiError)
  }, [])

  useEffect(() => {
    const handler = () => setView(parseHash())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const loadOrder = (id: string) => {
    api.salesOrder(id).then((res) => setSelectedOrder(res as SalesOrderDetail)).catch(handleApiError)
  }

  const loadStock = (sku: string) => {
    api.stock(sku).then((res) => setStock(res as StockSummary)).catch(handleApiError)
  }

  const loadShipment = (id: string) => {
    api.shipment(id).then((res) => setSelectedShipment(res as Shipment)).catch(handleApiError)
  }

  const loadQuotes = () => {
    api.quote(quoteSku, quoteQty).then((res) => setQuoteOptions(res.options || [])).catch(handleApiError)
  }

  useEffect(() => {
    if (view.page === 'orders') {
      if (view.id) {
        loadOrder(view.id)
      } else {
        setSelectedOrder(null)
      }
    }
    if (view.page === 'shipments') {
      if (view.id) {
        loadShipment(view.id)
      } else {
        setSelectedShipment(null)
      }
    }
    if (view.page === 'items') {
      if (view.id) {
        loadStock(view.id)
      }
    }
    if (view.page === 'customers') {
      if (view.id) {
        setSelectedCustomer(customers.find((c) => c.id === view.id) || null)
      } else {
        setSelectedCustomer(null)
      }
    }
    if (view.page !== 'items') {
      setStock(null)
    }
  }, [view, customers])

  const Nav = () => (
    <div className="flex gap-3 text-sm text-slate-700">
      {(
        [
          { page: 'home', label: 'Overview' },
          { page: 'customers', label: 'Customers' },
          { page: 'items', label: 'Items' },
          { page: 'orders', label: 'Sales Orders' },
          { page: 'shipments', label: 'Shipments' },
          { page: 'quotes', label: 'Quotes' },
        ] as Array<{ page: ViewPage; label: string }>
      ).map((link) => (
        <button
          key={link.page}
          className={`px-3 py-1 rounded ${view.page === link.page ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          onClick={() => setHash(link.page)}
        >
          {link.label}
        </button>
      ))}
    </div>
  )

  return (
    <Layout>
      <div className="space-y-6">
        {apiError ? (
          <div className="flex items-start justify-between gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <div>
              <div className="font-semibold">API unavailable</div>
              <div className="text-amber-700">Start the backend on http://127.0.0.1:8000 so the UI can load data.</div>
            </div>
            <button className="text-amber-700 hover:underline" onClick={() => setApiError(null)}>
              Dismiss
            </button>
          </div>
        ) : null}

        <Nav />

        {view.page === 'home' && (
          <section>
            <SectionHeading id="overview" title="Overview" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
              <Card title="Customers">
                <div className="text-2xl font-semibold text-slate-800">{customers.length}</div>
                <div className="text-sm text-slate-600 mb-2">total customers</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('customers')}>
                  View customers
                </button>
              </Card>
              <Card title="Items in stock">
                <div className="text-2xl font-semibold text-slate-800">{items.length}</div>
                <div className="text-sm text-slate-600 mb-2">tracked SKUs</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('items')}>
                  View items
                </button>
              </Card>
              <Card title="Sales orders">
                <div className="text-2xl font-semibold text-slate-800">{orders.length}</div>
                <div className="text-sm text-slate-600 mb-2">orders loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('orders')}>
                  View orders
                </button>
              </Card>
              <Card title="Shipments">
                <div className="text-2xl font-semibold text-slate-800">{shipments.length}</div>
                <div className="text-sm text-slate-600 mb-2">shipments loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('shipments')}>
                  View shipments
                </button>
              </Card>
              <Card title="Quotes">
                <div className="text-sm text-slate-600 mb-2">Compute scenarios quickly.</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('quotes')}>
                  Get a quote
                </button>
              </Card>
            </div>
          </section>
        )}

        {view.page === 'customers' && (
          <section>
            <SectionHeading id="customers" title="Customers" />
            <Card>
              <Table
                rows={customers}
                columns={[
                  { key: 'id', label: 'ID' },
                  {
                    key: 'name',
                    label: 'Name',
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('customers', row.id)}>
                        {row.name}
                      </button>
                    ),
                  },
                  { key: 'company', label: 'Company' },
                  { key: 'email', label: 'Email' },
                  { key: 'city', label: 'City' },
                ]}
              />
              {view.id ? (
                <div className="mt-4 space-y-2 text-sm text-slate-700">
                  <div className="font-semibold">Customer {selectedCustomer?.name || view.id}</div>
                  <div className="text-slate-600">Company: {selectedCustomer?.company || '—'}</div>
                  <div className="text-slate-600">Email: {selectedCustomer?.email || '—'}</div>
                  <div className="text-slate-600">City: {selectedCustomer?.city || '—'}</div>
                  <div className="text-xs text-slate-500">More customer details will appear here as we extend the MCP surface.</div>
                </div>
              ) : null}
            </Card>
          </section>
        )}

        {view.page === 'items' && (
          <section>
            <SectionHeading id="items" title="Items (in stock)" />
            <Card>
              <Table
                rows={items}
                columns={[
                  { key: 'sku', label: 'SKU' },
                  { key: 'name', label: 'Name' },
                  { key: 'unit_price', label: 'Unit price', render: (row) => (row.unit_price != null ? `${row.unit_price} €` : '—') },
                  { key: 'type', label: 'Type' },
                  { key: 'available_total', label: 'Available' },
                  {
                    key: 'id',
                    label: 'Stock',
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('items', row.sku)}>
                        View item
                      </button>
                    ),
                  },
                ]}
              />
              {view.id ? (
                <div className="mt-4 space-y-2 text-sm text-slate-700">
                  <div className="font-semibold">Item {view.id}</div>
                  <div className="text-slate-600 text-xs">{items.find((i) => i.sku === view.id)?.name || 'Loading item details…'}</div>
                  <div className="text-slate-600 text-xs">Unit price: {(() => {
                    const item = items.find((i) => i.sku === view.id)
                    return item?.unit_price != null ? `${item.unit_price} €` : '—'
                  })()}</div>
                  {stock ? (
                    <div className="space-y-2">
                      <div className="flex gap-3 text-slate-600">
                        <span>On hand: {stock.on_hand_total}</span>
                        <span>Reserved: {stock.reserved_total}</span>
                        <span>Available: {stock.available_total}</span>
                      </div>
                      <Table
                        rows={stock.by_location as any}
                        columns={[
                          { key: 'warehouse', label: 'Wh' },
                          { key: 'location', label: 'Loc' },
                          { key: 'on_hand', label: 'On hand' },
                          { key: 'reserved', label: 'Reserved' },
                          { key: 'available', label: 'Available' },
                        ]}
                      />
                    </div>
                  ) : (
                    <div className="text-slate-500">Loading stock…</div>
                  )}
                </div>
              ) : null}
            </Card>
          </section>
        )}

        {view.page === 'orders' && (
          <section>
            <SectionHeading id="orders" title="Sales Orders" />
            <Card>
              <Table
                rows={orders}
                columns={[
                  { key: 'sales_order_id', label: 'Order' },
                  { key: 'summary', label: 'Summary' },
                  { key: 'fulfillment_state', label: 'Status', render: (row) => <Badge>{row.fulfillment_state || row.status}</Badge> },
                  { key: 'created_at', label: 'Created' },
                  {
                    key: 'status',
                    label: 'Detail',
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('orders', row.sales_order_id)}>
                        View
                      </button>
                    ),
                  },
                ]}
              />
              {view.id && !selectedOrder ? <div className="mt-3 text-sm text-slate-500">Loading order…</div> : null}
              {selectedOrder ? (
                <div className="mt-4 space-y-3 text-sm text-slate-800">
                  <div className="font-semibold">Order {selectedOrder.sales_order.id}</div>
                  <div className="grid grid-cols-2 gap-3">
                    <Card title="Lines">
                      <Table rows={selectedOrder.lines as any} columns={[{ key: 'sku', label: 'SKU' }, { key: 'qty', label: 'Qty' }]} />
                    </Card>
                    <Card title="Pricing">
                      <div>Total: {selectedOrder.pricing.total}</div>
                      <div className="text-slate-600 text-xs">Currency: {selectedOrder.pricing.currency}</div>
                    </Card>
                  </div>
                  <Card title="Shipments">
                    {selectedOrder.shipments?.length ? (
                      <Table
                        rows={selectedOrder.shipments as any}
                        columns={[
                          { key: 'id', label: 'Shipment' },
                          { key: 'status', label: 'Status' },
                          { key: 'planned_departure', label: 'Departure' },
                          { key: 'planned_arrival', label: 'Arrival' },
                        ]}
                      />
                    ) : (
                      <div className="text-slate-500">No shipments linked.</div>
                    )}
                  </Card>
                </div>
              ) : null}
            </Card>
          </section>
        )}

        {view.page === 'shipments' && (
          <section>
            <SectionHeading id="shipments" title="Shipments" />
            <Card>
              <Table
                rows={shipments}
                columns={[
                  { key: 'id', label: 'Shipment' },
                  { key: 'status', label: 'Status' },
                  { key: 'planned_departure', label: 'Departure' },
                  { key: 'planned_arrival', label: 'Arrival' },
                  {
                    key: 'tracking_ref',
                    label: 'Detail',
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('shipments', row.id)}>
                        View
                      </button>
                    ),
                  },
                ]}
              />
              {view.id && !selectedShipment ? <div className="mt-3 text-sm text-slate-500">Loading shipment…</div> : null}
              {selectedShipment ? (
                <div className="mt-3 text-sm text-slate-800 space-y-1">
                  <div className="font-semibold">Shipment {selectedShipment.id}</div>
                  <div>Status: {selectedShipment.status}</div>
                  <div>Depart: {selectedShipment.planned_departure}</div>
                  <div>Arrive: {selectedShipment.planned_arrival}</div>
                  {selectedShipment.tracking_ref ? <div>Tracking: {selectedShipment.tracking_ref}</div> : null}
                </div>
              ) : null}
            </Card>
          </section>
        )}

        {view.page === 'quotes' && (
          <section>
            <SectionHeading id="quotes" title="Quotes" />
            <Card>
              <div className="flex gap-3 items-end text-sm">
                <div>
                  <label className="block text-xs text-slate-500">SKU</label>
                  <input
                    className="border border-slate-200 rounded px-2 py-1"
                    value={quoteSku}
                    onChange={(e) => setQuoteSku(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-500">Qty</label>
                  <input
                    type="number"
                    className="border border-slate-200 rounded px-2 py-1 w-24"
                    value={quoteQty}
                    onChange={(e) => setQuoteQty(parseInt(e.target.value, 10) || 0)}
                  />
                </div>
                <button className="bg-brand-600 text-white px-3 py-2 rounded shadow" onClick={loadQuotes}>
                  Get options
                </button>
              </div>
              {quoteOptions ? (
                <div className="mt-3 space-y-2">
                  {quoteOptions.map((opt) => (
                    <div key={opt.option_id} className="border border-slate-200 rounded p-3 bg-slate-50">
                      <div className="font-semibold">{opt.summary}</div>
                      <div className="text-xs text-slate-600">ETA: {opt.can_arrive_by}</div>
                      <div className="text-xs text-slate-600">Lines: {opt.lines.map((l) => `${l.qty} x ${l.sku} (${l.source})`).join(', ')}</div>
                      {opt.notes ? <div className="text-xs text-slate-500">{opt.notes}</div> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-500 mt-2">Enter SKU and qty to see options.</div>
              )}
            </Card>
          </section>
        )}
      </div>
    </Layout>
  )
}
