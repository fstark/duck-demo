import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Supplier, PurchaseOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

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

function setHash(page: string, id: string) {
    if (typeof window !== 'undefined') {
        window.location.hash = `#/${page}/${encodeURIComponent(id)}`
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
    const { listContext } = useNavigation()

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
            <Card title="Supplier Detail">
                <div className="text-sm text-gray-500">Loading supplier...</div>
            </Card>
        )
    }

    if (error) {
        return (
            <Card title="Supplier Detail">
                <div className="text-sm text-red-600">Error: {error}</div>
            </Card>
        )
    }

    if (!supplier) {
        return (
            <Card title="Supplier Detail">
                <div className="text-sm text-gray-500">Supplier not found</div>
            </Card>
        )
    }

    const purchaseOrders = supplier.purchase_orders || []
    const sortedPOs = sortRows(purchaseOrders, poSort)

    return (
        <>
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">{supplier.name} · Supplier {supplier.id}</div>
                <Card>
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
                                { key: 'item_sku', label: 'Item SKU', sortable: true },
                                { key: 'item_name', label: 'Item', sortable: true },
                                { key: 'qty', label: 'Qty', sortable: true },
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
