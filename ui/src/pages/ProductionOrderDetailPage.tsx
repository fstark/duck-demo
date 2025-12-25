import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { ProductionOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { Quantity } from '../utils/quantity.tsx'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function SectionHeading({ id, title }: { id: string; title: string }) {
    return (
        <div id={id} className="flex items-center justify-between">
            <div className="text-lg font-semibold text-slate-800">{title}</div>
        </div>
    )
}

type ProductionOrderDetailPageProps = {
    productionOrderId: string
}

export function ProductionOrderDetailPage({ productionOrderId }: ProductionOrderDetailPageProps) {
    const [productionOrder, setProductionOrder] = useState<ProductionOrder | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        api
            .productionOrder(productionOrderId)
            .then((res) => {
                setProductionOrder(res as ProductionOrder)
                setLoading(false)
            })
            .catch((err) => {
                setError(err.message || 'Failed to load production order')
                setLoading(false)
            })
    }, [productionOrderId])

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

    if (loading) {
        return (
            <section>
                <SectionHeading id="production" title="Production Order" />
                <Card>
                    <div className="text-sm text-slate-500">Loading production order…</div>
                </Card>
            </section>
        )
    }

    if (error || !productionOrder) {
        return (
            <section>
                <SectionHeading id="production" title="Production Order" />
                <Card>
                    <div className="text-sm text-red-600">Error: {error || 'Production order not found'}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="flex items-center justify-between mb-4">
                <SectionHeading id="production" title="Production Order" />
                <button
                    onClick={() => {
                        if (referrer) {
                            clearListContext()
                            setHash(referrer.page, referrer.id)
                        } else {
                            setHash('production')
                        }
                    }}
                    className="text-sm text-brand-600 hover:underline"
                    type="button"
                >
                    ← {referrer ? `Back to ${referrer.label}` : 'Back to Production Orders'}
                </button>
            </div>
            <Card>
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="text-lg font-semibold text-slate-800">Production Order {productionOrder.id}</div>
                        {(hasPrevious || hasNext) && (
                            <div className="flex gap-2">
                                <button
                                    onClick={handlePrevious}
                                    disabled={!hasPrevious}
                                    className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                    type="button"
                                >
                                    ← Previous
                                </button>
                                <button
                                    onClick={handleNext}
                                    disabled={!hasNext}
                                    className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                    type="button"
                                >
                                    Next →
                                </button>
                            </div>
                        )}
                    </div>

                    <div className="space-y-2 text-sm text-slate-700">
                        <div className="grid grid-cols-2 gap-2">
                            <div className="font-medium">Item SKU:</div>
                            <div>
                                {productionOrder.item_sku ? (
                                    <button
                                        className="text-brand-600 hover:underline text-left"
                                        onClick={() => {
                                            setReferrer({ page: 'production', id: productionOrderId, label: `Production Order ${productionOrder.id}` })
                                            setHash('items', productionOrder.item_sku)
                                        }}
                                        type="button"
                                    >
                                        {productionOrder.item_sku}
                                    </button>
                                ) : '—'}
                            </div>

                            <div className="font-medium">Item Name:</div>
                            <div>{productionOrder.item_name || '—'}</div>

                            <div className="font-medium">Item Type:</div>
                            <div>{productionOrder.item_type ? <Badge>{productionOrder.item_type}</Badge> : '—'}</div>

                            <div className="font-medium">Status:</div>
                            <div>{productionOrder.status ? <Badge>{productionOrder.status}</Badge> : '—'}</div>

                            <div className="font-medium">Recipe ID:</div>
                            <div>{productionOrder.recipe_id || '—'}</div>

                            <div className="font-medium">Started:</div>
                            <div>{productionOrder.started_at || '—'}</div>

                            <div className="font-medium">Completed:</div>
                            <div>{productionOrder.completed_at || '—'}</div>

                            <div className="font-medium">ETA Finish:</div>
                            <div>{productionOrder.eta_finish || '—'}</div>

                            <div className="font-medium">ETA Ship:</div>
                            <div>{productionOrder.eta_ship || '—'}</div>
                        </div>
                    </div>

                    {productionOrder.operations && productionOrder.operations.length > 0 && (
                        <div className="mt-6">
                            <div className="text-sm font-semibold text-slate-800 mb-3">Production Operations</div>
                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-slate-200">
                                    <thead>
                                        <tr className="bg-slate-50">
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Seq</th>
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Operation</th>
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Duration (hrs)</th>
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Started</th>
                                            <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Completed</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-200">
                                        {productionOrder.operations.map((op) => (
                                            <tr key={op.id} className="hover:bg-slate-50">
                                                <td className="px-3 py-2 text-sm text-slate-700">{op.sequence_order}</td>
                                                <td className="px-3 py-2 text-sm text-slate-700">{op.operation_name}</td>
                                                <td className="px-3 py-2 text-sm text-slate-700">{op.duration_hours}</td>
                                                <td className="px-3 py-2 text-sm">
                                                    <Badge>{op.status}</Badge>
                                                </td>
                                                <td className="px-3 py-2 text-sm text-slate-700">{op.started_at || '—'}</td>
                                                <td className="px-3 py-2 text-sm text-slate-700">{op.completed_at || '—'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </Card>
        </section>
    )
}
