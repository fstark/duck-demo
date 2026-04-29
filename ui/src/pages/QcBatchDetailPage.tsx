import { useEffect, useState } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { QcHoldBatchDetail, QcInspectionFinding } from '../types'
import { api } from '../api'
import { useTableSort } from '../utils/useTableSort'

function setHash(page: string, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

const SEVERITY_COLORS: Record<string, 'red' | 'yellow' | 'blue'> = {
  critical: 'red',
  major: 'yellow',
  minor: 'blue',
}

const DECISION_COLORS: Record<string, 'green' | 'yellow' | 'red'> = {
  pass: 'green',
  partial_scrap: 'yellow',
  full_scrap: 'red',
}

export function QcBatchDetailPage({ batchId }: { batchId: string }) {
  const [batch, setBatch] = useState<QcHoldBatchDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api.qcBatch(batchId)
      .then(setBatch)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [batchId])

  const findingSort = useTableSort<QcInspectionFinding>(batch?.inspection?.findings ?? [])

  if (loading) return <div className="text-slate-500 text-sm py-4">Loading...</div>
  if (error) return <div className="text-red-600 text-sm py-4">{error}</div>
  if (!batch) return null

  const line = batch.lines?.[0]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <button
          className="text-blue-600 hover:underline text-sm"
          onClick={() => setHash('qc-queue')}
          type="button"
        >
          ← QC Queue
        </button>
        <span className="text-slate-400">/</span>
        <span className="font-mono text-sm text-slate-700">{batch.id}</span>
      </div>

      {/* Batch summary */}
      <Card title="QC Hold Batch">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-slate-500">Batch ID</div>
            <div className="font-mono">{batch.id}</div>
          </div>
          <div>
            <div className="text-slate-500">Production Order</div>
            <div className="font-mono">
              <button
                className="text-blue-600 hover:underline"
                onClick={() => setHash('production', batch.production_order_id)}
                type="button"
              >
                {batch.production_order_id}
              </button>
            </div>
          </div>
          {batch.sales_order_id && (
            <div>
              <div className="text-slate-500">Sales Order</div>
              <div className="font-mono">
                <button
                  className="text-blue-600 hover:underline"
                  onClick={() => setHash('orders', batch.sales_order_id)}
                  type="button"
                >
                  {batch.sales_order_id}
                </button>
              </div>
            </div>
          )}
          <div>
            <div className="text-slate-500">Product</div>
            <div>{batch.item_name} <span className="text-slate-400 font-mono text-xs">{batch.item_sku}</span></div>
          </div>
          <div>
            <div className="text-slate-500">Status</div>
            <Badge color="blue">{batch.status.replace(/_/g, ' ')}</Badge>
          </div>
          <div>
            <div className="text-slate-500">Created</div>
            <div>{batch.created_at}</div>
          </div>
        </div>

        {line && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="text-sm font-medium text-slate-700 mb-2">Quantities</div>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-slate-500">On Hold</div>
                <div className="font-semibold">{line.qty_on_hold}</div>
              </div>
              <div>
                <div className="text-slate-500">Pending</div>
                <div className="font-semibold text-yellow-700">{line.qty_pending}</div>
              </div>
              <div>
                <div className="text-slate-500">Released</div>
                <div className="font-semibold text-green-700">{line.qty_released}</div>
              </div>
              <div>
                <div className="text-slate-500">Scrapped</div>
                <div className="font-semibold text-red-700">{line.qty_scrapped}</div>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Images */}
      <Card title={`Evidence Images (${batch.images?.length ?? 0})`}>
        {!batch.images || batch.images.length === 0 ? (
          <div className="text-slate-500 text-sm">No images attached yet. Use the MCP chat interface to attach images.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {batch.images.map((img) => {
              const src = img.image_url
              return (
                <div key={img.id} className="space-y-1">
                  <a href={src} target="_blank" rel="noreferrer">
                    <img
                      src={src}
                      alt={`QC evidence ${img.id}`}
                      className="rounded border border-slate-200 max-h-64 object-contain w-full bg-slate-50"
                    />
                  </a>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="font-mono">{img.id}</span>
                    {img.uploaded_by && <span>by {img.uploaded_by}</span>}
                    <span>{img.created_at}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* Inspection result */}
      <Card title="Inspection Result">
        {!batch.inspection ? (
          <div className="text-slate-500 text-sm">
            No inspection run yet.
            {batch.images && batch.images.length > 0
              ? ' Use the MCP chat interface to run the AI inspection.'
              : ' Attach images first, then run the inspection via MCP chat.'}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-slate-500">Decision</div>
                <Badge color={DECISION_COLORS[batch.inspection.decision] ?? 'gray'}>
                  {batch.inspection.decision.replace(/_/g, ' ')}
                </Badge>
              </div>
              <div>
                <div className="text-slate-500">Confidence</div>
                <div className="font-semibold">
                  {batch.inspection.confidence_overall != null
                    ? `${(batch.inspection.confidence_overall * 100).toFixed(0)}%`
                    : '—'}
                </div>
              </div>
              <div>
                <div className="text-slate-500">Model</div>
                <div className="font-mono text-xs">{batch.inspection.model_name}</div>
              </div>
              <div>
                <div className="text-slate-500">Status</div>
                <Badge color={batch.inspection.status === 'completed' ? 'green' : 'yellow'}>
                  {batch.inspection.status}
                </Badge>
              </div>
            </div>

            {batch.inspection.decision_reason && (
              <div className="text-sm">
                <div className="text-slate-500 mb-1">Decision Reason</div>
                <div className="text-slate-700">{batch.inspection.decision_reason}</div>
              </div>
            )}

            {batch.inspection.findings && batch.inspection.findings.length > 0 && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">
                  Findings ({batch.inspection.findings.length})
                </div>
                <Table
                  columns={[
                    { key: 'finding_type' as keyof QcInspectionFinding, label: 'Type', sortable: true },
                    { key: 'severity' as keyof QcInspectionFinding, label: 'Severity', sortable: true },
                    { key: 'confidence' as keyof QcInspectionFinding, label: 'Confidence', sortable: true },
                    { key: 'description' as keyof QcInspectionFinding, label: 'Description', sortable: false },
                    { key: 'location_hint' as keyof QcInspectionFinding, label: 'Location', sortable: false },
                  ]}
                  rows={findingSort.sortedRows.map((f) => ({
                    ...f,
                    severity: (
                      <Badge color={SEVERITY_COLORS[f.severity] ?? 'gray'}>
                        {f.severity}
                      </Badge>
                    ),
                    confidence: f.confidence != null ? `${(f.confidence * 100).toFixed(0)}%` : '—',
                  }))}
                  sortKey={findingSort.sortKey}
                  sortDir={findingSort.sortDir}
                  onSort={findingSort.onSort}
                />
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Replacements */}
      {batch.replacements && batch.replacements.length > 0 && (
        <Card title={`Replacement Orders (${batch.replacements.length})`}>
          <div className="space-y-2">
            {batch.replacements.map((r) => (
              <div key={r.id} className="flex items-center gap-4 text-sm">
                <span className="text-slate-500">Replacement MO:</span>
                <button
                  className="text-blue-600 hover:underline font-mono"
                  onClick={() => setHash('production', r.replacement_production_order_id)}
                  type="button"
                >
                  {r.replacement_production_order_id || '(pending)'}
                </button>
                <span className="text-slate-500">Scrapped: {r.qty_short}</span>
                <span className="text-slate-500">Replacement qty: {r.qty_replacement}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
