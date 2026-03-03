import { useMemo, useState } from 'react'
import type {
  SalesOrderTimeline,
  ProductionOrderTimeline,
  TimelineWait,
} from '../types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BarSegment = {
  start: number    // ms since epoch
  end: number
  color: string
  label: string
  tooltip: string
  entityId?: string
  entityPage?: string
}

type Row = {
  id: string
  label: string
  indent: number
  segments: BarSegment[]
}

type TimelineGanttProps = {
  soTimeline?: SalesOrderTimeline
  moTimeline?: ProductionOrderTimeline
  onNavigate?: (page: string, id: string) => void
}

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const COLORS = {
  completed: '#22c55e',           // green-500
  in_progress: '#3b82f6',        // blue-500
  pending: '#94a3b8',            // slate-400
  planned: '#94a3b8',
  ready: '#60a5fa',              // blue-400
  waiting: '#f59e0b',            // amber-500
  draft: '#cbd5e1',              // slate-300
  confirmed: '#3b82f6',
  // Wait reasons
  material: '#f59e0b',           // amber-500
  work_center: '#ef4444',        // red-500
  // Quote
  sent: '#8b5cf6',               // violet-500
  accepted: '#22c55e',
  rejected: '#ef4444',
  expired: '#94a3b8',
  superseded: '#94a3b8',
  // Shipment
  in_transit: '#3b82f6',
  delivered: '#22c55e',
  dispatched: '#3b82f6',
  // Invoice
  issued: '#8b5cf6',
  paid: '#22c55e',
  overdue: '#ef4444',
} as Record<string, string>

