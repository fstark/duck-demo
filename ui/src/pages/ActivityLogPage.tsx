import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { ActivityLogEntry } from '../types'
import { formatDate } from '../utils/date'

const CATEGORIES = ['sales', 'production', 'logistics', 'purchasing', 'billing'] as const

const CATEGORY_COLORS: Record<string, string> = {
    sales: 'bg-blue-100 text-blue-700',
    production: 'bg-amber-100 text-amber-700',
    logistics: 'bg-green-100 text-green-700',
    purchasing: 'bg-purple-100 text-purple-700',
    billing: 'bg-rose-100 text-rose-700',
}

/** Map entity_type values to hash page routes. */
function entityHref(entityType: string | null, entityId: string | null): string | null {
    if (!entityType || !entityId) return null
    const map: Record<string, string> = {
        sales_order: 'orders',
        quote: 'quotes',
        production_order: 'production',
        shipment: 'shipments',
        invoice: 'invoices',
        purchase_order: 'purchase-orders',
        email: 'emails',
    }
    const page = map[entityType]
    return page ? `#/${page}/${encodeURIComponent(entityId)}` : null
}

const PAGE_SIZE = 50

export function ActivityLogPage() {
    const [entries, setEntries] = useState<ActivityLogEntry[]>([])
    const [total, setTotal] = useState(0)
    const [offset, setOffset] = useState(0)
    const [loading, setLoading] = useState(true)
    const [category, setCategory] = useState('')
    const [actionFilter, setActionFilter] = useState('')
    const [error, setError] = useState<string | null>(null)

    const load = useCallback((newOffset: number) => {
        setLoading(true)
        api.activityLog({
            limit: PAGE_SIZE,
            offset: newOffset,
            category: category || undefined,
            action: actionFilter || undefined,
        })
            .then((data) => {
                if (newOffset === 0) {
                    setEntries(data.entries)
                } else {
                    setEntries((prev) => [...prev, ...data.entries])
                }
                setTotal(data.total)
                setOffset(newOffset)
                setError(null)
            })
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false))
    }, [category, actionFilter])

    // Reload on filter change
    useEffect(() => {
        load(0)
    }, [load])

    const handleLoadMore = () => {
        load(offset + PAGE_SIZE)
    }

    return (
        <section className="space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold text-slate-800">Activity Log</h1>
                <span className="text-sm text-slate-500">{total.toLocaleString()} entries</span>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-3 items-center">
                <select
                    className="rounded border border-slate-300 bg-white px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                >
                    <option value="">All categories</option>
                    {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{c}</option>
                    ))}
                </select>
                <input
                    type="text"
                    placeholder="Filter by action…"
                    className="rounded border border-slate-300 bg-white px-2 py-1 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-slate-400"
                    value={actionFilter}
                    onChange={(e) => setActionFilter(e.target.value)}
                />
            </div>

            {error && (
                <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
            )}

            {/* Entries table */}
            <div className="overflow-x-auto rounded border border-slate-200 bg-white">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        <tr>
                            <th className="px-3 py-2 w-40">Time</th>
                            <th className="px-3 py-2 w-28">Category</th>
                            <th className="px-3 py-2">Action</th>
                            <th className="px-3 py-2 w-32">Entity</th>
                            <th className="px-3 py-2 w-28">Actor</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {entries.map((e) => {
                            const href = entityHref(e.entity_type, e.entity_id)
                            const catClass = CATEGORY_COLORS[e.category] || 'bg-slate-100 text-slate-700'
                            return (
                                <tr key={e.id} className="hover:bg-slate-50">
                                    <td className="px-3 py-1.5 tabular-nums text-slate-600 whitespace-nowrap">{formatDate(e.timestamp)}</td>
                                    <td className="px-3 py-1.5">
                                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${catClass}`}>
                                            {e.category}
                                        </span>
                                    </td>
                                    <td className="px-3 py-1.5 text-slate-800">{e.action}</td>
                                    <td className="px-3 py-1.5">
                                        {href ? (
                                            <a href={href} className="text-blue-600 hover:underline font-mono text-xs">{e.entity_id}</a>
                                        ) : (
                                            <span className="font-mono text-xs text-slate-400">{e.entity_id ?? '—'}</span>
                                        )}
                                    </td>
                                    <td className="px-3 py-1.5 text-slate-500">{e.actor}</td>
                                </tr>
                            )
                        })}
                        {entries.length === 0 && !loading && (
                            <tr>
                                <td colSpan={5} className="px-3 py-6 text-center text-slate-400">No entries</td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Load more */}
            {entries.length < total && (
                <div className="flex justify-center">
                    <button
                        onClick={handleLoadMore}
                        disabled={loading}
                        className="rounded bg-slate-100 px-4 py-1.5 text-sm text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                    >
                        {loading ? 'Loading…' : `Load more (${entries.length} / ${total})`}
                    </button>
                </div>
            )}
            {loading && entries.length === 0 && (
                <div className="text-center text-sm text-slate-400 py-8">Loading…</div>
            )}
        </section>
    )
}
