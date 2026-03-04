import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { CustomerDetail, Customer, Email, Invoice, Quote } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface CustomerDetailPageProps {
    customerId: string
}

export function CustomerDetailPage({ customerId }: CustomerDetailPageProps) {
    const [customer, setCustomer] = useState<CustomerDetail | null>(null)
    const [emails, setEmails] = useState<Email[]>([])
    const [invoices, setInvoices] = useState<Invoice[]>([])
    const [quotes, setQuotes] = useState<Quote[]>([])
    const [loading, setLoading] = useState(true)
    const { listContext, setListContext, referrer, setReferrer } = useNavigation()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        // Fetch customer details, emails, invoices, and quotes
        Promise.all([
            api.customerDetail(customerId),
            api.emails({ customer_id: customerId }),
            api.invoices({ customer_id: customerId }),
            api.quotes({ customer_id: customerId }),
        ])
            .then(([customerData, emailsData, invoicesData, quotesData]) => {
                setCustomer(customerData)
                setEmails(emailsData.emails)
                setInvoices(invoicesData.invoices || [])
                setQuotes(quotesData.quotes || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load customer details')
                setLoading(false)
            })
    }, [customerId])

    // Call hooks before conditional returns
    const salesOrdersSort = useTableSort(customer?.sales_orders || [])
    const shipmentsSort = useTableSort(customer?.shipments || [])
    const invoicesSort = useTableSort(invoices)
    const quotesSort = useTableSort(quotes)
    const emailsSort = useTableSort(emails)

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading customer...</div>
                </Card>
            </section>
        )
    }

    if (error || !customer) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Customer not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('customers')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Customers'}
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
        const prevCustomer = listContext.items[prevIndex] as Customer
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('customers', prevCustomer.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextCustomer = listContext.items[nextIndex] as Customer
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('customers', nextCustomer.id)
    }

    // Compute customer status badge
    const hasLateInvoices = invoices.some(inv => inv.status === 'overdue')
    const hasInvoices = invoices.length > 0
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)
    const isActive = (customer.sales_orders || []).some(o =>
        o.created_at && new Date(o.created_at) >= thirtyDaysAgo
    )

    let customerStatusLabel: string
    let customerStatusVariant: 'danger' | 'info' | 'success' | 'neutral'
    if (hasLateInvoices) {
        customerStatusLabel = 'Late Invoices'
        customerStatusVariant = 'danger'
    } else if (hasInvoices) {
        customerStatusLabel = 'Has Invoices'
        customerStatusVariant = 'info'
    } else if (isActive) {
        customerStatusLabel = 'Active'
        customerStatusVariant = 'success'
    } else {
        customerStatusLabel = 'Inactive'
        customerStatusVariant = 'neutral'
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Customer Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('customers')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Customers'}
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
                    <div className="font-semibold text-lg">
                        {customer.id} — {customer.name}
                        <span className="ml-3 align-middle">
                            <Badge variant={customerStatusVariant}>{customerStatusLabel}</Badge>
                        </span>
                    </div>
                    {customer.company && (
                        <div className="text-slate-600">{customer.company}</div>
                    )}
                    <div className="text-slate-500 text-xs">
                        Created {formatDate(customer.created_at)}
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Contact">
                            <div className="space-y-1 text-sm text-slate-600">
                                <div><span className="font-medium">Email:</span> {customer.email || '—'}</div>
                                <div><span className="font-medium">Phone:</span> {customer.phone || '—'}</div>
                            </div>
                        </Card>
                        <Card title="Billing">
                            <div className="space-y-1 text-sm text-slate-600">
                                <div><span className="font-medium">Tax ID:</span> {customer.tax_id || '—'}</div>
                                <div><span className="font-medium">Payment Terms:</span> {customer.payment_terms ? `Net ${customer.payment_terms}` : '—'}</div>
                                <div><span className="font-medium">Currency:</span> {customer.currency || '—'}</div>
                            </div>
                        </Card>
                    </div>

                    <Card title="Address">
                        {customer.address_line1 || customer.city ? (
                            <div className="text-sm text-slate-600">
                                {customer.address_line1 && <div>{customer.address_line1}</div>}
                                {customer.address_line2 && <div>{customer.address_line2}</div>}
                                <div>
                                    {[customer.postal_code, customer.city].filter(Boolean).join(' ')}
                                    {customer.country && `, ${customer.country}`}
                                </div>
                            </div>
                        ) : (
                            <div className="text-sm text-slate-400 italic">No address on file</div>
                        )}
                    </Card>

                    {customer.notes && (
                        <Card title="Notes">
                            <div className="text-sm text-slate-600 whitespace-pre-wrap">{customer.notes}</div>
                        </Card>
                    )}
                </div>
                {quotes.length > 0 && (
                    <Card title="Quotes">
                        <Table
                            rows={quotesSort.sortedRows as any}
                            sortKey={quotesSort.sortKey}
                            sortDir={quotesSort.sortDir}
                            onSort={quotesSort.onSort}
                            columns={[
                                { key: 'id', label: 'Quote', sortable: true },
                                { key: 'revision_number', label: 'Rev', sortable: true, render: (q: Quote) => `R${q.revision_number}` },
                                { key: 'total', label: 'Total', sortable: true, render: (q: Quote) => <div className="text-right">{formatCurrency(q.total)}</div> },
                                { key: 'status', label: 'Status', sortable: true, render: (q: Quote) => <Badge>{q.status}</Badge> },
                                { key: 'valid_until', label: 'Valid Until', sortable: true, render: (q: Quote) => q.valid_until ? formatDate(q.valid_until) : '—' },
                                { key: 'created_at', label: 'Created', sortable: true, render: (q: Quote) => formatDate(q.created_at) },
                            ]}
                            onRowClick={(q: Quote, index: number) => {
                                setListContext({
                                    listType: 'quotes',
                                    items: quotes.map(qt => ({ id: qt.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('quotes', q.id)
                            }}
                        />
                    </Card>
                )}
                {customer.sales_orders && customer.sales_orders.length > 0 && (
                    <Card title="Sales Orders">
                        <Table
                            rows={salesOrdersSort.sortedRows as any}
                            sortKey={salesOrdersSort.sortKey}
                            sortDir={salesOrdersSort.sortDir}
                            onSort={salesOrdersSort.onSort}
                            columns={[
                                { key: 'sales_order_id', label: 'Order', sortable: true },
                                { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'total', label: 'Total', sortable: true, render: (row: any) => <div className="text-right">{formatCurrency(row.total, row.currency)}</div> },
                                { key: 'created_at', label: 'Created', sortable: true, render: (row: any) => formatDate(row.created_at) },
                                { key: 'requested_delivery_date', label: 'Delivery Date', sortable: true, render: (row: any) => formatDate(row.requested_delivery_date) },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'orders',
                                    items: customer.sales_orders!.map(o => ({ sales_order_id: o.sales_order_id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('orders', row.sales_order_id)
                            }}
                        />
                    </Card>
                )}
                {customer.shipments && customer.shipments.length > 0 && (
                    <Card title="Shipments">
                        <Table
                            rows={shipmentsSort.sortedRows as any}
                            sortKey={shipmentsSort.sortKey}
                            sortDir={shipmentsSort.sortDir}
                            onSort={shipmentsSort.onSort}
                            columns={[
                                { key: 'id', label: 'Shipment', sortable: true },
                                {
                                    key: 'sales_order_id', label: 'Sales Order', sortable: true, render: (row) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                                setHash('orders', row.sales_order_id)
                                            }}
                                            type="button"
                                        >
                                            {row.sales_order_id}
                                        </button>
                                    )
                                },
                                { key: 'status', label: 'Status', sortable: true, render: (row) => <Badge>{row.status}</Badge> },
                                { key: 'planned_departure', label: 'Departure', sortable: true, render: (row: any) => formatDate(row.planned_departure) },
                                { key: 'planned_arrival', label: 'Arrival', sortable: true, render: (row: any) => formatDate(row.planned_arrival) },
                            ]}
                            onRowClick={(row, index) => {
                                setListContext({
                                    listType: 'shipments',
                                    items: customer.shipments!.map(s => ({ id: s.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('shipments', row.id)
                            }}
                        />
                    </Card>
                )}
                {invoices.length > 0 && (
                    <Card title="Invoices">
                        <Table
                            rows={invoicesSort.sortedRows as any}
                            sortKey={invoicesSort.sortKey}
                            sortDir={invoicesSort.sortDir}
                            onSort={invoicesSort.onSort}
                            columns={[
                                { key: 'id', label: 'Invoice', sortable: true },
                                {
                                    key: 'sales_order_id', label: 'Sales Order', sortable: true, render: (row: Invoice) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                                setHash('orders', row.sales_order_id)
                                            }}
                                            type="button"
                                        >
                                            {row.sales_order_id}
                                        </button>
                                    )
                                },
                                { key: 'total', label: 'Total', sortable: true, render: (row: Invoice) => <div className="text-right">{formatCurrency(row.total, row.currency)}</div> },
                                { key: 'status', label: 'Status', sortable: true, render: (row: Invoice) => <Badge>{row.status}</Badge> },
                                { key: 'invoice_date', label: 'Invoice Date', sortable: true, render: (row: Invoice) => formatDate(row.invoice_date) },
                                { key: 'due_date', label: 'Due Date', sortable: true, render: (row: Invoice) => formatDate(row.due_date) },
                            ]}
                            onRowClick={(row: Invoice, index: number) => {
                                setListContext({
                                    listType: 'invoices',
                                    items: invoices.map(i => ({ id: i.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('invoices', row.id)
                            }}
                        />
                    </Card>
                )}
                {emails.length > 0 && (
                    <Card title="Emails">
                        <Table
                            rows={emailsSort.sortedRows as any}
                            sortKey={emailsSort.sortKey}
                            sortDir={emailsSort.sortDir}
                            onSort={emailsSort.onSort}
                            columns={[
                                { key: 'subject', label: 'Subject', sortable: true },
                                { key: 'recipient_email', label: 'Recipient', sortable: true },
                                {
                                    key: 'status',
                                    label: 'Status',
                                    sortable: true,
                                    render: (row: Email) => <Badge>{row.status}</Badge>
                                },
                                { key: 'modified_at', label: 'Modified', sortable: true, render: (row: Email) => formatDate(row.modified_at) },
                            ]}
                            onRowClick={(row: Email, index: number) => {
                                setListContext({
                                    listType: 'emails',
                                    items: emails.map(e => ({ id: e.id })) as any,
                                    currentIndex: index,
                                })
                                setReferrer({ page: 'customers', id: customerId, label: customer.name })
                                setHash('emails', row.id)
                            }}
                        />
                    </Card>
                )}
            </Card>
        </section>
    )
}
