import { useState, useEffect } from 'react'
import { getTickers } from '../api'

function Sparkline({ history }) {
  if (!history || history.length === 0) return <span className="text-slate-600">—</span>

  const values = history.map((h) => h.comments_per_hour)
  const max = Math.max(...values, 1)
  const width = 80
  const height = 28
  const step = width / Math.max(values.length - 1, 1)

  const points = values
    .map((v, i) => {
      const x = i * step
      const y = height - (v / max) * (height - 4) - 2
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg width={width} height={height} className="inline-block align-middle">
      <polyline
        points={points}
        fill="none"
        stroke="#34d399"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

function DatasetDots({ datasets }) {
  if (!datasets) return null
  const keys = ['yahoo_comments', 'yahoo_evaluations', 'minkabu_raw_html']
  const labels = { yahoo_comments: 'YC', yahoo_evaluations: 'YE', minkabu_raw_html: 'MK' }
  return (
    <div className="flex gap-1">
      {keys.map((k) => (
        <span
          key={k}
          title={k}
          className={[
            'inline-flex items-center justify-center w-6 h-5 rounded text-xs font-mono',
            datasets[k] ? 'bg-emerald-900/60 text-emerald-400' : 'bg-slate-800 text-slate-600',
          ].join(' ')}
        >
          {labels[k]}
        </span>
      ))}
    </div>
  )
}

function TickerPanel({ ticker, onClose }) {
  const latest =
    ticker.speed_history && ticker.speed_history.length > 0
      ? ticker.speed_history[ticker.speed_history.length - 1].comments_per_hour
      : null

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-100">
            {ticker.ticker}
            {latest != null && (
              <span className="ml-3 text-sm text-emerald-400 font-normal">
                {latest.toFixed(1)} c/h
              </span>
            )}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="mb-4">
          <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Speed history (comments/hr)</p>
          {ticker.speed_history && ticker.speed_history.length > 0 ? (
            <div>
              <div className="mb-3">
                <Sparkline history={ticker.speed_history} />
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {[...ticker.speed_history].reverse().map((h, i) => {
                  const max = Math.max(...ticker.speed_history.map((x) => x.comments_per_hour), 1)
                  const pct = Math.round((h.comments_per_hour / max) * 100)
                  return (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500 w-24 shrink-0">{h.date}</span>
                      <div className="flex-1 bg-slate-800 rounded-full h-1.5">
                        <div
                          className="bg-emerald-500 h-1.5 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-slate-300 w-12 text-right">
                        {h.comments_per_hour.toFixed(1)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <p className="text-slate-600 text-sm">No history available</p>
          )}
        </div>

        <div>
          <p className="text-xs text-slate-500 mb-2 uppercase tracking-wider">Datasets</p>
          <div className="flex gap-2 flex-wrap">
            {ticker.datasets
              ? Object.entries(ticker.datasets).map(([k, v]) => (
                  <span
                    key={k}
                    className={[
                      'px-2 py-1 rounded text-xs',
                      v ? 'bg-emerald-900/60 text-emerald-400' : 'bg-slate-800 text-slate-600',
                    ].join(' ')}
                  >
                    {k}
                  </span>
                ))
              : <span className="text-slate-600 text-sm">—</span>}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Tickers() {
  const [tickers, setTickers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    getTickers()
      .then((data) => setTickers(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  const sorted = [...tickers].sort((a, b) => (a.bbs_rank ?? 9999) - (b.bbs_rank ?? 9999))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Tickers</h2>
        <span className="text-slate-500 text-sm">{tickers.length} total</span>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-3 w-16">Rank</th>
              <th className="text-left px-4 py-3">Ticker</th>
              <th className="text-left px-4 py-3">Last Seen</th>
              <th className="text-left px-4 py-3">Last Scraped</th>
              <th className="text-left px-4 py-3">Speed</th>
              <th className="text-left px-4 py-3">Datasets</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const latestSpeed =
                t.speed_history && t.speed_history.length > 0
                  ? t.speed_history[t.speed_history.length - 1].comments_per_hour
                  : null

              return (
                <tr
                  key={t.ticker}
                  onClick={() => setSelected(t)}
                  className={[
                    'border-b border-slate-800/60 cursor-pointer transition-colors',
                    i % 2 === 0 ? 'bg-transparent' : 'bg-slate-900/40',
                    'hover:bg-slate-800/50',
                  ].join(' ')}
                >
                  <td className="px-4 py-2.5 text-slate-500 font-mono">
                    {t.bbs_rank ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 font-semibold text-emerald-400 font-mono">
                    {t.ticker}
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">
                    {t.last_seen ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">
                    {t.last_scraped_at ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    {latestSpeed != null ? (
                      <span className="text-slate-300 font-mono text-xs">
                        {latestSpeed.toFixed(1)}{' '}
                        <span className="text-slate-600">c/h</span>
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <DatasetDots datasets={t.datasets} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {selected && (
        <TickerPanel ticker={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

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
