import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { SalesOrder, SalesOrderDetail, Email, Invoice, ProductionOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { Quantity } from '../utils/quantity.tsx'
import { formatDate } from '../utils/date'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface SalesOrderDetailPageProps {
    orderId: string
}

export function SalesOrderDetailPage({ orderId }: SalesOrderDetailPageProps) {
    const [order, setOrder] = useState<SalesOrderDetail | null>(null)
    const [emails, setEmails] = useState<Email[]>([])
    const [invoices, setInvoices] = useState<Invoice[]>([])
    const [productionOrders, setProductionOrders] = useState<ProductionOrder[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, setReferrer, referrer, clearListContext } = useNavigation()

    useEffect(() => {
        Promise.all([
            api.salesOrder(orderId),
            api.emails({ sales_order_id: orderId }),
            api.invoices({ sales_order_id: orderId }),
            api.productionOrders({ sales_order_id: orderId }),
        ])
            .then(([orderData, emailsData, invoicesData, prodData]) => {
                setOrder(orderData as SalesOrderDetail)
                setEmails(emailsData.emails)
                setInvoices(invoicesData.invoices || [])
                setProductionOrders(prodData.production_orders || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load sales order details')
                setLoading(false)
            })
    }, [orderId])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevOrder = listContext.items[prevIndex] as SalesOrder
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('orders', prevOrder.sales_order_id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextOrder = listContext.items[nextIndex] as SalesOrder
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('orders', nextOrder.sales_order_id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading order...</div>
                </Card>
            </section>
        )
    }

    if (error || !order) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Order not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('orders')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Sales Orders'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('orders')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Sales Orders'}
                    </button>
                    {listContext && (
                        <div className="flex items-center gap-2">
                            <button
                                className={`px-3 py-1 text-sm rounded ${hasPrevious
                                    ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                    : 'bg-slate-50 text-slate-300 cursor-not-allowed'
                                    }`}
                                onClick={handlePrevious}
                                disabled={!hasPrevious}
                                type="button"
                            >
                                ← Previous
                            </button>
                            <span className="text-xs text-slate-500">
                                {listContext.currentIndex + 1} of {listContext.items.length}
                            </span>
                            <button
                                className={`px-3 py-1 text-sm rounded ${hasNext
                                    ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                    : 'bg-slate-50 text-slate-300 cursor-not-allowed'
                                    }`}
                                onClick={handleNext}
                                disabled={!hasNext}
                                type="button"
                            >
                                Next →
                            </button>
                        </div>
                    )}
                </div>
                <div className="space-y-3 text-sm text-slate-800">
                    <div className="font-semibold text-lg">Order {order.sales_order.id}</div>
                    <div className="grid grid-cols-2 gap-3">
                        {order.customer && (
                            <Card title="Customer">
                                <div className="space-y-1">
                                    <button
                                        className="font-medium text-brand-600 hover:underline text-left"
                                        onClick={() => {
                                            setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                            setHash('customers', order.customer!.id)
                                        }}
                                        type="button"
                                    >
                                        {order.customer.name}
                                    </button>
                                    {order.customer.company && <div className="text-slate-600 text-sm">{order.customer.company}</div>}
                                    {order.customer.email && <div className="text-slate-600 text-sm">{order.customer.email}</div>}
                                    {order.customer.city && <div className="text-slate-600 text-sm">{order.customer.city}</div>}
                                </div>
                            </Card>
                        )}
                        <Card title="Dates">
                            <div className="space-y-1">
                                {order.sales_order.created_at && (
                                    <div>
                                        <span className="text-slate-500">Order Date: </span>
                                        <span>{formatDate(order.sales_order.created_at)}</span>
                                    </div>
                                )}
                                {order.sales_order.requested_delivery_date && (
                                    <div>
                                        <span className="text-slate-500">Requested Delivery: </span>
                                        <span>{formatDate(order.sales_order.requested_delivery_date)}</span>
                                    </div>
                                )}
                                {!order.sales_order.created_at && !order.sales_order.requested_delivery_date && (
                                    <div className="text-slate-400 text-sm">No dates available</div>
                                )}
                            </div>
                        </Card>
                    </div>
                    {(order.sales_order.ship_to_line1 || order.sales_order.ship_to_city) && (
                        <Card title="Shipping Address">
                            <div className="space-y-1">
                                {order.sales_order.ship_to_line1 && <div>{order.sales_order.ship_to_line1}</div>}
                                {order.sales_order.ship_to_line2 && <div>{order.sales_order.ship_to_line2}</div>}
                                {(order.sales_order.ship_to_postal_code || order.sales_order.ship_to_city) && (
                                    <div>
                                        {order.sales_order.ship_to_postal_code && <span>{order.sales_order.ship_to_postal_code} </span>}
                                        {order.sales_order.ship_to_city && <span>{order.sales_order.ship_to_city}</span>}
                                    </div>
                                )}
                                {order.sales_order.ship_to_country && <div>{order.sales_order.ship_to_country}</div>}
                            </div>
                        </Card>
                    )}
                    {order.sales_order.note && (
                        <Card title="Note">
                            <div className="text-slate-700 whitespace-pre-wrap">{order.sales_order.note}</div>
                        </Card>
                    )}
                    {order.sales_order.quote_id && (
                        <Card title="Quote">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('quotes', order.sales_order.quote_id)
                                }}
                                type="button"
                            >
                                {order.sales_order.quote_id}
                            </button>
                        </Card>
                    )}
                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Lines">
                            <Table
                                rows={order.lines as any}
                                columns={[
                                    {
                                        key: 'sku',
                                        label: 'SKU',
                                        render: (row) => (
                                            <button
                                                className="text-brand-600 hover:underline text-left"
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                                    setHash('items', row.sku)
                                                }}
                                                type="button"
                                            >
                                                {row.sku}
                                            </button>
                                        )
                                    },
                                    { key: 'qty', label: 'Qty', render: (row) => <Quantity value={row.qty} /> },
                                    { key: 'unit_price', label: 'Unit Price', render: (row) => <div className="text-right">{formatCurrency(row.unit_price, order.pricing.currency)}</div> },
                                    { key: 'line_total', label: 'Line Total', render: (row) => <div className="text-right">{formatCurrency(row.line_total, order.pricing.currency)}</div> },
                                ]}
                                onRowClick={(row, index) => {
                                    setListContext({
                                        listType: 'items',
                                        items: order.lines.map(l => ({ sku: l.sku })) as any,
                                        currentIndex: index,
                                    })
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('items', row.sku)
                                }}
                            />
                        </Card>
                        <Card title="Pricing">
                            <div className="space-y-1 text-sm">
                                <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{formatCurrency(order.pricing.subtotal, order.pricing.currency)}</span></div>
                                {order.pricing.discount > 0 && <div className="flex justify-between"><span className="text-slate-500">Discount</span><span>−{formatCurrency(order.pricing.discount, order.pricing.currency)}</span></div>}
                                {order.pricing.shipping > 0 && <div className="flex justify-between"><span className="text-slate-500">Shipping</span><span>{formatCurrency(order.pricing.shipping, order.pricing.currency)}</span></div>}
                                <div className="flex justify-between"><span className="text-slate-500">Tax</span><span>{formatCurrency(order.pricing.tax, order.pricing.currency)}</span></div>
                                <div className="flex justify-between font-semibold border-t pt-1"><span>Total</span><span>{formatCurrency(order.pricing.total, order.pricing.currency)}</span></div>
                            </div>
                        </Card>
                    </div>
                    <Card title="Shipments">
                        {order.shipments?.length ? (
                            <Table
                                rows={order.shipments as any}
                                columns={[
                                    { key: 'id', label: 'Shipment' },
                                    { key: 'status', label: 'Status', render: (row) => <Badge>{row.status}</Badge> },
                                    { key: 'planned_departure', label: 'Departure', render: (row) => formatDate(row.planned_departure) },
                                    { key: 'planned_arrival', label: 'Arrival', render: (row) => formatDate(row.planned_arrival) },
                                ]}
                                onRowClick={(row, index) => {
                                    setListContext({
                                        listType: 'shipments',
                                        items: order.shipments!.map(s => ({ id: s.id })) as any,
                                        currentIndex: index,
                                    })
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('shipments', row.id)
                                }}
                            />
                        ) : (
                            <div className="text-slate-500">No shipments linked.</div>
                        )}
                    </Card>
                    {emails.length > 0 && (
                        <Card title="Emails">
                            <Table
                                rows={emails as any}
                                columns={[
                                    { key: 'subject', label: 'Subject' },
                                    { key: 'recipient_email', label: 'Recipient' },
                                    {
                                        key: 'status',
                                        label: 'Status',
                                        render: (row: Email) => <Badge>{row.status}</Badge>
                                    },
                                    { key: 'modified_at', label: 'Modified', render: (row: Email) => formatDate(row.modified_at) },
                                ]}
                                onRowClick={(row: Email, index: number) => {
                                    setListContext({
                                        listType: 'emails',
                                        items: emails.map(e => ({ id: e.id })) as any,
                                        currentIndex: index,
                                    })
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('emails', row.id)
                                }}
                            />
                        </Card>
                    )}
                    {invoices.length > 0 && (
                        <Card title="Invoices">
                            <Table
                                rows={invoices as any}
                                columns={[
                                    { key: 'id', label: 'Invoice' },
                                    { key: 'total', label: 'Total', render: (row: Invoice) => <div className="text-right">{formatCurrency(row.total, row.currency)}</div> },
                                    { key: 'status', label: 'Status', render: (row: Invoice) => <Badge>{row.status}</Badge> },
                                    { key: 'invoice_date', label: 'Invoice Date', render: (row: Invoice) => formatDate(row.invoice_date) },
                                    { key: 'due_date', label: 'Due Date', render: (row: Invoice) => formatDate(row.due_date) },
                                ]}
                                onRowClick={(row: Invoice, index: number) => {
                                    setListContext({
                                        listType: 'invoices',
                                        items: invoices.map(i => ({ id: i.id })) as any,
                                        currentIndex: index,
                                    })
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('invoices', row.id)
                                }}
                            />
                        </Card>
                    )}
                    {productionOrders.length > 0 && (
                        <Card title="Production Orders">
                            <Table
                                rows={productionOrders as any}
                                columns={[
                                    { key: 'id', label: 'Order' },
                                    {
                                        key: 'item_sku', label: 'Item', render: (row: ProductionOrder) => (
                                            <div>
                                                <div>{row.item_sku}</div>
                                                <div className="text-xs text-slate-500">{row.item_name}</div>
                                            </div>
                                        )
                                    },
                                    { key: 'status', label: 'Status', render: (row: ProductionOrder) => <Badge>{row.status}</Badge> },
                                    { key: 'eta_finish', label: 'ETA Finish', render: (row: ProductionOrder) => formatDate(row.eta_finish) },
                                ]}
                                onRowClick={(row: ProductionOrder, index: number) => {
                                    setListContext({
                                        listType: 'production',
                                        items: productionOrders.map(p => ({ id: p.id })) as any,
                                        currentIndex: index,
                                    })
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('production', row.id)
                                }}
                            />
                        </Card>
                    )}
                </div>
            </Card>
        </section>
    )
}
