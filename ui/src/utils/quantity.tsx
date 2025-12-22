/**
 * Format a quantity/count number for display.
 * Shows '—' (long dash) for zero values.
 * Uses space as thousands separator.
 */
export function formatQuantity(value: number | null | undefined): string {
  if (value == null || value === 0) {
    return '—'
  }
  // Manual formatting: space for thousands separator
  return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

/**
 * Quantity display component with consistent styling.
 * Right-aligned with monospace font.
 */
export function Quantity({ value, className }: { value: number | null | undefined; className?: string }) {
  return (
    <span className={className || "text-right block font-mono"}>
      {formatQuantity(value)}
    </span>
  )
}
