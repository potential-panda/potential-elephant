import { useState, useEffect } from 'react'
import { getSourceDefinitions, getSourceRegistry, getSourceRuns, getSourceSchedulerStatus, getStats } from '../api'
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

function latestDateColor(latest) {
  if (!latest) return 'text-slate-600'
  const now = new Date()
  const date = new Date(latest)
  const diffDays = (now - date) / (1000 * 60 * 60 * 24)
  if (diffDays < 2) return 'text-emerald-400'
  if (diffDays < 7) return 'text-amber-400'
  return 'text-red-400'
}

function StatCard({ stat }) {
  const color = latestDateColor(stat.latest)

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
      <h3 className="font-mono font-semibold text-slate-200 text-sm mb-3 truncate" title={stat.dataset}>
        {stat.dataset}
      </h3>

      <div className="grid grid-cols-2 gap-y-3 gap-x-4">
        <div>
          <p className="text-xs text-slate-600 uppercase tracking-wider mb-0.5">Records</p>
          <p className="text-slate-100 font-mono text-base font-semibold">
            {stat.records != null ? stat.records.toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-600 uppercase tracking-wider mb-0.5">Files</p>
          <p className="text-slate-100 font-mono text-base font-semibold">
            {stat.files != null ? stat.files.toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-600 uppercase tracking-wider mb-0.5">Tickers</p>
          <p className="text-slate-100 font-mono text-base font-semibold">
            {stat.tickers != null ? stat.tickers.toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-600 uppercase tracking-wider mb-0.5">Size</p>
          <p className="text-slate-100 font-mono text-base font-semibold">
            {stat.size_mb != null ? `${stat.size_mb.toFixed(1)} MB` : '—'}
          </p>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-slate-800">
        <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Date Range</p>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-500">{stat.earliest ?? '—'}</span>
          <span className="text-slate-700">→</span>
          <span className={color}>{stat.latest ?? '—'}</span>
        </div>
      </div>
    </div>
  )
}

function fmtTs(ts) {
  if (!ts) return '—'
  return ts.slice(0, 19).replace('T', ' ')
}

function statusColor(status) {
  if (status === 'available') return 'text-emerald-400'
  if (status === 'unavailable') return 'text-red-400'
  if (status === 'degraded') return 'text-amber-400'
  return 'text-slate-500'
}

function SourceStatusTable({ rows, defs }) {
  if (!rows || rows.length === 0) return <p className="text-slate-600 text-sm">No source registry entries.</p>

  const defMap = Object.fromEntries((defs || []).map((d) => [d.source_id, d]))
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
            <th className="text-left px-3 py-2">Source</th>
            <th className="text-right px-3 py-2">Available</th>
            <th className="text-right px-3 py-2">Unavailable</th>
            <th className="text-right px-3 py-2">Unknown</th>
            <th className="text-right px-3 py-2">Tickers</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const def = defMap[row.source_id]
            return (
              <tr key={row.source_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                <td className="px-3 py-2">
                  <div className="font-semibold text-slate-200">{def?.name || row.source_id}</div>
                  <div className="text-[11px] text-slate-600">{row.source_id}</div>
                </td>
                <td className="px-3 py-2 text-right text-emerald-400 font-mono">{row.available}</td>
                <td className="px-3 py-2 text-right text-red-400 font-mono">{row.unavailable}</td>
                <td className="px-3 py-2 text-right text-slate-500 font-mono">{row.unknown}</td>
                <td className="px-3 py-2 text-right text-slate-300 font-mono">{row.tickers}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function SourceRunTable({ runs }) {
  if (!runs || runs.length === 0) return <p className="text-slate-600 text-sm">No recent runs.</p>

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
            <th className="text-left px-3 py-2 w-40">Finished</th>
            <th className="text-left px-3 py-2 w-24">Kind</th>
            <th className="text-left px-3 py-2 w-28">Source</th>
            <th className="text-left px-3 py-2 w-24">Ticker</th>
            <th className="text-left px-3 py-2 w-20">Status</th>
            <th className="text-right px-3 py-2 w-16">Rows</th>
            <th className="text-left px-3 py-2">Error</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.run_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td className="px-3 py-2 text-slate-400 font-mono whitespace-nowrap">{fmtTs(run.finished_at)}</td>
              <td className="px-3 py-2 text-slate-300">{run.kind || '—'}</td>
              <td className="px-3 py-2 text-slate-300">{run.source_id || '—'}</td>
              <td className="px-3 py-2 text-slate-300 font-mono">
                {run.ticker ? (
                  <TickerLink
                    ticker={run.ticker}
                    className="text-emerald-400 hover:text-emerald-300 hover:underline"
                  />
                ) : (
                  'market'
                )}
              </td>
              <td className={['px-3 py-2 font-mono', statusColor(run.status)].join(' ')}>{run.status || '—'}</td>
              <td className="px-3 py-2 text-right text-slate-300 font-mono">{run.row_count ?? 0}</td>
              <td className="px-3 py-2 text-slate-500 truncate max-w-0">{run.error || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Stats() {
  const [stats, setStats] = useState([])
  const [sourceStatus, setSourceStatus] = useState(null)
  const [sourceRuns, setSourceRuns] = useState([])
  const [sourceDefs, setSourceDefs] = useState([])
  const [sourceRegistry, setSourceRegistry] = useState(null)
  const [dataDir, setDataDir] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refresh = () => {
    Promise.all([
      getStats(),
      getSourceSchedulerStatus(),
      getSourceRuns(30),
      getSourceDefinitions('ticker'),
      getSourceRegistry(),
    ])
      .then(([d, scheduler, runs, defs, registry]) => {
        setStats(d.items)
        setDataDir(d.data_dir)
        setSourceStatus(scheduler)
        setSourceRuns(runs)
        setSourceDefs(defs)
        setSourceRegistry(registry)
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

  const registryRows = sourceRegistry
    ? Object.entries(
        Object.values(sourceRegistry).reduce((acc, record) => {
          const sources = record.sources || {}
          for (const [sourceId, source] of Object.entries(sources)) {
            if (!acc[sourceId]) {
              acc[sourceId] = { source_id: sourceId, available: 0, unavailable: 0, unknown: 0, tickers: 0 }
            }
            acc[sourceId][source.status || 'unknown'] = (acc[sourceId][source.status || 'unknown'] || 0) + 1
            acc[sourceId].tickers += 1
          }
          return acc
        }, {}),
      )
        .map(([, row]) => row)
        .sort((a, b) => a.source_id.localeCompare(b.source_id))
    : []

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-lg font-semibold text-slate-100">Stats</h2>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-slate-500">&lt; 2 days</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span className="text-slate-500">&lt; 7 days</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-400" />
            <span className="text-slate-500">older</span>
          </span>
        </div>
      </div>

      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">Source Ops</h3>
          <span className="text-slate-600 text-xs">Refreshes every 30s</span>
        </div>

        {sourceStatus && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 mb-4">
            <div className="flex items-center gap-3 mb-4">
              <span
                className={[
                  'w-2.5 h-2.5 rounded-full shrink-0',
                  sourceStatus.running ? 'bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]' : 'bg-slate-600',
                ].join(' ')}
              />
              <span className={['font-semibold text-base', sourceStatus.running ? 'text-emerald-400' : 'text-slate-500'].join(' ')}>
                {sourceStatus.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Availability Checks</p>
                <p className="text-slate-300 font-mono text-sm">{sourceStatus.availability_completed ?? 0} done / {sourceStatus.availability_failed ?? 0} failed</p>
              </div>
              <div>
                <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Last Check</p>
                <p className="text-slate-300 font-mono text-sm">{sourceStatus.last_availability_check_at ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Planned Tasks</p>
                <p className="text-slate-300 font-mono text-sm">{sourceStatus.planned_tasks ?? 0}</p>
              </div>
              <div>
                <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Workers</p>
                <p className="text-slate-300 font-mono text-sm">{sourceStatus.max_workers ?? '—'}</p>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
          <div>
            <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Registry by Source</h4>
            <SourceStatusTable rows={registryRows} defs={sourceDefs} />
          </div>
          <div>
            <h4 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Recent Source Runs</h4>
            <SourceRunTable runs={sourceRuns} />
          </div>
        </div>
      </div>

      {stats.length === 0 ? (
        <p className="text-slate-600 text-sm">No stats available.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((s) => (
            <StatCard key={s.dataset} stat={s} />
          ))}
        </div>
      )}

      <StorageFooter paths={dataDir} />
    </div>
  )
}
