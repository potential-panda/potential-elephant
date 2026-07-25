import { useEffect, useMemo, useState } from 'react'
import { getSourceDefinitions, getTickersOverview } from '../api'
import { appHashHref } from '../app-base'
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

function SortIcon({ active, dir }) {
  if (!active) return <span className="ml-1 text-slate-700">↕</span>
  return <span className="ml-1 text-emerald-400">{dir === 'asc' ? '↑' : '↓'}</span>
}

function fmtScraped(ts) {
  if (!ts) return '—'
  return ts.slice(0, 19).replace('T', ' ')
}

const SOURCE_SHORT = {
  daily_prices: 'PRICE',
  yahoo_jp_bbs: 'BBS',
  minkabu: 'MK',
  fool_quote_news: 'FOOL',
  tdnet_disclosures: 'TD',
}

const STATUS_CLASS = {
  available: 'bg-emerald-900/60 text-emerald-400 border-emerald-800/60',
  unavailable: 'bg-red-950/50 text-red-400 border-red-800/50',
  degraded: 'bg-amber-950/50 text-amber-400 border-amber-800/60',
  retired: 'bg-slate-900 text-slate-500 border-slate-800',
  unknown: 'bg-slate-900 text-slate-500 border-slate-800',
}

function sourceCount(row, defs) {
  const sources = row?.sources || {}
  return defs.filter((def) => sources[def.source_id]?.status === 'available').length
}

function SourceBadges({ row, defs }) {
  const sources = row?.sources || {}
  return (
    <div className="flex flex-wrap gap-1.5">
      {defs.map((def) => {
        const source = sources[def.source_id]
        const status = source?.status || 'unknown'
        const urls = source?.urls || []
        const title = [
          def.name,
          `status: ${status}`,
          source?.checked_at ? `checked: ${source.checked_at}` : null,
          urls.length ? `urls:\n${urls.join('\n')}` : null,
        ].filter(Boolean).join('\n')

        return (
          <span
            key={def.source_id}
            title={title}
            className={[
              'inline-flex items-center gap-1 px-2 py-1 rounded border text-[11px] font-mono whitespace-nowrap',
              STATUS_CLASS[status] || STATUS_CLASS.unknown,
            ].join(' ')}
          >
            <span className="font-semibold">{SOURCE_SHORT[def.source_id] || def.source_id}</span>
          </span>
        )
      })}
      {defs.length === 0 && <span className="text-slate-600 text-xs">No sources configured</span>}
    </div>
  )
}

