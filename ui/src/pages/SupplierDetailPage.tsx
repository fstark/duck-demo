import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Supplier, PurchaseOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatQtyWithUom } from '../utils/quantity'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof PurchaseOrder; dir: SortDir }

function sortRows(rows: PurchaseOrder[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof PurchaseOrder): SortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: 'asc' }
}

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface SupplierDetailPageProps {
    supplierId: string
}

export function SupplierDetailPage({ supplierId }: SupplierDetailPageProps) {
    const [supplier, setSupplier] = useState<Supplier | null>(null)
    const [poSort, setPOSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        // Navigation context comes from list page
    }, [])

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.supplierDetail(supplierId)
            .then((data) => {
                if (!cancelled) {
                    setSupplier(data)
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
    }, [supplierId])

    function handlePOHeaderClick(key: keyof PurchaseOrder) {
        setPOSort((prev) => nextSort(prev, key))
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Supplier Detail</div>
                <Card>
                    <div className="text-sm text-gray-500">Loading supplier...</div>
                </Card>
            </section>
        )
    }

    if (error || !supplier) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Supplier Detail</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Supplier not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('suppliers')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Suppliers'}
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
        const prevItem = listContext.items[prevIndex] as Supplier
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('suppliers', prevItem.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextItem = listContext.items[nextIndex] as Supplier
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('suppliers', nextItem.id)
    }

    const purchaseOrders = supplier.purchase_orders || []
    const sortedPOs = sortRows(purchaseOrders, poSort)

    return (
        <>
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">{supplier.name} · Supplier {supplier.id}</div>
                <Card>
                    <div className="flex items-center justify-between mb-4">
                        <button
                            className="text-brand-600 hover:underline text-sm"
                            onClick={() => {
                                if (referrer) {
                                    clearListContext()
                                    setHash(referrer.page, referrer.id)
                                } else {
                                    setHash('suppliers')
                                }
                            }}
                            type="button"
                        >
                            ← {referrer ? `Back to ${referrer.label}` : 'Back to Suppliers'}
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
                            <dt className="text-sm font-medium text-gray-500">Contact Name</dt>
                            <dd className="text-sm text-gray-900">{supplier.contact_name || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Contact Email</dt>
                            <dd className="text-sm text-gray-900">{supplier.contact_email || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Contact Phone</dt>
                            <dd className="text-sm text-gray-900">{supplier.contact_phone || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Lead Time</dt>
                            <dd className="text-sm text-gray-900">{supplier.lead_time_days != null ? `${supplier.lead_time_days} days` : '—'}</dd>
                        </div>
                    </dl>
                </Card>
            </section>

            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Orders · {purchaseOrders.length} total</div>
                <Card>
                    {purchaseOrders.length === 0 ? (
                        <div className="text-sm text-gray-500">No purchase orders</div>
                    ) : (
                        <Table
                            rows={sortedPOs}
                            columns={[
                                { key: 'id', label: 'PO ID', sortable: true },
                                {
                                    key: 'item_sku',
                                    label: 'Item SKU',
                                    sortable: true,
                                    render: (row) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'suppliers', id: supplierId, label: supplier!.name })
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
                                {
                                    key: 'status',
                                    label: 'Status',
                                    sortable: true,
                                    render: (row) => (
                                        <Badge>{row.status}</Badge>
                                    )
                                },
                                { key: 'expected_delivery', label: 'Expected Delivery', sortable: true },
                            ]}
                            sortKey={poSort?.key}
                            sortDir={poSort?.dir}
                            onSort={(key) => setPOSort((prev) => nextSort(prev, key as keyof PurchaseOrder))}
                            onRowClick={(row) => setHash('purchase-orders', row.id)}
                        />
                    )}
                </Card>
            </section>
        </>
    )
}
