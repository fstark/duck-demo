/**
 * Format a price value with currency symbol
 * @param amount - The numeric amount to format
 * @param currency - Currency code (default: 'EUR')
 * @returns Formatted price string (e.g., "19 €") or "—" for null/undefined
 */
export function formatPrice(amount: number | null | undefined, currency: string = 'EUR'): string {
  if (amount == null) {
    return '—'
  }
  
  // Map currency codes to symbols
  const symbols: Record<string, string> = {
    EUR: '€',
    USD: '$',
    GBP: '£',
  }
  
  const symbol = symbols[currency] || currency
  return `${amount} ${symbol}`
}
