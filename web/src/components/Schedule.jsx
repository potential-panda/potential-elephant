import { useState, useEffect } from 'react'
import { getSourceSchedulerStatus, getSourceSchedulerPlan } from '../api'
import StorageFooter from './StorageFooter'
import TickerLink from './TickerLink'

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
    Promise.all([getSourceSchedulerStatus(), getSourceSchedulerPlan()])
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

  const sortedPlan = [...plan].sort((a, b) => {
    const at = a.scheduled_at || a.time || ''
    const bt = b.scheduled_at || b.time || ''
    return at.localeCompare(bt)
  })
  const nextTasks = status?.next_tasks || []
  const metrics = [
    { label: 'Planned', value: status?.planned_tasks ?? '—' },
    { label: 'Submitted', value: status?.submitted ?? '—' },
    { label: 'Completed', value: status?.completed ?? '—' },
    { label: 'Failed', value: status?.failed ?? '—' },
    { label: 'Avail OK', value: status?.availability_completed ?? '—' },
    { label: 'Avail Fail', value: status?.availability_failed ?? '—' },
    { label: 'Analysis OK', value: status?.analysis_completed ?? '—' },
    { label: 'Analysis Fail', value: status?.analysis_failed ?? '—' },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Source Scheduler</h2>
        <span className="text-slate-600 text-xs">Auto-refreshes every 30s</span>
      </div>

      {status && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <span
              className={[
                'w-2.5 h-2.5 rounded-full shrink-0',
                status.running ? 'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]' : 'bg-slate-600',
              ].join(' ')}
            />
            <span
              className={[
                'font-semibold text-base',
                status.running ? 'text-emerald-400' : 'text-slate-500',
              ].join(' ')}
            >
              {status.running ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Started</p>
              <p className="text-slate-300 font-mono text-sm">{status.started_at ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Planned</p>
              <p className="text-slate-300 font-mono text-sm">{status.last_planned_at ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Availability</p>
              <p className="text-slate-300 font-mono text-sm">{status.last_availability_check_at ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Analysis</p>
              <p className="text-slate-300 font-mono text-sm">{status.last_analysis_at ?? '—'}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
            {metrics.map((item) => (
              <div key={item.label} className="bg-slate-950/60 border border-slate-800 rounded px-3 py-2">
                <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">{item.label}</p>
                <p className="text-slate-200 font-mono text-sm">{item.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4 mt-5">
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Workers</p>
              <p className="text-slate-300 font-mono text-sm">{status.max_workers ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Next Tasks</p>
              <p className="text-slate-300 font-mono text-sm">{nextTasks.length}</p>
            </div>
          </div>
        </div>
      )}

      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Today's Plan
        </h3>
        {sortedPlan.length === 0 ? (
          <p className="text-slate-600 text-sm">No tasks scheduled.</p>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3 w-36">Time</th>
                  <th className="text-left px-4 py-3 w-28">Source</th>
                  <th className="text-left px-4 py-3 w-28">Ticker</th>
                  <th className="text-left px-4 py-3">URL</th>
                </tr>
              </thead>
              <tbody>
                {sortedPlan.map((item, i) => (
                  <tr
                    key={`${item.source_id}-${item.ticker}-${item.scheduled_at || item.time || i}`}
                    className={[
                      'border-b border-slate-800/60',
                      i === sortedPlan.length - 1 ? 'border-b-0' : '',
                    ].join(' ')}
                  >
                    <td className="px-4 py-2.5 font-mono text-emerald-400">{item.scheduled_at || item.time}</td>
                    <td className="px-4 py-2.5 text-slate-300">{item.source_id || '—'}</td>
                    <td className="px-4 py-2.5 text-slate-300 font-mono">
                      <TickerLink
                        ticker={item.ticker}
                        className="text-emerald-400 hover:text-emerald-300 hover:underline"
                      />
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 font-mono truncate max-w-0">
                      {item.url || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {nextTasks.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
            Upcoming Tasks
          </h3>
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3 w-36">Time</th>
                  <th className="text-left px-4 py-3 w-28">Source</th>
                  <th className="text-left px-4 py-3 w-28">Ticker</th>
                  <th className="text-left px-4 py-3">URL</th>
                </tr>
              </thead>
              <tbody>
                {nextTasks.map((item, i) => (
                  <tr
                    key={`${item.source_id}-${item.ticker}-${item.scheduled_at}-${i}`}
                    className={[
                      'border-b border-slate-800/60',
                      i === nextTasks.length - 1 ? 'border-b-0' : '',
                    ].join(' ')}
                  >
                    <td className="px-4 py-2.5 font-mono text-emerald-400">{item.scheduled_at}</td>
                    <td className="px-4 py-2.5 text-slate-300">{item.source_id}</td>
                    <td className="px-4 py-2.5 text-slate-300 font-mono">
                      <TickerLink
                        ticker={item.ticker}
                        className="text-emerald-400 hover:text-emerald-300 hover:underline"
                      />
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 font-mono truncate max-w-0">
                      {item.url}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <StorageFooter paths={status?.log_file} />
    </div>
  )
}
