import { useEffect, useMemo, useRef, useState } from 'react'
import { getDetail, getJobV2, recordDecisionV2, startDiveV2 } from '../api'
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

function SectionTitle({ title, subtitle }) {
  return (
    <div className="mb-3">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">{title}</h3>
      {subtitle ? <p className="text-xs text-slate-600 mt-1">{subtitle}</p> : null}
    </div>
  )
}

function Block({ title, subtitle, children, className = '' }) {
  return (
    <section className={['bg-slate-900 border border-slate-800 rounded-lg p-4', className].join(' ')}>
      <SectionTitle title={title} subtitle={subtitle} />
      {children}
    </section>
  )
}

function fmtTs(ts) {
  if (!ts) return '—'
  return String(ts).slice(0, 19).replace('T', ' ')
}

function fmtNum(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return Number.isInteger(n) ? String(n) : n.toFixed(digits)
}

function fmtPrice(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return n.toFixed(3)
}

function fmtPct(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return String(value)
  return `${n.toFixed(1)}%`
}

function normalizeDirection(direction) {
  if (!direction) return 'unknown'
  return String(direction).replace(/_/g, ' ')
}

function directionClass(direction) {
  const d = String(direction || '').toLowerCase()
  if (d.includes('bull')) return 'bg-emerald-950/50 text-emerald-400 border-emerald-800/60'
  if (d.includes('bear')) return 'bg-red-950/50 text-red-400 border-red-800/60'
  if (d.includes('flat') || d.includes('neutral')) return 'bg-slate-900 text-slate-400 border-slate-800'
  return 'bg-slate-900 text-slate-500 border-slate-800'
}

function statusClass(status) {
  const s = String(status || 'unknown').toLowerCase()
  if (s === 'available') return 'bg-emerald-950/50 text-emerald-400 border-emerald-800/60'
  if (s === 'unavailable') return 'bg-red-950/50 text-red-400 border-red-800/60'
  return 'bg-slate-900 text-slate-500 border-slate-800'
}

function textPreview(value, limit = 260) {
  if (!value) return '—'
  const text = String(value).trim()
  if (!text) return '—'
  return text.length > limit ? `${text.slice(0, limit).trimEnd()}...` : text
}

function tickerFromHash() {
  const parts = window.location.hash.slice(1).replace(/^\/+/, '').split('/')
  if (parts[0] !== 'detail' || !parts[1]) return ''
  return decodeURIComponent(parts[1])
}

function getSourceRowMap(sources) {
  return Object.fromEntries((sources || []).map((row) => [row.source_id, row]))
}

function SourceMeta({ source }) {
  if (!source) return null
  const urls = Array.isArray(source.urls) ? source.urls : []
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px]">
      <span className={['inline-flex items-center px-2 py-1 rounded border font-mono', statusClass(source.status)].join(' ')}>
        {source.status || 'unknown'}
      </span>
      {source.checked_at ? (
        <span className="text-slate-600 font-mono">checked {fmtTs(source.checked_at)}</span>
      ) : null}
      {source.last_harvested_at ? (
        <span className="text-slate-600 font-mono">harvested {fmtTs(source.last_harvested_at)}</span>
      ) : null}
      {source.last_row_count !== undefined && source.last_row_count !== null ? (
        <span className="text-slate-600 font-mono">rows {source.last_row_count}</span>
      ) : null}
      {urls.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {urls.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2"
            >
              {url}
            </a>
          ))}
        </div>
      ) : null}
      {source.last_error ? <span className="text-red-400 truncate">{source.last_error}</span> : null}
    </div>
  )
}

function PriceSummary({ price }) {
  const summary = price?.summary || {}
  const items = [
    ['Last close', summary.last_close],
    ['Last date', summary.last_date],
    ['1M', summary['1m']],
    ['3M', summary['3m']],
    ['6M', summary['6m']],
    ['1Y', summary['1y']],
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
      {items.map(([label, value]) => (
        <div key={label} className="bg-slate-950/50 border border-slate-800 rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-600 mb-1">{label}</div>
          <div className="text-slate-200 font-mono text-sm">{typeof value === 'number' ? fmtNum(value) : (value ?? '—')}</div>
        </div>
      ))}
    </div>
  )
}

