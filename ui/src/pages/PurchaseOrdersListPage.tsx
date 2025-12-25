import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { PurchaseOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatQuantity } from '../utils/quantity'

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

export function PurchaseOrdersListPage() {
    const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([])
    const [poSort, setPOSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [statusFilter, setStatusFilter] = useState<string>('')
    const { setListContext } = useNavigation()

    useEffect(() => {
        // Navigation context will be set on row click
    }, [])

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.purchaseOrders(statusFilter || undefined)
            .then((data) => {
                if (!cancelled) {
                    setPurchaseOrders(data.purchase_orders)
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
    }, [statusFilter])

    const sortedPOs = sortRows(purchaseOrders, poSort)

    function handleHeaderClick(key: keyof PurchaseOrder) {
        setPOSort((prev) => nextSort(prev, key))
    }

    if (loading) {
        return (
            <Card title="Purchase Orders">
                <div className="text-sm text-gray-500">Loading purchase orders...</div>
            </Card>
        )
    }

    if (error) {
        return (
            <Card title="Purchase Orders">
                <div className="text-sm text-red-600">Error: {error}</div>
            </Card>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Orders · {purchaseOrders.length} total</div>
            <div className="mb-4 flex gap-2">
                <button
                    onClick={() => setStatusFilter('')}
                    className={`px-3 py-1 text-sm rounded ${
                        statusFilter === '' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                    }`}
                >
                    All
                </button>
                <button
                    onClick={() => setStatusFilter('ordered')}
                    className={`px-3 py-1 text-sm rounded ${
                        statusFilter === 'ordered' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                    }`}
                >
                    Ordered
                </button>
                <button
                    onClick={() => setStatusFilter('received')}
                    className={`px-3 py-1 text-sm rounded ${
                        statusFilter === 'received' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700'
                    }`}
                >
                    Received
                </button>
            </div>
            <Card>
                <Table
                    rows={sortedPOs}
                    columns={[
                        { key: 'id', label: 'PO ID', sortable: true },
                        { key: 'supplier_name', label: 'Supplier', sortable: true },
                        { key: 'item_sku', label: 'Item SKU', sortable: true },
                        { key: 'item_name', label: 'Item', sortable: true },
                        { 
                            key: 'qty', 
                            label: 'Quantity',
                            sortable: true,
                            render: (row) => `${formatQuantity(row.qty)} ${row.uom || 'ea'}`
                        },
                        { 
                            key: 'status', 
                            label: 'Status',
                            sortable: true,
                            render: (row) => <Badge>{row.status}</Badge>
                        },
                        { key: 'eta_delivery', label: 'ETA Delivery', sortable: true },
                    ]}
                    sortKey={poSort?.key}
                    sortDir={poSort?.dir}
                    onSort={(key) => setPOSort((prev) => nextSort(prev, key as keyof PurchaseOrder))}
                    onRowClick={(row, index) => {
                        setListContext({
                            listType: 'purchase-orders',
                            items: sortedPOs,
                            currentIndex: index,
                        })
                        setHash('purchase-orders', row.id)
                    }}
                />
            </Card>
        </section>
    )
}
