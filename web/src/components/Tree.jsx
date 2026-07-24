import { useState, useEffect } from 'react'
import { getTree, getPriceChanges } from '../api'
import StorageFooter from './StorageFooter'
import { appHashHref } from '../app-base'

const LAYER_STYLE = {
  source: {
    header: 'text-purple-400 border-purple-900',
    chip: 'bg-purple-900/30 border-purple-700/50 hover:border-purple-400/60',
    laggard: 'bg-purple-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  upper: {
    header: 'text-blue-400 border-blue-900',
    chip: 'bg-blue-900/30 border-blue-700/50 hover:border-blue-400/60',
    laggard: 'bg-blue-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  middle: {
    header: 'text-emerald-400 border-emerald-900',
    chip: 'bg-emerald-900/30 border-emerald-700/50 hover:border-emerald-400/60',
    laggard: 'bg-emerald-900/50 border-amber-600/60 hover:border-amber-400/80',
  },
  lower: {
    header: 'text-amber-400 border-amber-900',
    chip: 'bg-amber-900/30 border-amber-700/50 hover:border-amber-400/60',
    laggard: 'bg-amber-900/50 border-amber-500/70 hover:border-amber-300/90',
  },
}

const LAYER_LABELS = {
  source: 'Source',
  upper: 'Upper Stream',
  middle: 'Middle Stream',
  lower: 'Lower Stream',
}

const PERIODS = ['1y', '6m', '3m', '1m']

