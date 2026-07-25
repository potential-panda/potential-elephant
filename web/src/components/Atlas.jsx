import { useState, useEffect } from 'react'
import { getAtlas, getPriceChanges } from '../api'
import StorageFooter from './StorageFooter'
import { appHashHref } from '../app-base'

const STAGE_STYLE = {
  driver: {
    header: 'text-purple-400 border-purple-900',
    chip: 'bg-purple-900/30 border-purple-700/50 hover:border-purple-400/60',
    laggard: 'bg-purple-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  prime: {
    header: 'text-blue-400 border-blue-900',
    chip: 'bg-blue-900/30 border-blue-700/50 hover:border-blue-400/60',
    laggard: 'bg-blue-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  bottleneck: {
    header: 'text-emerald-400 border-emerald-900',
    chip: 'bg-emerald-900/30 border-emerald-700/50 hover:border-emerald-400/60',
    laggard: 'bg-emerald-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  capacity: {
    header: 'text-amber-400 border-amber-900',
    chip: 'bg-amber-900/30 border-amber-700/50 hover:border-amber-400/60',
    laggard: 'bg-amber-900/50 border-amber-500/70 hover:border-amber-300/90',
  },
}

const STAGE_LABELS = {
  driver: 'Driver',
  prime: 'Prime Stream',
  bottleneck: 'Bottleneck Stream',
  capacity: 'Capacity Stream',
}

const PERIODS = ['1y', '6m', '3m', '1m']

