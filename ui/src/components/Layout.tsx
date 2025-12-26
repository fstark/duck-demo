import { ReactNode, useEffect, useState } from 'react'
import { api } from '../api'

export function Layout({ children }: { children: ReactNode }) {
  const [simTime, setSimTime] = useState<string | null>(null)

  useEffect(() => {
    api.simulationTime()
      .then((res: any) => setSimTime(res.current_time))
      .catch(() => setSimTime(null))
  }, [])

  const formatSimTime = (timeStr: string) => {
    // SQLite returns datetime as 'YYYY-MM-DD HH:MM:SS', ensure it's ISO format
    const isoTime = timeStr.replace(' ', 'T')
    return new Date(isoTime).toLocaleString()
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {simTime && (
        <div className="bg-slate-800 text-white px-6 py-2 text-sm">
          <div className="mx-auto max-w-6xl">
            Simulation Time: <span className="font-mono">{formatSimTime(simTime)}</span>
          </div>
        </div>
      )}
      <main className="mx-auto max-w-6xl p-6 space-y-6">{children}</main>
    </div>
  )
}
