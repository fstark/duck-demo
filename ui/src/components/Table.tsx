type Column<T> = { key: keyof T; label: string; render?: (row: T) => React.ReactNode; sortable?: boolean }

export function Table<T extends { [key: string]: any }>({
  rows,
  columns,
  sortKey,
  sortDir,
  onSort,
}: {
  rows: T[]
  columns: Column<T>[]
  sortKey?: keyof T
  sortDir?: 'asc' | 'desc'
  onSort?: (key: keyof T) => void
}) {
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm text-slate-800">
        <thead className="bg-slate-100 text-xs uppercase text-slate-500">
          <tr>
            {columns.map((col) => (
              <th key={String(col.key)} className="px-3 py-2 text-left font-semibold">
                {col.sortable && onSort ? (
                  <button
                    className="flex items-center gap-1 hover:text-slate-700"
                    onClick={() => onSort(col.key)}
                    type="button"
                  >
                    <span>{col.label}</span>
                    {sortKey === col.key ? <span>{sortDir === 'desc' ? '▼' : '▲'}</span> : null}
                  </button>
                ) : (
                  col.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className="border-b border-slate-100">
              {columns.map((col) => (
                <td key={String(col.key)} className="px-3 py-2">
                  {col.render ? col.render(row) : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
