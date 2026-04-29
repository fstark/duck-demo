import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { ImportJobDetail, ImportRow } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatDate } from '../utils/date'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function statusVariant(status: string) {
    switch (status) {
        case 'executed': return 'success' as const
        case 'validated': return 'info' as const
        case 'staging': return 'warning' as const
        case 'ready': return 'success' as const
        case 'imported': return 'success' as const
        case 'needs_review': return 'warning' as const
        case 'rejected': return 'danger' as const
        case 'merged': return 'neutral' as const
        default: return 'neutral' as const
    }
}

interface ImportJobDetailPageProps {
    jobId: string
}

export function ImportJobDetailPage({ jobId }: ImportJobDetailPageProps) {
    const [job, setJob] = useState<ImportJobDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer } = useNavigation()

    useEffect(() => {
        api.importJobDetail(jobId)
            .then((data) => {
                setJob(data)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load import job')
                setLoading(false)
            })
    }, [jobId])

    const rowsSort = useTableSort(job?.rows || [])

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Import Job</div>
                <Card><div className="text-sm text-slate-500">Loading import job...</div></Card>
            </section>
        )
    }

    if (error || !job) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Import Job</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Import job not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => setHash('import-jobs')}
                        type="button"
                    >
                        ← Back to Data Imports
                    </button>
                </Card>
            </section>
        )
    }

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevJob = listContext.items[prevIndex] as { id: string }
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('import-jobs', prevJob.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextJob = listContext.items[nextIndex] as { id: string }
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('import-jobs', nextJob.id)
    }

    const rowColumns = [
        { key: 'source_row' as keyof ImportRow, label: 'Row #', sortable: true },
        {
            key: 'status' as keyof ImportRow,
            label: 'Status',
            sortable: true,
            render: (row: ImportRow) => <Badge variant={statusVariant(row.status)}>{row.status}</Badge>,
        },
        {
            key: 'mapped_data' as keyof ImportRow,
            label: 'Mapped Data',
            render: (row: ImportRow) => {
                const entries = Object.entries(row.mapped_data).filter(([, v]) => v != null && v !== '')
                if (entries.length === 0) return '—'
                return (
                    <div className="max-w-md truncate text-xs text-slate-600">
                        {entries.map(([k, v]) => `${k}: ${v}`).join(', ')}
                    </div>
                )
            },
        },
        {
            key: 'issues' as keyof ImportRow,
            label: 'Issues',
            render: (row: ImportRow) => {
                if (!row.issues || row.issues.length === 0) return '—'
                return (
                    <div className="space-y-0.5">
                        {row.issues.map((iss, i) => (
                            <div key={i} className="text-xs">
                                <Badge variant={iss.severity === 'error' ? 'danger' : 'warning'}>{iss.severity}</Badge>
                                <span className="ml-1 text-slate-600">{iss.message}</span>
                            </div>
                        ))}
                    </div>
                )
            },
        },
        {
            key: 'created_entity_id' as keyof ImportRow,
            label: 'Created Entity',
            sortable: true,
            render: (row: ImportRow) => {
                if (row.merged_into) return <span className="text-xs text-slate-500">merged → {row.merged_into}</span>
                if (!row.created_entity_id) return '—'
                return <span className="text-xs">{row.created_entity_type}: {row.created_entity_id}</span>
            },
        },
    ]

    return (
        <section className="space-y-4">
            <div className="text-lg font-semibold text-slate-800">Import Job</div>

            {/* Header card */}
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('import-jobs')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Data Imports'}
                    </button>
                    {listContext && listContext.listType === 'import-jobs' && (
                        <div className="flex items-center gap-2 text-sm">
                            <button
                                className="px-2 py-1 rounded border border-slate-200 disabled:opacity-40"
                                disabled={!hasPrevious}
                                onClick={handlePrevious}
                                type="button"
                            >
                                ← Prev
                            </button>
                            <span className="text-slate-500">
                                {listContext.currentIndex + 1} of {listContext.items.length}
                            </span>
                            <button
                                className="px-2 py-1 rounded border border-slate-200 disabled:opacity-40"
                                disabled={!hasNext}
                                onClick={handleNext}
                                type="button"
                            >
                                Next →
                            </button>
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                        <div className="text-xs text-slate-500">ID</div>
                        <div className="text-sm font-medium">{job.id}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Entity Type</div>
                        <div className="text-sm font-medium">{job.entity_type || '—'}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Source File</div>
                        <div className="text-sm font-medium">{job.source_filename || '—'}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Format</div>
                        <div className="text-sm font-medium">{job.source_format || '—'}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Status</div>
                        <div className="text-sm"><Badge variant={statusVariant(job.status)}>{job.status}</Badge></div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Rows</div>
                        <div className="text-sm font-medium">{job.row_count ?? '—'}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Created</div>
                        <div className="text-sm font-medium">{formatDate(job.created_at)}</div>
                    </div>
                    <div>
                        <div className="text-xs text-slate-500">Executed</div>
                        <div className="text-sm font-medium">{job.executed_at ? formatDate(job.executed_at) : '—'}</div>
                    </div>
                </div>
            </Card>

            {/* Column mapping */}
            {job.mapping_plan && job.mapping_plan.length > 0 && (
                <Card title="Column Mapping">
                    <div className="overflow-auto">
                        <table className="min-w-full text-sm text-slate-800">
                            <thead className="bg-slate-100 text-xs uppercase text-slate-500">
                                <tr>
                                    <th className="px-3 py-2 text-left font-semibold">Source Column</th>
                                    <th className="px-3 py-2 text-left font-semibold">Target Field</th>
                                    <th className="px-3 py-2 text-left font-semibold">Transform</th>
                                    <th className="px-3 py-2 text-left font-semibold">Confidence</th>
                                </tr>
                            </thead>
                            <tbody>
                                {job.mapping_plan.map((m, i) => (
                                    <tr key={i} className="border-b border-slate-100">
                                        <td className="px-3 py-2">{m.source}</td>
                                        <td className="px-3 py-2">{m.target || '—'}</td>
                                        <td className="px-3 py-2 text-slate-500">{m.transform || '—'}</td>
                                        <td className="px-3 py-2">
                                            {m.confidence != null ? `${Math.round(m.confidence * 100)}%` : '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}

            {/* Issues summary */}
            {Object.keys(job.issues_summary).length > 0 && (
                <Card title="Row Status Summary">
                    <div className="flex flex-wrap gap-3">
                        {Object.entries(job.issues_summary).map(([status, count]) => (
                            <div key={status} className="flex items-center gap-1.5">
                                <Badge variant={statusVariant(status)}>{status}</Badge>
                                <span className="text-sm font-medium">{count}</span>
                            </div>
                        ))}
                    </div>
                </Card>
            )}

            {/* Rows table */}
            <Card title={`Import Rows (${job.rows.length})`}>
                <Table
                    rows={rowsSort.sortedRows}
                    columns={rowColumns}
                    sortKey={rowsSort.sortKey}
                    sortDir={rowsSort.sortDir}
                    onSort={rowsSort.onSort}
                />
                {job.rows.length === 0 && (
                    <div className="text-sm text-slate-500 py-4 text-center">No rows.</div>
                )}
            </Card>
        </section>
    )
}