function ScoreCard({ score }) {
  const supportIds = Array.isArray(score?.supporting_data_ids) ? score.supporting_data_ids : []
  return (
    <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-600 mb-1">Aggregate score</div>
          <div className="flex items-center gap-2">
            <span className={['inline-flex items-center px-2 py-1 rounded border text-[11px] font-mono', directionClass(score?.direction)].join(' ')}>
              {normalizeDirection(score?.direction)}
            </span>
            <span className="text-slate-500 text-xs font-mono">{fmtTs(score?.generated_at)}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-semibold font-mono text-slate-100">{fmtNum(score?.score, 2)}</div>
          <div className="text-xs text-slate-600">confidence {fmtPct(score?.confidence)}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
        <div className="bg-slate-900/80 border border-slate-800 rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-600 mb-1">Signals</div>
          <div className="text-slate-200 font-mono">{score?.signal_count ?? '—'}</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-600 mb-1">Generated</div>
          <div className="text-slate-200 font-mono">{fmtTs(score?.generated_at)}</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-600 mb-1">Supporting IDs</div>
          <div className="text-slate-200 font-mono">{supportIds.length}</div>
        </div>
        <div className="bg-slate-900/80 border border-slate-800 rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-600 mb-1">Ticker</div>
          <TickerLink
            ticker={score?.ticker}
            className="text-slate-200 hover:text-emerald-300 hover:underline font-mono"
          />
        </div>
      </div>

      {supportIds.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {supportIds.map((id) => (
            <span key={id} className="px-2 py-1 rounded border border-slate-800 bg-slate-900 text-[11px] font-mono text-slate-400">
              {id}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function SignalsTable({ signals }) {
  if (!signals || signals.length === 0) {
    return <p className="text-slate-600 text-sm">No analysis signals.</p>
  }

  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-lg overflow-x-auto">
      <table className="w-full min-w-max text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
            <th className="text-left px-3 py-2">Kind</th>
            <th className="text-left px-3 py-2">Direction</th>
            <th className="text-right px-3 py-2">Score</th>
            <th className="text-right px-3 py-2">Confidence</th>
            <th className="text-right px-3 py-2">Weight</th>
            <th className="text-right px-3 py-2">Freshness</th>
            <th className="text-left px-3 py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal, idx) => (
            <tr key={`${signal.data_id || 'signal'}-${idx}`} className="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td className="px-3 py-2 text-slate-200 font-mono whitespace-nowrap">{signal.kind || '—'}</td>
              <td className="px-3 py-2 whitespace-nowrap">
                <span className={['inline-flex px-2 py-1 rounded border font-mono text-[11px]', directionClass(signal.direction)].join(' ')}>
                  {normalizeDirection(signal.direction)}
                </span>
              </td>
              <td className="px-3 py-2 text-right text-slate-200 font-mono">{fmtNum(signal.score, 2)}</td>
              <td className="px-3 py-2 text-right text-slate-400 font-mono">{fmtPct(signal.confidence)}</td>
              <td className="px-3 py-2 text-right text-slate-400 font-mono">{fmtNum(signal.weight, 2)}</td>
              <td className="px-3 py-2 text-right text-slate-400 font-mono">{signal.freshness_days ?? '—'}</td>
              <td className="px-3 py-2 text-slate-300">
                <div className="max-w-[520px]">
                  <div className="text-slate-200">{textPreview(signal.reason, 180)}</div>
                  {signal.evidence && signal.evidence.length > 0 ? (
                    <div className="mt-1 text-[11px] text-slate-600 font-mono">
                      {signal.evidence.map((e, i) => (
                        <span key={i} className="mr-2">
                          {e && typeof e === 'object'
                            ? (e.source || e.label || e.type || `evidence-${i + 1}`)
                            : String(e || `evidence-${i + 1}`)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function OverviewCard({ data }) {
  const available = (data.sources || []).filter((s) => s.status === 'available').length
  const sources = data.sources || []
  return (
    <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-600 mb-1">Ticker</div>
          <div className="flex items-center gap-3">
            <TickerLink
              ticker={data.ticker}
              className="text-2xl font-semibold text-emerald-400 hover:text-emerald-300 hover:underline font-mono"
            />
            <span className="text-xs font-mono text-slate-500">{data.market}</span>
          </div>
          <div className="text-xs text-slate-600 font-mono mt-1">bare {data.bare || '—'}</div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wider text-slate-600 mb-1">Source coverage</div>
          <div className="text-2xl font-semibold font-mono text-slate-100">{available}/{sources.length}</div>
        </div>
      </div>
      <PriceSummary price={data.price} />
    </div>
  )
}

function RawTable({ rows, columns, empty = 'No data available.' }) {
  if (!rows || rows.length === 0) {
    return <p className="text-slate-600 text-sm">{empty}</p>
  }

  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-lg overflow-x-auto">
      <table className="w-full min-w-max text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
            {columns.map((col) => (
              <th key={col.key} className={['px-3 py-2', col.align === 'right' ? 'text-right' : 'text-left'].join(' ')}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/30">
              {columns.map((col) => (
                <td key={col.key} className={['px-3 py-2 text-slate-300 align-top', col.className || '', col.align === 'right' ? 'text-right' : 'text-left'].join(' ')}>
                  {col.render ? col.render(row) : (row[col.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MarkdownBlock({ content }) {
  if (!content) return <p className="text-slate-600 text-sm">No dive content.</p>

  const text = String(content)
  const linkLines = text
    .split('\n')
    .filter((line) => /^\s*-\s+\[.+\]\(.+\)\s*$/.test(line))
    .map((line) => {
      const match = line.match(/^\s*-\s+\[(.+?)\]\((.+?)\)\s*$/)
      return match ? { label: match[1], href: match[2] } : null
    })
    .filter(Boolean)

  const body = text.replace(/\n---\n## Links\n[\s\S]*$/m, '').trim()

  return (
    <div className="space-y-3">
      <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-300 font-mono bg-slate-950/50 border border-slate-800 rounded-lg p-4 max-h-[500px] overflow-auto">
        {body}
      </pre>
      {linkLines.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {linkLines.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 rounded border border-slate-700 bg-slate-900 hover:bg-slate-800 text-xs text-emerald-400 hover:text-emerald-300"
            >
              {link.label}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default function Detail() {
  const [ticker, setTicker] = useState(tickerFromHash)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [diving, setDiving] = useState(false)
  const [diveError, setDiveError] = useState(null)
  const [watching, setWatching] = useState(false)
  const [watchError, setWatchError] = useState(null)
  const [watchMessage, setWatchMessage] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    const onHash = () => {
      const next = tickerFromHash()
      if (next) {
        setTicker(next)
        setInputVal(next)
      }
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    setError(null)
    setData(null)
    setWatchError(null)
    setWatchMessage(null)
    getDetail(ticker)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [ticker])

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])

  const sourceMap = useMemo(() => getSourceRowMap(data?.sources), [data])

  const sourceSections = useMemo(() => {
    if (!data) return []
    return [
      {
        key: 'yahoo_jp_bbs',
        title: 'Yahoo Finance JP BBS',
        subtitle: 'comments and evaluations',
        source: sourceMap.yahoo_jp_bbs,
        body: (
          <div className="space-y-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-600 mb-2">Comments</div>
              <RawTable
                rows={data.comments || []}
                columns={[
                  { key: 'post_datetime', label: 'Post Time' },
                  {
                    key: 'author',
                    label: 'Author',
                    render: (row) => {
                      const author = row.author ? String(row.author) : '—'
                      return author === '—' ? author : author.slice(0, 8)
                    },
                  },
                  { key: 'body', label: 'Body', className: 'max-w-[640px]' },
                ]}
                empty="No Yahoo comments."
              />
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-600 mb-2">Evaluations</div>
              <RawTable
                rows={data.evaluations || []}
                columns={[
                  { key: 'scraped_at', label: 'Scraped' },
                  { key: 'bull_pct', label: 'Bull', align: 'right', render: (row) => (row.bull_pct ?? row.strongest ?? '—') },
                  { key: 'bear_pct', label: 'Bear', align: 'right', render: (row) => (row.bear_pct ?? row.weak ?? '—') },
                  { key: 'neutral_pct', label: 'Neutral', align: 'right', render: (row) => (row.neutral_pct ?? row.both ?? '—') },
                ]}
                empty="No Yahoo evaluations."
              />
            </div>
          </div>
        ),
      },
      {
        key: 'minkabu',
        title: 'Minkabu',
        subtitle: 'analysis, research, pick, analyst consensus',
        source: sourceMap.minkabu,
        body: data.minkabu ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {['analysis', 'research', 'pick', 'analyst_consensus'].map((field) => {
              const value = data.minkabu[field]
              return (
                <div key={field} className="bg-slate-950/50 border border-slate-800 rounded-lg p-3">
                  <div className="text-xs uppercase tracking-wider text-slate-600 mb-2">{field.replace(/_/g, ' ')}</div>
                  <div className="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap break-words max-h-[360px] overflow-auto">
                    {value || '—'}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-slate-600 text-sm">No Minkabu content.</p>
        ),
      },
      {
        key: 'fool_quote_news',
        title: 'Motley Fool Quote News',
        subtitle: 'ticker-scoped quote page articles',
        source: sourceMap.fool_quote_news,
        body: (
          <RawTable
            rows={data.news || []}
            columns={[
              { key: 'published', label: 'Published' },
              {
                key: 'source',
                label: 'Source',
                render: (row) => {
                  let domain = null
                  try {
                    domain = new URL(row.url).hostname.replace(/^www\./, '')
                  } catch {
                    domain = null
                  }
                  return row.source || domain || '—'
                },
              },
              {
                key: 'title',
                label: 'Title',
                className: 'max-w-[640px]',
                render: (row) => (
                  <div className="space-y-1">
                    {row.url ? (
                      <a href={row.url} target="_blank" rel="noreferrer" className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2">
                        {row.title || '—'}
                      </a>
                    ) : (
                      <span>{row.title || '—'}</span>
                    )}
                    {row.summary ? <div className="text-slate-500">{textPreview(row.summary, 300)}</div> : null}
                  </div>
                ),
              },
            ]}
            empty="No Fool news."
          />
        ),
      },
      {
        key: 'tdnet_disclosures',
        title: 'TDnet Disclosures',
        subtitle: 'market-wide JP disclosures',
        source: sourceMap.tdnet_disclosures,
        body: (
          <RawTable
            rows={data.tdnet || []}
            columns={[
              { key: 'date', label: 'Date' },
              { key: 'time', label: 'Time' },
              { key: 'title', label: 'Title', className: 'max-w-[720px]' },
              {
                key: 'url',
                label: 'Link',
                render: (row) => (row.url ? <a className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2" href={row.url} target="_blank" rel="noreferrer">open</a> : '—'),
              },
            ]}
            empty="No TDnet disclosures."
          />
        ),
      },
      {
        key: 'daily_prices',
        title: 'Price History',
        subtitle: 'latest bars and change summary',
        source: sourceMap.daily_prices,
        body: (
          <div className="space-y-4">
            <PriceSummary price={data.price} />
            <RawTable
              rows={data.price?.history || []}
              columns={[
                { key: 'date', label: 'Date' },
                { key: 'open', label: 'Open', align: 'right', render: (row) => fmtPrice(row.open) },
                { key: 'high', label: 'High', align: 'right', render: (row) => fmtPrice(row.high) },
                { key: 'low', label: 'Low', align: 'right', render: (row) => fmtPrice(row.low) },
                { key: 'close', label: 'Close', align: 'right', render: (row) => fmtPrice(row.close) },
                { key: 'volume', label: 'Volume', align: 'right' },
              ]}
              empty="No price history."
            />
          </div>
        ),
      },
    ]
  }, [data, sourceMap])

  const handleDive = () => {
    if (!ticker) return
    setDiving(true)
    setDiveError(null)
    startDiveV2(data?.ticker || ticker)
      .then(({ job_id }) => {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = setInterval(() => {
          getJobV2(job_id)
            .then((job) => {
              if (job.status === 'done') {
                clearInterval(pollRef.current)
                pollRef.current = null
                setDiving(false)
                getDetail(ticker).then(setData).catch((e) => setDiveError(e.message))
              } else if (job.status === 'error') {
                clearInterval(pollRef.current)
                pollRef.current = null
                setDiving(false)
                setDiveError(job.error || 'Dive failed')
              }
            })
            .catch((e) => {
              clearInterval(pollRef.current)
              pollRef.current = null
              setDiving(false)
              setDiveError(e.message)
            })
        }, 2000)
      })
      .catch((e) => {
        setDiving(false)
        setDiveError(e.message)
      })
  }

  const handleWatch = () => {
    if (!ticker || !data) return
    setWatching(true)
    setWatchError(null)
    setWatchMessage(null)

    const score = data.analysis?.score || {}
    const snapshot = {
      last_close: data.price?.summary?.last_close ?? null,
      price_date: data.price?.summary?.last_date ?? null,
      score: score.score ?? null,
      confidence: score.confidence ?? null,
      direction: score.direction ?? null,
      value_chain_id: score.value_chain_id ?? null,
      stage: score.stage ?? null,
    }

    recordDecisionV2({
      ticker: data.ticker || ticker,
      decision: 'watch',
      reason: 'manual watch from detail page',
      snapshot,
      what_would_change: 'keep tracking this ticker from the detail view',
    })
      .then(() => {
        setWatchMessage('Saved to watchlist')
      })
      .catch((e) => {
        setWatchError(e.message)
      })
      .finally(() => {
        setWatching(false)
      })
  }

  if (loading) return <Spinner />
  if (error) return <ErrorMsg msg={error} />

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Detail</h2>
          <p className="text-sm text-slate-600 mt-1">Known ticker view with analysis first and raw source data below.</p>
        </div>
        {data?.ticker ? (
          <div className="text-right">
            <div className="text-xs uppercase tracking-wider text-slate-600">Current</div>
            <TickerLink
              ticker={data.ticker}
              className="text-slate-300 hover:text-emerald-300 hover:underline font-mono"
            />
            <div className="mt-3 flex flex-col items-end gap-2">
              <button
                type="button"
                onClick={handleWatch}
                disabled={watching}
                className="px-4 py-2 rounded border border-sky-700 bg-sky-900/30 hover:bg-sky-900 text-xs text-sky-300 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {watching ? 'Saving...' : 'Save to Watchlist'}
              </button>
              {watchMessage ? <div className="text-xs text-emerald-400">{watchMessage}</div> : null}
              {watchError ? <div className="text-xs text-red-400">{watchError}</div> : null}
            </div>
          </div>
        ) : null}
      </div>

      {!data ? (
        <p className="text-slate-600 text-sm">No ticker selected.</p>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 xl:grid-cols-2">
            <OverviewCard data={data} />
            <Block
              title="Analysis"
              subtitle="latest aggregate score and supporting signals"
            >
              <div className="space-y-4">
                <ScoreCard score={data.analysis?.score} />
                <SignalsTable signals={data.analysis?.signals || []} />
              </div>
            </Block>
          </div>

          <Block title="Dive" subtitle="latest generated summary">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="text-xs text-slate-600">
                Regenerate the current ticker brief from the underlying sources.
              </div>
              <button
                type="button"
                onClick={handleDive}
                disabled={diving}
                className="px-3 py-1.5 rounded border border-emerald-700 bg-emerald-900/40 hover:bg-emerald-900 text-xs text-emerald-300 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {diving ? 'Diving...' : 'Dive'}
              </button>
            </div>
            {diveError ? (
              <div className="mb-3 text-red-400 bg-red-950/30 border border-red-800/50 rounded px-3 py-2 text-xs">
                {diveError}
              </div>
            ) : null}
            <MarkdownBlock content={data.dive?.content} />
          </Block>

          <Block title="Available Sources" subtitle="availability registry and resolved urls">
            <div className="space-y-3">
              {(data.sources || []).map((source) => (
                <div key={source.source_id} className="bg-slate-950/50 border border-slate-800 rounded-lg p-3">
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                    <div>
                      <div className="text-slate-200 font-semibold">{source.name || source.source_id}</div>
                      <div className="text-xs text-slate-600 font-mono">{source.source_id}</div>
                    </div>
                    <span className={['inline-flex items-center px-2 py-1 rounded border text-[11px] font-mono', statusClass(source.status)].join(' ')}>
                      {source.status || 'unknown'}
                    </span>
                  </div>
                  <SourceMeta source={source} />
                </div>
              ))}
            </div>
          </Block>

          <Block title="Raw Data" subtitle="source blocks">
            <div className="space-y-4">
              {sourceSections.map((section) => (
                <div key={section.key} className="bg-slate-950/50 border border-slate-800 rounded-lg p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-200">{section.title}</div>
                      {section.subtitle ? <div className="text-xs text-slate-600 mt-0.5">{section.subtitle}</div> : null}
                    </div>
                    {section.source ? <SourceMeta source={section.source} /> : null}
                  </div>
                  {section.body}
                </div>
              ))}
            </div>
          </Block>

        </div>
      )}
    </div>
  )
}
