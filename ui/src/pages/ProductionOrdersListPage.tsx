import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { ProductionOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function nextSort<T>(prev: SortState<T> | null, key: keyof T, defaultDir: SortDir = 'asc'): SortState<T> | null {
    if (!prev || prev.key !== key) return { key, dir: defaultDir }
    if (prev.dir === defaultDir) return { key, dir: defaultDir === 'asc' ? 'desc' : 'asc' }
    return null
}

function sortRows<T extends Record<string, any>>(rows: T[], state: SortState<T> | null) {
    if (!state) return rows
    return [...rows].sort((a, b) => {
        const aVal = a[state.key]
        const bVal = b[state.key]
        if (aVal == null && bVal == null) return 0
        if (aVal == null) return 1
        if (bVal == null) return -1
        const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true })
        return state.dir === 'asc' ? cmp : -cmp
    })
}

function SectionHeading({ id, title }: { id: string; title: string }) {
    return (
        <div id={id} className="flex items-center justify-between">
            <div className="text-lg font-semibold text-slate-800">{title}</div>
        </div>
    )
}

export function ProductionOrdersListPage() {
    const [productionOrders, setProductionOrders] = useState<ProductionOrder[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [productionSort, setProductionSort] = useState<SortState<ProductionOrder> | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api
            .productionOrders()
            .then((res) => {
                setProductionOrders(res.production_orders || [])
                setLoading(false)
            })
            .catch((err) => {
                setError(err.message || 'Failed to load production orders')
                setLoading(false)
            })
    }, [])

    const sortedProductionOrders = sortRows(productionOrders, productionSort)

    const handleProductionOrderClick = (row: ProductionOrder, index: number) => {
        setListContext({
            listType: 'production',
            items: sortedProductionOrders,
            currentIndex: index,
        })
        setHash('production', row.id)
    }

    if (loading) {
        return (
            <section>
                <SectionHeading id="production" title="Production Orders" />
                <Card>
                    <div className="text-sm text-slate-500">Loading production orders…</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <SectionHeading id="production" title="Production Orders" />
                <Card>
                    <div className="text-sm text-red-600">Error: {error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <SectionHeading id="production" title="Production Orders" />
            <Card>
                <Table
                    rows={sortedProductionOrders}
                    sortKey={productionSort?.key}
                    sortDir={productionSort?.dir}
                    onSort={(key) => setProductionSort((prev) => nextSort(prev, key, key === 'eta_finish' ? 'desc' : 'asc'))}
                    onRowClick={handleProductionOrderClick}
                    columns={[
                        {
                            key: 'id',
                            label: 'Order',
                            sortable: true,
                        },
                        {
                            key: 'item_sku',
                            label: 'Item',
                            sortable: true,
                            render: (row) => (
                                <div>
                                    <div>{row.item_sku}</div>
                                    <div className="text-xs text-slate-500">{row.item_name}</div>
                                </div>
                            ),
                        },
                        { key: 'qty_planned', label: 'Planned', sortable: true },
                        { key: 'qty_completed', label: 'Completed', sortable: true },
                        { key: 'current_operation', label: 'Operation', sortable: true },
                        { key: 'eta_finish', label: 'ETA Finish', sortable: true },
                        { key: 'eta_ship', label: 'ETA Ship', sortable: true },
                    ]}
                />
            </Card>
        </section>
    )
}