// Compute average of a period across nodes that have data
function layerAvg(nodes, prices, period) {
  const vals = nodes.map((n) => prices[n.ticker]?.[period]).filter((v) => v != null)
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

// Color for the "vs layer" delta — amber = laggard (opportunity), slate = leader (already moved)
function vsLayerColor(delta) {
  if (delta == null) return 'text-slate-600'
  if (delta <= -30) return 'text-amber-400'
  if (delta <= -10) return 'text-amber-600'
  if (delta < 10)   return 'text-slate-500'
  return 'text-slate-600'
}

function TickerChip({ node, priceData, avgs, peerAvgs }) {
  const style = LAYER_STYLE[node.layer] || {
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
      href={appHashHref(`/detail/${encodeURIComponent(node.ticker)}`)}
      title={node.causal_edge || node.role || node.name}
      className={[
        'inline-flex flex-col px-3 py-2 rounded border text-xs transition-colors min-w-[132px]',
        chipClass,
      ].join(' ')}
    >
      {/* Ticker + 1y absolute */}
      <div className="flex items-baseline justify-between gap-2 mb-0.5">
        <span className="font-mono font-bold text-slate-100">{node.ticker}</span>
        <PctValue v={p['1y']} />
      </div>

      {/* Company name */}
      {node.name && (
        <div className="text-[10px] text-slate-500 truncate mb-1" title={node.role || node.name}>
          {node.name}
        </div>
      )}

      {/* vs layer — primary signal */}
      <div className={['font-mono text-[11px] font-semibold mb-0.5', vsLayerColor(primaryDelta)].join(' ')}>
        {primaryDelta == null
          ? <span className="text-slate-700">— vs peer</span>
          : <>{primaryDelta >= 0 ? '+' : ''}{primaryDelta.toFixed(1)}% vs {peerDelta1y == null ? 'layer' : 'peer'}</>
        }
      </div>
      {peerDelta1y != null && delta1y != null && (
        <div className={['font-mono text-[10px] mb-1.5', vsLayerColor(delta1y)].join(' ')}>
          {delta1y >= 0 ? '+' : ''}{delta1y.toFixed(1)}% vs layer
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

function LayerSection({ layer, nodes, prices }) {
  const style = LAYER_STYLE[layer] || { header: 'text-slate-400 border-slate-800' }
  const headerColor = style.header.split(' ')[0]

  // Compute per-period averages for this layer
  const avgs = {}
  PERIODS.forEach((p) => { avgs[p] = layerAvg(nodes, prices, p) })

  const groups = nodes.reduce((acc, node) => {
    const key = node.peer_group || 'unassigned'
    if (!acc[key]) acc[key] = []
    acc[key].push(node)
    return acc
  }, {})

  const sortedGroups = Object.entries(groups).sort(([aKey, aNodes], [bKey, bNodes]) => {
    const aAvg = layerAvg(aNodes, prices, '1y')
    const bAvg = layerAvg(bNodes, prices, '1y')
    const aMin = Math.min(...aNodes.map((n) => {
      const base = aNodes.length > 1 ? aAvg : avgs['1y']
      return prices[n.ticker]?.['1y'] != null && base != null ? prices[n.ticker]['1y'] - base : Infinity
    }))
    const bMin = Math.min(...bNodes.map((n) => {
      const base = bNodes.length > 1 ? bAvg : avgs['1y']
      return prices[n.ticker]?.['1y'] != null && base != null ? prices[n.ticker]['1y'] - base : Infinity
    }))
    if (aMin !== bMin) return aMin - bMin
    return groupLabel(aKey).localeCompare(groupLabel(bKey))
  })

  function sortedNodes(groupNodes) {
    const peerAvgs = {}
    PERIODS.forEach((p) => { peerAvgs[p] = layerAvg(groupNodes, prices, p) })
    return [...groupNodes].sort((a, b) => {
      const aBase = groupNodes.length > 1 ? peerAvgs['1y'] : avgs['1y']
      const bBase = groupNodes.length > 1 ? peerAvgs['1y'] : avgs['1y']
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

  const laggardCount = nodes.filter((n) => {
    const groupNodes = groups[n.peer_group || 'unassigned'] || []
    const peerAvg = groupNodes.length > 1 ? layerAvg(groupNodes, prices, '1y') : null
    const base = peerAvg ?? avgs['1y']
    const d = prices[n.ticker]?.['1y'] != null && base != null
      ? prices[n.ticker]['1y'] - base : null
    return d != null && d <= -10
  }).length

  function peerAverages(groupNodes) {
    const result = {}
    PERIODS.forEach((p) => { result[p] = groupNodes.length > 1 ? layerAvg(groupNodes, prices, p) : null })
    return result
  }

  return (
    <div className="mb-8">
      <div className={['flex items-center gap-3 mb-3 pb-2 border-b', style.header].join(' ')}>
        <span className={['text-xs font-semibold uppercase tracking-widest', headerColor].join(' ')}>
          {LAYER_LABELS[layer] || layer}
        </span>
        <span className="text-slate-600 text-xs">{nodes.length} nodes</span>
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
      {nodes.length === 0 ? (
        <p className="text-slate-700 text-xs">—</p>
      ) : (
        <div className="space-y-3">
          {sortedGroups.map(([group, groupNodes]) => {
            const peerAvgs = peerAverages(groupNodes)
            return (
              <div key={group}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[11px] font-mono uppercase text-slate-500">
                    {groupLabel(group)}
                  </span>
                  <span className="text-[10px] text-slate-700">{groupNodes.length} peers</span>
                  {peerAvgs['1y'] != null && (
                    <span className="text-[10px] font-mono text-slate-600">
                      median 1y {peerAvgs['1y'] >= 0 ? '+' : ''}{peerAvgs['1y'].toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {sortedNodes(groupNodes).map((node, i) => (
                    <TickerChip
                      key={i}
                      node={node}
                      priceData={prices[node.ticker]}
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

export default function Tree() {
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeRiver, setActiveRiver] = useState(null)
  const [prices, setPrices] = useState({})
  const [pricesLoading, setPricesLoading] = useState(false)

  useEffect(() => {
    getTree()
      .then((d) => {
        setTree(d)
        if (d.rivers && d.rivers.length > 0) setActiveRiver(d.rivers[0].id)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Fetch prices whenever active river changes
  useEffect(() => {
    if (!tree || !activeRiver) return
    const river = tree.rivers.find((r) => r.id === activeRiver)
    if (!river || !river.nodes.length) return
    const tickers = river.nodes.map((n) => n.ticker)
    setPricesLoading(true)
    getPriceChanges(tickers)
      .then(setPrices)
      .catch(() => setPrices({}))
      .finally(() => setPricesLoading(false))
  }, [activeRiver, tree])

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

  if (!tree) return null

  const layers = tree.layers || ['source', 'upper', 'middle', 'lower']
  const rivers = tree.rivers || []
  const river = rivers.find((r) => r.id === activeRiver) || rivers[0]

  if (rivers.length === 0) return <p className="text-slate-600 text-sm">No rivers configured.</p>

  const nodesByLayer = {}
  layers.forEach((l) => { nodesByLayer[l] = [] })
  ;(river?.nodes || []).forEach((n) => {
    if (nodesByLayer[n.layer]) nodesByLayer[n.layer].push(n)
    else nodesByLayer[n.layer] = [n]
  })

  return (
    <div>
      {/* River tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-800">
        {rivers.map((r) => (
          <button
            key={r.id}
            onClick={() => setActiveRiver(r.id)}
            className={[
              'px-4 py-2 text-xs font-medium rounded-t transition-colors -mb-px border-b-2',
              r.id === activeRiver
                ? 'text-emerald-400 border-emerald-400 bg-slate-900'
                : 'text-slate-500 border-transparent hover:text-slate-300 hover:border-slate-600',
            ].join(' ')}
          >
            {r.name}
          </button>
        ))}
      </div>

      {/* Active river */}
      {river && (
        <div>
          {river.description && (
            <p className="text-slate-500 text-sm mb-6">{river.description}</p>
          )}

          {/* Legend + loading indicator */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-amber-500">■</span>
              <span className="text-slate-600">laggard (≤ −10% vs layer avg) · sorted laggards first</span>
            </div>
            {pricesLoading && (
              <div className="w-3 h-3 border-t-2 border-emerald-500 rounded-full animate-spin" />
            )}
          </div>

          {layers.map((layer) => (
            <LayerSection
              key={layer}
              layer={layer}
              nodes={nodesByLayer[layer] || []}
              prices={prices}
            />
          ))}
        </div>
      )}

      <StorageFooter paths={tree.file} />
    </div>
  )
}
