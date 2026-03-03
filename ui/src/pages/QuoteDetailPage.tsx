import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import type { QuoteDetail } from '../types'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'
import { formatQuantity } from '../utils/quantity'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface QuoteDetailPageProps {
    quoteId: string
}

function QuoteDetailPage({ quoteId }: QuoteDetailPageProps) {
    const [quote, setQuote] = useState<QuoteDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!quoteId) return
        loadQuote()
    }, [quoteId])

    const loadQuote = async () => {
        if (!quoteId) return
        setLoading(true)
        setError(null)
        try {
            const result = await api.quoteDetail(quoteId)
            setQuote(result)
        } catch (err) {
            console.error('Failed to load quote:', err)
            setError(err instanceof Error ? err.message : 'Failed to load quote')
        } finally {
            setLoading(false)
        }
    }

    const getStatusBadge = (status: string) => {
        const variants: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
            draft: 'info',
            sent: 'warning',
            accepted: 'success',
            rejected: 'danger',
            expired: 'danger',
            superseded: 'info'
        }
        return <Badge variant={variants[status] || 'info'}>{status}</Badge>
    }

    const downloadPDF = () => {
        if (!quoteId) return
        const apiBase = import.meta.env.VITE_API_BASE || '/api'
        window.open(`${apiBase}/quotes/${encodeURIComponent(quoteId)}/pdf`, '_blank')
    }

    if (loading) {
        return (
            <div className="space-y-4">
                <h1 className="text-2xl font-bold">Loading quote...</h1>
            </div>
        )
    }

    if (error || !quote) {
        return (
            <div className="space-y-4">
                <h1 className="text-2xl font-bold text-red-600">Error</h1>
                <Card>
                    <p>{error || 'Quote not found'}</p>
                </Card>
            </div>
        )
    }

    const q = quote.quote
    const lines = quote.lines || []
    const revisions = quote.revisions || []

    const linesSort = useTableSort(lines)
    const revisionsSort = useTableSort(revisions)

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold">Quote {q.id}</h1>
                <div className="flex gap-2">
                    <button
                        onClick={downloadPDF}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                        📄 Download PDF
                    </button>
                </div>
            </div>

            {/* Quote Information */}
            <Card>
                <h2 className="text-xl font-semibold mb-4">Quote Information</h2>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <p className="text-sm text-gray-600">Quote ID</p>
                        <p className="font-medium">{q.id}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Revision</p>
                        <p className="font-medium">R{q.revision_number}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Status</p>
                        <div className="mt-1">{getStatusBadge(q.status)}</div>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Customer</p>
                        <button
                            className="font-medium text-brand-600 hover:underline text-left"
                            onClick={() => setHash('customers', q.customer_id)}
                            type="button"
                        >
                            {q.customer_company || q.customer_name || q.customer_id}
                        </button>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Created At</p>
                        <p className="font-medium">{formatDate(q.created_at)}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Sent At</p>
                        <p className="font-medium">{q.sent_at ? formatDate(q.sent_at) : '-'}</p>
                    </div>
                    <div>
                        <p className="text-sm text-gray-600">Valid Until</p>
                        <p className="font-medium">{q.valid_until ? formatDate(q.valid_until) : '-'}</p>
                    </div>
                    {q.requested_delivery_date && (
                        <div>
                            <p className="text-sm text-gray-600">Requested Delivery</p>
                            <p className="font-medium">{formatDate(q.requested_delivery_date)}</p>
                        </div>
                    )}
                    {q.supersedes_quote_id && (
                        <div>
                            <p className="text-sm text-gray-600">Supersedes</p>
                            <button
                                className="font-medium text-brand-600 hover:underline text-left"
                                onClick={() => setHash('quotes', q.supersedes_quote_id!)}
                                type="button"
                            >
                                {q.supersedes_quote_id}
                            </button>
                        </div>
                    )}
                    {quote.newer_revision && (
                        <div>
                            <p className="text-sm text-gray-600">Newer Revision</p>
                            <button
                                className="font-medium text-brand-600 hover:underline text-left"
                                onClick={() => setHash('quotes', quote.newer_revision!.id)}
                                type="button"
                            >
                                {quote.newer_revision.id}
                            </button>
                        </div>
                    )}
                    {q.accepted_at && (
                        <div>
                            <p className="text-sm text-gray-600">Accepted At</p>
                            <p className="font-medium">{formatDate(q.accepted_at)}</p>
                        </div>
                    )}
                    {q.rejected_at && (
                        <div>
                            <p className="text-sm text-gray-600">Rejected At</p>
                            <p className="font-medium">{formatDate(q.rejected_at)}</p>
                        </div>
                    )}
                    {q.sales_order_id && (
                        <div>
                            <p className="text-sm text-gray-600">Sales Order</p>
                            <button
                                className="font-medium text-brand-600 hover:underline text-left"
                                onClick={() => setHash('orders', q.sales_order_id!)}
                                type="button"
                            >
                                {q.sales_order_id}
                            </button>
                        </div>
                    )}
                </div>
            </Card>

            {/* Shipping Address */}
            {(q.ship_to_line1 || q.ship_to_city) && (
                <Card>
                    <h2 className="text-xl font-semibold mb-4">Shipping Address</h2>
                    <div className="space-y-1">
                        {q.ship_to_line1 && <p>{q.ship_to_line1}</p>}
                        {q.ship_to_line2 && <p>{q.ship_to_line2}</p>}
                        {(q.ship_to_postal_code || q.ship_to_city) && (
                            <p>
                                {q.ship_to_postal_code && <span>{q.ship_to_postal_code} </span>}
                                {q.ship_to_city && <span>{q.ship_to_city}</span>}
                            </p>
                        )}
                        {q.ship_to_country && <p>{q.ship_to_country}</p>}
                    </div>
                </Card>
            )}

            {/* Note */}
            {q.note && (
                <Card>
                    <h2 className="text-xl font-semibold mb-4">Note</h2>
                    <p className="text-slate-700 whitespace-pre-wrap">{q.note}</p>
                </Card>
            )}

            {/* Quote Lines */}
            <Card>
                <h2 className="text-xl font-semibold mb-4">Line Items</h2>
                {lines.length === 0 ? (
                    <p className="text-gray-500">No line items</p>
                ) : (
                    <Table
                        rows={linesSort.sortedRows as any}
                        sortKey={linesSort.sortKey}
                        sortDir={linesSort.sortDir}
                        onSort={linesSort.onSort}
                        columns={[
                            {
                                key: 'sku', label: 'SKU', sortable: true, render: (line: any) => (
                                    <button
                                        className="text-brand-600 hover:underline text-left"
                                        onClick={() => setHash('items', line.sku)}
                                        type="button"
                                    >
                                        {line.sku}
                                    </button>
                                )
                            },
                            { key: 'item_name', label: 'Item', sortable: true, render: (line: any) => line.item_name || '—' },
                            { key: 'qty', label: 'Quantity', sortable: true, render: (line: any) => formatQuantity(line.qty) },
                            { key: 'unit_price', label: 'Unit Price', sortable: true, render: (line: any) => formatCurrency(line.unit_price) },
                            { key: 'line_total', label: 'Line Total', sortable: true, render: (line: any) => formatCurrency(line.line_total) }
                        ]}
                    />
                )}
            </Card>

            {/* Pricing Summary */}
            <Card>
                <h2 className="text-xl font-semibold mb-4">Pricing Summary</h2>
                <div className="space-y-2">
                    <div className="flex justify-between">
                        <span>Subtotal</span>
                        <span className="font-medium">{formatCurrency(q.subtotal)}</span>
                    </div>
                    {q.discount > 0 && (
                        <div className="flex justify-between">
                            <span>Discount</span>
                            <span className="font-medium">−{formatCurrency(q.discount)}</span>
                        </div>
                    )}
                    {q.shipping > 0 && (
                        <div className="flex justify-between">
                            <span>Shipping</span>
                            <span className="font-medium">{formatCurrency(q.shipping)}</span>
                        </div>
                    )}
                    <div className="flex justify-between">
                        <span>Tax</span>
                        <span className="font-medium">{formatCurrency(q.tax)}</span>
                    </div>
                    <div className="flex justify-between text-lg font-semibold border-t pt-2">
                        <span>Total</span>
                        <span>{formatCurrency(q.total)}</span>
                    </div>
                </div>
            </Card>

            {/* Revisions */}
            {revisions.length > 0 && (
                <Card>
                    <h2 className="text-xl font-semibold mb-4">Revision History</h2>
                    <Table
                        rows={revisionsSort.sortedRows as any}
                        sortKey={revisionsSort.sortKey}
                        sortDir={revisionsSort.sortDir}
                        onSort={revisionsSort.onSort}
                        onRowClick={(r: any) => setHash('quotes', r.id)}
                        columns={[
                            { key: 'id', label: 'Quote ID', sortable: true },
                            { key: 'revision_number', label: 'Revision', sortable: true, render: (r: any) => `R${r.revision_number}` },
                            { key: 'status', label: 'Status', sortable: true, render: (r: any) => getStatusBadge(r.status) },
                            { key: 'created_at', label: 'Created', sortable: true, render: (r: any) => formatDate(r.created_at) },
                        ]}
                    />
                </Card>
            )}
        </div>
    )
}

export default QuoteDetailPage
