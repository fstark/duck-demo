import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { WorkCenter } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

function nextSort<T>(prev: SortState<T> | null, key: keyof T, defaultDir: SortDir = 'asc'): SortState<T> | null {
    if (!prev || prev.key !== key) return { key, dir: defaultDir }
    if (prev.dir === defaultDir) return { key, dir: defaultDir === 'asc' ? 'desc' : 'asc' }
    return null
}

function sortRows<T extends Record<string, any>>(rows: T[], state: SortState<T> | null) {
    if (!state) return rows
    return [...rows].sort((a, b) => {
        const aVal = a[state.key]
        const bVal = b[state.key]
        if (aVal == null && bVal == null) return 0
        if (aVal == null) return 1
        if (bVal == null) return -1
        const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true })
        return state.dir === 'asc' ? cmp : -cmp
    })
}

function SectionHeading({ id, title }: { id: string; title: string }) {
    return (
        <div id={id} className="flex items-center justify-between">
            <div className="text-lg font-semibold text-slate-800">{title}</div>
        </div>
    )
}

export function WorkCentersListPage() {
    const [workCenters, setWorkCenters] = useState<WorkCenter[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [sort, setSort] = useState<SortState<WorkCenter> | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api
            .workCenters()
            .then((res) => {
                setWorkCenters(res.work_centers || [])
                setLoading(false)
            })
            .catch((err) => {
                setError(err.message || 'Failed to load work centers')
                setLoading(false)
            })
    }, [])

    const sortedWorkCenters = sortRows(workCenters, sort)

    const handleWorkCenterClick = (row: WorkCenter, index: number) => {
        setListContext({
            listType: 'work-centers',
            items: sortedWorkCenters,
            currentIndex: index,
        })
        setHash('work-centers', row.id)
    }

    if (loading) {
        return (
            <section>
                <SectionHeading id="work-centers" title="Work Centers" />
                <Card>
                    <div className="text-sm text-slate-500">Loading work centers…</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <SectionHeading id="work-centers" title="Work Centers" />
                <Card>
                    <div className="text-sm text-red-600">Error: {error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <SectionHeading id="work-centers" title="Work Centers" />
            <Card>
                <Table
                    rows={sortedWorkCenters}
                    sortKey={sort?.key}
                    sortDir={sort?.dir}
                    onSort={(key) => setSort((prev) => nextSort(prev, key))}
                    onRowClick={handleWorkCenterClick}
                    columns={[
                        {
                            key: 'name',
                            label: 'Work Center',
                            sortable: true,
                            render: (row) => <span className="font-medium text-sky-600">{row.name}</span>,
                        },
                        {
                            key: 'description',
                            label: 'Description',
                            sortable: false,
                            render: (row) => <span className="text-sm text-slate-600">{row.description || '—'}</span>,
                        },
                        {
                            key: 'max_concurrent',
                            label: 'Capacity',
                            sortable: true,
                            render: (row) => <span className="font-mono text-sm">{row.max_concurrent}</span>,
                        },
                        {
                            key: 'in_progress',
                            label: 'In Progress',
                            sortable: true,
                            render: (row) => (
                                <Badge>
                                    <span className={row.in_progress >= row.max_concurrent ? 'text-red-600 font-semibold' : row.in_progress > 0 ? 'text-orange-600' : ''}>
                                        {row.in_progress} / {row.max_concurrent}
                                    </span>
                                </Badge>
                            ),
                        },
                        {
                            key: 'pending',
                            label: 'Pending',
                            sortable: true,
                            render: (row) => (
                                <Badge>
                                    <span className={row.pending > 0 ? 'text-yellow-700' : ''}>{row.pending}</span>
                                </Badge>
                            ),
                        },
                        {
                            key: 'utilization',
                            label: 'Utilization',
                            sortable: true,
                            render: (row) => {
                                const util = row.utilization
                                const color = util >= 100 ? 'text-red-600' : util >= 75 ? 'text-orange-600' : util >= 50 ? 'text-yellow-600' : 'text-green-600'
                                return <span className={`font-mono text-sm font-semibold ${color}`}>{util}%</span>
                            },
                        },
                        {
                            key: 'completed',
                            label: 'Completed',
                            sortable: true,
                            render: (row) => <span className="text-sm text-slate-600">{row.completed}</span>,
                        },
                    ]}
                />
                {sortedWorkCenters.length === 0 && (
                    <div className="text-sm text-slate-500 text-center py-4">No work centers configured</div>
                )}
            </Card>
        </section>
    )
}
