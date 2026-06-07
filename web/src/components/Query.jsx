import { useState, useEffect } from 'react'
import { queryDataset } from '../api'
import StorageFooter from './StorageFooter'

const DATASETS = [
  { value: 'yahoo_comments', label: 'Yahoo Comments', hasTicker: true, hasKeyword: false },
  { value: 'yahoo_evaluations', label: 'Yahoo Evaluations', hasTicker: true, hasKeyword: false },
  { value: 'minkabu_raw_html', label: 'Minkabu Raw HTML', hasTicker: true, hasKeyword: false },
  { value: 'news_headlines', label: 'News Headlines', hasTicker: false, hasKeyword: true },
  { value: 'tdnet_disclosures', label: 'TDnet Disclosures', hasTicker: true, hasKeyword: false },
]

const DATASET_VALUES = new Set(DATASETS.map((d) => d.value))

function datasetFromHash() {
  const sub = window.location.hash.slice(1).split('/')[1]
  return sub && DATASET_VALUES.has(sub) ? sub : 'yahoo_comments'
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

function CommentsTable({ records }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
          <th className="text-left px-3 py-2 w-40">DateTime</th>
          <th className="text-left px-3 py-2">Body</th>
          <th className="text-left px-3 py-2 w-32">Author</th>
        </tr>
      </thead>
      <tbody>
        {records.map((r, i) => (
          <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
            <td className="px-3 py-2 text-slate-500 font-mono align-top whitespace-nowrap">
              {r.post_datetime ?? '—'}
            </td>
            <td className="px-3 py-2 text-slate-300 align-top leading-relaxed">{r.body ?? '—'}</td>
            <td className="px-3 py-2 text-slate-400 align-top whitespace-nowrap">{r.author ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EvaluationsTable({ records }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
          <th className="text-left px-3 py-2">Scraped At</th>
          <th className="text-right px-3 py-2">Bull %</th>
          <th className="text-right px-3 py-2">Bear %</th>
          <th className="text-right px-3 py-2">Neutral %</th>
        </tr>
      </thead>
      <tbody>
        {records.map((r, i) => (
          <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
            <td className="px-3 py-2 text-slate-400 font-mono">{r.scraped_at ?? '—'}</td>
            <td className="px-3 py-2 text-emerald-400 text-right font-mono">
              {r.bull_pct != null ? `${r.bull_pct}%` : '—'}
            </td>
            <td className="px-3 py-2 text-red-400 text-right font-mono">
              {r.bear_pct != null ? `${r.bear_pct}%` : '—'}
            </td>
            <td className="px-3 py-2 text-slate-400 text-right font-mono">
              {r.neutral_pct != null ? `${r.neutral_pct}%` : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function stripHtml(str) {
  if (!str) return ''
  return str.replace(/<[^>]*>/g, '').replace(/&[a-z]+;/gi, ' ').replace(/\s+/g, ' ').trim()
}

function sourceDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

function NewsTable({ records }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
          <th className="text-left px-3 py-2 w-28">Date</th>
          <th className="text-left px-3 py-2 w-32">Source</th>
          <th className="text-left px-3 py-2">Title</th>
        </tr>
      </thead>
      <tbody>
        {records.map((r, i) => {
          const summary = stripHtml(r.summary)
          const showSummary = summary && summary !== r.title
          const domain = r.url ? sourceDomain(r.url) : null
          const sourceHref = domain ? `https://${domain}` : null
          return (
            <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td className="px-3 py-2 text-slate-500 font-mono align-top whitespace-nowrap">
                {r.published ? r.published.slice(0, 16) : (r.date ?? '—')}
              </td>
              <td className="px-3 py-2 text-slate-400 align-top whitespace-nowrap">
                {sourceHref ? (
                  <a href={sourceHref} target="_blank" rel="noopener noreferrer"
                    className="hover:text-emerald-400 underline underline-offset-2">
                    {r.source ?? domain}
                  </a>
                ) : (r.source ?? '—')}
              </td>
              <td className="px-3 py-2 align-top">
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noopener noreferrer"
                    className="text-slate-200 font-medium hover:text-emerald-400 underline underline-offset-2">
                    {r.title ?? '—'}
                  </a>
                ) : (
                  <span className="text-slate-200 font-medium">{r.title ?? '—'}</span>
                )}
                {showSummary && (
                  <p className="text-slate-500 mt-1 leading-relaxed">{summary}</p>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function GenericTable({ records }) {
  if (!records || records.length === 0) return null
  const keys = Object.keys(records[0])
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-slate-800 text-slate-500 text-xs uppercase tracking-wider">
          {keys.map((k) => (
            <th key={k} className="text-left px-3 py-2">{k}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {records.map((r, i) => (
          <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
            {keys.map((k) => (
              <td key={k} className="px-3 py-2 text-slate-300 align-top max-w-xs truncate">
                {r[k] != null ? String(r[k]) : '—'}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ResultsTable({ dataset, records }) {
  if (!records || records.length === 0) {
    return <p className="text-slate-600 text-sm py-4">No results.</p>
  }

  const tableMap = {
    yahoo_comments: CommentsTable,
    news_headlines: NewsTable,
    yahoo_evaluations: EvaluationsTable,
  }
  const Table = tableMap[dataset] || GenericTable

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
      <Table records={records} />
    </div>
  )
}

export default function Query() {
  const [dataset, setDataset] = useState(datasetFromHash)
  const [ticker, setTicker] = useState('')
  const [keyword, setKeyword] = useState('')
  const [limit, setLimit] = useState(50)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [results, setResults] = useState(null)
  const [queried, setQueried] = useState(null)
  const [dataDir, setDataDir] = useState(null)

  useEffect(() => {
    const onHashChange = () => setDataset(datasetFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleDatasetChange = (value) => {
    window.location.hash = `query/${value}`
    setDataset(value)
    setResults(null)
  }

  const selectedDataset = DATASETS.find((d) => d.value === dataset)

  const handleSubmit = (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResults(null)
    const params = { dataset, limit }
    if (selectedDataset.hasTicker && ticker.trim()) params.ticker = ticker.trim()
    if (selectedDataset.hasKeyword && keyword.trim()) params.keyword = keyword.trim()

    queryDataset(params)
      .then((data) => {
        setResults(data.items)
        setQueried(dataset)
        setDataDir(data.data_dir ?? null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-slate-100 mb-4">Query</h2>

      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-lg p-4 mb-6">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Dataset selector */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 uppercase tracking-wider">Dataset</label>
            <select
              value={dataset}
              onChange={(e) => handleDatasetChange(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50"
            >
              {DATASETS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>

          {/* Ticker input */}
          {selectedDataset.hasTicker && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-500 uppercase tracking-wider">Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="e.g. 9984"
                className="bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-600 rounded-md px-3 py-2 text-sm font-mono w-36 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50"
              />
            </div>
          )}

          {/* Keyword input */}
          {selectedDataset.hasKeyword && (
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-500 uppercase tracking-wider">Keyword</label>
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="Search keyword..."
                className="bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-600 rounded-md px-3 py-2 text-sm w-48 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50"
              />
            </div>
          )}

          {/* Limit slider */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-500 uppercase tracking-wider">
              Limit: <span className="text-slate-300">{limit}</span>
            </label>
            <input
              type="range"
              min="10"
              max="200"
              step="10"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-32 accent-emerald-500 mt-1.5"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-md transition-colors self-end"
          >
            {loading && (
              <div className="w-3 h-3 border-t-2 border-white/70 rounded-full animate-spin" />
            )}
            {loading ? 'Querying...' : 'Submit'}
          </button>
        </div>
      </form>

      {error && <div className="mb-4"><ErrorMsg msg={error} /></div>}

      {loading && <Spinner />}

      {results && !loading && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500 uppercase tracking-wider">
              Results
            </span>
            <span className="text-xs text-slate-600">{results.length} rows</span>
          </div>
          <ResultsTable dataset={queried} records={results} />
        </div>
      )}

      <StorageFooter paths={dataDir} />
    </div>
  )
}
