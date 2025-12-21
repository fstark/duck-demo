import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { SalesOrder, SalesOrderDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatPrice } from '../utils/currency'

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
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, setReferrer, referrer, clearListContext } = useNavigation()

    useEffect(() => {
        api.salesOrder(orderId)
            .then((res) => {
                setOrder(res as SalesOrderDetail)
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
                    <Card title="Customer">
                        <div className="space-y-1">
                            <button
                                className="font-medium text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'orders', id: orderId, label: `Order ${order.sales_order.id}` })
                                    setHash('customers', order.customer.id)
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
                                    { key: 'qty', label: 'Qty' }
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
                            <div>{formatPrice(order.pricing.total, order.pricing.currency)}</div>
                        </Card>
                    </div>
                    <Card title="Shipments">
                        {order.shipments?.length ? (
                            <Table
                                rows={order.shipments as any}
                                columns={[
                                    { key: 'id', label: 'Shipment' },
                                    { key: 'status', label: 'Status', render: (row) => <Badge>{row.status}</Badge> },
                                    { key: 'planned_departure', label: 'Departure' },
                                    { key: 'planned_arrival', label: 'Arrival' },
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
                </div>
            </Card>
        </section>
    )
}
