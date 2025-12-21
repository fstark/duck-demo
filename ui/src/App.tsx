import { useEffect, useState } from 'react'
import './index.css'
import { Layout } from './components/Layout'
import { Card } from './components/Card'
import { Table } from './components/Table'
import { Badge } from './components/Badge'
import { api } from './api'
import { Customer, Item, SalesOrder, SalesOrderDetail, StockSummary, Shipment, QuoteOption, ProductionOrder } from './types'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

type ViewPage = 'home' | 'customers' | 'items' | 'orders' | 'shipments' | 'quotes' | 'production'
type ViewState = { page: ViewPage; id?: string }

function SectionHeading({ id, title }: { id: string; title: string }) {
  return (
    <div id={id} className="flex items-center justify-between">
      <div className="text-lg font-semibold text-slate-800">{title}</div>
    </div>
  )
}

function parseHash(): ViewState {
  if (typeof window === 'undefined') return { page: 'home' }
  const hash = window.location.hash.replace(/^#/, '')
  const parts = hash.split('/').filter(Boolean)
  const page = (parts[0] as ViewPage) || 'home'
  const id = parts[1] ? decodeURIComponent(parts.slice(1).join('/')) : undefined
  const allowed: ViewPage[] = ['home', 'customers', 'items', 'orders', 'shipments', 'quotes', 'production']
  return { page: allowed.includes(page) ? page : 'home', id }
}

function setHash(page: ViewPage, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

function sortRows<T extends Record<string, any>>(rows: T[], state: SortState<T> | null) {
  if (!state) return rows
  const { key, dir } = state
  const sorted = [...rows].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') {
      return dir === 'asc' ? av - bv : bv - av
    }
    const compare = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' })
    return dir === 'asc' ? compare : -compare
  })
  return sorted
}

