import { useMemo, useState } from 'react'
import type { SupplyChainTrace, SupplyChainNode } from '../types'

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const COL_X: Record<string, number> = { shipment: 0, fg_batch: 1, mo: 2, po: 3 }
const COL_LABELS = ['Shipment', 'FG Batches', 'Manufacturing', 'Purchase Orders']
const COL_COLORS: Record<string, string> = {
    po: '#8b5cf6',      // violet
    mo: '#3b82f6',      // blue
    fg_batch: '#22c55e', // green
    shipment: '#f59e0b', // amber
}
const NODE_W = 140
const NODE_H = 50
const COL_GAP = 140
const ROW_GAP = 16
const HEADER_H = 36
const PAD_X = 24
const PAD_Y = 12

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LayoutNode = SupplyChainNode & { x: number; y: number; col: number; row: number }

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------

function layoutNodes(nodes: SupplyChainNode[], edges: { source: string; target: string }[]): LayoutNode[] {
    // Group by column
    const cols: Record<number, SupplyChainNode[]> = { 0: [], 1: [], 2: [], 3: [] }
    for (const n of nodes) {
        const col = COL_X[n.type] ?? 0
        cols[col].push(n)
    }

    // Sort within each column by timestamp (primary), then by ID (stable secondary)
    for (const c of Object.values(cols)) {
        c.sort((a, b) => {
            const tCmp = (a.timestamp || '').localeCompare(b.timestamp || '')
            if (tCmp !== 0) return tCmp
            return a.id.localeCompare(b.id)
        })
    }

    // First pass: assign preliminary positions
    const nodeRowMap = new Map<string, number>()
    for (const [colStr, colNodes] of Object.entries(cols)) {
        colNodes.forEach((n, idx) => nodeRowMap.set(n.id, idx))
    }

    // Build adjacency map for connections
    const connectionsMap = new Map<string, string[]>()
    for (const e of edges) {
        if (!connectionsMap.has(e.source)) connectionsMap.set(e.source, [])
        if (!connectionsMap.has(e.target)) connectionsMap.set(e.target, [])
        connectionsMap.get(e.source)!.push(e.target)
        connectionsMap.get(e.target)!.push(e.source)
    }

    // Second pass: within each timestamp group, reorder by topological position
    // This reduces edge crossings by keeping connected nodes vertically aligned
    for (const [colStr, colNodes] of Object.entries(cols)) {
        // Group nodes by timestamp
        const timestampGroups: SupplyChainNode[][] = []
        let currentGroup: SupplyChainNode[] = []
        let currentTimestamp = ''

        for (const n of colNodes) {
            const ts = n.timestamp || ''
            if (ts !== currentTimestamp) {
                if (currentGroup.length > 0) timestampGroups.push(currentGroup)
                currentGroup = [n]
                currentTimestamp = ts
            } else {
                currentGroup.push(n)
            }
        }
        if (currentGroup.length > 0) timestampGroups.push(currentGroup)

        // For each group with multiple nodes, compute connection-based position scores
        const sortedNodes: SupplyChainNode[] = []
        for (const group of timestampGroups) {
            if (group.length === 1) {
                sortedNodes.push(group[0])
            } else {
                // Compute average row of connected nodes for each node in this group
                const scored = group.map(n => {
                    const connections = connectionsMap.get(n.id) || []
                    const connectedRows = connections
                        .map(cid => nodeRowMap.get(cid))
                        .filter((r): r is number => r !== undefined)
                    const avgRow = connectedRows.length > 0
                        ? connectedRows.reduce((sum, r) => sum + r, 0) / connectedRows.length
                        : nodeRowMap.get(n.id) || 0
                    return { node: n, score: avgRow }
                })
                // Sort by score, then by ID for stability
                scored.sort((a, b) => {
                    const sCmp = a.score - b.score
                    if (sCmp !== 0) return sCmp
                    return a.node.id.localeCompare(b.node.id)
                })
                sortedNodes.push(...scored.map(s => s.node))
            }
        }

        // Update the column with reordered nodes
        cols[Number(colStr)] = sortedNodes
    }

    // Final pass: assign positions
    const result: LayoutNode[] = []
    for (const [colStr, colNodes] of Object.entries(cols)) {
        const col = Number(colStr)
        const x = PAD_X + col * (NODE_W + COL_GAP)
        for (let row = 0; row < colNodes.length; row++) {
            const y = HEADER_H + PAD_Y + row * (NODE_H + ROW_GAP)
            result.push({ ...colNodes[row], x, y, col, row })
        }
    }
    return result
}

