import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Item, StockSummary } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { formatQuantity, Quantity, formatQtyWithUom } from '../utils/quantity'
import { formatDate } from '../utils/date'
import { useTableSort } from '../utils/useTableSort'

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

    // Prepare data for sorting - before conditional returns
    const recipesRows = [
        ...(item?.recipes || []).map(r => ({
            ...r,
            role: 'output',
            recipe_id: r.id,
            item_name: item?.name || '',
            batch_qty: formatQtyWithUom(r.output_qty, item?.uom || 'ea'),
        })),
        ...(item?.used_in_recipes || []).map(r => ({
            ...r,
            role: 'ingredient',
            id: r.recipe_id,
            item_name: r.output_name,
            batch_qty: formatQtyWithUom(r.qty_per_batch, item?.uom || 'ea'),
            production_time_hours: undefined,
            ingredient_count: undefined,
            operation_count: undefined,
        })),
    ] as any

    // Call hooks unconditionally before any returns
    const recipesSort = useTableSort(recipesRows)
    const productionSort = useTableSort(item?.production_orders || [])
    const purchaseSort = useTableSort(item?.purchase_orders || [])

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
                    <div className="flex items-start gap-6">
                        <div className="flex-1">
                            <div className="font-semibold text-lg">{item.name}</div>
                            <div className="text-slate-600">
                                <span className="font-medium">SKU:</span> {item.sku}
                            </div>
                            <div className="text-slate-600">
                                <span className="font-medium">Type:</span> {item.type ? <Badge>{item.type}</Badge> : '—'}
                            </div>
                            {item.uom && (
                                <div className="text-slate-600">
                                    <span className="font-medium">Unit of Measure:</span> {item.uom}
                                </div>
                            )}
                            <div className="text-slate-600">
                                <span className="font-medium">Unit price:</span> {formatCurrency(item.unit_price)}
                            </div>
                            {item.cost_price != null && (
                                <div className="text-slate-600">
                                    <span className="font-medium">Cost price:</span> {formatCurrency(item.cost_price)}
                                </div>
                            )}
                            {item.reorder_qty != null && item.reorder_qty > 0 && (
                                <div className="text-slate-600">
                                    <span className="font-medium">Reorder qty:</span> {formatQtyWithUom(item.reorder_qty, item.uom)}
                                </div>
                            )}
                            {item.default_supplier_id && (
                                <div className="text-slate-600">
                                    <span className="font-medium">Default supplier:</span>{' '}
                                    <button
                                        className="text-brand-600 hover:underline text-left"
                                        onClick={() => {
                                            setReferrer({ page: 'items', id: sku, label: item.name })
                                            setHash('suppliers', item.default_supplier_id!)
                                        }}
                                        type="button"
                                    >
                                        {item.default_supplier_id}
                                    </button>
                                </div>
                            )}
                        </div>
                        {item.image_url && (
                            <div className="flex-shrink-0">
                                <img
                                    src={item.image_url}
                                    alt={item.name}
                                    className="w-64 h-64 object-contain rounded border border-slate-200"
                                />
                            </div>
                        )}
                    </div>
                </div>
                {((item.recipes && item.recipes.length > 0) || (item.used_in_recipes && item.used_in_recipes.length > 0)) && (
                    <Card title="Recipes">
                        <Table
                            rows={recipesSort.sortedRows}
                            sortKey={recipesSort.sortKey}
                            sortDir={recipesSort.sortDir}
                            onSort={recipesSort.onSort}
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
                            onRowClick={(row: any) => setHash('recipes', row.recipe_id || row.id)}
                        />
                    </Card>
                )}
                {stock && stock.by_location.length > 0 && (
                    <Card title="Stock Summary">
                        <div className="flex gap-3 text-slate-600 text-sm mb-3">
                            <span>On hand: <Quantity value={stock.on_hand_total} uom={item.uom} /></span>
                            <span>Reserved: <Quantity value={stock.reserved_total} uom={item.uom} /></span>
                            <span>Available: <Quantity value={stock.available_total} uom={item.uom} /></span>
                        </div>
                        <Table
                            rows={stock.by_location as any}
                            columns={[
                                { key: 'warehouse', label: 'Wh' },
                                { key: 'location', label: 'Loc' },
                                { key: 'on_hand', label: 'On hand', render: (row) => <Quantity value={row.on_hand} uom={item.uom} /> },
                                { key: 'reserved', label: 'Reserved', render: (row) => <Quantity value={row.reserved} uom={item.uom} /> },
                                { key: 'available', label: 'Available', render: (row) => <Quantity value={row.available} uom={item.uom} /> },
                            ]}
                            onRowClick={(row: any, index) => {
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
                {item.production_orders && item.production_orders.length > 0 && (
                    <Card title="Production Orders">
                        <Table
                            rows={productionSort.sortedRows as any}
                            sortKey={productionSort.sortKey}
                            sortDir={productionSort.sortDir}
                            onSort={productionSort.onSort}
                            columns={[
                                { key: 'id', label: 'Order ID', sortable: true },
                                { key: 'recipe_id', label: 'Recipe', sortable: true },
                                { key: 'qty_produced', label: 'Qty', sortable: true, render: (row) => <Quantity value={row.qty_produced} uom="ea" /> },
                                { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'started_at', label: 'Started', sortable: true, render: (row) => formatDate(row.started_at) },
                                { key: 'eta_finish', label: 'ETA Finish', sortable: true, render: (row) => formatDate(row.eta_finish) },
                            ]}
                            onRowClick={(row) => {
                                setReferrer({ page: 'items', id: sku, label: item.name })
                                setHash('production', row.id)
                            }}
                        />
                    </Card>
                )}
                {item.purchase_orders && item.purchase_orders.length > 0 && (
                    <Card title="Purchase Orders">
                        <Table
                            rows={purchaseSort.sortedRows as any}
                            sortKey={purchaseSort.sortKey}
                            sortDir={purchaseSort.sortDir}
                            onSort={purchaseSort.onSort}
                            columns={[
                                { key: 'id', label: 'PO ID', sortable: true },
                                { key: 'supplier_name', label: 'Supplier', sortable: true },
                                { key: 'qty', label: 'Qty', sortable: true, render: (row) => <Quantity value={row.qty} uom={item.uom} /> },
                                { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'expected_delivery', label: 'Expected', sortable: true },
                            ]}
                            onRowClick={(row) => {
                                setReferrer({ page: 'items', id: sku, label: item.name })
                                setHash('purchase-orders', row.id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
