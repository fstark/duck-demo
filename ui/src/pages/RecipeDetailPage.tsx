import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Badge } from '../components/Badge'
import { Recipe, RecipeIngredient, RecipeOperation } from '../types'
import { formatQtyWithUom } from '../utils/quantity'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'
import { useTableSort } from '../utils/useTableSort'

type SortDir = 'asc' | 'desc'
type IngredientSortState = { key: keyof RecipeIngredient; dir: SortDir }
type OperationSortState = { key: keyof RecipeOperation; dir: SortDir }

function sortIngredients(rows: RecipeIngredient[], state: IngredientSortState | null) {
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

function sortOperations(rows: RecipeOperation[], state: OperationSortState | null) {
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

function nextIngredientSort(prev: IngredientSortState | null, key: keyof RecipeIngredient): IngredientSortState {
    if (prev && prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    }
    return { key, dir: 'asc' }
}

function nextOperationSort(prev: OperationSortState | null, key: keyof RecipeOperation): OperationSortState {
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

interface RecipeDetailPageProps {
    recipeId: string
}

export function RecipeDetailPage({ recipeId }: RecipeDetailPageProps) {
    const [recipe, setRecipe] = useState<Recipe | null>(null)
    const [ingredientSort, setIngredientSort] = useState<IngredientSortState | null>(null)
    const [operationSort, setOperationSort] = useState<OperationSortState | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { listContext, setListContext, referrer, setReferrer, clearListContext } = useNavigation()

    useEffect(() => {
        // Navigation context comes from list page
    }, [])

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)
        api.recipeDetail(recipeId)
            .then((data) => {
                if (!cancelled) {
                    setRecipe(data)
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
    }, [recipeId])

    function handleIngredientHeaderClick(key: keyof RecipeIngredient) {
        setIngredientSort((prev) => nextIngredientSort(prev, key))
    }

    function handleOperationHeaderClick(key: keyof RecipeOperation) {
        setOperationSort((prev) => nextOperationSort(prev, key))
    }

    if (loading) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Recipe Details</div>
                <Card>
                    <div className="text-sm text-slate-500">Loading recipe...</div>
                </Card>
            </section>
        )
    }

    if (error || !recipe) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Recipe Details</div>
                <Card>
                    <div className="text-sm text-red-600">{error || 'Recipe not found'}</div>
                    <button
                        className="mt-3 text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('recipes')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Recipes'}
                    </button>
                </Card>
            </section>
        )
    }

    const hasPrevious = listContext && listContext.currentIndex > 0
    const hasNext = listContext && listContext.currentIndex < listContext.items.length - 1

    const handlePrevious = () => {
        if (!hasPrevious || !listContext) return
        const prevIndex = listContext.currentIndex - 1
        const prevItem = listContext.items[prevIndex] as Recipe
        setListContext({ ...listContext, currentIndex: prevIndex })
        setHash('recipes', prevItem.id)
    }

    const handleNext = () => {
        if (!hasNext || !listContext) return
        const nextIndex = listContext.currentIndex + 1
        const nextItem = listContext.items[nextIndex] as Recipe
        setListContext({ ...listContext, currentIndex: nextIndex })
        setHash('recipes', nextItem.id)
    }

    const ingredients = recipe.ingredients || []
    const operations = recipe.operations || []
    const sortedIngredients = sortIngredients(ingredients, ingredientSort)
    const sortedOperations = sortOperations(operations, operationSort)

    return (
        <section>
            <div className="text-lg font-semibold text-slate-800 mb-4">Recipe Details</div>
            <Card>
                <div className="flex items-center justify-between mb-4">
                    <button
                        className="text-brand-600 hover:underline text-sm"
                        onClick={() => {
                            if (referrer) {
                                clearListContext()
                                setHash(referrer.page, referrer.id)
                            } else {
                                setHash('recipes')
                            }
                        }}
                        type="button"
                    >
                        ← {referrer ? `Back to ${referrer.label}` : 'Back to Recipes'}
                    </button>
                    {listContext && (
                        <div className="flex items-center gap-2">
                            <button
                                className={`px-3 py-1 text-sm rounded ${hasPrevious
                                    ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                    : 'bg-slate-50 text-slate-300 cursor-not-allowed'
                                    }`}
                                onClick={handlePrevious}
                                disabled={!hasPrevious}
                                type="button"
                            >
                                ← Previous
                            </button>
                            <span className="text-xs text-slate-500">
                                {listContext.currentIndex + 1} of {listContext.items.length}
                            </span>
                            <button
                                className={`px-3 py-1 text-sm rounded ${hasNext
                                    ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                    : 'bg-slate-50 text-slate-300 cursor-not-allowed'
                                    }`}
                                onClick={handleNext}
                                disabled={!hasNext}
                                type="button"
                            >
                                Next →
                            </button>
                        </div>
                    )}
                </div>
                <div className="space-y-3 text-sm text-slate-800">
                    <div className="font-semibold text-lg">Recipe {recipe.id}</div>

                    <div className="grid grid-cols-2 gap-3">
                        <Card title="Output">
                            <div className="space-y-2">
                                <div>
                                    <button
                                        className="text-brand-600 hover:underline font-medium"
                                        onClick={() => {
                                            setReferrer({ page: 'recipes', id: recipeId, label: `Recipe ${recipe.id}` })
                                            setHash('items', recipe.output_sku)
                                        }}
                                        type="button"
                                    >
                                        {recipe.output_sku}
                                    </button>
                                </div>
                                <div className="text-slate-600">{recipe.output_name}</div>
                                {recipe.output_type && <div><Badge>{recipe.output_type}</Badge></div>}
                            </div>
                        </Card>

                        <Card title="Production">
                            <div className="space-y-2">
                                <div><span className="text-slate-500">Batch size:</span> {formatQtyWithUom(recipe.output_qty, recipe.output_uom || 'ea')}</div>
                                <div><span className="text-slate-500">Production time:</span> {recipe.production_time_hours} hours</div>
                            </div>
                        </Card>
                    </div>

                    {recipe.notes && (
                        <Card title="Notes">
                            <div className="text-slate-700 whitespace-pre-wrap">{recipe.notes}</div>
                        </Card>
                    )}

                    <Card title={`Ingredients (${ingredients.length})`}>
                        {ingredients.length === 0 ? (
                            <div className="text-sm text-slate-500">No ingredients</div>
                        ) : (
                            <Table
                                rows={sortedIngredients}
                                columns={[
                                    { key: 'sequence_order', label: '#', sortable: true },
                                    { key: 'ingredient_sku', label: 'SKU', sortable: true },
                                    { key: 'ingredient_name', label: 'Ingredient', sortable: true },
                                    {
                                        key: 'input_qty',
                                        label: 'Qty per Batch',
                                        sortable: true,
                                        render: (row) => formatQtyWithUom(row.input_qty, row.input_uom)
                                    },
                                ]}
                                sortKey={ingredientSort?.key}
                                sortDir={ingredientSort?.dir}
                                onSort={(key) => setIngredientSort((prev) => nextIngredientSort(prev, key as keyof RecipeIngredient))}
                                onRowClick={(row) => {
                                    setReferrer({ page: 'recipes', id: recipeId, label: `Recipe ${recipe.id}` })
                                    setHash('items', row.ingredient_sku || '')
                                }}
                            />
                        )}
                    </Card>

                    <Card title={`Operations (${operations.length})`}>
                        {operations.length === 0 ? (
                            <div className="text-sm text-slate-500">No operations</div>
                        ) : (
                            <Table
                                rows={sortedOperations}
                                columns={[
                                    { key: 'sequence_order', label: '#', sortable: true },
                                    { key: 'operation_name', label: 'Operation', sortable: true },
                                    { key: 'work_center', label: 'Work Center', sortable: true, render: (row) => row.work_center || '—' },
                                    { key: 'duration_hours', label: 'Duration (hrs)', sortable: true },
                                ]}
                                sortKey={operationSort?.key}
                                sortDir={operationSort?.dir}
                                onSort={(key) => setOperationSort((prev) => nextOperationSort(prev, key as keyof RecipeOperation))}
                            />
                        )}
                    </Card>
                </div>
            </Card>
        </section>
    )
}
