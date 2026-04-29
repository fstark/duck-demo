import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { ImportJob } from '../types'
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
        default: return 'neutral' as const
    }
}

export function ImportJobsListPage() {
    const [jobs, setJobs] = useState<ImportJob[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.importJobs()
            .then((res) => {
                setJobs(res.import_jobs || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load import jobs')
                setLoading(false)
            })
    }, [])

    const tableSort = useTableSort(jobs, { key: 'created_at', dir: 'desc' })

    const handleRowClick = (job: ImportJob, index: number) => {
        setListContext({
            listType: 'import-jobs',
            items: tableSort.sortedRows,
            currentIndex: index,
        })
        setHash('import-jobs', job.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Data Imports</div>
                <Card><div className="text-sm text-slate-500">Loading imports...</div></Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Data Imports</div>
                <Card><div className="text-sm text-red-600">{error}</div></Card>
            </section>
        )
    }

    const columns = [
        { key: 'id' as keyof ImportJob, label: 'ID', sortable: true },
        { key: 'entity_type' as keyof ImportJob, label: 'Entity Type', sortable: true },
        { key: 'source_filename' as keyof ImportJob, label: 'Source File', sortable: true },
        { key: 'row_count' as keyof ImportJob, label: 'Rows', sortable: true },
        {
            key: 'status' as keyof ImportJob,
            label: 'Status',
            sortable: true,
            render: (row: ImportJob) => (
                <Badge variant={statusVariant(row.status)}>{row.status}</Badge>
            ),
        },
        {
            key: 'created_at' as keyof ImportJob,
            label: 'Created',
            sortable: true,
            render: (row: ImportJob) => formatDate(row.created_at),
        },
        {
            key: 'executed_at' as keyof ImportJob,
            label: 'Executed',
            sortable: true,
            render: (row: ImportJob) => row.executed_at ? formatDate(row.executed_at) : '—',
        },
    ]

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Data Imports</div>
            <Card>
                <Table
                    rows={tableSort.sortedRows}
                    columns={columns}
                    sortKey={tableSort.sortKey}
                    sortDir={tableSort.sortDir}
                    onSort={tableSort.onSort}
                    onRowClick={handleRowClick}
                />
                {jobs.length === 0 && (
                    <div className="text-sm text-slate-500 py-4 text-center">No import jobs found.</div>
                )}
            </Card>
        </section>
    )
}
