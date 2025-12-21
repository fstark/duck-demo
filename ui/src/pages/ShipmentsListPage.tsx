import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Shipment } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Shipment; dir: SortDir }

function sortRows(rows: Shipment[], state: SortState | null) {
    if (!state) return rows
    const { key, dir } = state
    const sorted = [...rows].sort((a, b) => {
        const av = a[key]
        const bv = b[key]
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        if (typeof av === 'number' && typeof bv === 'number') {
            return dir === 'asc' ? av - bv : bv - av
        }
        const compare = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: 'base' })
        return dir === 'asc' ? compare : -compare
    })
    return sorted
}

function nextSort(prev: SortState | null, key: keyof Shipment): SortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: 'asc' }
}

function setHash(page: string, id?: string) {
    const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
    if (typeof window !== 'undefined') {
        window.location.hash = path
    }
}

export function ShipmentsListPage() {
    const [shipments, setShipments] = useState<Shipment[]>([])
    const [shipmentSort, setShipmentSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.shipments()
            .then((res) => {
                setShipments(res.shipments || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load shipments')
                setLoading(false)
            })
    }, [])

    const sortedShipments = sortRows(shipments, shipmentSort)

    const handleShipmentClick = (shipment: Shipment, index: number) => {
        // Store list context for future navigation
        setListContext({
            listType: 'shipments',
            items: sortedShipments,
            currentIndex: index,
        })
        setHash('shipments', shipment.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Shipments</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading shipments...</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Shipments</div>
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Shipments</div>
            <Card>
                <Table
                    rows={sortedShipments}
                    sortKey={shipmentSort?.key}
                    sortDir={shipmentSort?.dir}
                    onSort={(key) => setShipmentSort((prev) => nextSort(prev, key))}
                    onRowClick={handleShipmentClick}
                    columns={[
                        {
                            key: 'id',
                            label: 'Shipment',
                            sortable: true,
                        },
                        {
                            key: 'status',
                            label: 'Status',
                            sortable: true,
                            render: (row) => <Badge>{row.status}</Badge>,
                        },
                        { key: 'planned_departure', label: 'Departure', sortable: true },
                        { key: 'planned_arrival', label: 'Arrival', sortable: true },
                    ]}
                />
            </Card>
        </section>
    )
}
