import { useState, useEffect } from 'react'
import { getTickers } from '../api'
import StorageFooter from './StorageFooter'

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

function fmtScraped(ts) {
  if (!ts) return '—'
  // ISO string: "2026-06-07T18:58:04.851260" → "2026-06-07 18:58:04"
  return ts.slice(0, 19).replace('T', ' ')
}

function SortIcon({ active, dir }) {
  if (!active) return <span className="ml-1 text-slate-700">↕</span>
  return <span className="ml-1 text-emerald-400">{dir === 'asc' ? '↑' : '↓'}</span>
}

const COLS = [
  { id: 'bbs_rank',      label: 'Rank' },
  { id: 'ticker',        label: 'Ticker' },
  { id: 'last_seen',     label: 'Last Seen' },
  { id: 'last_scraped',  label: 'Last Scraped' },
  { id: 'speed',         label: 'Speed' },
]

function sortVal(t, col) {
  switch (col) {
    case 'bbs_rank':     return t.bbs_rank ?? 9999
    case 'ticker':       return t.ticker ?? ''
    case 'last_seen':    return t.last_seen ?? ''
    case 'last_scraped': return t.last_scraped_at ?? ''
    case 'speed': {
      const h = t.speed_history
      return h && h.length > 0 ? h[h.length - 1].comments_per_hour : -1
    }
    default: return ''
  }
}

export default function Tickers() {
  const [tickers, setTickers] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortCol, setSortCol] = useState('bbs_rank')
  const [sortDir, setSortDir] = useState('asc')

  useEffect(() => {
    getTickers()
      .then((data) => { setTickers(data.items); setMeta(data) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  function handleSort(col) {
    if (col === sortCol) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const sorted = [...tickers].sort((a, b) => {
    const av = sortVal(a, sortCol)
    const bv = sortVal(b, sortCol)
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sortDir === 'asc' ? cmp : -cmp
  })

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
              {COLS.map((col) => (
                <th
                  key={col.id}
                  className="text-left px-4 py-3 cursor-pointer select-none hover:text-slate-300 whitespace-nowrap"
                  onClick={() => handleSort(col.id)}
                >
                  {col.label}
                  <SortIcon active={sortCol === col.id} dir={sortDir} />
                </th>
              ))}
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
                  className={[
                    'border-b border-slate-800/60 transition-colors',
                    i % 2 === 0 ? 'bg-transparent' : 'bg-slate-900/40',
                    'hover:bg-slate-800/50',
                  ].join(' ')}
                >
                  <td className="px-4 py-2.5 text-slate-500 font-mono">
                    {t.bbs_rank ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 font-semibold font-mono">
                    <a
                      href={`#detail/${t.ticker}`}
                      className="text-emerald-400 hover:text-emerald-300 hover:underline"
                    >
                      {t.ticker}
                    </a>
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">
                    {t.last_seen ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs whitespace-nowrap">
                    {fmtScraped(t.last_scraped_at)}
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

      <StorageFooter paths={[meta?.tickers_file, meta?.cache_file].filter(Boolean)} />
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
