import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Item } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatPrice } from '../utils/currency'
import { Quantity } from '../utils/quantity.tsx'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Item; dir: SortDir }

function sortRows(rows: Item[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Item): SortState {
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

export function ItemsListPage() {
    const [items, setItems] = useState<Item[]>([])
    const [itemSort, setItemSort] = useState<SortState | null>({ key: 'type', dir: 'asc' })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.items(false)
            .then((res) => {
                setItems(res.items || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load items')
                setLoading(false)
            })
    }, [])

    const sortedItems = sortRows(items, itemSort)

    const handleItemClick = (item: Item, index: number) => {
        // Store list context for future navigation
        setListContext({
            listType: 'items',
            items: sortedItems,
            currentIndex: index,
        })
        setHash('items', item.sku)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading items...</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
            <Card>
                <Table
                    rows={sortedItems}
                    sortKey={itemSort?.key}
                    sortDir={itemSort?.dir}
                    onSort={(key) => setItemSort((prev) => nextSort(prev, key))}
                    onRowClick={handleItemClick}
                    columns={[
                        {
                            key: 'image_url',
                            label: '',
                            sortable: false,
                            render: (row) => (
                                <div className="w-10 h-10 flex items-center justify-center">
                                    {row.image_url ? (
                                        <img
                                            src={row.image_url}
                                            alt={row.name}
                                            className="w-10 h-10 object-contain"
                                        />
                                    ) : (
                                        <div className="w-10 h-10 bg-slate-100 rounded flex items-center justify-center text-slate-400 text-xs">
                                            —
                                        </div>
                                    )}
                                </div>
                            ),
                        },
                        {
                            key: 'sku',
                            label: 'SKU',
                            sortable: true,
                        },
                        {
                            key: 'name',
                            label: 'Name',
                            sortable: true,
                        },
                        {
                            key: 'unit_price',
                            label: 'Unit price',
                            sortable: true,
                            render: (row) => <div className="text-right">{formatPrice(row.unit_price)}</div>,
                        },
                        {
                            key: 'type',
                            label: 'Type',
                            sortable: true,
                            render: (row) => <Badge>{row.type}</Badge>,
                        },
                        {
                            key: 'on_hand_total',
                            label: 'On hand',
                            sortable: true,
                            render: (row) => <Quantity value={row.on_hand_total} />,
                        },
                        {
                            key: 'reserved_total',
                            label: 'Reserved',
                            sortable: true,
                            render: (row) => <Quantity value={row.reserved_total} />,
                        },
                        {
                            key: 'available_total',
                            label: 'Available',
                            sortable: true,
                            render: (row) => <Quantity value={row.available_total} />,
                        },
                    ]}
                />
            </Card>
        </section>
    )
}
