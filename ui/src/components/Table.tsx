type Column<T> = { key: keyof T; label: string; render?: (row: T) => React.ReactNode }

export function Table<T extends { [key: string]: any }>({ rows, columns }: { rows: T[]; columns: Column<T>[] }) {
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm text-slate-800">
        <thead className="bg-slate-100 text-xs uppercase text-slate-500">
          <tr>
            {columns.map((col) => (
              <th key={String(col.key)} className="px-3 py-2 text-left font-semibold">
                {col.label}
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
