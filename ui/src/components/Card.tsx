import { ReactNode } from 'react'

type CardProps = {
  title?: string
  children: ReactNode
  onClick?: () => void
}

export function Card({ title, children, onClick }: CardProps) {
  const isClickable = !!onClick
  
  return (
    <div 
      className={`card p-4 space-y-3 ${isClickable ? 'cursor-pointer transition-all hover:shadow-md hover:border-slate-300 hover:-translate-y-0.5' : ''}`}
      onClick={onClick}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      {title ? <div className="section-title">{title}</div> : null}
      {children}
    </div>
  )
}
