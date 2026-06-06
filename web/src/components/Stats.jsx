import { useState, useEffect } from 'react'
import { getStats } from '../api'

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

export default function Stats() {
  const [stats, setStats] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getStats()
      .then((d) => setStats(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

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

      {stats.length === 0 ? (
        <p className="text-slate-600 text-sm">No stats available.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((s) => (
            <StatCard key={s.dataset} stat={s} />
          ))}
        </div>
      )}
    </div>
  )
}
