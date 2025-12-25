import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Badge } from '../components/Badge'
import { PurchaseOrder } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { formatQuantity } from '../utils/quantity'

interface PurchaseOrderDetailPageProps {
    purchaseOrderId: string
}

export function PurchaseOrderDetailPage({ purchaseOrderId }: PurchaseOrderDetailPageProps) {
    const [purchaseOrder, setPurchaseOrder] = useState<PurchaseOrder | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext } = useNavigation()

    useEffect(() => {
        // Navigation context comes from list page
    }, [])

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.purchaseOrderDetail(purchaseOrderId)
            .then((data) => {
                if (!cancelled) {
                    setPurchaseOrder(data)
                    setLoading(false)
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(String(err))
                    setLoading(false)
                }
            })
        return () => {
            cancelled = true
        }
    }, [purchaseOrderId])

    if (loading) {
        return (
            <Card title="Purchase Order Detail">
                <div className="text-sm text-gray-500">Loading purchase order...</div>
            </Card>
        )
    }

    if (error) {
        return (
            <Card title="Purchase Order Detail">
                <div className="text-sm text-red-600">Error: {error}</div>
            </Card>
        )
    }

    if (!purchaseOrder) {
        return (
            <Card title="Purchase Order Detail">
                <div className="text-sm text-gray-500">Purchase order not found</div>
            </Card>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Purchase Order {purchaseOrder.id}</div>
            <Card>
                <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Status</dt>
                        <dd className="text-sm text-gray-900">
                            <Badge>{purchaseOrder.status}</Badge>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Expected Delivery</dt>
                        <dd className="text-sm text-gray-900">{purchaseOrder.expected_delivery || '—'}</dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Supplier</dt>
                        <dd className="text-sm text-gray-900">
                            <a
                                href={`#/suppliers/${purchaseOrder.supplier_id}`}
                                className="text-blue-600 hover:underline"
                            >
                                {purchaseOrder.supplier_name || purchaseOrder.supplier_id}
                            </a>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Contact Name</dt>
                        <dd className="text-sm text-gray-900">{purchaseOrder.contact_name || '—'}</dd>
                    </div>
                    <div>
                        <dt className="text-sm font-medium text-gray-500">Contact Email</dt>
                        <dd className="text-sm text-gray-900">
                            {purchaseOrder.contact_email ? (
                                <a href={`mailto:${purchaseOrder.contact_email}`} className="text-blue-600 hover:underline">
                                    {purchaseOrder.contact_email}
                                </a>
                            ) : '—'}
                        </dd>
                    </div>
                </dl>

                <div className="mt-6 border-t pt-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Item Details</h3>
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item SKU</dt>
                            <dd className="text-sm text-gray-900">
                                <a
                                    href={`#/items/${purchaseOrder.item_sku}`}
                                    className="text-blue-600 hover:underline"
                                >
                                    {purchaseOrder.item_sku}
                                </a>
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item Name</dt>
                            <dd className="text-sm text-gray-900">{purchaseOrder.item_name || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Item Type</dt>
                            <dd className="text-sm text-gray-900">{purchaseOrder.item_type || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Quantity</dt>
                            <dd className="text-sm text-gray-900">
                                {formatQuantity(purchaseOrder.qty)} {purchaseOrder.uom || 'ea'}
                            </dd>
                        </div>
                    </dl>
                </div>
            </Card>
        </section>
    )
}
