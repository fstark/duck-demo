import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { SalesOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof SalesOrder; dir: SortDir }

function sortRows(rows: SalesOrder[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof SalesOrder, defaultDir: SortDir = 'asc'): SortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: defaultDir }
}

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

export function SalesOrdersListPage() {
    const [orders, setOrders] = useState<SalesOrder[]>([])
    const [orderSort, setOrderSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.salesOrders()
            .then((res) => {
                setOrders(res.sales_orders || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load sales orders')
                setLoading(false)
            })
    }, [])

    const sortedOrders = sortRows(orders, orderSort)

    const handleOrderClick = (order: SalesOrder, index: number) => {
        // Store list context for future navigation
        setListContext({
            listType: 'sales-orders',
            items: sortedOrders,
            currentIndex: index,
        })
        setHash('orders', order.sales_order_id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Sales Orders</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading sales orders...</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Sales Orders</div>
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Sales Orders</div>
            <Card>
                <Table
                    rows={sortedOrders}
                    sortKey={orderSort?.key}
                    sortDir={orderSort?.dir}
                    onSort={(key) => setOrderSort((prev) => nextSort(prev, key, key === 'created_at' ? 'desc' : 'asc'))}
                    onRowClick={handleOrderClick}
                    columns={[
                        {
                            key: 'sales_order_id',
                            label: 'Order',
                            sortable: true,
                        },
                        {
                            key: 'customer_name',
                            label: 'Customer',
                            sortable: true,
                            render: (row) => (
                                <div>
                                    <div>{row.customer_name || '—'}</div>
                                    {row.customer_company && <div className="text-xs text-slate-500">{row.customer_company}</div>}
                                </div>
                            ),
                        },
                        { key: 'summary', label: 'Summary' },
                        {
                            key: 'fulfillment_state',
                            label: 'Status',
                            sortable: true,
                            render: (row) => <Badge>{row.fulfillment_state || row.status}</Badge>,
                        },
                        { key: 'created_at', label: 'Created', sortable: true },
                    ]}
                />
            </Card>
        </section>
    )
}
