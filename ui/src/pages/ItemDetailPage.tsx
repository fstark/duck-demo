import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Item, StockSummary } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatPrice } from '../utils/currency'
import { formatQuantity, Quantity } from '../utils/quantity.tsx'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface ItemDetailPageProps {
    sku: string
}

export function ItemDetailPage({ sku }: ItemDetailPageProps) {
    const [item, setItem] = useState<Item | null>(null)
    const [stock, setStock] = useState<StockSummary | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        Promise.all([
            api.itemDetail(sku),
            api.stock(sku)
        ])
            .then(([itemRes, stockRes]) => {
                setItem(itemRes as Item)
                setStock(stockRes as StockSummary)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load item details')
                setLoading(false)
            })
    }, [sku])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevItem = listContext.items[prevIndex] as Item
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('items', prevItem.sku)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextItem = listContext.items[nextIndex] as Item
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('items', nextItem.sku)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Item Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading item...</div>
                </Card>
            </section>
        )
    }

    if (error || !item) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Item Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Item not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('items')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Items'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Item Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('items')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Items'}
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
                <div className="space-y-2 text-sm text-slate-700">
                    <div className="font-semibold text-lg">{item.name}</div>
                    <div className="text-slate-600">
                        <span className="font-medium">SKU:</span> {item.sku}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Type:</span> {item.type ? <Badge>{item.type}</Badge> : '—'}
                    </div>
                    <div className="text-slate-600">
                        <span className="font-medium">Unit price:</span> {formatPrice(item.unit_price)}
                    </div>
                </div>
                {((item.recipes && item.recipes.length > 0) || (item.used_in_recipes && item.used_in_recipes.length > 0)) && (
                    <Card title="Recipes">
                        <Table
                            rows={[
                                ...(item.recipes || []).map(r => ({
                                    ...r,
                                    role: 'output',
                                    recipe_id: r.id,
                                    item_name: item.name,
                                    batch_qty: `${r.output_qty} ${item.uom || 'ea'}`,
                                })),
                                ...(item.used_in_recipes || []).map(r => ({
                                    ...r,
                                    role: 'ingredient',
                                    id: r.recipe_id,
                                    item_name: r.output_name,
                                    batch_qty: `${r.qty_per_batch} ${item.uom || ''}`,
                                    production_time_hours: undefined,
                                    ingredient_count: undefined,
                                    operation_count: undefined,
                                })),
                            ] as any}
                            columns={[
                                {
                                    key: 'role',
                                    label: 'Role',
                                    sortable: true,
                                    render: (row) => <Badge>{row.role}</Badge>
                                },
                                { key: 'recipe_id', label: 'Recipe ID', sortable: true, render: (row) => row.recipe_id || row.id },
                                { key: 'item_name', label: 'Item', sortable: true },
                                { key: 'batch_qty', label: 'Qty/Batch', sortable: true },
                                { key: 'production_time_hours', label: 'Time', sortable: true, render: (row) => row.production_time_hours ? `${row.production_time_hours}h` : '—' },
                                { key: 'ingredient_count', label: 'Ingredients', sortable: true, render: (row) => row.ingredient_count ?? '—' },
                                { key: 'operation_count', label: 'Operations', sortable: true, render: (row) => row.operation_count ?? '—' },
                            ]}
                            onRowClick={(row) => setHash('recipes', row.recipe_id || row.id)}
                        />
                    </Card>
                )}
                {stock && stock.by_location.length > 0 && (
                    <Card title="Stock Summary">
                        <div className="flex gap-3 text-slate-600 text-sm mb-3">
                            <span>On hand: <Quantity value={stock.on_hand_total} /></span>
                            <span>Reserved: <Quantity value={stock.reserved_total} /></span>
                            <span>Available: <Quantity value={stock.available_total} /></span>
                        </div>
                        <Table
                            rows={stock.by_location as any}
                            columns={[
                                { key: 'warehouse', label: 'Wh' },
                                { key: 'location', label: 'Loc' },
                                { key: 'on_hand', label: 'On hand', render: (row) => <Quantity value={row.on_hand} /> },
                                { key: 'reserved', label: 'Reserved', render: (row) => <Quantity value={row.reserved} /> },
                                { key: 'available', label: 'Available', render: (row) => <Quantity value={row.available} /> },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'stock',
                                    items: stock.by_location.map(s => ({ id: s.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'items', id: sku, label: item.name })
                                setHash('stock', row.id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
