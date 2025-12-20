import { ReactNode } from 'react'

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="card p-4 space-y-3">
      {title ? <div className="section-title">{title}</div> : null}
      {children}
    </div>
  )
}
