import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { Email, EmailDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatDate } from '../utils/date'

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

interface EmailDetailPageProps {
    emailId: string
}

export function EmailDetailPage({ emailId }: EmailDetailPageProps) {
    const [emailData, setEmailData] = useState<EmailDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()
    const [error, setError] = useState<string | null>(null)
    const [showRaw, setShowRaw] = useState(false)

    useEffect(() => {
        api.emailDetail(emailId)
            .then((data) => {
                setEmailData(data)
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load email details')
                setLoading(false)
            })
    }, [emailId])

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Email Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading email...</div>
                </Card>
            </section>
        )
    }

    if (error || !emailData) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Email Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Email not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('emails')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Emails'}
                    </button>
                </Card>
            </section>
        )
    }

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const email = emailData.email
    const customer = emailData.customer
    const salesOrder = emailData.sales_order

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevEmail = listContext.items[prevIndex] as Email
        setListContext({
            ...listContext,
            currentIndex: prevIndex,
        })
        setHash('emails', prevEmail.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextEmail = listContext.items[nextIndex] as Email
        setListContext({
            ...listContext,
            currentIndex: nextIndex,
        })
        setHash('emails', nextEmail.id)
    }

    const getStatusBadge = (status: string) => {
        const variants: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
            sent: 'success',
            draft: 'info',
            failed: 'danger',
        }
        return <Badge variant={variants[status] || 'info'}>{status}</Badge>
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Email Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('emails')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Emails'}
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
                    <div className="flex items-center gap-3">
                        <div className="font-semibold text-lg">Email {email.id}</div>
                        {getStatusBadge(email.status)}
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Email Information">
                            <div className="space-y-2">
                                <div><span className="text-slate-500">Subject:</span> <span className="font-medium">{email.subject}</span></div>
                                <div><span className="text-slate-500">Created:</span> {formatDate(email.created_at)}</div>
                                <div><span className="text-slate-500">Modified:</span> {formatDate(email.modified_at)}</div>
                                {email.sent_at && (
                                    <div><span className="text-slate-500">Sent:</span> {formatDate(email.sent_at)}</div>
                                )}
                            </div>
                        </Card>

                        <Card title="Recipient">
                            <div className="space-y-2">
                                <div><span className="text-slate-500">Name:</span> {email.recipient_name || '—'}</div>
                                <div><span className="text-slate-500">Email:</span> {email.recipient_email}</div>
                            </div>
                        </Card>
                    </div>

                    <Card title="Email Body">
                        <div className="mb-3">
                            <button
                                className="text-xs text-brand-600 hover:underline"
                                onClick={() => setShowRaw(!showRaw)}
                                type="button"
                            >
                                {showRaw ? 'Show Rendered' : 'Show Raw'}
                            </button>
                        </div>
                        {showRaw ? (
                            <pre className="text-sm text-slate-700 whitespace-pre-wrap font-mono">{email.body}</pre>
                        ) : (
                            <div className="prose prose-slate prose-sm max-w-none">
                                <ReactMarkdown>{email.body}</ReactMarkdown>
                            </div>
                        )}
                    </Card>

                    {customer && (
                        <Card title="Customer">
                            <div className="space-y-2">
                                <div>
                                    <button
                                        className="text-brand-600 hover:underline font-medium"
                                        onClick={() => {
                                            setReferrer({ page: 'emails', id: email.id, label: `Email ${email.id}` })
                                            setHash('customers', email.customer_id)
                                        }}
                                        type="button"
                                    >
                                        {customer.name}
                                    </button>
                                </div>
                                {customer.company && (
                                    <div className="text-slate-600">{customer.company}</div>
                                )}
                                {customer.email && (
                                    <div className="text-slate-600 text-xs">{customer.email}</div>
                                )}
                            </div>
                        </Card>
                    )}

                    {salesOrder && (
                        <Card title="Sales Order">
                            <div className="space-y-2">
                                <div>
                                    <button
                                        className="text-brand-600 hover:underline font-medium"
                                        onClick={() => {
                                            setReferrer({ page: 'emails', id: email.id, label: `Email ${email.id}` })
                                            setHash('orders', email.sales_order_id!)
                                        }}
                                        type="button"
                                    >
                                        {email.sales_order_id}
                                    </button>
                                </div>
                                {salesOrder.status && (
                                    <div>
                                        <Badge variant="neutral">{salesOrder.status}</Badge>
                                    </div>
                                )}
                            </div>
                        </Card>
                    )}
                </div>
            </Card>
        </section>
    )
}
