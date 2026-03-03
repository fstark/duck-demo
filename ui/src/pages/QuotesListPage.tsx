import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import type { Quote } from '../types'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'
import { useNavigation } from '../contexts/NavigationContext'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function QuotesListPage() {
    const [quotes, setQuotes] = useState<Quote[]>([])
    const [statusFilter, setStatusFilter] = useState<string>('')
    const [showSuperseded, setShowSuperseded] = useState(false)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setReferrer } = useNavigation()

    useEffect(() => {
        loadQuotes()
    }, [statusFilter, showSuperseded])

    const loadQuotes = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await api.quotes({
                status: statusFilter || undefined,
                show_superseded: showSuperseded
            })
            setQuotes(result.quotes || [])
        } catch (err) {
            console.error('Failed to load quotes:', err)
            setError(err instanceof Error ? err.message : 'Failed to load quotes')
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

    const quotesSort = useTableSort(quotes)

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold">Quotes</h1>
            </div>

            <Card>
                <div className="flex gap-4 mb-4">
                    <div>
                        <label className="block text-sm font-medium mb-1">Status</label>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="border rounded px-3 py-2"
                        >
                            <option value="">All Statuses</option>
                            <option value="draft">Draft</option>
                            <option value="sent">Sent</option>
                            <option value="accepted">Accepted</option>
                            <option value="rejected">Rejected</option>
                            <option value="expired">Expired</option>
                        </select>
                    </div>
                    <div className="flex items-end">
                        <label className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                checked={showSuperseded}
                                onChange={(e) => setShowSuperseded(e.target.checked)}
                                className="rounded"
                            />
                            <span className="text-sm">Show superseded revisions</span>
                        </label>
                    </div>
                </div>

                {loading ? (
                    <div className="text-center py-8 text-gray-500">Loading quotes...</div>
                ) : error ? (
                    <div className="text-center py-8">
                        <div className="text-sm text-red-600">{error}</div>
                    </div>
                ) : quotes.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">No quotes found</div>
                ) : (
                    <Table
                        rows={quotesSort.sortedRows as any}
                        sortKey={quotesSort.sortKey}
                        sortDir={quotesSort.sortDir}
                        onSort={quotesSort.onSort}
                        onRowClick={(q: Quote) => setHash('quotes', q.id)}
                        columns={[
                            { key: 'id', label: 'Quote ID', sortable: true },
                            {
                                key: 'customer_company',
                                label: 'Customer',
                                sortable: true,
                                render: (q: Quote) => (
                                    <button
                                        className="text-brand-600 hover:underline text-left"
                                        onClick={(e) => {
                                            e.stopPropagation()
                                            setReferrer({ page: 'quotes', label: 'Quotes' })
                                            setHash('customers', q.customer_id)
                                        }}
                                        type="button"
                                    >
                                        {q.customer_company || q.customer_name || q.customer_id}
                                    </button>
                                ),
                            },
                            { key: 'revision_number', label: 'Revision', sortable: true, render: (q: Quote) => `R${q.revision_number}` },
                            { key: 'status', label: 'Status', sortable: true, render: (q: Quote) => getStatusBadge(q.status) },
                            { key: 'total', label: 'Total', sortable: true, render: (q: Quote) => formatCurrency(q.total) },
                            { key: 'valid_until', label: 'Valid Until', sortable: true, render: (q: Quote) => q.valid_until ? formatDate(q.valid_until) : '—' },
                            { key: 'created_at', label: 'Created', sortable: true, render: (q: Quote) => formatDate(q.created_at) },
                            { key: 'sent_at', label: 'Sent', sortable: true, render: (q: Quote) => q.sent_at ? formatDate(q.sent_at) : '—' },
                        ]}
                    />
                )}
            </Card>
        </div>
    )
}

export default QuotesListPage
