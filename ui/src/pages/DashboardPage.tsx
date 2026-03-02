import { useState, useEffect } from 'react'
import { api } from '../api'
import { DashboardData, ActivityLogEntry } from '../types'
import { formatCurrency } from '../utils/currency'
import { formatDate } from '../utils/date'

const STATUS_COLORS: Record<string, string> = {
  // Sales orders
  draft: '#94a3b8',
  confirmed: '#3b82f6',
  completed: '#22c55e',
  cancelled: '#ef4444',
  // Production
  waiting: '#f59e0b',
  ready: '#3b82f6',
  in_progress: '#8b5cf6',
  // Shipments
  planned: '#94a3b8',
  in_transit: '#3b82f6',
  delivered: '#22c55e',
  // Invoices
  issued: '#3b82f6',
  paid: '#22c55e',
  overdue: '#ef4444',
  // Quotes
  sent: '#3b82f6',
  accepted: '#22c55e',
  rejected: '#ef4444',
  expired: '#94a3b8',
}

const CATEGORY_COLORS: Record<string, string> = {
  sales: 'bg-blue-100 text-blue-700',
  production: 'bg-amber-100 text-amber-700',
  logistics: 'bg-green-100 text-green-700',
  purchasing: 'bg-purple-100 text-purple-700',
  billing: 'bg-rose-100 text-rose-700',
}

function entityHref(entityType: string | null, entityId: string | null): string | null {
  if (!entityType || !entityId) return null
  const map: Record<string, string> = {
    sales_order: 'orders',
    quote: 'quotes',
    production_order: 'production',
    shipment: 'shipments',
    invoice: 'invoices',
    purchase_order: 'purchase-orders',
    email: 'emails',
  }
  const page = map[entityType]
  return page ? `#/${page}/${encodeURIComponent(entityId)}` : null
}

/** Horizontal segmented status bar. */
function StatusBar({ items, label }: { items: { status: string; count: number }[]; label: string }) {
  const total = items.reduce((s, i) => s + i.count, 0)
  if (total === 0) return null
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="text-slate-400 text-xs">{total}</span>
      </div>
      <div className="flex h-5 rounded overflow-hidden bg-slate-100">
        {items.map((item) => {
          const pct = (item.count / total) * 100
          if (pct < 0.5) return null
          const color = STATUS_COLORS[item.status] || '#94a3b8'
          return (
            <div
              key={item.status}
              className="relative group"
              style={{ width: `${pct}%`, backgroundColor: color }}
              title={`${item.status}: ${item.count}`}
            >
              {pct > 8 && (
                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-white drop-shadow-sm">
                  {item.count}
                </span>
              )}
            </div>
          )
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
        {items.map((item) => (
          <span key={item.status} className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: STATUS_COLORS[item.status] || '#94a3b8' }} />
            {item.status} ({item.count})
          </span>
        ))}
      </div>
    </div>
  )
}

