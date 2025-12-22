import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { Stock } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatQuantity } from '../utils/quantity.tsx'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface StockDetailPageProps {
    stockId: string
}

export function StockDetailPage({ stockId }: StockDetailPageProps) {
    const [stock, setStock] = useState<Stock | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer } = useNavigation()

    useEffect(() => {
        api.stockDetail(stockId)
            .then((res) => {
                setStock(res as Stock)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load stock details')
                setLoading(false)
            })
    }, [stockId])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevStock = listContext.items[prevIndex] as Stock
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('stock', prevStock.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextStock = listContext.items[nextIndex] as Stock
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('stock', nextStock.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Stock Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading stock...</div>
                </Card>
            </section>
        )
    }

    if (error || !stock) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Stock Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Stock not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('stock')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Stock'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Stock Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('stock')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Stock'}
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
                <div className="space-y-3 text-sm text-slate-800">
                    <div className="font-semibold text-lg">
                        <button
                            className="text-brand-600 hover:underline text-left"
                            onClick={() => {
                                setReferrer({ page: 'stock', id: stockId, label: `Stock ${stock.id}` })
                                setHash('items', stock.item_sku)
                            }}
                            type="button"
                        >
                            {stock.item_sku}
                        </button>
                        <span className="text-slate-600 font-normal"> — {stock.item_name}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Item">
                            <div className="space-y-1">
                                <div><span className="font-medium">SKU:</span> {stock.item_sku}</div>
                                <div><span className="font-medium">Name:</span> {stock.item_name}</div>
                                <div><span className="font-medium">Type:</span> <Badge>{stock.item_type}</Badge></div>
                            </div>
                        </Card>
                        <Card title="Location">
                            <div className="space-y-1">
                                <div><span className="font-medium">Warehouse:</span> {stock.warehouse}</div>
                                <div><span className="font-medium">Location:</span> {stock.location}</div>
                            </div>
                        </Card>
                    </div>
                    <Card title="Quantities">
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <div className="text-2xl font-semibold text-red-600 font-mono">{formatQuantity(stock.on_hand)}</div>
                                <div className="text-xs text-slate-600">On Hand</div>
                            </div>
                            <div>
                                <div className="text-2xl font-semibold text-red-600 font-mono">{formatQuantity(stock.reserved)}</div>
                                <div className="text-xs text-slate-600">Reserved</div>
                            </div>
                            <div>
                                <div className="text-2xl font-semibold text-red-600 font-mono">{formatQuantity(stock.available)}</div>
                                <div className="text-xs text-slate-600">Available</div>
                            </div>
                        </div>
                    </Card>
                </div>
            </Card>
        </section>
    )
}
