import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Recipe } from '../types'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

type SortDir = 'asc' | 'desc'
type SortState = { key: keyof Recipe; dir: SortDir }

function sortRows(rows: Recipe[], state: SortState | null) {
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

function nextSort(prev: SortState | null, key: keyof Recipe): SortState {
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

export function RecipesListPage() {
    const [recipes, setRecipes] = useState<Recipe[]>([])
    const [recipeSort, setRecipeSort] = useState<SortState | null>(null)
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
        api.recipes()
            .then((data) => {
                if (!cancelled) {
                    setRecipes(data.recipes)
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

    const sortedRecipes = sortRows(recipes, recipeSort)

    function handleHeaderClick(key: keyof Recipe) {
        setRecipeSort((prev) => nextSort(prev, key))
    }

    if (loading) {
        return (
            <Card title="Recipes">
                <div className="text-sm text-gray-500">Loading recipes...</div>
            </Card>
        )
    }

    if (error) {
        return (
            <Card title="Recipes">
                <div className="text-sm text-red-600">Error: {error}</div>
            </Card>
        )
    }

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Recipes · {recipes.length} total</div>
            <Card>
                <Table
                    rows={sortedRecipes}
                    columns={[
                        { key: 'id', label: 'Recipe ID', sortable: true },
                        { key: 'output_sku', label: 'Output SKU', sortable: true },
                        { key: 'output_name', label: 'Output Item', sortable: true },
                        { key: 'output_qty', label: 'Batch Size', sortable: true },
                        { key: 'production_time_hours', label: 'Time (hrs)', sortable: true },
                    ]}
                    sortKey={recipeSort?.key}
                    sortDir={recipeSort?.dir}
                    onSort={(key) => setRecipeSort((prev) => nextSort(prev, key as keyof Recipe))}
                    onRowClick={(row, index) => {
                        setListContext({
                            listType: 'recipes',
                            items: sortedRecipes,
                            currentIndex: index,
                        })
                        setHash('recipes', row.id)
                    }}
                />
            </Card>
        </section>
    )
}
