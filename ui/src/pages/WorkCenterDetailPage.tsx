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
    const { listContext, clearListContext } = useNavigation()

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

    const navigateTo = (direction: 'prev' | 'next') => {
        if (!listContext || listContext.listType !== 'work-centers') return
        const { items, currentIndex } = listContext
        const newIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1
        if (newIndex >= 0 && newIndex < items.length) {
            const newItem = items[newIndex]
            setHash('work-centers', newItem.id)
        }
    }

    const canNavigate = (direction: 'prev' | 'next') => {
        if (!listContext || listContext.listType !== 'work-centers') return false
        const { items, currentIndex } = listContext
        return direction === 'prev' ? currentIndex > 0 : currentIndex < items.length - 1
    }

    if (loading) {
        return (
            <div>
                <div className="mb-4">
                    <button onClick={() => setHash('work-centers')} className="text-sky-600 hover:text-sky-700 text-sm">
                        ← Back to Work Centers
                    </button>
                </div>
                <Card>
                    <div className="text-sm text-slate-500">Loading work center…</div>
                </Card>
            </div>
        )
    }

    if (error || !workCenter) {
        return (
            <div>
                <div className="mb-4">
                    <button onClick={() => setHash('work-centers')} className="text-sky-600 hover:text-sky-700 text-sm">
                        ← Back to Work Centers
                    </button>
                </div>
                <Card>
                    <div className="text-sm text-red-600">Error: {error || 'Work center not found'}</div>
                </Card>
            </div>
        )
    }

    const inProgressOps = workCenter.operations.filter(op => op.status === 'in_progress')
    const pendingOps = workCenter.operations.filter(op => op.status === 'pending')
    const completedOps = workCenter.operations.filter(op => op.status === 'completed')

    const inProgressSort = useTableSort(inProgressOps)
    const pendingSort = useTableSort(pendingOps.slice(0, 20))
    const completedSort = useTableSort(completedOps.slice(0, 10))

    return (
        <div>
            <div className="mb-4 flex items-center justify-between">
                <button
                    onClick={() => {
                        clearListContext()
                        setHash('work-centers')
                    }}
                    className="text-sky-600 hover:text-sky-700 text-sm"
                >
                    ← Back to Work Centers
                </button>
                {listContext && listContext.listType === 'work-centers' && (
                    <div className="flex gap-2">
                        <button
                            onClick={() => navigateTo('prev')}
                            disabled={!canNavigate('prev')}
                            className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            ← Previous
                        </button>
                        <button
                            onClick={() => navigateTo('next')}
                            disabled={!canNavigate('next')}
                            className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            Next →
                        </button>
                    </div>
                )}
            </div>

            <SectionHeading id="work-center-details" title={workCenter.name} />

            <Card>
                <div className="space-y-4">
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
            </Card>

            {/* In Progress Operations */}
            {inProgressOps.length > 0 && (
                <>
                    <SectionHeading id="in-progress-ops" title="In Progress Operations" />
                    <Card>
                        <Table
                            rows={inProgressSort.sortedRows}
                            sortKey={inProgressSort.sortKey}
                            sortDir={inProgressSort.sortDir}
                            onSort={inProgressSort.onSort}
                            onRowClick={(row) => setHash('production', row.production_order_id)}
                            columns={[
                                {
                                    key: 'production_order_id',
                                    label: 'Production Order',
                                    sortable: true,
                                    render: (row) => <span className="font-mono text-sm text-sky-600">{row.production_order_id}</span>,
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
                </>
            )}

            {/* Pending Operations */}
            {pendingOps.length > 0 && (
                <>
                    <SectionHeading id="pending-ops" title={`Pending Operations (${pendingOps.length})`} />
                    <Card>
                        <Table
                            rows={pendingSort.sortedRows}
                            sortKey={pendingSort.sortKey}
                            sortDir={pendingSort.sortDir}
                            onSort={pendingSort.onSort}
                            onRowClick={(row) => setHash('production', row.production_order_id)}
                            columns={[
                                {
                                    key: 'production_order_id',
                                    label: 'Production Order',
                                    sortable: true,
                                    render: (row) => <span className="font-mono text-sm text-sky-600">{row.production_order_id}</span>,
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
                </>
            )}

            {/* Completed Operations */}
            {completedOps.length > 0 && (
                <>
                    <SectionHeading id="completed-ops" title={`Recently Completed (${Math.min(completedOps.length, 10)})`} />
                    <Card>
                        <Table
                            rows={completedSort.sortedRows}
                            sortKey={completedSort.sortKey}
                            sortDir={completedSort.sortDir}
                            onSort={completedSort.onSort}
                            onRowClick={(row) => setHash('production', row.production_order_id)}
                            columns={[
                                {
                                    key: 'production_order_id',
                                    label: 'Production Order',
                                    sortable: true,
                                    render: (row) => <span className="font-mono text-sm text-sky-600">{row.production_order_id}</span>,
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
                </>
            )}
        </div>
    )
}
