import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { QcHoldBatch } from '../types'
import { api } from '../api'
import { useTableSort } from '../utils/useTableSort'

const STATUS_COLORS: Record<string, 'yellow' | 'blue' | 'green' | 'red' | 'gray'> = {
  pending_images: 'yellow',
  ready_for_inspection: 'blue',
  inspected: 'blue',
  released: 'green',
  partially_released: 'green',
  closed: 'gray',
}

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending_images', label: 'Pending Images' },
  { value: 'ready_for_inspection', label: 'Ready for Inspection' },
  { value: 'inspected', label: 'Inspected' },
  { value: 'released', label: 'Released' },
  { value: 'partially_released', label: 'Partially Released' },
  { value: 'closed', label: 'Closed' },
]

export function QcQueuePage({ onSelect }: { onSelect: (id: string) => void }) {
  const [batches, setBatches] = useState<QcHoldBatch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('pending_images')

  const tableSort = useTableSort(batches)

  useEffect(() => {
    setLoading(true)
    const endpoint = statusFilter ? statusFilter : 'pending_images'
    api.qcBatches(endpoint)
      .then((res) => setBatches(res.batches ?? []))
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [statusFilter])

  const columns = [
    {
      key: 'id' as keyof QcHoldBatch, label: 'Batch ID', sortable: true,
      render: (b: QcHoldBatch) => (
        <button className="text-blue-600 hover:underline font-mono text-sm" onClick={() => onSelect(b.id)} type="button">
          {b.id}
        </button>
      ),
    },
    { key: 'production_order_id' as keyof QcHoldBatch, label: 'Production Order', sortable: true },
    { key: 'item_sku' as keyof QcHoldBatch, label: 'SKU', sortable: true },
    { key: 'item_name' as keyof QcHoldBatch, label: 'Product', sortable: true },
    { key: 'qty_pending' as keyof QcHoldBatch, label: 'Qty Pending', sortable: true },
    { key: 'qty_released' as keyof QcHoldBatch, label: 'Qty Released', sortable: true },
    { key: 'qty_scrapped' as keyof QcHoldBatch, label: 'Qty Scrapped', sortable: true },
    {
      key: 'status' as keyof QcHoldBatch, label: 'Status', sortable: true,
      render: (b: QcHoldBatch) => (
        <Badge color={STATUS_COLORS[b.status] ?? 'gray'}>{b.status.replace(/_/g, ' ')}</Badge>
      ),
    },
    { key: 'created_at' as keyof QcHoldBatch, label: 'Created', sortable: true },
  ]

  const rows = tableSort.sortedRows

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-lg font-semibold text-slate-800">QC Queue</div>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="qc-status-filter" className="text-slate-600">Status:</label>
          <select
            id="qc-status-filter"
            className="border border-slate-300 rounded px-2 py-1 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>
      <Card title={`QC Hold Batches${batches.length > 0 ? ` (${batches.length})` : ''}`}>
        {loading && <div className="text-slate-500 text-sm py-4">Loading...</div>}
        {error && <div className="text-red-600 text-sm py-2">{error}</div>}
        {!loading && !error && batches.length === 0 && (
          <div className="text-slate-500 text-sm py-4">No batches with status '{statusFilter}'.</div>
        )}
        {!loading && !error && batches.length > 0 && (
          <Table
            columns={columns}
            rows={rows}
            sortKey={tableSort.sortKey}
            sortDir={tableSort.sortDir}
            onSort={tableSort.onSort}
          />
        )}
      </Card>
    </div>
  )
}