function statusColor(status?: string | null): string {
  return (status && COLORS[status]) || COLORS.pending
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function toMs(d?: string | null): number | null {
  if (!d) return null
  const t = new Date(d.replace(' ', 'T')).getTime()
  return isNaN(t) ? null : t
}

function fmtDate(ms: number): string {
  const d = new Date(ms)
  return d.toISOString().slice(0, 10)
}

function fmtDateTime(ms: number): string {
  const d = new Date(ms)
  return d.toISOString().replace('T', ' ').slice(0, 16)
}

function daysBetween(a: number, b: number): string {
  const days = Math.round((b - a) / 86400000)
  return days === 1 ? '1 day' : `${days} days`
}

// ---------------------------------------------------------------------------
// Build rows
// ---------------------------------------------------------------------------

function buildSalesOrderRows(tl: SalesOrderTimeline): Row[] {
  const rows: Row[] = []

  // Quotes
  for (const q of tl.quotes) {
    const segs: BarSegment[] = []
    const created = toMs(q.created_at)
    const sent = toMs(q.sent_at)
    const accepted = toMs(q.accepted_at)
    const rejected = toMs(q.rejected_at)

    if (created != null) {
      const end = sent ?? accepted ?? rejected ?? created + 86400000
      segs.push({
        start: created, end,
        color: COLORS.draft,
        label: 'Draft',
        tooltip: `Quote ${q.id} rev.${q.revision_number}\nCreated: ${fmtDate(created)}`,
        entityId: q.id, entityPage: 'quotes',
      })
    }
    if (sent != null) {
      const end = accepted ?? rejected ?? sent + 86400000
      segs.push({
        start: sent, end,
        color: COLORS.sent,
        label: 'Sent',
        tooltip: `Quote ${q.id} sent ${fmtDate(sent)}`,
        entityId: q.id, entityPage: 'quotes',
      })
    }
    if (accepted != null) {
      segs.push({
        start: accepted, end: accepted + 3600000,
        color: COLORS.accepted,
        label: '✓',
        tooltip: `Accepted ${fmtDate(accepted)}`,
        entityId: q.id, entityPage: 'quotes',
      })
    }
    if (rejected != null) {
      segs.push({
        start: rejected, end: rejected + 3600000,
        color: COLORS.rejected,
        label: '✗',
        tooltip: `Rejected ${fmtDate(rejected)}`,
        entityId: q.id, entityPage: 'quotes',
      })
    }
    rows.push({
      id: q.id, indent: 0, segments: segs,
      label: `Quote ${q.id} (rev ${q.revision_number})`,
    })
  }

  // Sales Order
  {
    const so = tl.sales_order
    const created = toMs(so.created_at)
    const segs: BarSegment[] = []
    if (created != null) {
      // span until last event or requested delivery
      const reqDel = toMs(so.requested_delivery_date)
      const endMs = reqDel ?? created + 86400000
      segs.push({
        start: created, end: Math.max(created + 3600000, endMs),
        color: statusColor(so.status),
        label: so.status || 'SO',
        tooltip: `Sales Order ${so.id}\nStatus: ${so.status}\nCreated: ${fmtDate(created)}${reqDel ? `\nReq. delivery: ${fmtDate(reqDel)}` : ''}`,
        entityId: so.id, entityPage: 'orders',
      })
    }
    rows.push({ id: so.id, indent: 0, segments: segs, label: `SO ${so.id}` })
  }

  // Production orders + operations + waits
  for (const mo of tl.production_orders) {
    const moSegs: BarSegment[] = []
    const moStart = toMs(mo.started_at)
    const moEnd = toMs(mo.completed_at) ?? toMs(mo.eta_finish)

    // MO bar
    if (moStart != null || moEnd != null) {
      const s = moStart ?? (moEnd! - 86400000)
      const e = moEnd ?? (moStart! + 86400000)
      moSegs.push({
        start: s, end: Math.max(s + 3600000, e),
        color: statusColor(mo.status),
        label: mo.status || '',
        tooltip: `${mo.id} — ${mo.item_sku || ''}\nStatus: ${mo.status}${moStart ? `\nStarted: ${fmtDate(moStart)}` : ''}${mo.completed_at ? `\nCompleted: ${fmtDate(toMs(mo.completed_at)!)}` : ''}`,
        entityId: mo.id, entityPage: 'production',
      })
    }

    // Wait overlays on MO bar
    for (const w of mo.waits) {
      if (!w.production_operation_id) {
        const ws = toMs(w.started_at)
        const we = toMs(w.resolved_at) ?? (ws ? ws + 86400000 : null)
        if (ws != null && we != null) {
          moSegs.push({
            start: ws, end: we,
            color: COLORS[w.reason_type] || COLORS.waiting,
            label: w.reason_type === 'material' ? '⏳ material' : '⏳ WC',
            tooltip: waitTooltip(w),
          })
        }
      }
    }

    rows.push({
      id: mo.id, indent: 1, segments: moSegs,
      label: `MO ${mo.id} — ${mo.item_sku || mo.item_id}`,
    })

    // Operations as sub-rows
    for (const op of mo.operations) {
      const opSegs: BarSegment[] = []
      const opStart = toMs(op.started_at)
      const opEnd = toMs(op.completed_at)

      if (opStart != null) {
        const e = opEnd ?? (opStart + op.duration_hours * 3600000)
        opSegs.push({
          start: opStart, end: Math.max(opStart + 1800000, e),
          color: statusColor(op.status),
          label: op.status,
          tooltip: `${op.operation_name}${op.work_center ? ` @ ${op.work_center}` : ''}\nDuration: ${op.duration_hours}h\nStatus: ${op.status}${opStart ? `\nStarted: ${fmtDateTime(opStart)}` : ''}${opEnd ? `\nCompleted: ${fmtDateTime(opEnd)}` : ''}`,
        })
      }

      // Work-center wait overlays for this operation
      for (const w of mo.waits) {
        if (w.production_operation_id === op.id) {
          const ws = toMs(w.started_at)
          const we = toMs(w.resolved_at) ?? (ws ? ws + 86400000 : null)
          if (ws != null && we != null) {
            opSegs.push({
              start: ws, end: we,
              color: COLORS.work_center,
              label: '⏳ WC',
              tooltip: waitTooltip(w),
            })
          }
        }
      }

      rows.push({
        id: op.id, indent: 2, segments: opSegs,
        label: `${op.sequence_order}. ${op.operation_name}`,
      })
    }
  }

  // Shipments
  for (const sh of tl.shipments) {
    const segs: BarSegment[] = []
    const dep = toMs(sh.planned_departure) ?? toMs(sh.dispatched_at)
    const arr = toMs(sh.delivered_at) ?? toMs(sh.planned_arrival)
    if (dep != null) {
      const e = arr ?? dep + 2 * 86400000
      segs.push({
        start: dep, end: Math.max(dep + 3600000, e),
        color: statusColor(sh.status),
        label: sh.status,
        tooltip: `Shipment ${sh.id}\nStatus: ${sh.status}${dep ? `\nDeparture: ${fmtDate(dep)}` : ''}${arr ? `\nArrival: ${fmtDate(arr)}` : ''}`,
        entityId: sh.id, entityPage: 'shipments',
      })
    }
    rows.push({ id: sh.id, indent: 0, segments: segs, label: `Ship ${sh.id}` })
  }

  // Invoices
  for (const inv of tl.invoices) {
    const segs: BarSegment[] = []
    const created = toMs(inv.created_at)
    const paid = toMs(inv.paid_at)
    if (created != null) {
      const e = paid ?? created + 86400000
      segs.push({
        start: created, end: Math.max(created + 3600000, e),
        color: statusColor(inv.status),
        label: inv.status,
        tooltip: `Invoice ${inv.id}\nStatus: ${inv.status}${created ? `\nCreated: ${fmtDate(created)}` : ''}${paid ? `\nPaid: ${fmtDate(paid)}` : ''}`,
        entityId: inv.id, entityPage: 'invoices',
      })
    }
    rows.push({ id: inv.id, indent: 0, segments: segs, label: `Inv ${inv.id}` })
  }

  return rows
}


function buildProductionOrderRows(tl: ProductionOrderTimeline): Row[] {
  const rows: Row[] = []
  const mo = tl.production_order

  // Context: parent SO
  if (tl.sales_order) {
    const so = tl.sales_order
    const created = toMs(so.created_at)
    const segs: BarSegment[] = []
    if (created != null) {
      const reqDel = toMs(so.requested_delivery_date)
      const endMs = reqDel ?? created + 86400000
      segs.push({
        start: created, end: Math.max(created + 3600000, endMs),
        color: statusColor(so.status),
        label: so.status || 'SO',
        tooltip: `Sales Order ${so.id}\nStatus: ${so.status}`,
        entityId: so.id, entityPage: 'orders',
      })
    }
    rows.push({ id: so.id, indent: 0, segments: segs, label: `SO ${so.id}` })
  }

  // The production order itself
  const moSegs: BarSegment[] = []
  const moStart = toMs(mo.started_at)
  const moEnd = toMs(mo.completed_at) ?? toMs(mo.eta_finish)
  if (moStart != null || moEnd != null) {
    const s = moStart ?? (moEnd! - 86400000)
    const e = moEnd ?? (moStart! + 86400000)
    moSegs.push({
      start: s, end: Math.max(s + 3600000, e),
      color: statusColor(mo.status),
      label: mo.status || '',
      tooltip: `${mo.id} — ${mo.item_sku || ''}`,
      entityId: mo.id, entityPage: 'production',
    })
  }
  // MO-level waits
  for (const w of mo.waits) {
    if (!w.production_operation_id) {
      const ws = toMs(w.started_at)
      const we = toMs(w.resolved_at) ?? (ws ? ws + 86400000 : null)
      if (ws != null && we != null) {
        moSegs.push({
          start: ws, end: we,
          color: COLORS[w.reason_type] || COLORS.waiting,
          label: w.reason_type === 'material' ? '⏳ material' : '⏳ WC',
          tooltip: waitTooltip(w),
        })
      }
    }
  }
  rows.push({
    id: mo.id, indent: 0, segments: moSegs,
    label: `MO ${mo.id} — ${mo.item_sku || mo.item_id}`,
  })

  // Operations
  for (const op of mo.operations) {
    const opSegs: BarSegment[] = []
    const opStart = toMs(op.started_at)
    const opEnd = toMs(op.completed_at)

    if (opStart != null) {
      const e = opEnd ?? (opStart + op.duration_hours * 3600000)
      opSegs.push({
        start: opStart, end: Math.max(opStart + 1800000, e),
        color: statusColor(op.status),
        label: op.status,
        tooltip: `${op.operation_name}${op.work_center ? ` @ ${op.work_center}` : ''}\nDuration: ${op.duration_hours}h\nStatus: ${op.status}`,
      })
    }

    for (const w of mo.waits) {
      if (w.production_operation_id === op.id) {
        const ws = toMs(w.started_at)
        const we = toMs(w.resolved_at) ?? (ws ? ws + 86400000 : null)
        if (ws != null && we != null) {
          opSegs.push({
            start: ws, end: we,
            color: COLORS.work_center,
            label: '⏳ WC',
            tooltip: waitTooltip(w),
          })
        }
      }
    }

    rows.push({
      id: op.id, indent: 1, segments: opSegs,
      label: `${op.sequence_order}. ${op.operation_name}`,
    })
  }

  // Sub-assemblies
  for (const child of tl.children) {
    const segs: BarSegment[] = []
    const cs = toMs(child.started_at)
    const ce = toMs(child.completed_at) ?? toMs(child.eta_finish)
    if (cs != null || ce != null) {
      const s = cs ?? (ce! - 86400000)
      const e = ce ?? (cs! + 86400000)
      segs.push({
        start: s, end: Math.max(s + 3600000, e),
        color: statusColor(child.status),
        label: child.status || '',
        tooltip: `Sub-assembly ${child.id}\n${child.item_sku || ''}`,
        entityId: child.id, entityPage: 'production',
      })
    }
    rows.push({
      id: child.id, indent: 1, segments: segs,
      label: `Sub ${child.id} — ${child.item_sku || ''}`,
    })
  }

  // Shipments
  for (const sh of tl.shipments) {
    const segs: BarSegment[] = []
    const dep = toMs(sh.planned_departure) ?? toMs(sh.dispatched_at)
    const arr = toMs(sh.delivered_at) ?? toMs(sh.planned_arrival)
    if (dep != null) {
      const e = arr ?? dep + 2 * 86400000
      segs.push({
        start: dep, end: Math.max(dep + 3600000, e),
        color: statusColor(sh.status),
        label: sh.status,
        tooltip: `Shipment ${sh.id}`,
        entityId: sh.id, entityPage: 'shipments',
      })
    }
    rows.push({ id: sh.id, indent: 0, segments: segs, label: `Ship ${sh.id}` })
  }

  // Invoices
  for (const inv of tl.invoices) {
    const segs: BarSegment[] = []
    const created = toMs(inv.created_at)
    const paid = toMs(inv.paid_at)
    if (created != null) {
      const e = paid ?? created + 86400000
      segs.push({
        start: created, end: Math.max(created + 3600000, e),
        color: statusColor(inv.status),
        label: inv.status,
        tooltip: `Invoice ${inv.id}\nStatus: ${inv.status}`,
        entityId: inv.id, entityPage: 'invoices',
      })
    }
    rows.push({ id: inv.id, indent: 0, segments: segs, label: `Inv ${inv.id}` })
  }

  return rows
}

function waitTooltip(w: TimelineWait): string {
  const s = toMs(w.started_at)
  const e = toMs(w.resolved_at)
  const dur = s && e ? ` (${daysBetween(s, e)})` : s ? ' (ongoing)' : ''
  if (w.reason_type === 'material') {
    return `Waited for material: ${w.reason_ref}${dur}`
  }
  return `Blocked by work center: ${w.reason_ref}${dur}`
}

// ---------------------------------------------------------------------------
// SVG rendering
// ---------------------------------------------------------------------------

const ROW_HEIGHT = 26
const LABEL_WIDTH = 220
const BAR_HEIGHT = 16
const BAR_Y_OFFSET = (ROW_HEIGHT - BAR_HEIGHT) / 2
const PADDING_X = 16
const HEADER_HEIGHT = 30
const LEGEND_HEIGHT = 32

function setHash(page: string, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

export function TimelineGantt({ soTimeline, moTimeline, onNavigate }: TimelineGanttProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null)

  const rows = useMemo(() => {
    if (soTimeline) return buildSalesOrderRows(soTimeline)
    if (moTimeline) return buildProductionOrderRows(moTimeline)
    return []
  }, [soTimeline, moTimeline])

  // Compute time domain
  const { minMs, maxMs } = useMemo(() => {
    let lo = Infinity, hi = -Infinity
    for (const row of rows) {
      for (const seg of row.segments) {
        if (seg.start < lo) lo = seg.start
        if (seg.end > hi) hi = seg.end
      }
    }
    if (!isFinite(lo)) {
      const now = Date.now()
      lo = now - 30 * 86400000
      hi = now
    }
    // Add 5% padding on each side
    const span = hi - lo || 86400000
    return { minMs: lo - span * 0.03, maxMs: hi + span * 0.03 }
  }, [rows])

  if (rows.length === 0) {
    return <div className="text-sm text-slate-400">No timeline data available.</div>
  }

  const chartWidth = 700
  const barAreaWidth = chartWidth - LABEL_WIDTH - PADDING_X * 2
  const svgHeight = HEADER_HEIGHT + rows.length * ROW_HEIGHT + LEGEND_HEIGHT
  const svgWidth = chartWidth

  function xPos(ms: number): number {
    return LABEL_WIDTH + PADDING_X + ((ms - minMs) / (maxMs - minMs)) * barAreaWidth
  }

  // Generate ticks (dates)
  const ticks: { ms: number; label: string }[] = []
  {
    const spanDays = (maxMs - minMs) / 86400000
    const step = spanDays > 90 ? 14 : spanDays > 30 ? 7 : spanDays > 14 ? 3 : 1
    const startDate = new Date(minMs)
    startDate.setUTCHours(0, 0, 0, 0)
    let t = startDate.getTime()
    while (t <= maxMs) {
      if (t >= minMs) {
        ticks.push({ ms: t, label: fmtDate(t).slice(5) }) // MM-DD
      }
      t += step * 86400000
    }
  }

  const handleClick = (seg: BarSegment) => {
    if (seg.entityId && seg.entityPage) {
      if (onNavigate) {
        onNavigate(seg.entityPage, seg.entityId)
      } else {
        setHash(seg.entityPage, seg.entityId)
      }
    }
  }

  return (
    <div className="overflow-x-auto">
      <svg
        width={svgWidth}
        height={svgHeight}
        className="text-xs select-none"
        onMouseLeave={() => setTooltip(null)}
      >
        {/* Background stripes */}
        {rows.map((_, i) => (
          <rect
            key={`bg-${i}`}
            x={0}
            y={HEADER_HEIGHT + i * ROW_HEIGHT}
            width={svgWidth}
            height={ROW_HEIGHT}
            fill={i % 2 === 0 ? '#f8fafc' : '#ffffff'}
          />
        ))}

        {/* Date gridlines + labels */}
        {ticks.map((tick, i) => {
          const x = xPos(tick.ms)
          return (
            <g key={`tick-${i}`}>
              <line
                x1={x} y1={HEADER_HEIGHT}
                x2={x} y2={HEADER_HEIGHT + rows.length * ROW_HEIGHT}
                stroke="#e2e8f0" strokeWidth={1}
              />
              <text
                x={x} y={HEADER_HEIGHT - 6}
                textAnchor="middle"
                className="fill-slate-400"
                style={{ fontSize: '10px' }}
              >
                {tick.label}
              </text>
            </g>
          )
        })}

        {/* Row labels */}
        {rows.map((row, i) => (
          <text
            key={`label-${row.id}`}
            x={8 + row.indent * 14}
            y={HEADER_HEIGHT + i * ROW_HEIGHT + ROW_HEIGHT / 2 + 4}
            className="fill-slate-600"
            style={{ fontSize: '11px' }}
          >
            {row.label.length > 28 ? row.label.slice(0, 26) + '…' : row.label}
          </text>
        ))}

        {/* Bars */}
        {rows.map((row, rowIdx) =>
          row.segments.map((seg, segIdx) => {
            const x1 = Math.max(xPos(seg.start), LABEL_WIDTH + PADDING_X)
            const x2 = Math.min(xPos(seg.end), LABEL_WIDTH + PADDING_X + barAreaWidth)
            const w = Math.max(x2 - x1, 3)
            const y = HEADER_HEIGHT + rowIdx * ROW_HEIGHT + BAR_Y_OFFSET
            const clickable = !!(seg.entityId && seg.entityPage)
            return (
              <rect
                key={`bar-${row.id}-${segIdx}`}
                x={x1}
                y={y}
                width={w}
                height={BAR_HEIGHT}
                rx={3}
                fill={seg.color}
                opacity={0.85}
                className={clickable ? 'cursor-pointer hover:opacity-100' : ''}
                onClick={() => handleClick(seg)}
                onMouseEnter={(e) => setTooltip({
                  x: e.clientX,
                  y: e.clientY,
                  text: seg.tooltip,
                })}
                onMouseMove={(e) => setTooltip({
                  x: e.clientX,
                  y: e.clientY,
                  text: seg.tooltip,
                })}
                onMouseLeave={() => setTooltip(null)}
              />
            )
          })
        )}

        {/* Legend */}
        <g transform={`translate(${LABEL_WIDTH + PADDING_X}, ${HEADER_HEIGHT + rows.length * ROW_HEIGHT + 8})`}>
          {[
            { color: COLORS.completed, label: 'Completed' },
            { color: COLORS.in_progress, label: 'In progress' },
            { color: COLORS.pending, label: 'Pending' },
            { color: COLORS.material, label: 'Waiting (material)' },
            { color: COLORS.work_center, label: 'Blocked (work center)' },
          ].map((item, i) => (
            <g key={`legend-${i}`} transform={`translate(${i * 130}, 0)`}>
              <rect x={0} y={0} width={10} height={10} rx={2} fill={item.color} opacity={0.85} />
              <text x={14} y={9} className="fill-slate-500" style={{ fontSize: '10px' }}>
                {item.label}
              </text>
            </g>
          ))}
        </g>
      </svg>

      {/* Floating tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 px-2 py-1 text-xs bg-slate-800 text-white rounded shadow-lg pointer-events-none whitespace-pre-line"
          style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  )
}
