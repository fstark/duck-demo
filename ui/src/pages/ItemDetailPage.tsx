import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Item, StockSummary } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatPrice } from '../utils/currency'

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
            api.items(false),
            api.stock(sku)
        ])
            .then(([itemsRes, stockRes]) => {
                const found = itemsRes.items?.find((i) => i.sku === sku)
                setItem(found || null)
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
                    {stock ? (
                        <div className="mt-4 space-y-2 border-t pt-3">
                            <div className="font-medium">Stock Summary</div>
                            <div className="flex gap-3 text-slate-600">
                                <span>On hand: {stock.on_hand_total}</span>
                                <span>Reserved: {stock.reserved_total}</span>
                                <span>Available: {stock.available_total}</span>
                            </div>
                            <Table
                                rows={stock.by_location as any}
                                columns={[
                                    { key: 'warehouse', label: 'Wh' },
                                    { key: 'location', label: 'Loc' },
                                    { key: 'on_hand', label: 'On hand' },
                                    { key: 'reserved', label: 'Reserved' },
                                    { key: 'available', label: 'Available' },
                                ]}
                                onRowClick={(row) => {
                                    setReferrer({ page: 'items', id: sku, label: item.name })
                                    setHash('stock', row.id)
                                }}
                            />
                        </div>
                    ) : (
                        <div className="text-slate-500 mt-4">Loading stock...</div>
                    )}
                </div>
            </Card>
        </section>
    )
}
