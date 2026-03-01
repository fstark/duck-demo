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
 * Format an integer quantity with UOM-awareness.
 *
 * Conversion rules (mirrors Python utils.format_qty):
 *  - "g"  + value ≥ 1000 → displayed as kg  (2400 → "2.4 kg")
 *  - "ml" + value ≥ 1000 → displayed as L   (1500 → "1.5 L")
 *  - otherwise            → "{value} {uom}"  (12 → "12 ea")
 *  - null / 0             → "—"
 */
export function formatQtyWithUom(value: number | null | undefined, uom?: string): string {
  if (value == null || value === 0) return '—'
  if (uom === 'g' && value >= 1000) {
    const kg = value / 1000
    return `${parseFloat(kg.toFixed(3))} kg`
  }
  if (uom === 'ml' && value >= 1000) {
    const l = value / 1000
    return `${parseFloat(l.toFixed(3))} L`
  }
  const formatted = value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return uom ? `${formatted} ${uom}` : formatted
}

/**
 * Quantity display component with consistent styling.
 * Right-aligned with monospace font.
 * Pass `uom` for UOM-aware human-readable formatting.
 */
export function Quantity({ value, uom, className }: { value: number | null | undefined; uom?: string; className?: string }) {
  return (
    <span className={className || "text-right block font-mono"}>
      {uom != null ? formatQtyWithUom(value, uom) : formatQuantity(value)}
    </span>
  )
}
