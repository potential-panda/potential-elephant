import { useState, useEffect } from 'react'
import { getScheduleStatus, getSchedulePlan } from '../api'
import StorageFooter from './StorageFooter'

function Spinner() {
  return (
    <div className="flex items-center gap-2 text-slate-500 py-8">
      <div className="w-4 h-4 border-t-2 border-emerald-400 rounded-full animate-spin" />
      Loading...
    </div>
  )
}

function ErrorMsg({ msg }) {
  return (
    <div className="text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3 text-sm">
      Error: {msg}
    </div>
  )
}

export default function Schedule() {
  const [status, setStatus] = useState(null)
  const [plan, setPlan] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = () => {
    Promise.all([getScheduleStatus(), getSchedulePlan()])
      .then(([s, p]) => {
        setStatus(s)
        setPlan(p)
        setError(null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 30000)
    return () => clearInterval(id)
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  const sortedPlan = [...plan].sort((a, b) => a.time.localeCompare(b.time))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Schedule</h2>
        <span className="text-slate-600 text-xs">Auto-refreshes every 30s</span>
      </div>

      {/* Status card */}
      {status && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <span
              className={[
                'w-2.5 h-2.5 rounded-full shrink-0',
                status.active ? 'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]' : 'bg-slate-600',
              ].join(' ')}
            />
            <span
              className={[
                'font-semibold text-base',
                status.active ? 'text-emerald-400' : 'text-slate-500',
              ].join(' ')}
            >
              {status.active ? 'Active' : 'Inactive'}
            </span>
            {status.state && (
              <span className="text-slate-500 text-sm ml-1">— {status.state}</span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">PID</p>
              <p className="text-slate-300 font-mono text-sm">{status.pid ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Since</p>
              <p className="text-slate-300 font-mono text-sm">{status.since ?? '—'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Today's plan */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Today's Plan
        </h3>
        {sortedPlan.length === 0 ? (
          <p className="text-slate-600 text-sm">No tasks scheduled.</p>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3 w-32">Time</th>
                  <th className="text-left px-4 py-3">Label</th>
                </tr>
              </thead>
              <tbody>
                {sortedPlan.map((item, i) => (
                  <tr
                    key={i}
                    className={[
                      'border-b border-slate-800/60',
                      i === sortedPlan.length - 1 ? 'border-b-0' : '',
                    ].join(' ')}
                  >
                    <td className="px-4 py-2.5 font-mono text-emerald-400">{item.time}</td>
                    <td className="px-4 py-2.5 text-slate-300">{item.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <StorageFooter paths={status?.log_file} />
    </div>
  )
}