// Compute average of a period across companies that have data
function stageAvg(companies, prices, period) {
  const vals = companies.map((n) => prices[n.ticker]?.[period]).filter((v) => v != null)
  if (!vals.length) return null
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

function groupLabel(value) {
  if (!value) return 'Unassigned'
  return value.replace(/_/g, ' ')
}

function pctColor(v) {
  if (v == null) return 'text-slate-600'
  return v >= 0 ? 'text-emerald-400' : 'text-red-400'
}

function PctValue({ v }) {
  if (v == null) return <span className="text-slate-700">—</span>
  return (
    <span className={pctColor(v)}>
      {v >= 0 ? '+' : ''}{v.toFixed(1)}%
    </span>
  )
}

// Color for the "vs stage" delta — amber = laggard (opportunity), slate = leader (already moved)
function vsStageColor(delta) {
  if (delta == null) return 'text-slate-600'
  if (delta <= -30) return 'text-amber-400'
  if (delta <= -10) return 'text-amber-600'
  if (delta < 10)   return 'text-slate-500'
  return 'text-slate-600'
}

function TickerChip({ company, priceData, avgs, peerAvgs }) {
  const style = STAGE_STYLE[company.stage] || {
    chip: 'bg-slate-800/60 border-slate-700 hover:border-slate-500',
    laggard: 'bg-slate-800/80 border-amber-600/60 hover:border-amber-400/80',
  }
  const p = priceData || {}
  const delta1y = (p['1y'] != null && avgs['1y'] != null) ? p['1y'] - avgs['1y'] : null
  const peerDelta1y = (p['1y'] != null && peerAvgs?.['1y'] != null) ? p['1y'] - peerAvgs['1y'] : null
  const primaryDelta = peerDelta1y ?? delta1y
  const isLaggard = primaryDelta != null && primaryDelta <= -10
  const chipClass = isLaggard ? style.laggard : style.chip

  return (
    <a
      href={appHashHref(`/detail/${encodeURIComponent(company.ticker)}`)}
      title={company.causal_edge || company.role || company.name}
      className={[
        'inline-flex flex-col px-3 py-2 rounded border text-xs transition-colors min-w-[132px]',
        chipClass,
      ].join(' ')}
    >
      {/* Ticker + 1y absolute */}
      <div className="flex items-baseline justify-between gap-2 mb-0.5">
        <span className="font-mono font-bold text-slate-100">{company.ticker}</span>
        <PctValue v={p['1y']} />
      </div>

      {/* Company name */}
      {company.name && (
        <div className="text-[10px] text-slate-500 truncate mb-1" title={company.role || company.name}>
          {company.name}
        </div>
      )}

      {/* vs stage — primary signal */}
      <div className={['font-mono text-[11px] font-semibold mb-0.5', vsStageColor(primaryDelta)].join(' ')}>
        {primaryDelta == null
          ? <span className="text-slate-700">— vs peer</span>
          : <>{primaryDelta >= 0 ? '+' : ''}{primaryDelta.toFixed(1)}% vs {peerDelta1y == null ? 'stage' : 'peer'}</>
        }
      </div>
      {peerDelta1y != null && delta1y != null && (
        <div className={['font-mono text-[10px] mb-1.5', vsStageColor(delta1y)].join(' ')}>
          {delta1y >= 0 ? '+' : ''}{delta1y.toFixed(1)}% vs stage
        </div>
      )}

      {/* 4-period grid (smaller, context only) */}
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono text-[10px]">
        {PERIODS.map((period) => (
          <div key={period} className="flex items-center justify-between gap-1">
            <span className="text-slate-700">{period}</span>
            <PctValue v={p[period]} />
          </div>
        ))}
      </div>
    </a>
  )
}

function StageSection({ stage, companies, prices }) {
  const style = STAGE_STYLE[stage] || { header: 'text-slate-400 border-slate-800' }
  const headerColor = style.header.split(' ')[0]

  // Compute per-period averages for this stage
  const avgs = {}
  PERIODS.forEach((p) => { avgs[p] = stageAvg(companies, prices, p) })

  const groups = companies.reduce((acc, company) => {
    const key = company.peer_group || 'unassigned'
    if (!acc[key]) acc[key] = []
    acc[key].push(company)
    return acc
  }, {})

  const sortedGroups = Object.entries(groups).sort(([aKey, aCompanies], [bKey, bCompanies]) => {
    const aAvg = stageAvg(aCompanies, prices, '1y')
    const bAvg = stageAvg(bCompanies, prices, '1y')
    const aMin = Math.min(...aCompanies.map((n) => {
      const base = aCompanies.length > 1 ? aAvg : avgs['1y']
      return prices[n.ticker]?.['1y'] != null && base != null ? prices[n.ticker]['1y'] - base : Infinity
    }))
    const bMin = Math.min(...bCompanies.map((n) => {
      const base = bCompanies.length > 1 ? bAvg : avgs['1y']
      return prices[n.ticker]?.['1y'] != null && base != null ? prices[n.ticker]['1y'] - base : Infinity
    }))
    if (aMin !== bMin) return aMin - bMin
    return groupLabel(aKey).localeCompare(groupLabel(bKey))
  })

  function sortedCompanies(groupCompanies) {
    const peerAvgs = {}
    PERIODS.forEach((p) => { peerAvgs[p] = stageAvg(groupCompanies, prices, p) })
    return [...groupCompanies].sort((a, b) => {
      const aBase = groupCompanies.length > 1 ? peerAvgs['1y'] : avgs['1y']
      const bBase = groupCompanies.length > 1 ? peerAvgs['1y'] : avgs['1y']
      const da = prices[a.ticker]?.['1y'] != null && aBase != null
        ? prices[a.ticker]['1y'] - aBase : null
      const db = prices[b.ticker]?.['1y'] != null && bBase != null
        ? prices[b.ticker]['1y'] - bBase : null
      if (da == null && db == null) return 0
      if (da == null) return 1
      if (db == null) return -1
      return da - db
    })
  }

  const laggardCount = companies.filter((n) => {
    const groupCompanies = groups[n.peer_group || 'unassigned'] || []
    const peerAvg = groupCompanies.length > 1 ? stageAvg(groupCompanies, prices, '1y') : null
    const base = peerAvg ?? avgs['1y']
    const d = prices[n.ticker]?.['1y'] != null && base != null
      ? prices[n.ticker]['1y'] - base : null
    return d != null && d <= -10
  }).length

  function peerAverages(groupCompanies) {
    const result = {}
    PERIODS.forEach((p) => { result[p] = groupCompanies.length > 1 ? stageAvg(groupCompanies, prices, p) : null })
    return result
  }

  return (
    <div className="mb-8">
      <div className={['flex items-center gap-3 mb-3 pb-2 border-b', style.header].join(' ')}>
        <span className={['text-xs font-semibold uppercase tracking-widest', headerColor].join(' ')}>
          {STAGE_LABELS[stage] || stage}
        </span>
        <span className="text-slate-600 text-xs">{companies.length} companies</span>
        {avgs['1y'] != null && (
          <span className="text-slate-600 text-xs font-mono">
            avg 1y: <span className={avgs['1y'] >= 0 ? 'text-emerald-600' : 'text-red-600'}>
              {avgs['1y'] >= 0 ? '+' : ''}{avgs['1y'].toFixed(1)}%
            </span>
          </span>
        )}
        {laggardCount > 0 && (
          <span className="text-amber-500 text-xs font-mono">
            {laggardCount} laggard{laggardCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      {companies.length === 0 ? (
        <p className="text-slate-700 text-xs">—</p>
      ) : (
        <div className="space-y-3">
          {sortedGroups.map(([group, groupCompanies]) => {
            const peerAvgs = peerAverages(groupCompanies)
            return (
              <div key={group}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-mono uppercase text-slate-500">
                    {groupLabel(group)}
                  </span>
                  <span className="text-[10px] text-slate-700">{groupCompanies.length} peers</span>
                  {peerAvgs['1y'] != null && (
                    <span className="text-[10px] font-mono text-slate-600">
                      median 1y {peerAvgs['1y'] >= 0 ? '+' : ''}{peerAvgs['1y'].toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {sortedCompanies(groupCompanies).map((company, i) => (
                    <TickerChip
                      key={i}
                      company={company}
                      priceData={prices[company.ticker]}
                      avgs={avgs}
                      peerAvgs={peerAvgs}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function Atlas() {
  const [atlas, setAtlas] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeValueChain, setActiveValueChain] = useState(null)
  const [prices, setPrices] = useState({})
  const [pricesLoading, setPricesLoading] = useState(false)

  useEffect(() => {
    getAtlas()
      .then((d) => {
        setAtlas(d)
        if (d.value_chains && d.value_chains.length > 0) setActiveValueChain(d.value_chains[0].id)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Fetch prices whenever active value_chain changes
  useEffect(() => {
    if (!atlas || !activeValueChain) return
    const value_chain = atlas.value_chains.find((r) => r.id === activeValueChain)
    if (!value_chain || !value_chain.companies.length) return
    const tickers = value_chain.companies.map((n) => n.ticker)
    setPricesLoading(true)
    getPriceChanges(tickers)
      .then(setPrices)
      .catch(() => setPrices({}))
      .finally(() => setPricesLoading(false))
  }, [activeValueChain, atlas])

  if (loading) return (
    <div className="flex items-center gap-2 text-slate-500 py-8">
      <div className="w-4 h-4 border-t-2 border-emerald-400 rounded-full animate-spin" />
      Loading...
    </div>
  )

  if (error) return (
    <div className="text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3 text-sm">
      Error: {error}
    </div>
  )

  if (!atlas) return null

  const stages = atlas.stages || ['driver', 'prime', 'bottleneck', 'capacity']
  const value_chains = atlas.value_chains || []
  const value_chain = value_chains.find((r) => r.id === activeValueChain) || value_chains[0]

  if (value_chains.length === 0) return <p className="text-slate-600 text-sm">No value_chains configured.</p>

  const companiesByStage = {}
  stages.forEach((l) => { companiesByStage[l] = [] })
  ;(value_chain?.companies || []).forEach((n) => {
    if (companiesByStage[n.stage]) companiesByStage[n.stage].push(n)
    else companiesByStage[n.stage] = [n]
  })

  return (
    <div>
      {/* Value Chain tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-800">
        {value_chains.map((r) => (
          <button
            key={r.id}
            onClick={() => setActiveValueChain(r.id)}
            className={[
              'px-4 py-2 text-xs font-medium rounded-t transition-colors -mb-px border-b-2',
              r.id === activeValueChain
                ? 'text-emerald-400 border-emerald-400 bg-slate-900'
                : 'text-slate-500 border-transparent hover:text-slate-300 hover:border-slate-600',
            ].join(' ')}
          >
            {r.name}
          </button>
        ))}
      </div>

      {/* Active value_chain */}
      {value_chain && (
        <div>
          {value_chain.description && (
            <p className="text-slate-500 text-sm mb-6">{value_chain.description}</p>
          )}

          {/* Legend + loading indicator */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-amber-500">■</span>
              <span className="text-slate-600">laggard (≤ −10% vs stage avg) · sorted laggards first</span>
            </div>
            {pricesLoading && (
              <div className="w-3 h-3 border-t-2 border-emerald-500 rounded-full animate-spin" />
            )}
          </div>

          {stages.map((stage) => (
            <StageSection
              key={stage}
              stage={stage}
              companies={companiesByStage[stage] || []}
              prices={prices}
            />
          ))}
        </div>
      )}

      <StorageFooter paths={atlas.file} />
    </div>
  )
}
