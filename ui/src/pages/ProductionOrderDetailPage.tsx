import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { TimelineGantt } from '../components/TimelineGantt'
import { ProductionOrder, ProductionOrderTimeline } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { Quantity } from '../utils/quantity'
import { formatDate } from '../utils/date'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

type ProductionOrderDetailPageProps = {
    productionOrderId: string
}

export function ProductionOrderDetailPage({ productionOrderId }: ProductionOrderDetailPageProps) {
    const [productionOrder, setProductionOrder] = useState<ProductionOrder | null>(null)
    const [timeline, setTimeline] = useState<ProductionOrderTimeline | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        Promise.all([
            api.productionOrder(productionOrderId),
            api.productionOrderTimeline(productionOrderId).catch(() => null),
        ])
            .then(([res, tl]) => {
                setProductionOrder(res as ProductionOrder)
                setTimeline(tl)
                setLoading(false)
            })
            .catch((err) => {
                setError(err.message || 'Failed to load production order')
                setLoading(false)
            })
    }, [productionOrderId])

    // Call hooks before conditional returns
    const operationsSort = useTableSort(productionOrder?.operations || [])

    const hasPrevious = listContext?.listType === 'production' && (listContext.currentIndex ?? 0) > 0
    const hasNext =
        listContext?.listType === 'production' &&
        listContext.items &&
        (listContext.currentIndex ?? 0) < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const newIndex = (listContext.currentIndex ?? 0) - 1
        const prevItem = listContext.items[newIndex] as ProductionOrder
        setListContext({
            ...listContext,
            currentIndex: newIndex,
        })
        setHash('production', prevItem.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const newIndex = (listContext.currentIndex ?? 0) + 1
        const nextItem = listContext.items[newIndex] as ProductionOrder
        setListContext({
            ...listContext,
            currentIndex: newIndex,
        })
        setHash('production', nextItem.id)
    }

    const goBack = () => {
        if (referrer) {
            clearListContext()
            setHash(referrer.page, referrer.id)
        } else {
            setHash('production')
        }
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Production Order Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading production order…</div>
                </Card>
            </section>
        )
    }

    if (error || !productionOrder) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Production Order Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Production order not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={goBack}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Production Orders'}
                    </button>
                </Card>
            </section>
        )
    }

    const ref = { page: 'production', id: productionOrderId, label: `Production Order ${productionOrder.id}` }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Production Order Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={goBack}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Production Orders'}
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
                                {(listContext.currentIndex ?? 0) + 1} of {listContext.items.length}
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
                    <div className="font-semibold text-lg">
                        Production Order {productionOrder.id}
                        {productionOrder.status && (
                            <span className="ml-3 align-middle"><Badge>{productionOrder.status}</Badge></span>
                        )}
                    </div>

                    {/* Item & Schedule side-by-side */}
                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Item">
                            <div className="space-y-1">
                                {productionOrder.item_sku ? (
                                    <div>
                                        <button
                                            className="font-medium text-brand-600 hover:underline text-left"
                                            onClick={() => {
                                                setReferrer(ref)
                                                setHash('items', productionOrder.item_sku)
                                            }}
                                            type="button"
                                        >
                                            {productionOrder.item_sku}
                                        </button>
                                    </div>
                                ) : (
                                    <div className="text-slate-400">—</div>
                                )}
                                {productionOrder.item_name && (
                                    <div className="text-slate-600">{productionOrder.item_name}</div>
                                )}
                                {productionOrder.item_type && (
                                    <div><Badge>{productionOrder.item_type}</Badge></div>
                                )}
                                {productionOrder.qty_produced != null && productionOrder.qty_produced > 0 && (
                                    <div>
                                        <span className="text-slate-500">Qty Produced: </span>
                                        <Quantity value={productionOrder.qty_produced} />
                                    </div>
                                )}
                                {productionOrder.current_operation && (
                                    <div>
                                        <span className="text-slate-500">Current Op: </span>
                                        <span>{productionOrder.current_operation}</span>
                                    </div>
                                )}
                            </div>
                        </Card>
                        <Card title="Schedule">
                            <div className="space-y-1">
                                <div>
                                    <span className="text-slate-500">Started: </span>
                                    <span>{productionOrder.started_at ? formatDate(productionOrder.started_at) : '—'}</span>
                                </div>
                                <div>
                                    <span className="text-slate-500">Completed: </span>
                                    <span>{productionOrder.completed_at ? formatDate(productionOrder.completed_at) : '—'}</span>
                                </div>
                                <div>
                                    <span className="text-slate-500">ETA Finish: </span>
                                    <span>{productionOrder.eta_finish ? formatDate(productionOrder.eta_finish) : '—'}</span>
                                </div>
                                <div>
                                    <span className="text-slate-500">ETA Ship: </span>
                                    <span>{productionOrder.eta_ship ? formatDate(productionOrder.eta_ship) : '—'}</span>
                                </div>
                            </div>
                        </Card>
                    </div>

                    {/* Related entity links side-by-side when small */}
                    <div className="grid grid-cols-2 gap-3">
                        {productionOrder.sales_order_id && (
                            <Card title="Sales Order">
                                <button
                                    className="text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer(ref)
                                        setHash('orders', productionOrder.sales_order_id!)
                                    }}
                                    type="button"
                                >
                                    {productionOrder.sales_order_id}
                                </button>
                            </Card>
                        )}
                        {productionOrder.recipe_id && (
                            <Card title="Recipe">
                                <button
                                    className="text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer(ref)
                                        setHash('recipes', productionOrder.recipe_id!)
                                    }}
                                    type="button"
                                >
                                    {productionOrder.recipe_id}
                                </button>
                            </Card>
                        )}
                        {productionOrder.parent_production_order_id && (
                            <Card title="Parent Production Order">
                                <button
                                    className="text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer(ref)
                                        setHash('production', productionOrder.parent_production_order_id!)
                                    }}
                                    type="button"
                                >
                                    {productionOrder.parent_production_order_id}
                                </button>
                            </Card>
                        )}
                    </div>

                    {/* Timeline visualization */}
                    {timeline && (
                        <Card title="Production Timeline">
                            <TimelineGantt
                                moTimeline={timeline}
                                onNavigate={(page, id) => {
                                    setReferrer(ref)
                                    setHash(page, id)
                                }}
                            />
                        </Card>
                    )}

                    {/* Operations table */}
                    {productionOrder.operations && productionOrder.operations.length > 0 && (
                        <Card title="Operations">
                            <Table
                                rows={operationsSort.sortedRows}
                                sortKey={operationsSort.sortKey}
                                sortDir={operationsSort.sortDir}
                                onSort={operationsSort.onSort}
                                columns={[
                                    { key: 'sequence_order', label: 'Seq', sortable: true },
                                    { key: 'operation_name', label: 'Operation', sortable: true },
                                    { key: 'work_center', label: 'Work Center', sortable: true },
                                    { key: 'duration_hours', label: 'Duration (hrs)', sortable: true },
                                    {
                                        key: 'status', label: 'Status', sortable: true,
                                        render: (op) => <Badge>{op.status}</Badge>,
                                    },
                                    {
                                        key: 'started_at', label: 'Started', sortable: true,
                                        render: (op) => op.started_at ? formatDate(op.started_at) : '—',
                                    },
                                    {
                                        key: 'completed_at', label: 'Completed', sortable: true,
                                        render: (op) => op.completed_at ? formatDate(op.completed_at) : '—',
                                    },
                                ]}
                            />
                        </Card>
                    )}
                </div>
            </Card>
        </section>
    )
}
