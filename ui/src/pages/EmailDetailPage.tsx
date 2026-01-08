import { useState, useEffect } from 'react'
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
    const { listContext, setListContext, referrer, setReferrer } = useNavigation()
    const [error, setError] = useState<string | null>(null)

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
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('emails')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Emails'}
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

    return (
        <section className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="text-lg font-semibold text-slate-800">Email Details</div>
                <div className="flex gap-2">
                    {listContext && (
                        <>
                            <button
                                className="px-3 py-1 text-sm bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                                onClick={handlePrevious}
                                disabled={!hasPrevious}
                                type="button"
                            >
                                ← Previous
                            </button>
                            <button
                                className="px-3 py-1 text-sm bg-white border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
                                onClick={handleNext}
                                disabled={!hasNext}
                                type="button"
                            >
                                Next →
                            </button>
                        </>
                    )}
                    <button
                        className="px-3 py-1 text-sm bg-white border border-slate-300 rounded hover:bg-slate-50"
                        onClick={() => {
                            if (referrer) {
                                setReferrer(null)
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('emails')
                            }
                        }}
                        type="button"
                    >
                        ← Back to {referrer?.label || 'Emails'}
                    </button>
                </div>
            </div>

            <Card title="Email Information">
                <div className="space-y-3 text-sm">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <span className="font-medium text-slate-700">ID:</span>
                            <span className="ml-2 text-slate-600">{email.id}</span>
                        </div>
                        <div>
                            <span className="font-medium text-slate-700">Status:</span>
                            <span className="ml-2">
                                <Badge variant={email.status === 'sent' ? 'success' : 'neutral'}>
                                    {email.status}
                                </Badge>
                            </span>
                        </div>
                    </div>
                    <div>
                        <span className="font-medium text-slate-700">Subject:</span>
                        <div className="mt-1 text-slate-800">{email.subject}</div>
                    </div>
                    <div>
                        <span className="font-medium text-slate-700">Created:</span>
                        <span className="ml-2 text-slate-600">{formatDate(email.created_at)}</span>
                    </div>
                    <div>
                        <span className="font-medium text-slate-700">Modified:</span>
                        <span className="ml-2 text-slate-600">{formatDate(email.modified_at)}</span>
                    </div>
                    {email.sent_at && (
                        <div>
                            <span className="font-medium text-slate-700">Sent:</span>
                            <span className="ml-2 text-slate-600">{formatDate(email.sent_at)}</span>
                        </div>
                    )}
                </div>
            </Card>

            <Card title="Recipient">
                <div className="space-y-2 text-sm">
                    <div>
                        <span className="font-medium text-slate-700">Name:</span>
                        <span className="ml-2 text-slate-600">{email.recipient_name || '—'}</span>
                    </div>
                    <div>
                        <span className="font-medium text-slate-700">Email:</span>
                        <span className="ml-2 text-slate-600">{email.recipient_email}</span>
                    </div>
                </div>
            </Card>

            <Card title="Email Body">
                <div className="text-sm text-slate-700 whitespace-pre-wrap">{email.body}</div>
            </Card>

            {customer && (
                <Card title="Customer">
                    <div className="space-y-2 text-sm">
                        <div>
                            <span className="font-medium text-slate-700">Name:</span>
                            <button
                                className="ml-2 text-brand-600 hover:underline"
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
                            <div>
                                <span className="font-medium text-slate-700">Company:</span>
                                <span className="ml-2 text-slate-600">{customer.company}</span>
                            </div>
                        )}
                        {customer.email && (
                            <div>
                                <span className="font-medium text-slate-700">Email:</span>
                                <span className="ml-2 text-slate-600">{customer.email}</span>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {salesOrder && (
                <Card title="Sales Order">
                    <div className="space-y-2 text-sm">
                        <div>
                            <span className="font-medium text-slate-700">Order ID:</span>
                            <button
                                className="ml-2 text-brand-600 hover:underline"
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
                                <span className="font-medium text-slate-700">Status:</span>
                                <span className="ml-2">
                                    <Badge variant="neutral">{salesOrder.status}</Badge>
                                </span>
                            </div>
                        )}
                    </div>
                </Card>
            )}
        </section>
    )
}
