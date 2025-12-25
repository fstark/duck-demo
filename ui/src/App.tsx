import { useEffect, useState } from 'react'
import './index.css'
import { Layout } from './components/Layout'
import { Card } from './components/Card'
import { Table } from './components/Table'
import { Badge } from './components/Badge'
import { api } from './api'
import { Customer, Item, SalesOrder, SalesOrderDetail, StockSummary, Shipment, ProductionOrder } from './types'
import { NavigationProvider, useNavigation } from './contexts/NavigationContext'
import { Quantity } from './utils/quantity.tsx'
import { formatPrice } from './utils/currency'
import { CustomersListPage } from './pages/CustomersListPage'
import { CustomerDetailPage } from './pages/CustomerDetailPage'
import { ItemsListPage } from './pages/ItemsListPage'
import { ItemDetailPage } from './pages/ItemDetailPage'
import { SalesOrdersListPage } from './pages/SalesOrdersListPage'
import { SalesOrderDetailPage } from './pages/SalesOrderDetailPage'
import { ShipmentsListPage } from './pages/ShipmentsListPage'
import { ShipmentDetailPage } from './pages/ShipmentDetailPage'
import { ProductionOrdersListPage } from './pages/ProductionOrdersListPage'
import { ProductionOrderDetailPage } from './pages/ProductionOrderDetailPage'
import { StockListPage } from './pages/StockListPage'
import { StockDetailPage } from './pages/StockDetailPage'
import { SuppliersListPage } from './pages/SuppliersListPage'
import { SupplierDetailPage } from './pages/SupplierDetailPage'
import { RecipesListPage } from './pages/RecipesListPage'
import { RecipeDetailPage } from './pages/RecipeDetailPage'
import { PurchaseOrdersListPage } from './pages/PurchaseOrdersListPage'
import { PurchaseOrderDetailPage } from './pages/PurchaseOrderDetailPage'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

type ViewPage = 'home' | 'customers' | 'items' | 'stock' | 'orders' | 'shipments' | 'production' | 'suppliers' | 'recipes' | 'purchase-orders'
type ViewState = { page: ViewPage; id?: string }

function SectionHeading({ id, title }: { id: string; title: string }) {
  return (
    <div id={id} className="flex items-center justify-between">
      <div className="text-lg font-semibold text-slate-800">{title}</div>
    </div>
  )
}

