import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { PurchaseOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatQtyWithUom } from '../utils/quantity'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface PurchaseOrderDetailPageProps {
    purchaseOrderId: string
}

export function PurchaseOrderDetailPage({ purchaseOrderId }: PurchaseOrderDetailPageProps) {
    const [purchaseOrder, setPurchaseOrder] = useState<PurchaseOrder | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.purchaseOrderDetail(purchaseOrderId)
            .then((data) => {
                if (!cancelled) {
                    setPurchaseOrder(data)
                    setLoading(false)
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(String(err))
                    setLoading(false)
                }
            })
        return () => {
            cancelled = true
        }
    }, [purchaseOrderId])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevItem = listContext.items[prevIndex] as PurchaseOrder
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('purchase-orders', prevItem.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextItem = listContext.items[nextIndex] as PurchaseOrder
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('purchase-orders', nextItem.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Order Detail</div>
                <Card>
                    <div className="text-sm text-gray-500">Loading purchase order...</div>
                </Card>
            </section>
        )
    }

    if (error || !purchaseOrder) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Order Detail</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Purchase order not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('purchase-orders')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Purchase Orders'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Order {purchaseOrder.id}</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('purchase-orders')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Purchase Orders'}
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
                <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Status</dt>
                        <dd className="text-sm text-gray-900">
                            <Badge>{purchaseOrder.status}</Badge>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Ordered At</dt>
                        <dd className="text-sm text-gray-900">{purchaseOrder.ordered_at ? formatDate(purchaseOrder.ordered_at) : '—'}</dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Expected Delivery</dt>
                        <dd className="text-sm text-gray-900">{purchaseOrder.expected_delivery ? formatDate(purchaseOrder.expected_delivery) : '—'}</dd>
                    </div>
                    {purchaseOrder.received_at && (
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Received At</dt>
                            <dd className="text-sm text-gray-900">{formatDate(purchaseOrder.received_at)}</dd>
                        </div>
                    )}
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Supplier</dt>
                        <dd className="text-sm text-gray-900">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'purchase-orders', id: purchaseOrderId, label: `PO ${purchaseOrder.id}` })
                                    setHash('suppliers', purchaseOrder.supplier_id)
                                }}
                                type="button"
                            >
                                {purchaseOrder.supplier_name || purchaseOrder.supplier_id}
                            </button>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Contact Name</dt>
                        <dd className="text-sm text-gray-900">{purchaseOrder.contact_name || '—'}</dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Contact Email</dt>
                        <dd className="text-sm text-gray-900">
                            {purchaseOrder.contact_email ? (
                                <a href={`mailto:${purchaseOrder.contact_email}`} className="text-brand-600 hover:underline">
                                    {purchaseOrder.contact_email}
                                </a>
                            ) : '—'}
                        </dd>
                    </div>
                    {purchaseOrder.contact_phone && (
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Contact Phone</dt>
                            <dd className="text-sm text-gray-900">{purchaseOrder.contact_phone}</dd>
                        </div>
                    )}
                </dl>

                <div className="mt-6 border-t pt-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Item Details</h3>
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item SKU</dt>
                            <dd className="text-sm text-gray-900">
                                <button
                                    className="text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer({ page: 'purchase-orders', id: purchaseOrderId, label: `PO ${purchaseOrder.id}` })
                                        setHash('items', purchaseOrder.item_sku)
                                    }}
                                    type="button"
                                >
                                    {purchaseOrder.item_sku}
                                </button>
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item Name</dt>
                            <dd className="text-sm text-gray-900">{purchaseOrder.item_name || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item Type</dt>
                            <dd className="text-sm text-gray-900">{purchaseOrder.item_type || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Quantity</dt>
                            <dd className="text-sm text-gray-900">
                                {formatQtyWithUom(purchaseOrder.qty, purchaseOrder.uom)}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Unit Price</dt>
                            <dd className="text-sm text-gray-900">
                                {purchaseOrder.unit_price != null ? formatCurrency(purchaseOrder.unit_price, purchaseOrder.currency) : '—'}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Total</dt>
                            <dd className="text-sm text-gray-900">
                                {purchaseOrder.total != null ? formatCurrency(purchaseOrder.total, purchaseOrder.currency) : '—'}
                            </dd>
                        </div>
                    </dl>
                </div>
            </Card>
        </section>
    )
}
