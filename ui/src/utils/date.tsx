/**
 * Format a datetime string for display
 * @param dateStr - ISO datetime string or SQLite datetime format ('YYYY-MM-DD HH:MM:SS')
 * @returns Formatted datetime string or "—" for null/undefined
 */
export function formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) {
        return '—'
    }
    // SQLite returns 'YYYY-MM-DD HH:MM:SS', ensure ISO format
    const isoTime = dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T')
    return new Date(isoTime).toLocaleString()
}

/**
 * Format date-only (no time) for display
 * @param dateStr - Date string
 * @returns Formatted date string or "—" for null/undefined
 */
export function formatDateOnly(dateStr: string | null | undefined): string {
    if (!dateStr) {
        return '—'
    }
    const isoTime = dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T')
    return new Date(isoTime).toLocaleDateString()
}
