import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Invoice } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Invoice; dir: SortDir }

function sortRows(rows: Invoice[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Invoice, defaultDir: SortDir = 'asc'): SortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: defaultDir }
}

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

export function InvoicesListPage() {
    const [invoices, setInvoices] = useState<Invoice[]>([])
    const [invoiceSort, setInvoiceSort] = useState<SortState | null>({ key: 'created_at', dir: 'desc' })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext, setReferrer } = useNavigation()

    useEffect(() => {
        setLoading(true)
        api.invoices()
            .then((data) => {
                setInvoices(data.invoices || [])
                setError(null)
            })
            .catch((err) => setError(String(err)))
            .finally(() => setLoading(false))
    }, [])

    const sorted = sortRows(invoices, invoiceSort)

    const handleRowClick = (row: Invoice, index: number) => {
        setListContext({
            listType: 'invoices',
            items: sorted,
            currentIndex: index,
        })
        setHash('invoices', row.id)
    }

    const handleSort = (key: string) => {
        setInvoiceSort((prev) => nextSort(prev, key as keyof Invoice, key === 'created_at' ? 'desc' : 'asc'))
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Invoices</div>
            {loading && (
                <Card>
                    <div className="text-sm text-slate-500">Loading invoices...</div>
                </Card>
            )}
            {error && (
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            )}
            {!loading && !error && (
                <Card>
                    <Table
                        rows={sorted as any}
                        sortKey={invoiceSort?.key}
                        sortDir={invoiceSort?.dir}
                        onSort={handleSort}
                        onRowClick={handleRowClick}
                        columns={[
                            { key: 'id', label: 'Invoice', sortable: true },
                            { key: 'sales_order_id', label: 'Sales Order', sortable: true },
                            {
                                key: 'customer_name',
                                label: 'Customer',
                                sortable: true,
                                render: (row: Invoice) => (
                                    <div>
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                if (row.customer_id) {
                                                    setReferrer({ page: 'invoices', label: 'Invoices' })
                                                    setHash('customers', row.customer_id)
                                                }
                                            }}
                                            type="button"
                                        >
                                            {row.customer_name || row.customer_id}
                                        </button>
                                        {row.customer_company && <div className="text-xs text-slate-500">{row.customer_company}</div>}
                                    </div>
                                ),
                            },
                            {
                                key: 'total',
                                label: 'Total',
                                sortable: true,
                                render: (row: Invoice) => <div className="text-right">{formatCurrency(row.total, row.currency)}</div>,
                            },
                            {
                                key: 'status',
                                label: 'Status',
                                sortable: true,
                                render: (row: Invoice) => (
                                    <Badge>{row.status}</Badge>
                                ),
                            },
                            { key: 'invoice_date', label: 'Invoice Date', sortable: true, render: (row: Invoice) => formatDate(row.invoice_date) },
                            { key: 'due_date', label: 'Due Date', sortable: true, render: (row: Invoice) => formatDate(row.due_date) },
                        ]}
                    />
                </Card>
            )}
        </section>
    )
}
