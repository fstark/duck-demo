import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Item } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Item; dir: SortDir }

function sortRows(rows: Item[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Item): SortState {
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

export function ItemsListPage() {
  const [items, setItems] = useState<Item[]>([])
  const [itemSort, setItemSort] = useState<SortState | null>({ key: 'type', dir: 'asc' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { setListContext } = useNavigation()

  useEffect(() => {
    api.items(false)
      .then((res) => {
        setItems(res.items || [])
        setLoading(false)
      })
      .catch((err) => {
        console.error(err)
        setError('Failed to load items')
        setLoading(false)
      })
  }, [])

  const sortedItems = sortRows(items, itemSort)

  const handleItemClick = (item: Item, index: number) => {
    // Store list context for future navigation
    setListContext({
      listType: 'items',
      items: sortedItems,
      currentIndex: index,
    })
    setHash('items', item.sku)
  }

  if (loading) {
    return (
      <section>
        <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
        <Card>
          <div className="text-sm text-slate-500">Loading items...</div>
        </Card>
      </section>
    )
  }

  if (error) {
    return (
      <section>
        <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
        <Card>
          <div className="text-sm text-red-600">{error}</div>
        </Card>
      </section>
    )
  }

  return (
    <section>
      <div className="text-lg font-semibold text-slate-800 mb-4">Items</div>
      <Card>
        <Table
          rows={sortedItems}
          sortKey={itemSort?.key}
          sortDir={itemSort?.dir}
          onSort={(key) => setItemSort((prev) => nextSort(prev, key))}
          onRowClick={handleItemClick}
          columns={[
            {
              key: 'sku',
              label: 'SKU',
              sortable: true,
            },
            {
              key: 'name',
              label: 'Name',
              sortable: true,
            },
            {
              key: 'unit_price',
              label: 'Unit price',
              sortable: true,
              render: (row) => (row.unit_price != null ? `${row.unit_price} €` : '—'),
            },
            { key: 'type', label: 'Type', sortable: true },
            { key: 'available_total', label: 'Available', sortable: true },
          ]}
        />
      </Card>
    </section>
  )
}
