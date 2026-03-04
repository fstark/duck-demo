import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { SupplyChainFlow } from '../components/SupplyChainFlow'
import { Shipment, SupplyChainTrace } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatDate } from '../utils/date'
import { formatQtyWithUom } from '../utils/quantity'
import { useTableSort } from '../utils/useTableSort'

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
    const [supplyChainTrace, setSupplyChainTrace] = useState<SupplyChainTrace | null>(null)
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

    useEffect(() => {
        api.shipmentSupplyChain(shipmentId)
            .then((trace) => {
                setSupplyChainTrace(trace)
            })
            .catch((err) => {
                console.error('Failed to load supply chain trace:', err)
            })
    }, [shipmentId])

    // Call hooks before conditional returns
    const linesSort = useTableSort(shipment?.lines || [])
    const salesOrdersSort = useTableSort(shipment?.sales_orders || [])

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
                    <div className="grid grid-cols-2 gap-3 mt-3">
                        <Card title="Schedule">
                            <div className="space-y-1">
                                <div><span className="font-medium">Planned Departure:</span> {shipment.planned_departure ? formatDate(shipment.planned_departure) : '—'}</div>
                                <div><span className="font-medium">Planned Arrival:</span> {shipment.planned_arrival ? formatDate(shipment.planned_arrival) : '—'}</div>
                                {shipment.dispatched_at && (
                                    <div><span className="font-medium">Dispatched:</span> {formatDate(shipment.dispatched_at)}</div>
                                )}
                                {shipment.delivered_at && (
                                    <div><span className="font-medium">Delivered:</span> {formatDate(shipment.delivered_at)}</div>
                                )}
                                {shipment.tracking_ref && (
                                    <div><span className="font-medium">Tracking Ref:</span> {shipment.tracking_ref}</div>
                                )}
                            </div>
                        </Card>
                        <Card title="Addresses">
                            <div className="space-y-2">
                                {shipment.ship_from_warehouse && (
                                    <div>
                                        <div className="font-medium text-slate-500 text-xs uppercase">From</div>
                                        <div>{shipment.ship_from_warehouse}</div>
                                    </div>
                                )}
                                {(shipment.ship_to_line1 || shipment.ship_to_city) && (
                                    <div>
                                        <div className="font-medium text-slate-500 text-xs uppercase">To</div>
                                        {shipment.ship_to_line1 && <div>{shipment.ship_to_line1}</div>}
                                        {shipment.ship_to_line2 && <div>{shipment.ship_to_line2}</div>}
                                        {(shipment.ship_to_postal_code || shipment.ship_to_city) && (
                                            <div>
                                                {shipment.ship_to_postal_code && <span>{shipment.ship_to_postal_code} </span>}
                                                {shipment.ship_to_city && <span>{shipment.ship_to_city}</span>}
                                            </div>
                                        )}
                                        {shipment.ship_to_country && <div>{shipment.ship_to_country}</div>}
                                    </div>
                                )}
                            </div>
                        </Card>
                    </div>
                </div>
                {shipment.lines && shipment.lines.length > 0 && (
                    <Card title="Shipment Lines">
                        <Table
                            rows={linesSort.sortedRows as any}
                            sortKey={linesSort.sortKey}
                            sortDir={linesSort.sortDir}
                            onSort={linesSort.onSort}
                            columns={[
                                {
                                    key: 'item_sku',
                                    label: 'SKU',
                                    sortable: true,
                                    render: (row) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'shipments', id: shipmentId, label: `Shipment ${shipment.id}` })
                                                setHash('items', row.item_sku)
                                            }}
                                            type="button"
                                        >
                                            {row.item_sku}
                                        </button>
                                    ),
                                },
                                { key: 'item_name', label: 'Item', sortable: true },
                                { key: 'qty', label: 'Qty', sortable: true, render: (row) => formatQtyWithUom(row.qty, row.uom) },
                            ]}
                        />
                    </Card>
                )}
                {shipment.sales_orders && shipment.sales_orders.length > 0 && (
                    <Card title="Sales Orders">
                        <Table
                            rows={salesOrdersSort.sortedRows as any}
                            sortKey={salesOrdersSort.sortKey}
                            sortDir={salesOrdersSort.sortDir}
                            onSort={salesOrdersSort.onSort}
                            columns={[
                                { key: 'sales_order_id', label: 'Order', sortable: true },
                                {
                                    key: 'customer_name',
                                    label: 'Customer',
                                    sortable: true,
                                    render: (row) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'shipments', id: shipmentId, label: `Shipment ${shipment.id}` })
                                                setHash('customers', (row as any).customer_id)
                                            }}
                                            type="button"
                                        >
                                            {row.customer_name}
                                        </button>
                                    ),
                                },
                                { key: 'customer_company', label: 'Company', sortable: true },
                                { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge>{row.status}</Badge> },
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
                {supplyChainTrace && supplyChainTrace.nodes.length > 0 && (
                    <Card title="Supply Chain Trace">
                        <SupplyChainFlow 
                            trace={supplyChainTrace}
                            onNavigate={(page, id) => {
                                setReferrer({ page: 'shipments', id: shipmentId, label: `Shipment ${shipment.id}` })
                                setHash(page, id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
