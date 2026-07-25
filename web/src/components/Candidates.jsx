import { useEffect, useMemo, useState } from 'react'
import { getCandidatesV2 } from '../api'
import TickerLink from './TickerLink'

const MARKET_FILTERS = ['ALL', 'JP', 'US']

const SIGNAL_STYLE = {
  setup: 'bg-emerald-900/30 text-emerald-300 border-emerald-800/60',
  attention: 'bg-sky-900/30 text-sky-300 border-sky-800/60',
  sentiment: 'bg-amber-900/30 text-amber-300 border-amber-800/60',
  catalyst: 'bg-violet-900/30 text-violet-300 border-violet-800/60',
}

function fmtPct(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v.toFixed(digits)}%`
}

function fmtInt(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(0)
}

function fmtDvalue_chain(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(0)
}

function fmtSignedPct(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`
}

function fmtGroup(value) {
  if (!value) return '—'
  return String(value).replace(/_/g, ' ')
}

function scoreClass(score) {
  if (score >= 75) return 'text-emerald-300'
  if (score >= 55) return 'text-sky-300'
  if (score >= 35) return 'text-amber-300'
  return 'text-slate-300'
}

function SignalChip({ signal }) {
  const className = SIGNAL_STYLE[signal] || 'bg-slate-900/60 text-slate-300 border-slate-800/60'
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded border text-[10px] font-mono uppercase tracking-wider ${className}`}>
      {signal}
    </span>
  )
}

export default function Candidates() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [marketFilter, setMarketFilter] = useState('ALL')

  const load = () => {
    setLoading(true)
    setError(null)
    getCandidatesV2()
      .then((data) => {
        if (!Array.isArray(data)) throw new Error('unexpected response format')
        setRows(data)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const visibleRows = useMemo(() => {
    const filtered = marketFilter === 'ALL' ? rows : rows.filter((row) => row.market === marketFilter)
    return [...filtered].sort((a, b) => {
      const ap = Number(a.priority_score ?? a.score ?? 0)
      const bp = Number(b.priority_score ?? b.score ?? 0)
      if (bp !== ap) return bp - ap
      const as = Number(a.score ?? 0)
      const bs = Number(b.score ?? 0)
      if (bs !== as) return bs - as
      const ad = Number(a.d1_value_chain_fit ?? 0)
      const bd = Number(b.d1_value_chain_fit ?? 0)
      if (bd !== ad) return bd - ad
      return String(a.ticker || '').localeCompare(String(b.ticker || ''))
    })
  }, [rows, marketFilter])

  const jpCount = rows.filter((row) => row.market === 'JP').length
  const usCount = rows.filter((row) => row.market === 'US').length

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Candidates</h2>
        <div className="flex items-center gap-2">
          {MARKET_FILTERS.map((filter) => (
            <button
              key={filter}
              type="button"
              onClick={() => setMarketFilter(filter)}
              className={[
                'px-3 py-1.5 rounded border text-xs font-mono uppercase tracking-wider transition-colors',
                marketFilter === filter
                  ? 'border-emerald-500 text-emerald-400 bg-emerald-900/20'
                  : 'border-slate-800 text-slate-500 bg-slate-900 hover:text-slate-300',
              ].join(' ')}
            >
              {filter}
            </button>
          ))}
          <button
            type="button"
            onClick={load}
            className="px-3 py-1.5 rounded border border-slate-800 text-xs font-mono uppercase tracking-wider text-slate-500 bg-slate-900 hover:text-slate-300 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4 text-xs font-mono text-slate-500">
        <span>{rows.length} total</span>
        <span>{jpCount} JP</span>
        <span>{usCount} US</span>
        <span>{visibleRows.length} shown</span>
      </div>

      {loading && <div className="text-slate-500 text-sm">Loading candidates...</div>}
      {error && <div className="text-red-400 text-sm">Error: {error}</div>}

      {!loading && !error && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-500 text-[11px] uppercase tracking-wider">
                <th className="px-3 py-3 text-right whitespace-nowrap">#</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">Ticker</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Priority</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Base</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Setup</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">Peer Group</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Peer Lag</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Attention</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Catalyst</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Bull/Bear</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">Signals</th>
                <th className="px-3 py-3 text-left whitespace-nowrap">Reason</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, idx) => {
                const setup = (row.d1_value_chain_fit ?? 0) + (row.d2_stage_alpha ?? 0) + (row.d3_relative_laggard ?? 0)
                const signals = row.signal_families || []
                const reason = row.priority_reason || row.queue_reason || '—'
                const peerLag = row.peer_group_laggard_gap_1y ?? row.laggard_gap_1y
                const benchmark = row.peer_group_laggard_gap_1y == null ? 'stage' : 'peer'

                return (
                  <tr
                    key={row.ticker}
                    className="border-b border-slate-800/60 hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-500 whitespace-nowrap">
                      {idx + 1}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-col gap-1 min-w-0">
                        <TickerLink
                          ticker={row.ticker}
                          className="font-mono text-sm font-semibold text-emerald-400 hover:text-emerald-300 hover:underline whitespace-nowrap"
                        />
                        <div className="flex items-center gap-2 text-[11px] text-slate-500 whitespace-nowrap overflow-hidden">
                          <span>{row.market}</span>
                          {row.value_chain_name && <span className="truncate">{row.value_chain_name}</span>}
                          {row.stage && <span className="text-slate-600">/{row.stage}</span>}
                        </div>
                      </div>
                    </td>
                    <td className={`px-3 py-3 text-right font-mono text-xs font-semibold whitespace-nowrap ${scoreClass(row.priority_score ?? row.score)}`}>
                      {fmtInt(row.priority_score ?? row.score)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-300 whitespace-nowrap" title="Existing base score">
                      {fmtInt(row.score)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-300 whitespace-nowrap" title="D1 + D2 + D3">
                      {fmtDvalue_chain(setup)}
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-400 max-w-[180px]">
                      <span title={row.causal_edge || row.behind_reason || row.peer_group || ''}>
                        {fmtGroup(row.peer_group)}
                      </span>
                    </td>
                    <td
                      className={[
                        'px-3 py-3 text-right font-mono text-xs whitespace-nowrap',
                        peerLag == null ? 'text-slate-600' : peerLag <= -10 ? 'text-amber-300' : 'text-slate-300',
                      ].join(' ')}
                      title={`${benchmark} benchmark`}
                    >
                      {fmtSignedPct(peerLag)}
                      {peerLag != null && <span className="text-slate-600"> {benchmark}</span>}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-300 whitespace-nowrap" title="D5">
                      {fmtDvalue_chain(row.d5_attention_change)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-300 whitespace-nowrap" title="D4">
                      {fmtDvalue_chain(row.d4_catalyst)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-slate-300 whitespace-nowrap">
                      {row.bull_pct != null || row.bear_pct != null ? (
                        <span>
                          {fmtPct(row.bull_pct)} / {fmtPct(row.bear_pct)}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {signals.length > 0 ? signals.map((signal) => (
                          <SignalChip key={signal} signal={signal} />
                        )) : <span className="text-slate-600 text-xs">—</span>}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-xs text-slate-400 leading-5 max-w-[420px]">
                      <span title={reason}>{reason}</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
