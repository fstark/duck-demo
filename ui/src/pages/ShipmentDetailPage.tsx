import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Shipment } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface ShipmentDetailPageProps {
    shipmentId: string
}

export function ShipmentDetailPage({ shipmentId }: ShipmentDetailPageProps) {
    const [shipment, setShipment] = useState<Shipment | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        api.shipment(shipmentId)
            .then((res) => {
                setShipment(res as Shipment)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load shipment details')
                setLoading(false)
            })
    }, [shipmentId])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevShipment = listContext.items[prevIndex] as Shipment
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('shipments', prevShipment.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextShipment = listContext.items[nextIndex] as Shipment
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('shipments', nextShipment.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Shipment Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading shipment...</div>
                </Card>
            </section>
        )
    }

    if (error || !shipment) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Shipment Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Shipment not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('shipments')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Shipments'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Shipment Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('shipments')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Shipments'}
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
                    <div className="font-semibold text-lg">Shipment {shipment.id}</div>
                    <div className="text-slate-600">
                        <span className="font-medium">Status:</span> <Badge>{shipment.status}</Badge>
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Planned Departure:</span> {shipment.planned_departure || '—'}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Planned Arrival:</span> {shipment.planned_arrival || '—'}
                    </div>
                    {shipment.tracking_ref && (
                        <div className="text-slate-600">
                            <span className="font-medium">Tracking Reference:</span> {shipment.tracking_ref}
                        </div>
                    )}
                </div>
                {shipment.sales_orders && shipment.sales_orders.length > 0 && (
                    <Card title="Sales Orders">
                        <Table
                            rows={shipment.sales_orders as any}
                            columns={[
                                { key: 'sales_order_id', label: 'Order' },
                                { key: 'customer_name', label: 'Customer' },
                                { key: 'customer_company', label: 'Company' },
                                { key: 'status', label: 'Status', render: (row) => <Badge>{row.status}</Badge> },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'orders',
                                    items: shipment.sales_orders!.map(o => ({ sales_order_id: o.sales_order_id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'shipments', id: shipmentId, label: `Shipment ${shipment.id}` })
                                setHash('orders', row.sales_order_id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
