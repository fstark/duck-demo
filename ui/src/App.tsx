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

export default function App() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [orders, setOrders] = useState<SalesOrder[]>([])
  const [selectedOrder, setSelectedOrder] = useState<SalesOrderDetail | null>(null)
  const [stock, setStock] = useState<StockSummary | null>(null)
  const [shipments, setShipments] = useState<Shipment[]>([])
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null)
  const [quoteOptions, setQuoteOptions] = useState<QuoteOption[] | null>(null)
  const [quoteSku, setQuoteSku] = useState('ELVIS-DUCK-20CM')
  const [quoteQty, setQuoteQty] = useState(24)

  useEffect(() => {
    api.customers().then((res) => setCustomers(res.customers || [])).catch(console.error)
    api.items(true).then((res) => setItems(res.items || [])).catch(console.error)
    api.salesOrders().then((res) => setOrders(res.sales_orders || [])).catch(console.error)
    api.shipments().then((res) => setShipments(res.shipments || [])).catch(console.error)
  }, [])

  const loadOrder = (id: string) => {
    api.salesOrder(id).then((res) => setSelectedOrder(res as SalesOrderDetail)).catch(console.error)
  }

  const loadStock = (sku: string) => {
    api.stock(sku).then((res) => setStock(res as StockSummary)).catch(console.error)
  }

  const loadShipment = (id: string) => {
    api.shipment(id).then((res) => setSelectedShipment(res as Shipment)).catch(console.error)
  }

  const loadQuotes = () => {
    api.quote(quoteSku, quoteQty).then((res) => setQuoteOptions(res.options || [])).catch(console.error)
  }

  return (
    <Layout>
      <div className="space-y-8">
        <section>
          <SectionHeading id="customers" title="Customers" />
          <Card>
            <Table
              rows={customers}
              columns={[
                { key: 'id', label: 'ID' },
                { key: 'name', label: 'Name' },
                { key: 'company', label: 'Company' },
                { key: 'email', label: 'Email' },
                { key: 'city', label: 'City' },
              ]}
            />
          </Card>
        </section>

        <section>
          <SectionHeading id="items" title="Items (in stock)" />
          <Card>
            <Table
              rows={items}
              columns={[
                { key: 'sku', label: 'SKU' },
                { key: 'name', label: 'Name' },
                { key: 'type', label: 'Type' },
                { key: 'available_total', label: 'Available' },
                {
                  key: 'id',
                  label: 'Stock',
                  render: (row) => (
                    <button className="text-brand-600 hover:underline" onClick={() => loadStock(row.sku)}>
                      View stock
                    </button>
                  ),
                },
              ]}
            />
            {stock ? (
              <div className="mt-3 text-sm text-slate-700">
                <div className="font-semibold">Stock for {stock.item_id}</div>
                <div className="flex gap-3 text-slate-600">
                  <span>On hand: {stock.on_hand_total}</span>
                  <span>Reserved: {stock.reserved_total}</span>
                  <span>Available: {stock.available_total}</span>
                </div>
                <div className="mt-2">
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
              </div>
            ) : null}
          </Card>
        </section>

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
                    <button className="text-brand-600 hover:underline" onClick={() => loadOrder(row.sales_order_id)}>
                      View
                    </button>
                  ),
                },
              ]}
            />
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
                    <button className="text-brand-600 hover:underline" onClick={() => loadShipment(row.id)}>
                      View
                    </button>
                  ),
                },
              ]}
            />
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
      </div>
    </Layout>
  )
}
