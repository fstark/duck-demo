import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Invoice, InvoiceDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatCurrency } from '../utils/currency'
import { Quantity } from '../utils/quantity'
import { formatDate } from '../utils/date'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface InvoiceDetailPageProps {
    invoiceId: string
}

export function InvoiceDetailPage({ invoiceId }: InvoiceDetailPageProps) {
    const [data, setData] = useState<InvoiceDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, setReferrer, referrer, clearListContext } = useNavigation()

    useEffect(() => {
        api.invoiceDetail(invoiceId)
            .then((result) => {
                setData(result)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load invoice details')
                setLoading(false)
            })
    }, [invoiceId])

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevInvoice = listContext.items[prevIndex] as Invoice
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('invoices', prevInvoice.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextInvoice = listContext.items[nextIndex] as Invoice
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('invoices', nextInvoice.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Invoice Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading invoice...</div>
                </Card>
            </section>
        )
    }

    if (error || !data) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Invoice Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Invoice not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('invoices')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Invoices'}
                    </button>
                </Card>
            </section>
        )
    }

    const inv = data.invoice

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Invoice Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('invoices')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Invoices'}
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
                    <div className="flex items-center gap-3 justify-between">
                        <div className="flex items-center gap-3">
                            <div className="font-semibold text-lg">{inv.id}</div>
                            <Badge>{inv.status}</Badge>
                        </div>
                        <a
                            href={`/api/invoices/${encodeURIComponent(invoiceId)}/pdf`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="px-4 py-2 bg-brand-600 text-white rounded hover:bg-brand-700 text-sm font-medium"
                        >
                            📄 Download PDF
                        </a>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Customer">
                            {data.customer ? (
                                <div className="space-y-1">
                                    <button
                                        className="font-medium text-brand-600 hover:underline text-left"
                                        onClick={() => {
                                            setReferrer({ page: 'invoices', id: invoiceId, label: `Invoice ${inv.id}` })
                                            setHash('customers', data.customer!.id)
                                        }}
                                        type="button"
                                    >
                                        {data.customer.name}
                                    </button>
                                    {data.customer.company && <div className="text-slate-600 text-sm">{data.customer.company}</div>}
                                    {data.customer.email && <div className="text-slate-600 text-sm">{data.customer.email}</div>}
                                    {data.customer.city && <div className="text-slate-600 text-sm">{data.customer.city}</div>}
                                </div>
                            ) : (
                                <div className="text-slate-500">{inv.customer_id}</div>
                            )}
                        </Card>

                        <Card title="Dates & Amounts">
                            <div className="space-y-1">
                                <div><span className="text-slate-500">Invoice date:</span> {formatDate(inv.invoice_date)}</div>
                                <div><span className="text-slate-500">Due date:</span> {formatDate(inv.due_date)}</div>
                                {inv.issued_at && <div><span className="text-slate-500">Issued:</span> {formatDate(inv.issued_at)}</div>}
                                {inv.paid_at && <div><span className="text-slate-500">Paid:</span> {formatDate(inv.paid_at)}</div>}
                                <div className="pt-2 border-t mt-2">
                                    <div><span className="text-slate-500">Subtotal:</span> {formatCurrency(inv.subtotal, inv.currency)}</div>
                                    {inv.discount > 0 && <div><span className="text-slate-500">Discount:</span> -{formatCurrency(inv.discount, inv.currency)}</div>}
                                    {inv.shipping > 0 && <div><span className="text-slate-500">Shipping:</span> {formatCurrency(inv.shipping, inv.currency)}</div>}
                                    {inv.tax > 0 && <div><span className="text-slate-500">Tax:</span> {formatCurrency(inv.tax, inv.currency)}</div>}
                                    <div className="font-semibold"><span className="text-slate-500">Total:</span> {formatCurrency(inv.total, inv.currency)}</div>
                                </div>
                            </div>
                        </Card>
                    </div>

                    {data.sales_order && (
                        <Card title="Sales Order">
                            <button
                                className="text-brand-600 hover:underline text-left"
                                onClick={() => {
                                    setReferrer({ page: 'invoices', id: invoiceId, label: `Invoice ${inv.id}` })
                                    setHash('orders', data.sales_order!.id)
                                }}
                                type="button"
                            >
                                {data.sales_order.id}
                            </button>
                            {data.sales_order.status && (
                                <span className="ml-2"><Badge>{data.sales_order.status}</Badge></span>
                            )}
                        </Card>
                    )}

                    <Card title="Lines">
                        <Table
                            rows={data.lines as any}
                            columns={[
                                {
                                    key: 'sku',
                                    label: 'SKU',
                                    render: (row: any) => (
                                        <button
                                            className="text-brand-600 hover:underline text-left"
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                setReferrer({ page: 'invoices', id: invoiceId, label: `Invoice ${inv.id}` })
                                                setHash('items', row.sku)
                                            }}
                                            type="button"
                                        >
                                            {row.sku}
                                        </button>
                                    ),
                                },
                                { key: 'qty', label: 'Qty', render: (row: any) => <Quantity value={row.qty} /> },
                            ]}
                        />
                    </Card>

                    <Card title="Payments">
                        {data.payments.length > 0 ? (
                            <>
                                <Table
                                    rows={data.payments as any}
                                    columns={[
                                        { key: 'id', label: 'Payment' },
                                        {
                                            key: 'amount',
                                            label: 'Amount',
                                            render: (row: any) => <div className="text-right">{formatCurrency(row.amount, inv.currency)}</div>,
                                        },
                                        { key: 'payment_method', label: 'Method' },
                                        { key: 'payment_date', label: 'Date', render: (row: any) => formatDate(row.payment_date) },
                                        { key: 'reference', label: 'Reference', render: (row: any) => row.reference || '—' },
                                    ]}
                                />
                                <div className="flex justify-between mt-3 pt-2 border-t text-sm">
                                    <div><span className="text-slate-500">Amount paid:</span> {formatCurrency(data.amount_paid, inv.currency)}</div>
                                    <div className="font-semibold"><span className="text-slate-500">Balance due:</span> {formatCurrency(data.balance_due, inv.currency)}</div>
                                </div>
                            </>
                        ) : (
                            <div className="text-slate-500">No payments recorded yet.</div>
                        )}
                    </Card>
                </div>
            </Card>
        </section>
    )
}
