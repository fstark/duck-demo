import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Table } from '../components/Table'
import { Recipe, RecipeIngredient, RecipeOperation } from '../types'
import { formatQtyWithUom } from '../utils/quantity.tsx'
import { api } from '../api'
import { useNavigation } from '../contexts/NavigationContext'

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
                <div className="text-lg font-semibold text-slate-800 mb-4">Recipe Detail</div>
                <Card>
                    <div className="text-sm text-gray-500">Loading recipe...</div>
                </Card>
            </section>
        )
    }

    if (error || !recipe) {
        return (
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Recipe Detail</div>
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
        <>
            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Recipe: {recipe.output_name || recipe.output_sku} · {recipe.id}</div>
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
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Output Item</dt>
                            <dd className="text-sm text-gray-900">
                                <button
                                    className="text-brand-600 hover:underline text-left"
                                    onClick={() => {
                                        setReferrer({ page: 'recipes', id: recipeId, label: `Recipe ${recipe.id}` })
                                        setHash('items', recipe.output_sku)
                                    }}
                                    type="button"
                                >
                                    {recipe.output_sku}
                                </button>
                                {' - '}{recipe.output_name}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Output Type</dt>
                            <dd className="text-sm text-gray-900">{recipe.output_type || '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Batch Size</dt>
                            <dd className="text-sm text-gray-900">{formatQtyWithUom(recipe.output_qty, recipe.output_uom || 'ea')}</dd>
                        </div>
                        <div>
                            <dt className="text-sm font-medium text-gray-500">Production Time</dt>
                            <dd className="text-sm text-gray-900">{recipe.production_time_hours} hours</dd>
                        </div>
                    </dl>
                </Card>
            </section>

            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Ingredients · {ingredients.length} total</div>
                <Card>
                    {ingredients.length === 0 ? (
                        <div className="text-sm text-gray-500">No ingredients</div>
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
                            onRowClick={(row) => setHash('items', row.ingredient_sku || '')}
                        />
                    )}
                </Card>
            </section>

            <section>
                <div className="text-lg font-semibold text-slate-800 mb-4">Operations · {operations.length} operations, {recipe.production_time_hours} hrs total</div>
                <Card>
                    {operations.length === 0 ? (
                        <div className="text-sm text-gray-500">No operations</div>
                    ) : (
                        <Table
                            rows={sortedOperations}
                            columns={[
                                { key: 'sequence_order', label: '#', sortable: true },
                                { key: 'operation_name', label: 'Operation', sortable: true },
                                { key: 'duration_hours', label: 'Duration (hrs)', sortable: true },
                            ]}
                            sortKey={operationSort?.key}
                            sortDir={operationSort?.dir}
                            onSort={(key) => setOperationSort((prev) => nextOperationSort(prev, key as keyof RecipeOperation))}
                        />
                    )}
                </Card>
            </section>
        </>
    )
}
