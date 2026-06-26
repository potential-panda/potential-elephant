import { useState, useEffect } from 'react'
import { getTickers } from '../api'
import StorageFooter from './StorageFooter'

function FlagBadge({ value, label }) {
  const cls =
    value === true
      ? 'bg-emerald-900/60 text-emerald-400'
      : value === false
      ? 'bg-red-950/50 text-red-400'
      : 'bg-slate-800 text-slate-600'
  return (
    <span title={label} className={['inline-flex items-center justify-center w-7 h-5 rounded text-xs font-mono', cls].join(' ')}>
      {label}
    </span>
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

function sortVal(t, col) {
  switch (col) {
    case 'rank':         return t.bbs_rank ?? 9999
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

// Shared sortable ticker table. `variant` controls which columns are shown:
// 'jp' shows BBS rank (tickers.txt order); 'us' shows confirmed BBS/Minkabu
// flags (tickers-us.txt).
function TickerTable({ items, variant }) {
  const [sortCol, setSortCol] = useState(variant === 'jp' ? 'rank' : 'ticker')
  const [sortDir, setSortDir] = useState('asc')

  function handleSort(col) {
    if (col === sortCol) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const cols = variant === 'jp'
    ? [
        { id: 'rank',         label: 'Rank' },
        { id: 'ticker',       label: 'Ticker' },
        { id: 'last_seen',    label: 'Last Seen' },
        { id: 'last_scraped', label: 'Last Scraped' },
        { id: 'speed',        label: 'Speed' },
      ]
    : [
        { id: 'ticker',       label: 'Ticker' },
        { id: 'last_scraped', label: 'Last Scraped' },
        { id: 'speed',        label: 'Speed' },
      ]

  const sorted = [...items].sort((a, b) => {
    const av = sortVal(a, sortCol)
    const bv = sortVal(b, sortCol)
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sortDir === 'asc' ? cmp : -cmp
  })

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
            {cols.map((col) => (
              <th
                key={col.id}
                className="text-left px-4 py-3 cursor-pointer select-none hover:text-slate-300 whitespace-nowrap"
                onClick={() => handleSort(col.id)}
              >
                {col.label}
                <SortIcon active={sortCol === col.id} dir={sortDir} />
              </th>
            ))}
            {variant === 'us' && <th className="text-left px-4 py-3">Confirmed</th>}
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
                {variant === 'jp' && (
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">
                    {t.bbs_rank ?? '—'}
                  </td>
                )}
                <td className="px-4 py-2.5 font-semibold font-mono">
                  <a
                    href={`#detail/${t.ticker}`}
                    className="text-emerald-400 hover:text-emerald-300 hover:underline"
                  >
                    {t.ticker}
                  </a>
                </td>
                {variant === 'jp' && (
                  <td className="px-4 py-2.5 text-slate-400 font-mono text-xs">
                    {t.last_seen ?? '—'}
                  </td>
                )}
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
                {variant === 'us' && (
                  <td className="px-4 py-2.5">
                    <div className="flex gap-1">
                      <FlagBadge value={t.us_bbs} label="BBS" />
                      <FlagBadge value={t.us_minkabu} label="MK" />
                    </div>
                  </td>
                )}
                <td className="px-4 py-2.5">
                  <DatasetDots datasets={t.datasets} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Tickers() {
  const [jpItems, setJpItems] = useState([])
  const [usItems, setUsItems] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getTickers()
      .then((data) => {
        setJpItems(data.jp_items)
        setUsItems(data.us_items)
        setMeta(data)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-slate-100">JP Tickers</h2>
        <span className="text-slate-500 text-sm">{jpItems.length} total · from tickers.txt</span>
      </div>
      <TickerTable items={jpItems} variant="jp" />

      <div className="flex items-center justify-between mt-8 mb-2">
        <h2 className="text-lg font-semibold text-slate-100">US Tickers</h2>
        <span className="text-slate-500 text-sm">{usItems.length} total · from tickers-us.txt</span>
      </div>
      {usItems.length === 0 ? (
        <p className="text-slate-600 text-sm">No US ticker has been probed or confirmed yet.</p>
      ) : (
        <TickerTable items={usItems} variant="us" />
      )}

      <StorageFooter paths={[meta?.tickers_file, meta?.cache_file, meta?.tickers_us_file].filter(Boolean)} />
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
