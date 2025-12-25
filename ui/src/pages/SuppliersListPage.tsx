import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Supplier } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Supplier; dir: SortDir }

function sortRows(rows: Supplier[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Supplier): SortState {
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

export function SuppliersListPage() {
    const [suppliers, setSuppliers] = useState<Supplier[]>([])
    const [supplierSort, setSupplierSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        // Navigation context will be set on row click
    }, [])

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.suppliers()
            .then((data) => {
                if (!cancelled) {
                    setSuppliers(data.suppliers)
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
    }, [])

    const sortedSuppliers = sortRows(suppliers, supplierSort)

    function handleHeaderClick(key: keyof Supplier) {
        setSupplierSort((prev) => nextSort(prev, key))
    }

    if (loading) {
        return (
            <Card title="Suppliers">
                <div className="text-sm text-gray-500">Loading suppliers...</div>
            </Card>
        )
    }

    if (error) {
        return (
            <Card title="Suppliers">
                <div className="text-sm text-red-600">Error: {error}</div>
            </Card>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Suppliers · {suppliers.length} total</div>
            <Card>
                <Table
                    rows={sortedSuppliers}
                    columns={[
                        { key: 'name', label: 'Name', sortable: true },
                        { key: 'contact_name', label: 'Contact', sortable: true },
                        { key: 'contact_email', label: 'Email', sortable: true },
                        { key: 'contact_phone', label: 'Phone', sortable: true },
                    ]}
                    sortKey={supplierSort?.key}
                    sortDir={supplierSort?.dir}
                    onSort={(key) => setSupplierSort((prev) => nextSort(prev, key as keyof Supplier))}
                    onRowClick={(row, index) => {
                        setListContext({
                            listType: 'suppliers',
                            items: sortedSuppliers,
                            currentIndex: index,
                        })
                        setHash('suppliers', row.id)
                    }}
                />
            </Card>
        </section>
    )
}