function parseHash(): ViewState {
  if (typeof window === 'undefined') return { page: 'home' }
  const hash = window.location.hash.replace(/^#/, '')
  const parts = hash.split('/').filter(Boolean)
  const page = (parts[0] as ViewPage) || 'home'
  const id = parts[1] ? decodeURIComponent(parts.slice(1).join('/')) : undefined
  const allowed: ViewPage[] = ['home', 'customers', 'items', 'stock', 'orders', 'shipments', 'production', 'suppliers', 'recipes', 'purchase-orders']
  return { page: allowed.includes(page) ? page : 'home', id }
}

function setHash(page: ViewPage, id?: string) {
  const path = id ? `#/${page}/${encodeURIComponent(id)}` : `#/${page}`
  if (typeof window !== 'undefined') {
    window.location.hash = path
  }
}

function sortRows<T extends Record<string, any>>(rows: T[], state: SortState<T> | null) {
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

function nextSort<T>(prev: SortState<T> | null, key: keyof T, defaultDir: SortDir = 'asc'): SortState<T> {
  if (prev && prev.key === key) {
    return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
  }
  return { key, dir: defaultDir }
}

function AppContent() {
  const [customersCount, setCustomersCount] = useState(0)
  const [itemsCount, setItemsCount] = useState(0)
  const [stockCount, setStockCount] = useState(0)
  const [ordersCount, setOrdersCount] = useState(0)
  const [totalSalesAmount, setTotalSalesAmount] = useState(0)
  const [shipmentsCount, setShipmentsCount] = useState(0)
  const [productionCount, setProductionCount] = useState(0)
  const [totalProductionQty, setTotalProductionQty] = useState(0)
  const [recipesCount, setRecipesCount] = useState(0)
  const [suppliersCount, setSuppliersCount] = useState(0)
  const [activePurchasesCount, setActivePurchasesCount] = useState(0)
  const [view, setView] = useState<ViewState>(() => parseHash())
  const [apiError, setApiError] = useState<string | null>(null)

  const { clearListContext } = useNavigation()

  const handleApiError = (err: unknown) => {
    console.error(err)
    setApiError('API unavailable. Start the backend on http://127.0.0.1:8000 and refresh.')
  }

  useEffect(() => {
    api.customers().then((res) => setCustomersCount(res.customers?.length || 0)).catch(handleApiError)
    api.items(false).then((res) => setItemsCount(res.items?.length || 0)).catch(handleApiError)
    api.stockList().then((res) => setStockCount(res.stock?.length || 0)).catch(handleApiError)
    api.salesOrders().then((res) => {
      setOrdersCount(res.sales_orders?.length || 0)
      const total = res.sales_orders?.reduce((sum, order) => sum + (order.total || 0), 0) || 0
      setTotalSalesAmount(total)
    }).catch(handleApiError)
    api.shipments().then((res) => setShipmentsCount(res.shipments?.length || 0)).catch(handleApiError)
    api.productionOrders().then((res) => {
      setProductionCount(res.production_orders?.length || 0)
      const totalQty = res.production_orders?.reduce((sum, order) => sum + (order.qty_planned || 0), 0) || 0
      setTotalProductionQty(totalQty)
    }).catch(handleApiError)
    api.recipes().then((res) => setRecipesCount(res.recipes?.length || 0)).catch(handleApiError)
    api.suppliers().then((res) => setSuppliersCount(res.suppliers?.length || 0)).catch(handleApiError)
    api.purchaseOrders('ordered').then((res) => setActivePurchasesCount(res.purchase_orders?.length || 0)).catch(handleApiError)
  }, [])

  useEffect(() => {
    const handler = () => setView(parseHash())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const Nav = () => (
    <div className="flex gap-3 text-sm text-slate-700">
      {(
        [
          { page: 'home', label: 'Overview' },
          { page: 'customers', label: 'Customers' },
          { page: 'items', label: 'Items' },
          { page: 'stock', label: 'Stock' },
          { page: 'orders', label: 'Sales Orders' },
          { page: 'shipments', label: 'Shipments' },
          { page: 'production', label: 'Production' },
          { page: 'recipes', label: 'Recipes' },
          { page: 'suppliers', label: 'Suppliers' },
          { page: 'purchase-orders', label: 'Purchases' },
        ] as Array<{ page: ViewPage; label: string }>
      ).map((link) => (
        <button
          key={link.page}
          className={`px-3 py-1 rounded ${view.page === link.page ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          onClick={() => {
            clearListContext()
            setHash(link.page)
          }}
          type="button"
        >
          {link.label}
        </button>
      ))}
    </div>
  )

  return (
    <Layout>
      <div className="space-y-6">
        {apiError ? (
          <div className="flex items-start justify-between gap-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <div>
              <div className="font-semibold">API unavailable</div>
              <div className="text-amber-700">Start the backend on http://127.0.0.1:8000 so the UI can load data.</div>
            </div>
            <button className="text-amber-700 hover:underline" onClick={() => setApiError(null)} type="button">
              Dismiss
            </button>
          </div>
        ) : null}

        <Nav />

        {view.page === 'home' && (
          <section>
            <SectionHeading id="overview" title="Overview" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-2">
              <Card title="Customers">
                <div className="text-2xl font-semibold"><Quantity value={customersCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">total customers</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('customers')} type="button">
                  View customers
                </button>
              </Card>
              <Card title="Items">
                <div className="text-2xl font-semibold"><Quantity value={itemsCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">total items</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('items')} type="button">
                  View items
                </button>
              </Card>
              <Card title="Stock">
                <div className="text-2xl font-semibold"><Quantity value={stockCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">stock records</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('stock')} type="button">
                  View stock
                </button>
              </Card>
              <Card title="Sales orders">
                <div className="text-2xl font-semibold"><Quantity value={ordersCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">orders loaded · {formatPrice(totalSalesAmount)}</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('orders')} type="button">
                  View orders
                </button>
              </Card>
              <Card title="Shipments">
                <div className="text-2xl font-semibold"><Quantity value={shipmentsCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">shipments loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('shipments')} type="button">
                  View shipments
                </button>
              </Card>
              <Card title="Production Orders">
                <div className="text-2xl font-semibold"><Quantity value={productionCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">production orders · <Quantity value={totalProductionQty} className="font-mono inline" /> items</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('production')} type="button">
                  View production
                </button>
              </Card>
              <Card title="Recipes">
                <div className="text-2xl font-semibold"><Quantity value={recipesCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">recipes loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('recipes')} type="button">
                  View recipes
                </button>
              </Card>
              <Card title="Suppliers">
                <div className="text-2xl font-semibold"><Quantity value={suppliersCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">suppliers loaded</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('suppliers')} type="button">
                  View suppliers
                </button>
              </Card>
              <Card title="Purchase Orders">
                <div className="text-2xl font-semibold"><Quantity value={activePurchasesCount} className="text-left block" /></div>
                <div className="text-sm text-slate-600 mb-2">active purchase orders</div>
                <button className="text-brand-600 hover:underline text-sm" onClick={() => setHash('purchase-orders')} type="button">
                  View purchase orders
                </button>
              </Card>
            </div>
          </section>
        )}

        {view.page === 'customers' && !view.id && <CustomersListPage />}
        {view.page === 'customers' && view.id && <CustomerDetailPage customerId={view.id} />}

        {view.page === 'items' && !view.id && <ItemsListPage />}
        {view.page === 'items' && view.id && <ItemDetailPage sku={view.id} />}

        {view.page === 'stock' && !view.id && <StockListPage />}
        {view.page === 'stock' && view.id && <StockDetailPage stockId={view.id} />}

        {view.page === 'orders' && !view.id && <SalesOrdersListPage />}
        {view.page === 'orders' && view.id && <SalesOrderDetailPage orderId={view.id} />}

        {view.page === 'shipments' && !view.id && <ShipmentsListPage />}
        {view.page === 'shipments' && view.id && <ShipmentDetailPage shipmentId={view.id} />}

        {view.page === 'suppliers' && !view.id && <SuppliersListPage />}
        {view.page === 'suppliers' && view.id && <SupplierDetailPage supplierId={view.id} />}

        {view.page === 'recipes' && !view.id && <RecipesListPage />}
        {view.page === 'recipes' && view.id && <RecipeDetailPage recipeId={view.id} />}

        {view.page === 'purchase-orders' && !view.id && <PurchaseOrdersListPage />}
        {view.page === 'purchase-orders' && view.id && <PurchaseOrderDetailPage purchaseOrderId={view.id} />}

        {view.page === 'production' && !view.id && <ProductionOrdersListPage />}
        {view.page === 'production' && view.id && <ProductionOrderDetailPage productionOrderId={view.id} />}

      </div>
    </Layout>
  )
}

export default function App() {
  return (
    <NavigationProvider>
      <AppContent />
    </NavigationProvider>
  )
}
