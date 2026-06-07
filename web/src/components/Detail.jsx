import { useState, useEffect } from 'react'
import { getDetail, getTickers } from '../api'

function Spinner() {
  return (
    <div className="flex items-center gap-2 text-slate-500 py-8">
      <div className="w-4 h-4 border-t-2 border-emerald-400 rounded-full animate-spin" />
      Loading...
    </div>
  )
}

function SectionHeader({ title }) {
  return (
    <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3 mt-8 first:mt-0">
      {title}
    </h3>
  )
}

function Empty({ msg = 'No data available.' }) {
  return <p className="text-slate-600 text-sm">{msg}</p>
}

function stripHtml(str) {
  if (!str) return ''
  return str.replace(/<[^>]*>/g, '').replace(/&[a-z]+;/gi, ' ').replace(/\s+/g, ' ').trim()
}

// ── Dive section ─────────────────────────────────────────────────────────────

function DiveSection({ dive }) {
  if (!dive) return <Empty />
  const sep = dive.content.indexOf('\n---\n## Links\n')
  const body = sep !== -1 ? dive.content.slice(0, sep) : dive.content
  const linksBlock = sep !== -1 ? dive.content.slice(sep + '\n---\n## Links\n'.length) : ''
  const links = linksBlock
    .split('\n')
    .filter((l) => l.startsWith('- ['))
    .map((l) => { const m = l.match(/^- \[(.+?)\]\((.+?)\)$/); return m ? { label: m[1], href: m[2] } : null })
    .filter(Boolean)

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500 font-mono">{dive.date}</p>
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
          {body.trim()}
        </pre>
      </div>
      {links.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg px-4 py-3 flex flex-wrap gap-3">
          {links.map((l) => (
            <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer"
              className="text-xs text-emerald-400 hover:text-emerald-300 underline underline-offset-2">
              {l.label}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Comments section ──────────────────────────────────────────────────────────

function CommentsSection({ comments }) {
  if (!comments) return <Empty />
  const { total, records } = comments
  return (
    <div>
      <p className="text-xs text-slate-500 mb-3">{total.toLocaleString()} total comments · showing latest {records.length}</p>
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
              <th className="text-left px-3 py-2 w-40">DateTime</th>
              <th className="text-left px-3 py-2">Body</th>
              <th className="text-left px-3 py-2 w-28">Author</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r, i) => (
              <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                <td className="px-3 py-2 text-slate-500 font-mono align-top whitespace-nowrap">
                  {r.post_datetime ?? '—'}
                </td>
                <td className="px-3 py-2 text-slate-300 align-top leading-relaxed">{r.body ?? '—'}</td>
                <td className="px-3 py-2 text-slate-500 align-top whitespace-nowrap">{r.author ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Evaluations section ───────────────────────────────────────────────────────

function EvaluationsSection({ evaluations, minkabu }) {
  const hasEvals = evaluations && evaluations.length > 0
  const hasMinkabu = !!minkabu
  if (!hasEvals && !hasMinkabu) return <Empty />

  return (
    <div className="space-y-4">
      {hasEvals && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Yahoo Evaluations</p>
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-3 py-2">Scraped At</th>
                  <th className="text-right px-3 py-2">Bull %</th>
                  <th className="text-right px-3 py-2">Bear %</th>
                  <th className="text-right px-3 py-2">Neutral %</th>
                </tr>
              </thead>
              <tbody>
                {evaluations.map((r, i) => (
                  <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="px-3 py-2 text-slate-400 font-mono">{r.scraped_at ?? '—'}</td>
                    <td className="px-3 py-2 text-emerald-400 text-right font-mono">
                      {r.bull_pct != null ? `${r.bull_pct}%` : (r.strongest != null ? `${(parseFloat(r.strongest||0)+parseFloat(r.strong||0)).toFixed(0)}%` : '—')}
                    </td>
                    <td className="px-3 py-2 text-red-400 text-right font-mono">
                      {r.bear_pct != null ? `${r.bear_pct}%` : (r.weak != null ? `${(parseFloat(r.weak||0)+parseFloat(r.weakest||0)).toFixed(0)}%` : '—')}
                    </td>
                    <td className="px-3 py-2 text-slate-400 text-right font-mono">
                      {r.neutral_pct != null ? `${r.neutral_pct}%` : (r.both != null ? `${parseFloat(r.both||0).toFixed(0)}%` : '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {hasMinkabu && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Minkabu Analyst Consensus</p>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
              {minkabu}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

// ── News section ──────────────────────────────────────────────────────────────

function NewsSection({ news }) {
  if (!news || news.length === 0) return <Empty />
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-slate-500 uppercase tracking-wider">
            <th className="text-left px-3 py-2 w-44">Published</th>
            <th className="text-left px-3 py-2 w-28">Source</th>
            <th className="text-left px-3 py-2">Title</th>
          </tr>
        </thead>
        <tbody>
          {news.map((r, i) => {
            const summary = stripHtml(r.summary)
            const showSummary = summary && summary !== r.title
            let domain = null
            try { domain = new URL(r.url).hostname.replace(/^www\./, '') } catch {}
            return (
              <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                <td className="px-3 py-2 text-slate-500 font-mono align-top whitespace-nowrap">
                  {(r.published || '').slice(0, 16)}
                </td>
                <td className="px-3 py-2 text-slate-400 align-top whitespace-nowrap">
                  {domain ? (
                    <a href={`https://${domain}`} target="_blank" rel="noopener noreferrer"
                      className="hover:text-emerald-400 underline underline-offset-2">{r.source || domain}</a>
                  ) : (r.source || '—')}
                </td>
                <td className="px-3 py-2 align-top">
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noopener noreferrer"
                      className="text-slate-200 font-medium hover:text-emerald-400 underline underline-offset-2">
                      {r.title || '—'}
                    </a>
                  ) : <span className="text-slate-200 font-medium">{r.title || '—'}</span>}
                  {showSummary && <p className="text-slate-500 mt-1 leading-relaxed">{summary}</p>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Links section ─────────────────────────────────────────────────────────────

function LinksSection({ ticker, bare }) {
  const isJP = ticker.endsWith('.T')
  const minkabuHref = isJP
    ? `https://minkabu.jp/stock/${bare}`
    : `https://us.minkabu.jp/stock/${bare}`
  const links = [
    { label: 'Yahoo Finance JP BBS', href: `https://finance.yahoo.co.jp/quote/${ticker}/forum` },
    { label: 'Yahoo Finance JP', href: `https://finance.yahoo.co.jp/quote/${ticker}` },
    { label: isJP ? 'Minkabu' : 'Minkabu US', href: minkabuHref },
    ...(!isJP ? [{ label: 'Yahoo Finance US', href: `https://finance.yahoo.com/quote/${ticker}` }] : []),
    ...(isJP ? [{ label: 'TDnet', href: 'https://www.release.tdnet.info/' }] : []),
  ]
  return (
    <div className="flex flex-wrap gap-3">
      {links.map((l) => (
        <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer"
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs text-emerald-400 hover:text-emerald-300 transition-colors">
          {l.label} ↗
        </a>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

function tickerFromHash() {
  const parts = window.location.hash.slice(1).split('/')
  return parts[1] ? decodeURIComponent(parts[1]) : ''
}

export default function Detail() {
  const [inputVal, setInputVal] = useState(tickerFromHash)
  const [ticker, setTicker] = useState(tickerFromHash)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [knownTickers, setKnownTickers] = useState([])

  // populate autocomplete list
  useEffect(() => {
    getTickers()
      .then((d) => setKnownTickers(d.items.map((t) => t.ticker)))
      .catch(() => {})
  }, [])

  // sync from hash (back/forward navigation)
  useEffect(() => {
    const onHash = () => {
      const t = tickerFromHash()
      if (t) { setTicker(t); setInputVal(t) }
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // fetch data when ticker changes
  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    setError(null)
    setData(null)
    getDetail(ticker)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [ticker])

  const handleSubmit = (e) => {
    e.preventDefault()
    const t = inputVal.trim()
    if (!t) return
    window.location.hash = `detail/${t}`
    setTicker(t)
  }

  return (
    <div>
      {/* Header + search */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-100">
          Detail
          {data && (
            <span className="ml-3 text-emerald-400 font-mono">{data.ticker}</span>
          )}
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 mb-8">
        <div className="relative flex-1 max-w-xs">
          <input
            list="detail-ticker-list"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Ticker (e.g. 9984 or 9984.T)"
            className="w-full bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-600 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50"
          />
          <datalist id="detail-ticker-list">
            {knownTickers.map((t) => <option key={t} value={t} />)}
          </datalist>
        </div>
        <button
          type="submit"
          disabled={loading || !inputVal.trim()}
          className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-md transition-colors"
        >
          Show
        </button>
      </form>

      {loading && <Spinner />}
      {error && (
        <div className="text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3 text-sm">
          Error: {error}
        </div>
      )}

      {data && !loading && (
        <div>
          <SectionHeader title="Deep Dive" />
          <DiveSection dive={data.dive} />

          <SectionHeader title="Yahoo Comments" />
          <CommentsSection comments={data.comments} />

          <SectionHeader title="Evaluations" />
          <EvaluationsSection evaluations={data.evaluations} minkabu={data.minkabu} />

          <SectionHeader title="Recent News" />
          <NewsSection news={data.news} />

          <SectionHeader title="External Links" />
          <LinksSection ticker={data.ticker} bare={data.bare} />
        </div>
      )}
    </div>
  )
}
