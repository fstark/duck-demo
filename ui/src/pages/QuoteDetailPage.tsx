import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import type { Quote, QuoteDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { Quantity } from '../utils/quantity'
import { formatDate } from '../utils/date'
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

export function QuoteDetailPage({ quoteId }: QuoteDetailPageProps) {
    const [data, setData] = useState<QuoteDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, setReferrer, referrer, clearListContext } = useNavigation()

    useEffect(() => {
        if (!quoteId) return
        api.quoteDetail(quoteId)
            .then((result) => {
                setData(result)
                setLoading(false)
            })
            .catch((err) => {
                console.error('Failed to load quote:', err)
                setError(err instanceof Error ? err.message : 'Failed to load quote')
                setLoading(false)
            })
    }, [quoteId])

    // Call hooks before conditional returns
    const lines = data?.lines || []
    const revisions = data?.revisions || []
    const linesSort = useTableSort(lines)
    const revisionsSort = useTableSort(revisions)

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevQuote = listContext.items[prevIndex] as Quote
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('quotes', prevQuote.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextQuote = listContext.items[nextIndex] as Quote
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('quotes', nextQuote.id)
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

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Quote Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading quote...</div>
                </Card>
            </section>
        )
    }

    if (error || !data) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Quote Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Quote not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('quotes')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Quotes'}
                    </button>
                </Card>
            </section>
        )
    }

    const q = data.quote
    const currency = q.currency || 'EUR'

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Quote Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('quotes')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Quotes'}
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
                    <div className="flex items-center gap-3 justify-between">
                        <div className="flex items-center gap-3">
                            <div className="font-semibold text-lg">
                                Quote {q.id}
                                {q.revision_number != null && <span className="text-slate-500 text-sm ml-2">R{q.revision_number}</span>}
                            </div>
                            {getStatusBadge(q.status)}
                        </div>
                        <a
                            href={`/api/quotes/${encodeURIComponent(quoteId)}/pdf`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-4 py-2 bg-brand-600 text-white rounded hover:bg-brand-700 text-sm font-medium"
                        >
                            📄 Download PDF
                        </a>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Customer">
                            <div className="space-y-1">
                                <button
                                    className="font-medium text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                        setHash('customers', q.customer_id)
                                    }}
                                    type="button"
                                >
                                    {q.customer_company || q.customer_name || q.customer_id}
                                </button>
                                {q.customer_company && q.customer_name && (
                                    <div className="text-slate-600 text-sm">{q.customer_name}</div>
                                )}
                            </div>
                        </Card>

                        <Card title="Dates">
                            <div className="space-y-1">
                                <div><span className="text-slate-500">Created:</span> {formatDate(q.created_at)}</div>
                                {q.sent_at && <div><span className="text-slate-500">Sent:</span> {formatDate(q.sent_at)}</div>}
                                <div><span className="text-slate-500">Valid until:</span> {q.valid_until ? formatDate(q.valid_until) : '—'}</div>
                                {q.requested_delivery_date && <div><span className="text-slate-500">Requested delivery:</span> {formatDate(q.requested_delivery_date)}</div>}
                                {q.accepted_at && <div><span className="text-slate-500">Accepted:</span> {formatDate(q.accepted_at)}</div>}
                                {q.rejected_at && <div><span className="text-slate-500">Rejected:</span> {formatDate(q.rejected_at)}</div>}
                            </div>
                        </Card>
                    </div>

                    {(q.ship_to_line1 || q.ship_to_city) && (
                        <Card title="Shipping Address">
                            <div className="space-y-1">
                                {q.ship_to_line1 && <div>{q.ship_to_line1}</div>}
                                {q.ship_to_line2 && <div>{q.ship_to_line2}</div>}
                                {(q.ship_to_postal_code || q.ship_to_city) && (
                                    <div>
                                        {q.ship_to_postal_code && <span>{q.ship_to_postal_code} </span>}
                                        {q.ship_to_city && <span>{q.ship_to_city}</span>}
                                    </div>
                                )}
                                {q.ship_to_country && <div>{q.ship_to_country}</div>}
                            </div>
                        </Card>
                    )}

                    {q.note && (
                        <Card title="Note">
                            <div className="text-slate-700 whitespace-pre-wrap">{q.note}</div>
                        </Card>
                    )}

                    {q.supersedes_quote_id && (
                        <Card title="Supersedes">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                    setHash('quotes', q.supersedes_quote_id)
                                }}
                                type="button"
                            >
                                {q.supersedes_quote_id}
                            </button>
                        </Card>
                    )}

                    {data.newer_revision && (
                        <Card title="Newer Revision">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                    setHash('quotes', data.newer_revision!.id)
                                }}
                                type="button"
                            >
                                {data.newer_revision.id}
                            </button>
                        </Card>
                    )}

                    {q.sales_order_id && (
                        <Card title="Sales Order">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                    setHash('orders', q.sales_order_id)
                                }}
                                type="button"
                            >
                                {q.sales_order_id}
                            </button>
                        </Card>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Line Items">
                            {lines.length === 0 ? (
                                <div className="text-slate-500">No line items</div>
                            ) : (
                                <Table
                                    rows={linesSort.sortedRows as any}
                                    sortKey={linesSort.sortKey}
                                    sortDir={linesSort.sortDir}
                                    onSort={linesSort.onSort as any}
                                    columns={[
                                        {
                                            key: 'sku', label: 'SKU', sortable: true, render: (line: any) => (
                                                <button
                                                    className="text-brand-600 hover:underline text-left"
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                                        setHash('items', line.sku)
                                                    }}
                                                    type="button"
                                                >
                                                    {line.sku}
                                                </button>
                                            )
                                        },
                                        { key: 'item_name', label: 'Item', sortable: true, render: (line: any) => line.item_name || '—' },
                                        { key: 'qty', label: 'Qty', sortable: true, render: (line: any) => <Quantity value={line.qty} /> },
                                        { key: 'unit_price', label: 'Unit Price', sortable: true, render: (line: any) => formatCurrency(line.unit_price, currency) },
                                        { key: 'line_total', label: 'Line Total', sortable: true, render: (line: any) => <div className="text-right">{formatCurrency(line.line_total, currency)}</div> }
                                    ]}
                                    onRowClick={(line: any, index: number) => {
                                        setListContext({
                                            listType: 'items',
                                            items: lines.map((l: any) => ({ sku: l.sku })) as any,
                                            currentIndex: index,
                                        })
                                        setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                        setHash('items', line.sku)
                                    }}
                                />
                            )}
                        </Card>
                        <Card title="Pricing">
                            <div className="space-y-1 text-sm">
                                <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>{formatCurrency(q.subtotal, currency)}</span></div>
                                {q.discount > 0 && <div className="flex justify-between"><span className="text-slate-500">Discount</span><span>−{formatCurrency(q.discount, currency)}</span></div>}
                                {q.shipping > 0 && <div className="flex justify-between"><span className="text-slate-500">Shipping</span><span>{formatCurrency(q.shipping, currency)}</span></div>}
                                <div className="flex justify-between"><span className="text-slate-500">Tax</span><span>{formatCurrency(q.tax, currency)}</span></div>
                                <div className="flex justify-between font-semibold border-t pt-1"><span>Total</span><span>{formatCurrency(q.total, currency)}</span></div>
                            </div>
                        </Card>
                    </div>

                    {revisions.length > 0 && (
                        <Card title="Revision History">
                            <Table
                                rows={revisionsSort.sortedRows as any}
                                sortKey={revisionsSort.sortKey}
                                sortDir={revisionsSort.sortDir}
                                onSort={revisionsSort.onSort as any}
                                onRowClick={(r: any) => {
                                    setReferrer({ page: 'quotes', id: quoteId, label: `Quote ${q.id}` })
                                    setHash('quotes', r.id)
                                }}
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
            </Card>
        </section>
    )
}

export default QuoteDetailPage