/** Simple inline SVG bar chart for daily volumes. */
function DailyVolumeChart({ data }: { data: DashboardData['daily_volumes'] }) {
  if (data.length === 0) return <div className="text-slate-400 text-sm py-4 text-center">No volume data</div>
  const maxVal = Math.max(...data.map((d) => Math.max(d.created, d.shipped, d.invoiced)), 1)
  const barW = Math.max(4, Math.min(12, Math.floor(600 / data.length)))
  const chartW = data.length * (barW * 3 + 4) + 40
  const chartH = 120

  return (
    <div className="overflow-x-auto">
      <svg width={chartW} height={chartH + 30} className="text-xs">
        {/* Y axis labels */}
        <text x={4} y={12} className="fill-slate-400" fontSize={10}>{maxVal}</text>
        <text x={4} y={chartH + 2} className="fill-slate-400" fontSize={10}>0</text>
        {data.map((d, i) => {
          const x0 = 40 + i * (barW * 3 + 4)
          const hC = (d.created / maxVal) * chartH
          const hS = (d.shipped / maxVal) * chartH
          const hI = (d.invoiced / maxVal) * chartH
          return (
            <g key={d.date}>
              <rect x={x0} y={chartH - hC} width={barW} height={hC} fill="#3b82f6" rx={1}>
                <title>{d.date} created: {d.created}</title>
              </rect>
              <rect x={x0 + barW} y={chartH - hS} width={barW} height={hS} fill="#22c55e" rx={1}>
                <title>{d.date} shipped: {d.shipped}</title>
              </rect>
              <rect x={x0 + barW * 2} y={chartH - hI} width={barW} height={hI} fill="#f59e0b" rx={1}>
                <title>{d.date} invoiced: {d.invoiced}</title>
              </rect>
              {/* X label every ~7 days */}
              {i % 7 === 0 && (
                <text x={x0} y={chartH + 16} className="fill-slate-400" fontSize={9}>{d.date.slice(5)}</text>
              )}
            </g>
          )
        })}
        {/* Legend */}
        <g transform={`translate(${chartW - 200}, ${chartH + 18})`}>
          <rect x={0} y={0} width={8} height={8} fill="#3b82f6" rx={1} />
          <text x={10} y={8} className="fill-slate-500" fontSize={9}>Created</text>
          <rect x={55} y={0} width={8} height={8} fill="#22c55e" rx={1} />
          <text x={65} y={8} className="fill-slate-500" fontSize={9}>Shipped</text>
          <rect x={110} y={0} width={8} height={8} fill="#f59e0b" rx={1} />
          <text x={120} y={8} className="fill-slate-500" fontSize={9}>Invoiced</text>
        </g>
      </svg>
    </div>
  )
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.dashboard()
      .then((d) => { setData(d); setError(null) })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="py-12 text-center text-sm text-slate-400">Loading dashboard…</div>
  if (error) return <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
  if (!data) return null

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-800">Dashboard</h1>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <KpiCard label="Open Orders" value={data.kpis.open_orders} />
        <KpiCard label="In-Progress MOs" value={data.kpis.in_progress_mos} />
        <KpiCard label="Pending Shipments" value={data.kpis.pending_shipments} />
        <KpiCard label="Overdue Invoices" value={data.kpis.overdue_invoices} accent={data.kpis.overdue_invoices > 0 ? 'red' : undefined} />
        <KpiCard label="Total Revenue" value={formatCurrency(data.kpis.total_revenue)} />
      </div>

      {/* Status distributions */}
      <div className="card p-4 space-y-4">
        <div className="section-title">Status Distributions</div>
        <StatusBar items={data.status_distributions.sales_orders || []} label="Sales Orders" />
        <StatusBar items={data.status_distributions.production_orders || []} label="Production Orders" />
        <StatusBar items={data.status_distributions.quotes || []} label="Quotes" />
        <StatusBar items={data.status_distributions.invoices || []} label="Invoices" />
        <StatusBar items={data.status_distributions.shipments || []} label="Shipments" />
      </div>

      {/* Daily volume chart */}
      <div className="card p-4">
        <div className="section-title">Daily Volume</div>
        <DailyVolumeChart data={data.daily_volumes} />
      </div>

      {/* Recent activity */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="section-title">Recent Activity</div>
          <a href="#/activity" className="text-xs text-blue-600 hover:underline">View all →</a>
        </div>
        <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
          {data.recent_activity.map((e) => {
            const href = entityHref(e.entity_type, e.entity_id)
            const catClass = CATEGORY_COLORS[e.category] || 'bg-slate-100 text-slate-700'
            return (
              <div key={e.id} className="flex items-center gap-3 py-1.5 text-sm">
                <span className="text-slate-400 tabular-nums text-xs w-36 shrink-0">{formatDate(e.timestamp)}</span>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${catClass}`}>
                  {e.category}
                </span>
                <span className="text-slate-700 truncate">{e.action}</span>
                {href ? (
                  <a href={href} className="text-blue-600 hover:underline font-mono text-xs shrink-0">{e.entity_id}</a>
                ) : e.entity_id ? (
                  <span className="font-mono text-xs text-slate-400 shrink-0">{e.entity_id}</span>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function KpiCard({ label, value, accent }: { label: string; value: number | string; accent?: 'red' }) {
  const valColor = accent === 'red' ? 'text-red-600' : 'text-slate-900'
  return (
    <div className="card p-3">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className={`text-xl font-semibold ${valColor}`}>{typeof value === 'number' ? value.toLocaleString() : value}</div>
    </div>
  )
}
