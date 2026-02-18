import { ReactNode } from 'react'

type SpotlightItem = {
  label: string
  sublabel?: string
  href: string
}

type CardProps = {
  title?: string
  children: ReactNode
  onClick?: () => void
  spotlight?: SpotlightItem[]
}

export function Card({ title, children, onClick, spotlight }: CardProps) {
  const isClickable = !!onClick
  
  return (
    <div 
      className={`card p-4 ${isClickable ? 'cursor-pointer transition-all hover:shadow-md hover:border-slate-300' : ''}`}
      onClick={onClick}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
    >
      {title ? <div className="section-title">{title}</div> : null}
      <div className={spotlight?.length ? 'flex gap-4' : ''}>
        <div className="space-y-1 flex-1 min-w-0">
          {children}
        </div>
        {spotlight?.length ? (
          <div 
            className="grid gap-y-1 text-xs border-l border-slate-200 pl-3"
            style={{ gridTemplateColumns: 'auto auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            {spotlight.map((item, i) => (
              <a
                key={i}
                href={item.href}
                className="contents group"
              >
                <span className="text-right font-medium text-slate-600 group-hover:text-slate-900 group-hover:underline truncate pr-2">
                  {item.label}
                </span>
                <span className="text-left text-slate-400 group-hover:text-slate-500 whitespace-nowrap">
                  {item.sublabel}
                </span>
              </a>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