function TickerTable({ items, market, defs }) {
  const [sortCol, setSortCol] = useState(market === 'JP' ? 'rank' : 'ticker')
  const [sortDir, setSortDir] = useState('asc')

  function handleSort(col) {
    if (col === sortCol) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const sorted = useMemo(() => {
    const getValue = (row) => {
      switch (sortCol) {
        case 'rank':
          return row.bbs_rank ?? 9999
        case 'ticker':
          return row.ticker ?? ''
        case 'last_seen':
          return row.last_seen ?? ''
        case 'last_updated':
          return row.last_updated_at ?? ''
        case 'speed': {
          return row.speed_latest ?? -1
        }
        case 'sources':
          return sourceCount(row, defs)
        default:
          return ''
      }
    }
    return [...items].sort((a, b) => {
      const av = getValue(a)
      const bv = getValue(b)
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [items, defs, sortCol, sortDir])

  const cols = market === 'JP'
    ? [
        { id: 'ticker', label: 'Ticker' },
        { id: 'sources', label: 'Sources' },
        { id: 'last_updated', label: 'Last Updated' },
        { id: 'speed', label: 'Speed' },
        { id: 'rank', label: 'Rank' },
        { id: 'last_seen', label: 'Last Seen' },
      ]
    : [
        { id: 'ticker', label: 'Ticker' },
        { id: 'sources', label: 'Sources' },
        { id: 'last_updated', label: 'Last Updated' },
        { id: 'speed', label: 'Speed' },
      ]

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
      <table className="w-full min-w-max text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
            {cols.map((col) => (
              <th
                key={col.id}
                className={[
                  'px-4 py-3 cursor-pointer select-none hover:text-slate-300 whitespace-nowrap',
                  market === 'JP' && (col.id === 'rank' || col.id === 'last_seen') ? 'text-right' : 'text-left',
                ].join(' ')}
                onClick={() => handleSort(col.id)}
              >
                {col.label}
                <SortIcon active={sortCol === col.id} dir={sortDir} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => {
            const available = sourceCount(row, defs)

            return (
              <tr
                key={row.ticker}
                className={[
                  'border-b border-slate-800/60 transition-colors',
                  i % 2 === 0 ? 'bg-transparent' : 'bg-slate-900/40',
                  'hover:bg-slate-800/50',
                ].join(' ')}
              >
                <td className="px-4 py-2.5">
                  <div className="flex flex-col">
                    <a
                      href={appHashHref(`/detail/${encodeURIComponent(row.ticker)}`)}
                      className="text-emerald-400 hover:text-emerald-300 hover:underline font-semibold font-mono"
                    >
                      {row.ticker}
                    </a>
                    <span className="text-[11px] text-slate-500">{row.market}</span>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <div className="space-y-2">
                    <div className="text-slate-300 font-mono text-xs">
                      {available}/{defs.length} available
                    </div>
                    <SourceBadges row={row} defs={defs} />
                  </div>
                </td>
                <td className="px-4 py-2.5 text-slate-400 font-mono text-xs whitespace-nowrap" title={row.last_updated_source || ''}>
                  {fmtScraped(row.last_updated_at)}
                </td>
                <td className="px-4 py-2.5">
                  {row.speed_latest != null ? (
                    <span className="text-slate-300 font-mono text-xs">
                      {row.speed_latest.toFixed(1)}{' '}
                      <span className="text-slate-600">c/h</span>
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                {market === 'JP' && (
                  <td className="px-4 py-2.5 text-right text-slate-400 font-mono text-xs whitespace-nowrap">
                    {row.bbs_rank ?? '—'}
                  </td>
                )}
                {market === 'JP' && (
                  <td className="px-4 py-2.5 text-right text-slate-400 font-mono text-xs whitespace-nowrap">
                    {row.last_seen ?? '—'}
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Tickers() {
  function tabFromHash() {
    const [section, market] = window.location.hash.slice(1).replace(/^\/+/, '').split('/')
    if (section === 'tickers' && market?.toPrimeCase() === 'US') return 'us'
    return 'jp'
  }

  const [tab, setTab] = useState(tabFromHash)
  const [jpItems, setJpItems] = useState([])
  const [usItems, setUsItems] = useState([])
  const [sourceDefs, setSourceDefs] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getTickersOverview(), getSourceDefinitions('ticker')])
      .then(([overview, defs]) => {
        setJpItems(overview.jp_items || [])
        setUsItems(overview.us_items || [])
        setMeta(overview)
        setSourceDefs(defs || [])
        setError(null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const items = tab === 'jp' ? jpItems : usItems
  const market = tab === 'jp' ? 'JP' : 'US'
  const defs = useMemo(() => sourceDefs.filter((d) => d.markets.includes(market)), [sourceDefs, market])

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Tickers</h2>
        <span className="text-slate-500 text-sm">
          {items.length} total · {defs.length} source types · {tab === 'jp' ? 'JP universe' : 'US universe'}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <button
          type="button"
          onClick={() => {
            window.location.hash = '/tickers/JP'
            setTab('jp')
          }}
          className={[
            'px-3 py-1.5 rounded border text-xs uppercase tracking-wider font-semibold',
            tab === 'jp'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-900/20'
              : 'border-slate-800 text-slate-500 bg-slate-900 hover:text-slate-300',
          ].join(' ')}
        >
          JP
        </button>
        <button
          type="button"
          onClick={() => {
            window.location.hash = '/tickers/US'
            setTab('us')
          }}
          className={[
            'px-3 py-1.5 rounded border text-xs uppercase tracking-wider font-semibold',
            tab === 'us'
              ? 'border-emerald-500 text-emerald-400 bg-emerald-900/20'
              : 'border-slate-800 text-slate-500 bg-slate-900 hover:text-slate-300',
          ].join(' ')}
        >
          US
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {defs.map((def) => (
          <div key={def.source_id} className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">{def.name}</p>
            <p className="text-slate-300 text-xs">{def.description || def.source_id}</p>
          </div>
        ))}
      </div>

      {items.length === 0 ? (
        <p className="text-slate-600 text-sm">No tickers available.</p>
      ) : (
        <TickerTable items={items} market={market} defs={defs} />
      )}

      <StorageFooter paths={[meta?.tickers_file, meta?.cache_file].filter(Boolean)} />
    </div>
  )
}
