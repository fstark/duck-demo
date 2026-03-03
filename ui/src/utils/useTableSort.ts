import { useState, useMemo } from 'react'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

export function useTableSort<T extends { [key: string]: any }>(
    rows: T[],
    initialSort: SortState<T> | null = null
) {
    const [sortState, setSortState] = useState<SortState<T> | null>(initialSort)

    const sortedRows = useMemo(() => {
        if (!sortState) return rows
        const { key, dir } = sortState
        const sorted = [...rows].sort((a, b) => {
            const av = a[key]
            const bv = b[key]
            if (av == null && bv == null) return 0
            if (av == null) return 1
            if (bv == null) return -1
            if (typeof av === 'number' && typeof bv === 'number') {
                return dir === 'asc' ? av - bv : bv - av
            }
            const compare = String(av).localeCompare(String(bv), undefined, {
                numeric: true,
                sensitivity: 'base',
            })
            return dir === 'asc' ? compare : -compare
        })
        return sorted
    }, [rows, sortState])

    const onSort = (key: keyof T) => {
        setSortState((prev) => {
            if (prev && prev.key === key) {
                return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
            }
            return { key, dir: 'asc' }
        })
    }

    return {
        sortedRows,
        sortKey: sortState?.key,
        sortDir: sortState?.dir,
        onSort,
    }
}
