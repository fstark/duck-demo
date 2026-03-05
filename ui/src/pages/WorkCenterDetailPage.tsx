import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { WorkCenterDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function SectionHeading({ id, title }: { id: string; title: string }) {
    return (
        <div id={id} className="flex items-center justify-between">
            <div className="text-lg font-semibold text-slate-800">{title}</div>
        </div>
    )
}

type WorkCenterDetailPageProps = {
    workCenterId: string
}

export function WorkCenterDetailPage({ workCenterId }: WorkCenterDetailPageProps) {
    const [workCenter, setWorkCenter] = useState<WorkCenterDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        api
            .workCenterDetail(workCenterId)
            .then((res) => {
                setWorkCenter(res)
                setLoading(false)
            })
            .catch((err) => {
                setError(err.message || 'Failed to load work center details')
                setLoading(false)
            })
    }, [workCenterId])

    // Prepare data for sorting - use empty arrays if no data yet
    const inProgressOps = workCenter?.operations.filter(op => op.status === 'in_progress') ?? []
    const pendingOps = workCenter?.operations.filter(op => op.status === 'pending') ?? []
    const completedOps = workCenter?.operations.filter(op => op.status === 'completed') ?? []

    // Call hooks unconditionally before any returns
    const inProgressSort = useTableSort(inProgressOps)
    const pendingSort = useTableSort(pendingOps.slice(0, 20))
    const completedSort = useTableSort(completedOps.slice(0, 10))

    const hasPrevious = listContext && listContext.listType === 'work-centers' && listContext.currentIndex > 0
    const hasNext = listContext && listContext.listType === 'work-centers' && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevItem = listContext.items[prevIndex] as any
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('work-centers', prevItem.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextItem = listContext.items[nextIndex] as any
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('work-centers', nextItem.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Work Center Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading work center…</div>
                </Card>
            </section>
        )
    }

    if (error || !workCenter) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Work Center Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Work center not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('work-centers')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Work Centers'}
                    </button>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Work Center Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('work-centers')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Work Centers'}
                    </button>
                    {listContext && listContext.listType === 'work-centers' && (
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
                    <div className="font-semibold text-lg">Work Center {workCenter.id}</div>
                    <div className="text-slate-600 text-base">{workCenter.name}</div>

                    <div className="space-y-4 mt-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-sm text-slate-500">Description</div>
                                <div className="text-slate-800">{workCenter.description || '—'}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500">Capacity</div>
                                <div className="text-slate-800 font-mono">{workCenter.max_concurrent} concurrent operations</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-4 gap-4 pt-4 border-t">
                            <div>
                                <div className="text-sm text-slate-500">In Progress</div>
                                <div className="text-2xl font-bold text-orange-600">{workCenter.in_progress}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500">Pending</div>
                                <div className="text-2xl font-bold text-yellow-600">{workCenter.pending}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500">Completed</div>
                                <div className="text-2xl font-bold text-green-600">{workCenter.completed}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-500">Utilization</div>
                                <div className={`text-2xl font-bold ${workCenter.utilization >= 100 ? 'text-red-600' :
                                    workCenter.utilization >= 75 ? 'text-orange-600' :
                                        workCenter.utilization >= 50 ? 'text-yellow-600' : 'text-green-600'
                                    }`}>
                                    {workCenter.utilization}%
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* In Progress Operations */}
                    {inProgressOps.length > 0 && (
                        <Card title="In Progress Operations">
                            <Table
                                rows={inProgressSort.sortedRows}
                                sortKey={inProgressSort.sortKey}
                                sortDir={inProgressSort.sortDir}
                                onSort={inProgressSort.onSort}
                                onRowClick={(row) => {
                                    setReferrer({ page: 'work-centers', id: workCenterId, label: `Work Center ${workCenter.id}` })
                                    setHash('production', row.production_order_id)
                                }}
                                columns={[
                                    {
                                        key: 'production_order_id',
                                        label: 'Production Order',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm text-brand-600">{row.production_order_id}</span>,
                                    },
                                    {
                                        key: 'operation_name',
                                        label: 'Operation',
                                        sortable: true,
                                        render: (row) => <span className="font-medium">{row.operation_name}</span>,
                                    },
                                    {
                                        key: 'item_name',
                                        label: 'Item',
                                        sortable: true,
                                        render: (row) => (
                                            <span className="text-sm">
                                                {row.item_name} <span className="text-slate-500">({row.item_sku})</span>
                                            </span>
                                        ),
                                    },
                                    {
                                        key: 'duration_hours',
                                        label: 'Duration',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm">{row.duration_hours}h</span>,
                                    },
                                    {
                                        key: 'started_at',
                                        label: 'Started',
                                        sortable: true,
                                        render: (row) => (
                                            <span className="text-sm text-slate-600">
                                                {row.started_at ? row.started_at.split('.')[0] : '—'}
                                            </span>
                                        ),
                                    },
                                ]}
                            />
                        </Card>
                    )}

                    {/* Pending Operations */}
                    {pendingOps.length > 0 && (
                        <Card title={`Pending Operations (${pendingOps.length})`}>
                            <Table
                                rows={pendingSort.sortedRows}
                                sortKey={pendingSort.sortKey}
                                sortDir={pendingSort.sortDir}
                                onSort={pendingSort.onSort}
                                onRowClick={(row) => {
                                    setReferrer({ page: 'work-centers', id: workCenterId, label: `Work Center ${workCenter.id}` })
                                    setHash('production', row.production_order_id)
                                }}
                                columns={[
                                    {
                                        key: 'production_order_id',
                                        label: 'Production Order',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm text-brand-600">{row.production_order_id}</span>,
                                    },
                                    {
                                        key: 'operation_name',
                                        label: 'Operation',
                                        sortable: true,
                                        render: (row) => <span className="font-medium">{row.operation_name}</span>,
                                    },
                                    {
                                        key: 'item_name',
                                        label: 'Item',
                                        sortable: true,
                                        render: (row) => (
                                            <span className="text-sm">
                                                {row.item_name} <span className="text-slate-500">({row.item_sku})</span>
                                            </span>
                                        ),
                                    },
                                    {
                                        key: 'duration_hours',
                                        label: 'Duration',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm">{row.duration_hours}h</span>,
                                    },
                                ]}
                            />
                            {pendingOps.length > 20 && (
                                <div className="text-sm text-slate-500 text-center pt-4">
                                    Showing 20 of {pendingOps.length} pending operations
                                </div>
                            )}
                        </Card>
                    )}

                    {/* Completed Operations */}
                    {completedOps.length > 0 && (
                        <Card title={`Recently Completed (${Math.min(completedOps.length, 10)})`}>
                            <Table
                                rows={completedSort.sortedRows}
                                sortKey={completedSort.sortKey}
                                sortDir={completedSort.sortDir}
                                onSort={completedSort.onSort}
                                onRowClick={(row) => {
                                    setReferrer({ page: 'work-centers', id: workCenterId, label: `Work Center ${workCenter.id}` })
                                    setHash('production', row.production_order_id)
                                }}
                                columns={[
                                    {
                                        key: 'production_order_id',
                                        label: 'Production Order',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm text-brand-600">{row.production_order_id}</span>,
                                    },
                                    {
                                        key: 'operation_name',
                                        label: 'Operation',
                                        sortable: true,
                                        render: (row) => <span className="font-medium text-slate-600">{row.operation_name}</span>,
                                    },
                                    {
                                        key: 'item_name',
                                        label: 'Item',
                                        sortable: true,
                                        render: (row) => (
                                            <span className="text-sm text-slate-600">
                                                {row.item_name} <span className="text-slate-400">({row.item_sku})</span>
                                            </span>
                                        ),
                                    },
                                    {
                                        key: 'duration_hours',
                                        label: 'Duration',
                                        sortable: true,
                                        render: (row) => <span className="font-mono text-sm text-slate-600">{row.duration_hours}h</span>,
                                    },
                                    {
                                        key: 'completed_at',
                                        label: 'Completed',
                                        sortable: true,
                                        render: (row) => (
                                            <span className="text-sm text-slate-600">
                                                {row.completed_at ? row.completed_at.split('.')[0] : '—'}
                                            </span>
                                        ),
                                    },
                                ]}
                            />
                        </Card>
                    )}
                </div>
            </Card>
        </section>
    )
}
