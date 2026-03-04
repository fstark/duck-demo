type BadgeVariant = 'neutral' | 'success' | 'info' | 'danger' | 'warning'

const variantClasses: Record<BadgeVariant, string> = {
  neutral: 'bg-slate-100 text-slate-700',
  success: 'bg-green-100 text-green-700',
  info: 'bg-blue-100 text-blue-700',
  danger: 'bg-red-100 text-red-700',
  warning: 'bg-amber-100 text-amber-700',
}

export function Badge({ children, variant = 'neutral' }: { children: React.ReactNode; variant?: BadgeVariant }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${variantClasses[variant]}`}>{children}</span>
}