function nextSort<T>(prev: SortState<T> | null, key: keyof T, defaultDir: SortDir = 'asc'): SortState<T> {
  if (prev && prev.key === key) {
    return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
  }
  return { key, dir: defaultDir }
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
  const [productionOrders, setProductionOrders] = useState<ProductionOrder[]>([])
  const [selectedProductionOrder, setSelectedProductionOrder] = useState<ProductionOrder | null>(null)
  const [quoteOptions, setQuoteOptions] = useState<QuoteOption[] | null>(null)
  const [quoteSku, setQuoteSku] = useState('ELVIS-DUCK-20CM')
  const [quoteQty, setQuoteQty] = useState(24)
  const [view, setView] = useState<ViewState>(() => parseHash())
  const [apiError, setApiError] = useState<string | null>(null)
  const [customerSort, setCustomerSort] = useState<SortState<Customer> | null>(null)
  const [itemSort, setItemSort] = useState<SortState<Item> | null>({ key: 'type', dir: 'asc' })
  const [orderSort, setOrderSort] = useState<SortState<SalesOrder> | null>(null)
  const [shipmentSort, setShipmentSort] = useState<SortState<Shipment> | null>(null)
  const [productionSort, setProductionSort] = useState<SortState<ProductionOrder> | null>(null)

  const handleApiError = (err: unknown) => {
    console.error(err)
    setApiError('API unavailable. Start the backend on http://127.0.0.1:8000 and refresh.')
  }

  useEffect(() => {
    api.customers().then((res) => setCustomers(res.customers || [])).catch(handleApiError)
    api.items(false).then((res) => setItems(res.items || [])).catch(handleApiError)
    api.salesOrders().then((res) => setOrders(res.sales_orders || [])).catch(handleApiError)
    api.shipments().then((res) => setShipments(res.shipments || [])).catch(handleApiError)
    api.productionOrders().then((res) => setProductionOrders(res.production_orders || [])).catch(handleApiError)
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

  const loadProductionOrder = (id: string) => {
    api.productionOrder(id).then((res) => setSelectedProductionOrder(res as ProductionOrder)).catch(handleApiError)
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
    if (view.page === 'production') {
      if (view.id) {
        loadProductionOrder(view.id)
      } else {
        setSelectedProductionOrder(null)
      }
    }
    if (view.page !== 'items') {
      setStock(null)
    }
  }, [view, customers])

  const sortedCustomers = sortRows(customers, customerSort)
  const sortedItems = sortRows(items, itemSort)
  const sortedOrders = sortRows(orders, orderSort)
  const sortedShipments = sortRows(shipments, shipmentSort)
  const sortedProductionOrders = sortRows(productionOrders, productionSort)

  const Nav = () => (
    <div className="flex gap-3 text-sm text-slate-700">
      {(
        [
          { page: 'home', label: 'Overview' },
          { page: 'customers', label: 'Customers' },
          { page: 'items', label: 'Items' },
          { page: 'orders', label: 'Sales Orders' },
          { page: 'shipments', label: 'Shipments' },
          { page: 'production', label: 'Production' },
          { page: 'quotes', label: 'Quotes' },
        ] as Array<{ page: ViewPage; label: string }>
      ).map((link) => (
        <button
          key={link.page}
          className={`px-3 py-1 rounded ${view.page === link.page ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          onClick={() => setHash(link.page)}
          type="button"
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
            <button className="text-amber-700 hover:underline" onClick={() => setApiError(null)} type="button">
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
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('customers')} type="button">
                  View customers
                </button>
              </Card>
              <Card title="Items">
                <div className="text-2xl font-semibold text-slate-800">{items.length}</div>
                <div className="text-sm text-slate-600 mb-2">total items</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('items')} type="button">
                  View items
                </button>
              </Card>
              <Card title="Sales orders">
                <div className="text-2xl font-semibold text-slate-800">{orders.length}</div>
                <div className="text-sm text-slate-600 mb-2">orders loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('orders')} type="button">
                  View orders
                </button>
              </Card>
              <Card title="Shipments">
                <div className="text-2xl font-semibold text-slate-800">{shipments.length}</div>
                <div className="text-sm text-slate-600 mb-2">shipments loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('shipments')} type="button">
                  View shipments
                </button>
              </Card>
              <Card title="Production Orders">
                <div className="text-2xl font-semibold text-slate-800">{productionOrders.length}</div>
                <div className="text-sm text-slate-600 mb-2">production orders</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('production')} type="button">
                  View production
                </button>
              </Card>
              <Card title="Quotes">
                <div className="text-sm text-slate-600 mb-2">Compute scenarios quickly.</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('quotes')} type="button">
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
                rows={sortedCustomers}
                sortKey={customerSort?.key}
                sortDir={customerSort?.dir}
                onSort={(key) => setCustomerSort((prev) => nextSort(prev, key))}
                columns={[
                  {
                    key: 'id',
                    label: 'ID',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('customers', row.id)} type="button">
                        {row.id}
                      </button>
                    ),
                  },
                  {
                    key: 'name',
                    label: 'Name',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('customers', row.id)} type="button">
                        {row.name}
                      </button>
                    ),
                  },
                  { key: 'company', label: 'Company', sortable: true },
                  { key: 'email', label: 'Email', sortable: true },
                  { key: 'city', label: 'City', sortable: true },
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
            <SectionHeading id="items" title="Items" />
            <Card>
              <Table
                rows={sortedItems}
                sortKey={itemSort?.key}
                sortDir={itemSort?.dir}
                onSort={(key) => setItemSort((prev) => nextSort(prev, key))}
                columns={[
                  {
                    key: 'sku',
                    label: 'SKU',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('items', row.sku)} type="button">
                        {row.sku}
                      </button>
                    ),
                  },
                  {
                    key: 'name',
                    label: 'Name',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('items', row.sku)} type="button">
                        {row.name}
                      </button>
                    ),
                  },
                  {
                    key: 'unit_price',
                    label: 'Unit price',
                    sortable: true,
                    render: (row) => (row.unit_price != null ? `${row.unit_price} €` : '—'),
                  },
                  { key: 'type', label: 'Type', sortable: true },
                  { key: 'available_total', label: 'Available', sortable: true },
                ]}
              />
              {view.id ? (
                <div className="mt-4 space-y-2 text-sm text-slate-700">
                  <div className="font-semibold">Item {view.id}</div>
                  <div className="text-slate-600 text-xs">{items.find((i) => i.sku === view.id)?.name || 'Loading item details…'}</div>
                  <div className="text-slate-600 text-xs">
                    Unit price:{' '}
                    {(() => {
                      const item = items.find((i) => i.sku === view.id)
                      return item?.unit_price != null ? `${item.unit_price} €` : '—'
                    })()}
                  </div>
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
                rows={sortedOrders}
                sortKey={orderSort?.key}
                sortDir={orderSort?.dir}
                onSort={(key) => setOrderSort((prev) => nextSort(prev, key, key === 'created_at' ? 'desc' : 'asc'))}
                columns={[
                  {
                    key: 'sales_order_id',
                    label: 'Order',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('orders', row.sales_order_id)} type="button">
                        {row.sales_order_id}
                      </button>
                    ),
                  },
                  { key: 'summary', label: 'Summary' },
                  {
                    key: 'fulfillment_state',
                    label: 'Status',
                    sortable: true,
                    render: (row) => <Badge>{row.fulfillment_state || row.status}</Badge>,
                  },
                  { key: 'created_at', label: 'Created', sortable: true },
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
                rows={sortedShipments}
                sortKey={shipmentSort?.key}
                sortDir={shipmentSort?.dir}
                onSort={(key) => setShipmentSort((prev) => nextSort(prev, key))}
                columns={[
                  {
                    key: 'id',
                    label: 'Shipment',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('shipments', row.id)} type="button">
                        {row.id}
                      </button>
                    ),
                  },
                  { key: 'status', label: 'Status', sortable: true },
                  { key: 'planned_departure', label: 'Departure', sortable: true },
                  { key: 'planned_arrival', label: 'Arrival', sortable: true },
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

        {view.page === 'production' && (
          <section>
            <SectionHeading id="production" title="Production Orders" />
            <Card>
              <Table
                rows={sortedProductionOrders}
                sortKey={productionSort?.key}
                sortDir={productionSort?.dir}
                onSort={(key) => setProductionSort((prev) => nextSort(prev, key, key === 'eta_finish' ? 'desc' : 'asc'))}
                columns={[
                  {
                    key: 'id',
                    label: 'Order',
                    sortable: true,
                    render: (row) => (
                      <button className="text-brand-600 hover:underline" onClick={() => setHash('production', row.id)} type="button">
                        {row.id}
                      </button>
                    ),
                  },
                  {
                    key: 'item_sku',
                    label: 'Item',
                    sortable: true,
                    render: (row) => (
                      <div>
                        <div>{row.item_sku}</div>
                        <div className="text-xs text-slate-500">{row.item_name}</div>
                      </div>
                    ),
                  },
                  { key: 'qty_planned', label: 'Planned', sortable: true },
                  { key: 'qty_completed', label: 'Completed', sortable: true },
                  { key: 'current_operation', label: 'Operation', sortable: true },
                  { key: 'eta_finish', label: 'ETA Finish', sortable: true },
                  { key: 'eta_ship', label: 'ETA Ship', sortable: true },
                ]}
              />
              {view.id && !selectedProductionOrder ? <div className="mt-3 text-sm text-slate-500">Loading production order…</div> : null}
              {selectedProductionOrder ? (
                <div className="mt-3 text-sm text-slate-800 space-y-1">
                  <div className="font-semibold">Production Order {selectedProductionOrder.id}</div>
                  <div>Item: {selectedProductionOrder.item_sku} - {selectedProductionOrder.item_name}</div>
                  <div>Planned: {selectedProductionOrder.qty_planned} | Completed: {selectedProductionOrder.qty_completed}</div>
                  <div>Current Operation: {selectedProductionOrder.current_operation || '—'}</div>
                  <div>ETA Finish: {selectedProductionOrder.eta_finish || '—'}</div>
                  <div>ETA Ship: {selectedProductionOrder.eta_ship || '—'}</div>
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
                <button className="bg-brand-600 text-white px-3 py-2 rounded shadow" onClick={loadQuotes} type="button">
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
