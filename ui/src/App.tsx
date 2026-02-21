import { useEffect, useState } from 'react'
import './index.css'
import { Layout } from './components/Layout'
import { Card } from './components/Card'
import { Table } from './components/Table'
import { Badge } from './components/Badge'
import { api } from './api'
import { Customer, Item, SalesOrder, SalesOrderDetail, StockSummary, Shipment, ProductionOrder, Email, Invoice, Quote } from './types'
import { NavigationProvider, useNavigation } from './contexts/NavigationContext'
import { Quantity } from './utils/quantity.tsx'
import { formatCurrency } from './utils/currency'
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
import { EmailsListPage } from './pages/EmailsListPage'
import { EmailDetailPage } from './pages/EmailDetailPage'
import { InvoicesListPage } from './pages/InvoicesListPage'
import { InvoiceDetailPage } from './pages/InvoiceDetailPage'
import QuotesListPage from './pages/QuotesListPage'
import QuoteDetailPage from './pages/QuoteDetailPage'

type SortDir = 'asc' | 'desc'
type SortState<T> = { key: keyof T; dir: SortDir }

type ViewPage = 'home' | 'customers' | 'items' | 'stock' | 'orders' | 'shipments' | 'production' | 'suppliers' | 'recipes' | 'purchase-orders' | 'emails' | 'invoices' | 'quotes'
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
  const allowed: ViewPage[] = ['home', 'customers', 'items', 'stock', 'orders', 'shipments', 'production', 'suppliers', 'recipes', 'purchase-orders', 'emails', 'invoices', 'quotes']
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
  const [draftsCount, setDraftsCount] = useState(0)
  const [invoicesCount, setInvoicesCount] = useState(0)
  const [invoicesOutstanding, setInvoicesOutstanding] = useState(0)
  const [quotesCount, setQuotesCount] = useState(0)
  const [quotesPending, setQuotesPending] = useState(0)
  const [totalQuotesAmount, setTotalQuotesAmount] = useState(0)
  const [view, setView] = useState<ViewState>(() => parseHash())
  const [apiError, setApiError] = useState<string | null>(null)
  const [spotlight, setSpotlight] = useState<{
    customers?: { label: string; sublabel: string; href: string }[]
    quotes?: { label: string; sublabel: string; href: string }[]
    sales_orders?: { label: string; sublabel: string; href: string }[]
    shipments?: { label: string; sublabel: string; href: string }[]
    invoices?: { label: string; sublabel: string; href: string }[]
    emails?: { label: string; sublabel: string; href: string }[]
    stock?: { label: string; sublabel: string; href: string }[]
    production_orders?: { label: string; sublabel: string; href: string }[]
    purchase_orders?: { label: string; sublabel: string; href: string }[]
  }>({})

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
    api.emails({ status: 'draft' }).then((res) => setDraftsCount(res.emails?.length || 0)).catch(handleApiError)
    api.invoices().then((res) => {
      setInvoicesCount(res.invoices?.length || 0)
      const outstanding = res.invoices?.filter(i => i.status === 'issued' || i.status === 'overdue').length || 0
      setInvoicesOutstanding(outstanding)
    }).catch(handleApiError)
    api.quotes().then((res) => {
      setQuotesCount(res.quotes?.length || 0)
      const pending = res.quotes?.filter(q => q.status === 'draft' || q.status === 'sent').length || 0
      setQuotesPending(pending)
      const total = res.quotes?.reduce((sum, q) => sum + (q.total || 0), 0) || 0
      setTotalQuotesAmount(total)
    }).catch(handleApiError)
    api.spotlight().then(setSpotlight).catch(handleApiError)
  }, [])

  useEffect(() => {
    const handler = () => setView(parseHash())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const navGroups = [
    {
      label: 'Sales & CRM',
      items: [
        { page: 'customers' as ViewPage, label: 'Customers' },
        { page: 'quotes' as ViewPage, label: 'Quotes' },
        { page: 'orders' as ViewPage, label: 'Orders' },
        { page: 'shipments' as ViewPage, label: 'Shipments' },
        { page: 'invoices' as ViewPage, label: 'Invoices' },
        { page: 'emails' as ViewPage, label: 'Emails' },
      ],
    },
    {
      label: 'Catalog',
      items: [
        { page: 'items' as ViewPage, label: 'Items' },
        { page: 'stock' as ViewPage, label: 'Stock' },
        { page: 'recipes' as ViewPage, label: 'Recipes' },
      ],
    },
    {
      label: 'Supply Chain',
      items: [
        { page: 'production' as ViewPage, label: 'Production' },
        { page: 'suppliers' as ViewPage, label: 'Suppliers' },
        { page: 'purchase-orders' as ViewPage, label: 'Purchases' },
      ],
    },
  ]

  const Nav = () => {
    const isGroupActive = (group: typeof navGroups[0]) =>
      group.items.some((item) => view.page === item.page)

    return (
      <div className="flex items-center gap-2 text-sm text-slate-700">
        <button
          className={`px-3 py-1.5 rounded ${view.page === 'home' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
          onClick={() => {
            clearListContext()
            setHash('home')
          }}
          type="button"
        >
          Overview
        </button>
        {navGroups.map((group) => (
          <div key={group.label} className="relative group">
            <button
              className={`px-3 py-1.5 rounded flex items-center gap-1 ${isGroupActive(group)
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              type="button"
            >
              {group.label}
              <svg className="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div className="absolute left-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[160px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              {group.items.map((link) => (
                <button
                  key={link.page}
                  className={`w-full text-left px-3 py-1.5 ${view.page === link.page
                      ? 'bg-slate-100 text-slate-900 font-medium'
                      : 'text-slate-700 hover:bg-slate-50'
                    }`}
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
          </div>
        ))}
      </div>
    )
  }

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
          <section className="space-y-8">
            {/* Sales & CRM */}
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Sales & CRM</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Card
                  title="Customers"
                  onClick={() => setHash('customers')}
                  spotlight={spotlight.customers}
                >
                  <div className="text-2xl font-semibold"><Quantity value={customersCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">total customers</div>
                </Card>
                <Card
                  title="Quotes"
                  onClick={() => setHash('quotes')}
                  spotlight={spotlight.quotes}
                >
                  <div className="text-2xl font-semibold"><Quantity value={quotesCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">{quotesPending} pending · {formatCurrency(totalQuotesAmount)}</div>
                </Card>
                <Card
                  title="Sales Orders"
                  onClick={() => setHash('orders')}
                  spotlight={spotlight.sales_orders}
                >
                  <div className="text-2xl font-semibold"><Quantity value={ordersCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">orders · {formatCurrency(totalSalesAmount)}</div>
                </Card>
                <Card
                  title="Shipments"
                  onClick={() => setHash('shipments')}
                  spotlight={spotlight.shipments}
                >
                  <div className="text-2xl font-semibold"><Quantity value={shipmentsCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">shipments</div>
                </Card>
                <Card
                  title="Invoices"
                  onClick={() => setHash('invoices')}
                  spotlight={spotlight.invoices}
                >
                  <div className="text-2xl font-semibold"><Quantity value={invoicesCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">{invoicesOutstanding} outstanding</div>
                </Card>
                <Card
                  title="Emails"
                  onClick={() => setHash('emails')}
                  spotlight={spotlight.emails}
                >
                  <div className="text-2xl font-semibold"><Quantity value={draftsCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">draft emails</div>
                </Card>
              </div>
            </div>

            {/* Catalog & Inventory */}
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Catalog & Inventory</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Card title="Items" onClick={() => setHash('items')}>
                  <div className="text-2xl font-semibold"><Quantity value={itemsCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">catalog items</div>
                </Card>
                <Card
                  title="Stock"
                  onClick={() => setHash('stock')}
                  spotlight={spotlight.stock}
                >
                  <div className="text-2xl font-semibold"><Quantity value={stockCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">stock records</div>
                </Card>
                <Card title="Recipes" onClick={() => setHash('recipes')}>
                  <div className="text-2xl font-semibold"><Quantity value={recipesCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">product recipes</div>
                </Card>
              </div>
            </div>

            {/* Production & Supply Chain */}
            <div>
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Production & Supply Chain</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <Card
                  title="Production Orders"
                  onClick={() => setHash('production')}
                  spotlight={spotlight.production_orders}
                >
                  <div className="text-2xl font-semibold"><Quantity value={productionCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600"><Quantity value={totalProductionQty} className="font-mono inline" /> items planned</div>
                </Card>
                <Card title="Suppliers" onClick={() => setHash('suppliers')}>
                  <div className="text-2xl font-semibold"><Quantity value={suppliersCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">suppliers</div>
                </Card>
                <Card
                  title="Purchase Orders"
                  onClick={() => setHash('purchase-orders')}
                  spotlight={spotlight.purchase_orders}
                >
                  <div className="text-2xl font-semibold"><Quantity value={activePurchasesCount} className="text-left block" /></div>
                  <div className="text-sm text-slate-600">active orders</div>
                </Card>
              </div>
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

        {view.page === 'emails' && !view.id && <EmailsListPage />}
        {view.page === 'emails' && view.id && <EmailDetailPage emailId={view.id} />}

        {view.page === 'invoices' && !view.id && <InvoicesListPage />}
        {view.page === 'invoices' && view.id && <InvoiceDetailPage invoiceId={view.id} />}

        {view.page === 'quotes' && !view.id && <QuotesListPage />}
        {view.page === 'quotes' && view.id && <QuoteDetailPage quoteId={view.id} />}

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
