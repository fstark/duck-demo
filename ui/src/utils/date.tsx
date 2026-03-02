/**
 * Format a datetime string for display in ISO format
 * @param dateStr - ISO datetime string or SQLite datetime format ('YYYY-MM-DD HH:MM:SS')
 * @returns ISO formatted datetime string (YYYY-MM-DD HH:MM:SS) or "—" for null/undefined
 */
export function formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) {
        return '—'
    }
    // Return ISO format (YYYY-MM-DD HH:MM:SS)
    // If it's already in SQLite format, return as-is
    if (dateStr.includes(' ') && !dateStr.includes('T')) {
        return dateStr.split('.')[0] // Remove milliseconds if present
    }
    // If it has a T (ISO format), convert to YYYY-MM-DD HH:MM:SS
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) {
        return '—'
    }
    return date.toISOString().replace('T', ' ').substring(0, 19)
}

/**
 * Format date-only (no time) for display in ISO format
 * @param dateStr - Date string
 * @returns ISO formatted date string (YYYY-MM-DD) or "—" for null/undefined
 */
export function formatDateOnly(dateStr: string | null | undefined): string {
    if (!dateStr) {
        return '—'
    }
    // If it's already YYYY-MM-DD format, return as-is
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr
    }
    const isoTime = dateStr.includes('T') ? dateStr : dateStr.replace(' ', 'T')
    const date = new Date(isoTime)
    if (isNaN(date.getTime())) {
        return '—'
    }
    return date.toISOString().substring(0, 10)
}
