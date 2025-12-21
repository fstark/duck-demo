import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { CustomerDetail, Customer } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface CustomerDetailPageProps {
    customerId: string
}

export function CustomerDetailPage({ customerId }: CustomerDetailPageProps) {
    const [customer, setCustomer] = useState<CustomerDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const { listContext, setListContext, referrer, setReferrer } = useNavigation()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        // Fetch customer details
        api.customerDetail(customerId)
            .then((customer) => {
                setCustomer(customer)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load customer details')
                setLoading(false)
            })
    }, [customerId])

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading customer...</div>
                </Card>
            </section>
        )
    }

    if (error || !customer) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Customer not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('customers')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Customers'}
                    </button>
                </Card>
            </section>
        )
    }

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevCustomer = listContext.items[prevIndex] as Customer
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('customers', prevCustomer.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextCustomer = listContext.items[nextIndex] as Customer
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('customers', nextCustomer.id)
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('customers')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Customers'}
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
                <div className="space-y-2 text-sm text-slate-700">
                    <div className="font-semibold text-lg">{customer.name}</div>
                    <div className="text-slate-600">
                        <span className="font-medium">ID:</span> {customer.id}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Company:</span> {customer.company || '—'}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Email:</span> {customer.email || '—'}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">City:</span> {customer.city || '—'}
                    </div>
                </div>
                {customer.sales_orders && customer.sales_orders.length > 0 && (
                    <Card title="Sales Orders">
                        <Table
                            rows={customer.sales_orders as any}
                            columns={[
                                { key: 'sales_order_id', label: 'Order' },
                                { key: 'status', label: 'Status', render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'created_at', label: 'Created' },
                                { key: 'requested_delivery_date', label: 'Delivery Date' },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'orders',
                                    items: customer.sales_orders!.map(o => ({ sales_order_id: o.sales_order_id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('orders', row.sales_order_id)
                            }}
                        />
                    </Card>
                )}
                {customer.shipments && customer.shipments.length > 0 && (
                    <Card title="Shipments">
                        <Table
                            rows={customer.shipments as any}
                            columns={[
                                { key: 'id', label: 'Shipment' },
                                { key: 'status', label: 'Status', render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'planned_departure', label: 'Departure' },
                                { key: 'planned_arrival', label: 'Arrival' },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'shipments',
                                    items: customer.shipments!.map(s => ({ id: s.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('shipments', row.id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
