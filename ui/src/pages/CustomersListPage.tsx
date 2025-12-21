import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Customer } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Customer; dir: SortDir }

function sortRows(rows: Customer[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Customer): SortState {
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

export function CustomersListPage() {
    const [customers, setCustomers] = useState<Customer[]>([])
    const [customerSort, setCustomerSort] = useState<SortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { setListContext } = useNavigation()

    useEffect(() => {
        api.customers()
            .then((res) => {
                setCustomers(res.customers || [])
                setLoading(false)
            })
            .catch((err) => {
                console.error(err)
                setError('Failed to load customers')
                setLoading(false)
            })
    }, [])

    const sortedCustomers = sortRows(customers, customerSort)

    const handleCustomerClick = (customer: Customer, index: number) => {
        // Store list context for future navigation
        setListContext({
            listType: 'customers',
            items: sortedCustomers,
            currentIndex: index,
        })
        setHash('customers', customer.id)
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customers</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading customers...</div>
                </Card>
            </section>
        )
    }

    if (error) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Customers</div>
                <Card>
                    <div className="text-sm text-red-600">{error}</div>
                </Card>
            </section>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Customers</div>
            <Card>
                <Table
                    rows={sortedCustomers}
                    sortKey={customerSort?.key}
                    sortDir={customerSort?.dir}
                    onSort={(key) => setCustomerSort((prev) => nextSort(prev, key))}
                    onRowClick={handleCustomerClick}
                    columns={[
                        {
                            key: 'id',
                            label: 'ID',
                            sortable: true,
                        },
                        {
                            key: 'name',
                            label: 'Name',
                            sortable: true,
                        },
                        { key: 'company', label: 'Company', sortable: true },
                        { key: 'email', label: 'Email', sortable: true },
                        { key: 'city', label: 'City', sortable: true },
                    ]}
                />
            </Card>
        </section>
    )
}
