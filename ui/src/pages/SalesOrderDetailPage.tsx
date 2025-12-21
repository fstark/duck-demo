import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { SalesOrder, SalesOrderDetail } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

function setHash(page: string, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

interface SalesOrderDetailPageProps {
  orderId: string
}

export function SalesOrderDetailPage({ orderId }: SalesOrderDetailPageProps) {
  const [order, setOrder] = useState<SalesOrderDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { listContext, setListContext } = useNavigation()

  useEffect(() => {
    api.salesOrder(orderId)
      .then((res) => {
        setOrder(res as SalesOrderDetail)
        setLoading(false)
      })
      .catch((err) => {
        console.error(err)
        setError('Failed to load sales order details')
        setLoading(false)
      })
  }, [orderId])

  const hasPrevious = listContext && listContext.currentIndex > 0
  const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

  const handlePrevious = () => {
    if (!hasPrevious || !listContext) return
    const prevIndex = listContext.currentIndex - 1
    const prevOrder = listContext.items[prevIndex] as SalesOrder
    setListContext({
      ...listContext,
      currentIndex: prevIndex,
    })
    setHash('orders', prevOrder.sales_order_id)
  }

  const handleNext = () => {
    if (!hasNext || !listContext) return
    const nextIndex = listContext.currentIndex + 1
    const nextOrder = listContext.items[nextIndex] as SalesOrder
    setListContext({
      ...listContext,
      currentIndex: nextIndex,
    })
    setHash('orders', nextOrder.sales_order_id)
  }

  if (loading) {
    return (
      <section>
        <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
        <Card>
          <div className="text-sm text-slate-500">Loading order...</div>
        </Card>
      </section>
    )
  }

  if (error || !order) {
    return (
      <section>
        <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
        <Card>
          <div className="text-sm text-red-600">{error || 'Order not found'}</div>
          <button
            className="mt-3 text-brand-600 hover:underline text-sm"
            onClick={() => setHash('orders')}
            type="button"
          >
            ← Back to Sales Orders
          </button>
        </Card>
      </section>
    )
  }

  return (
    <section>
      <div className="text-lg font-semibold text-slate-800 mb-4">Sales Order Details</div>
      <Card>
        <div className="flex items-center justify-between mb-4">
          <button
            className="text-brand-600 hover:underline text-sm"
            onClick={() => setHash('orders')}
            type="button"
          >
            ← Back to Sales Orders
          </button>
          {listContext && (
            <div className="flex items-center gap-2">
              <button
                className={`px-3 py-1 text-sm rounded ${
                  hasPrevious
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
                className={`px-3 py-1 text-sm rounded ${
                  hasNext
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
          <div className="font-semibold text-lg">Order {order.sales_order.id}</div>
          <div className="grid grid-cols-2 gap-3">
            <Card title="Lines">
              <Table rows={order.lines as any} columns={[{ key: 'sku', label: 'SKU' }, { key: 'qty', label: 'Qty' }]} />
            </Card>
            <Card title="Pricing">
              <div>Total: {order.pricing.total}</div>
              <div className="text-slate-600 text-xs">Currency: {order.pricing.currency}</div>
            </Card>
          </div>
          <Card title="Shipments">
            {order.shipments?.length ? (
              <Table
                rows={order.shipments as any}
                columns={[
                  { key: 'id', label: 'Shipment' },
                  { key: 'status', label: 'Status' },
                  { key: 'planned_departure', label: 'Departure' },
                  { key: 'planned_arrival', label: 'Arrival' },
                ]}
              />
            ) : (
              <div className="text-slate-500">No shipments linked.</div>
            )}
          </Card>
        </div>
      </Card>
    </section>
  )
}
