import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Email } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatDate } from '../utils/date'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Email; dir: SortDir }

function sortRows(rows: Email[], state: SortState | null) {
    if (!state) return rows
    const { key, dir } = state
    const sorted = [...rows].sort((a, b) => {
        const av = a[key]
        const bv = b[key]
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        if (typeof av === 'number' && typeof bv === 'number') {
            return dir === 'asc' ? av - bv : bv - av
        }
        const compare = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' })
        return dir === 'asc' ? compare : -compare
    })
    return sorted
}

function nextSort(prev: SortState | null, key: keyof Email): SortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: 'asc' }
}

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

export function EmailsListPage() {
    const [emails, setEmails] = useState<Email[]>([])
    const [emailSort, setEmailSort] = useState<SortState | null>({ key: 'modified_at', dir: 'desc' })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        setLoading(true)
        api.emails()
            .then((data) => {
                setEmails(data.emails)
                setError(null)
            })
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false))
    }, [])

    const sorted = sortRows(emails, emailSort)

    const columns = [
        { key: 'subject', label: 'Subject', sortable: true },
        { key: 'recipient_email', label: 'Recipient', sortable: true },
        { key: 'customer_id', label: 'Customer', sortable: true },
        { key: 'sales_order_id', label: 'Sales Order', sortable: true, render: (row: Email) => row.sales_order_id || '—' },
        {
            key: 'status',
            label: 'Status',
            sortable: true,
            render: (row: Email) => (
                <Badge variant={row.status === 'sent' ? 'success' : 'neutral'}>
                    {row.status}
                </Badge>
            )
        },
        { key: 'created_at', label: 'Created', sortable: true, render: (row: Email) => formatDate(row.created_at) },
        { key: 'modified_at', label: 'Modified', sortable: true, render: (row: Email) => formatDate(row.modified_at) },
        { key: 'sent_at', label: 'Sent', sortable: true, render: (row: Email) => formatDate(row.sent_at) },
    ]

    const handleRowClick = (row: Email) => {
        const index = sorted.findIndex((e) => e.id === row.id)
        setListContext({
            listType: 'emails',
            items: sorted,
            currentIndex: index,
        })
        setHash('emails', row.id)
    }

    const handleSort = (key: string) => {
        setEmailSort(nextSort(emailSort, key as keyof Email))
    }

    return (
        <div className="space-y-6">
            <Card title="Emails">
                {loading && <div className="text-slate-600">Loading...</div>}
                {error && <div className="text-red-700">Error: {error}</div>}
                {!loading && !error && (
                    <Table
                        columns={columns}
                        rows={sorted as any}
                        onRowClick={handleRowClick}
                        onSort={handleSort}
                        sortState={emailSort ? { key: emailSort.key, direction: emailSort.dir } : undefined}
                    />
                )}
            </Card>
        </div>
    )
}