function computeSize(nodes: LayoutNode[]): { width: number; height: number } {
    const maxCol = 3
    const width = PAD_X * 2 + (maxCol + 1) * NODE_W + maxCol * COL_GAP
    let maxY = HEADER_H + PAD_Y + NODE_H
    for (const n of nodes) {
        maxY = Math.max(maxY, n.y + NODE_H + PAD_Y)
    }
    return { width, height: maxY }
}

// ---------------------------------------------------------------------------
// Date formatting
// ---------------------------------------------------------------------------

function shortDate(ts?: string | null): string {
    if (!ts) return ''
    const d = ts.slice(0, 10)  // YYYY-MM-DD
    const parts = d.split('-')
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${months[parseInt(parts[1], 10) - 1]} ${parseInt(parts[2], 10)}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type SupplyChainFlowProps = {
    trace: SupplyChainTrace
    onNavigate?: (page: string, id: string) => void
}

export function SupplyChainFlow({ trace, onNavigate }: SupplyChainFlowProps) {
    const [hoveredNode, setHoveredNode] = useState<string | null>(null)
    const [hoveredEdge, setHoveredEdge] = useState<string | null>(null)

    const laidOut = useMemo(() => layoutNodes(trace.nodes, trace.edges), [trace.nodes, trace.edges])
    const nodeMap = useMemo(() => {
        const m = new Map<string, LayoutNode>()
        for (const n of laidOut) m.set(n.id, n)
        return m
    }, [laidOut])

    const { width, height } = useMemo(() => computeSize(laidOut), [laidOut])

    // Which edges connect to hovered node?
    const connectedEdges = useMemo(() => {
        if (!hoveredNode) return new Set<string>()
        const s = new Set<string>()
        for (const e of trace.edges) {
            if (e.source === hoveredNode || e.target === hoveredNode) {
                s.add(`${e.source}-${e.target}`)
            }
        }
        return s
    }, [hoveredNode, trace.edges])

    const connectedNodes = useMemo(() => {
        if (!hoveredNode) return new Set<string>()
        const s = new Set<string>([hoveredNode])
        for (const e of trace.edges) {
            if (e.source === hoveredNode) s.add(e.target)
            if (e.target === hoveredNode) s.add(e.source)
        }
        return s
    }, [hoveredNode, trace.edges])

    function handleNodeClick(n: LayoutNode) {
        if (!onNavigate) return
        if (n.type === 'po') onNavigate('purchase-orders', n.id)
        else if (n.type === 'mo') onNavigate('production-orders', n.id)
        else if (n.type === 'shipment') onNavigate('shipments', n.id)
    }

    const dim = hoveredNode !== null

    return (
        <div className="overflow-x-auto">
            <svg width={width} height={height} className="font-sans">
                {/* Column headers */}
                {COL_LABELS.map((label, i) => {
                    const x = PAD_X + i * (NODE_W + COL_GAP) + NODE_W / 2
                    return (
                        <text
                            key={label}
                            x={x} y={20}
                            textAnchor="middle"
                            className="fill-slate-500 text-[11px] font-semibold uppercase tracking-wider"
                        >
                            {label}
                        </text>
                    )
                })}

                {/* Edges */}
                {trace.edges.map((e, i) => {
                    const src = nodeMap.get(e.source)
                    const tgt = nodeMap.get(e.target)
                    if (!src || !tgt) return null

                    const x1 = src.x + NODE_W
                    const y1 = src.y + NODE_H / 2
                    const x2 = tgt.x
                    const y2 = tgt.y + NODE_H / 2
                    const cx1 = x1 + (x2 - x1) * 0.4
                    const cx2 = x1 + (x2 - x1) * 0.6

                    const edgeKey = `${e.source}-${e.target}`
                    const isHighlighted = connectedEdges.has(edgeKey) || hoveredEdge === edgeKey
                    const opacity = dim && !isHighlighted ? 0.12 : 1

                    return (
                        <g key={`${edgeKey}-${i}`}
                            onMouseEnter={() => setHoveredEdge(edgeKey)}
                            onMouseLeave={() => setHoveredEdge(null)}
                        >
                            <path
                                d={`M${x1},${y1} C${cx1},${y1} ${cx2},${y2} ${x2},${y2}`}
                                fill="none"
                                stroke={isHighlighted ? '#3b82f6' : '#94a3b8'}
                                strokeWidth={isHighlighted ? 2 : 1.2}
                                opacity={opacity}
                                markerEnd="url(#arrowhead)"
                            />
                            {e.label && isHighlighted && (
                                <text
                                    x={(x1 + x2) / 2}
                                    y={(y1 + y2) / 2 - 6}
                                    textAnchor="middle"
                                    className="fill-slate-700 text-[10px] font-medium"
                                >
                                    {e.label}
                                </text>
                            )}
                        </g>
                    )
                })}

                {/* Nodes */}
                {laidOut.map((n) => {
                    const color = COL_COLORS[n.type]
                    const isHovered = hoveredNode === n.id
                    const isConnected = connectedNodes.has(n.id)
                    const opacity = dim && !isConnected ? 0.2 : 1
                    const clickable = n.type !== 'fg_batch' && onNavigate

                    return (
                        <g
                            key={n.id}
                            transform={`translate(${n.x}, ${n.y})`}
                            onMouseEnter={() => setHoveredNode(n.id)}
                            onMouseLeave={() => setHoveredNode(null)}
                            onClick={() => handleNodeClick(n)}
                            style={{ cursor: clickable ? 'pointer' : 'default', opacity }}
                        >
                            <rect
                                width={NODE_W} height={NODE_H} rx={6}
                                fill={isHovered ? color : 'white'}
                                stroke={color}
                                strokeWidth={isHovered || isConnected ? 2 : 1}
                            />
                            <text
                                x={NODE_W / 2} y={18}
                                textAnchor="middle"
                                className="text-[11px] font-semibold"
                                fill={isHovered ? 'white' : color}
                            >
                                {n.label}
                            </text>
                            <text
                                x={NODE_W / 2} y={34}
                                textAnchor="middle"
                                className="text-[10px]"
                                fill={isHovered ? 'rgba(255,255,255,0.85)' : '#64748b'}
                            >
                                {n.type === 'fg_batch' ? n.item_name : shortDate(n.timestamp)}
                            </text>
                            {n.type === 'fg_batch' && (
                                <text
                                    x={NODE_W / 2} y={46}
                                    textAnchor="middle"
                                    className="text-[9px]"
                                    fill={isHovered ? 'rgba(255,255,255,0.7)' : '#94a3b8'}
                                >
                                    {shortDate(n.timestamp)}
                                </text>
                            )}
                            {n.type === 'mo' && n.sales_order_id && n.sales_order_id !== trace.sales_order_id && (
                                <text
                                    x={NODE_W - 4} y={12}
                                    textAnchor="end"
                                    className="text-[8px] font-bold"
                                    fill="#f59e0b"
                                >
                                    cross
                                </text>
                            )}
                        </g>
                    )
                })}

                {/* Arrow marker */}
                <defs>
                    <marker
                        id="arrowhead" markerWidth="8" markerHeight="6"
                        refX="8" refY="3" orient="auto"
                    >
                        <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
                    </marker>
                </defs>
            </svg>
        </div>
    )
}
