import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Stock } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { Quantity } from '../utils/quantity.tsx'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Stock; dir: SortDir }

function sortRows(rows: Stock[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Stock, defaultDir: SortDir = 'asc'): SortState {
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

export function StockListPage() {
    const [stock, setStock] = useState<Stock[]>([])
    const [stockSort, setStockSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.stockList()
            .then((res) => {
                setStock(res.stock || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load stock')
                setLoading(false)
            })
    }, [])

    const sortedStock = sortRows(stock, stockSort)

    const handleStockClick = (row: Stock, index: number) => {
        setListContext({
            listType: 'stock',
            items: sortedStock,
            currentIndex: index,
        })
        setHash('stock', row.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Stock</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading stock...</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Stock</div>
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Stock</div>
            <Card>
                <Table
                    rows={sortedStock}
                    sortKey={stockSort?.key}
                    sortDir={stockSort?.dir}
                    onSort={(key) => setStockSort((prev) => nextSort(prev, key))}
                    onRowClick={handleStockClick}
                    columns={[
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
                        {
                            key: 'item_type',
                            label: 'Type',
                            sortable: true,
                            render: (row) => <Badge>{row.item_type}</Badge>,
                        },
                        { key: 'warehouse', label: 'Warehouse', sortable: true },
                        { key: 'location', label: 'Location', sortable: true },
                        {
                            key: 'on_hand',
                            label: 'On Hand',
                            sortable: true,
                            render: (row) => <Quantity value={row.on_hand} />,
                        },
                        {
                            key: 'reserved',
                            label: 'Reserved',
                            sortable: true,
                            render: (row) => <Quantity value={row.reserved} />,
                        },
                        {
                            key: 'available',
                            label: 'Available',
                            sortable: true,
                            render: (row) => <Quantity value={row.available} />,
                        },
                    ]}
                />
            </Card>
        </section>
    )
}
