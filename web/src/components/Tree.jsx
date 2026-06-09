import { useState, useEffect } from 'react'
import { getTree, getPriceChanges } from '../api'
import StorageFooter from './StorageFooter'

const LAYER_STYLE = {
  source: {
    header: 'text-purple-400 border-purple-900',
    chip: 'bg-purple-900/30 border-purple-700/50 hover:border-purple-400/60',
  },
  upper: {
    header: 'text-blue-400 border-blue-900',
    chip: 'bg-blue-900/30 border-blue-700/50 hover:border-blue-400/60',
  },
  middle: {
    header: 'text-emerald-400 border-emerald-900',
    chip: 'bg-emerald-900/30 border-emerald-700/50 hover:border-emerald-400/60',
  },
  lower: {
    header: 'text-amber-400 border-amber-900',
    chip: 'bg-amber-900/30 border-amber-700/50 hover:border-amber-400/60',
  },
}

const LAYER_LABELS = {
  source: 'Source',
  upper: 'Upper Stream',
  middle: 'Middle Stream',
  lower: 'Lower Stream',
}

const PERIODS = ['1y', '6m', '3m', '1m']

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

function TickerChip({ node, priceData }) {
  const style = LAYER_STYLE[node.layer] || {
    chip: 'bg-slate-800/60 border-slate-700 hover:border-slate-500',
  }
  const p = priceData || {}

  return (
    <a
      href={`#detail/${node.ticker}`}
      className={[
        'inline-flex flex-col px-3 py-2 rounded border text-xs transition-colors min-w-[100px]',
        style.chip,
      ].join(' ')}
    >
      <span className="font-mono font-bold text-slate-100 mb-1.5">{node.ticker}</span>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono text-[10px]">
        {PERIODS.map((period) => (
          <div key={period} className="flex items-center justify-between gap-1">
            <span className="text-slate-600">{period}</span>
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
  return (
    <div className="mb-8">
      <div className={['flex items-center gap-2 mb-3 pb-2 border-b', style.header].join(' ')}>
        <span className={['text-xs font-semibold uppercase tracking-widest', headerColor].join(' ')}>
          {LAYER_LABELS[layer] || layer}
        </span>
        <span className="text-slate-700 text-xs">{nodes.length} node{nodes.length !== 1 ? 's' : ''}</span>
      </div>
      {nodes.length === 0 ? (
        <p className="text-slate-700 text-xs">—</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {nodes.map((node, i) => (
            <TickerChip key={i} node={node} priceData={prices[node.ticker]} />
          ))}
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

          {/* Period legend + loading indicator */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex items-center gap-3 text-[10px] font-mono text-slate-600">
              {PERIODS.map((p) => (
                <span key={p}>{p}</span>
              ))}
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
