import { ReactNode } from 'react'

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-slate-900 text-slate-100 p-4 space-y-4">
        <div className="font-semibold text-lg">Duck Demo</div>
        <nav className="space-y-2 text-sm">
          <a className="block px-2 py-1 rounded hover:bg-slate-800" href="#customers">Customers</a>
          <a className="block px-2 py-1 rounded hover:bg-slate-800" href="#items">Items</a>
          <a className="block px-2 py-1 rounded hover:bg-slate-800" href="#orders">Sales Orders</a>
          <a className="block px-2 py-1 rounded hover:bg-slate-800" href="#shipments">Shipments</a>
          <a className="block px-2 py-1 rounded hover:bg-slate-800" href="#quotes">Quotes</a>
        </nav>
      </aside>
      <main className="flex-1 p-6 space-y-6 bg-slate-50">{children}</main>
    </div>
  )
}
