import { useState, useEffect } from 'react'
import { getTree } from '../api'

const LAYER_COLORS = {
  source: 'bg-purple-900/50 text-purple-300 border-purple-700/50',
  upper: 'bg-blue-900/50 text-blue-300 border-blue-700/50',
  middle: 'bg-emerald-900/50 text-emerald-300 border-emerald-700/50',
  lower: 'bg-amber-900/50 text-amber-300 border-amber-700/50',
}

const LAYER_HEADER = {
  source: 'text-purple-400',
  upper: 'text-blue-400',
  middle: 'text-emerald-400',
  lower: 'text-amber-400',
}

function TickerChip({ node }) {
  return (
    <div
      className={[
        'inline-flex flex-col px-2.5 py-1.5 rounded border text-xs mb-1.5 mr-1.5',
        LAYER_COLORS[node.layer] || 'bg-slate-800 text-slate-300 border-slate-700',
      ].join(' ')}
    >
      <span className="font-mono font-semibold">{node.ticker}</span>
      {node.name && (
        <span className="text-xs opacity-70 mt-0.5 max-w-[120px] truncate">{node.name}</span>
      )}
      {node.role && (
        <span className="text-xs opacity-50 mt-0.5">{node.role}</span>
      )}
    </div>
  )
}

function RiverSection({ river, layers }) {
  const nodesByLayer = {}
  layers.forEach((l) => { nodesByLayer[l] = [] })
  ;(river.nodes || []).forEach((n) => {
    if (nodesByLayer[n.layer]) nodesByLayer[n.layer].push(n)
    else nodesByLayer[n.layer] = [n]
  })

  return (
    <div className="mb-8">
      <div className="mb-3">
        <h3 className="text-base font-semibold text-slate-100">{river.name}</h3>
        {river.description && (
          <p className="text-slate-500 text-sm mt-0.5">{river.description}</p>
        )}
      </div>

      <div
        className="grid gap-3 bg-slate-900 border border-slate-800 rounded-lg p-4"
        style={{ gridTemplateColumns: `repeat(${layers.length}, minmax(0, 1fr))` }}
      >
        {layers.map((layer) => (
          <div key={layer}>
            <p
              className={[
                'text-xs font-medium uppercase tracking-wider mb-2 pb-1.5 border-b border-slate-800',
                LAYER_HEADER[layer] || 'text-slate-400',
              ].join(' ')}
            >
              {layer}
            </p>
            <div className="flex flex-wrap">
              {nodesByLayer[layer] && nodesByLayer[layer].length > 0 ? (
                nodesByLayer[layer].map((node, i) => (
                  <TickerChip key={i} node={node} />
                ))
              ) : (
                <span className="text-slate-700 text-xs">—</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Tree() {
  const [tree, setTree] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getTree()
      .then((d) => setTree(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 py-8">
        <div className="w-4 h-4 border-t-2 border-emerald-400 rounded-full animate-spin" />
        Loading...
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3 text-sm">
        Error: {error}
      </div>
    )
  }

  if (!tree) return null

  const layers = tree.layers || ['source', 'upper', 'middle', 'lower']
  const rivers = tree.rivers || []

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h2 className="text-lg font-semibold text-slate-100">River Tree</h2>
        <div className="flex items-center gap-3">
          {layers.map((l) => (
            <span key={l} className="flex items-center gap-1.5 text-xs">
              <span
                className={[
                  'w-2 h-2 rounded-full',
                  l === 'source' ? 'bg-purple-400' :
                  l === 'upper' ? 'bg-blue-400' :
                  l === 'middle' ? 'bg-emerald-400' :
                  'bg-amber-400',
                ].join(' ')}
              />
              <span className="text-slate-500 capitalize">{l}</span>
            </span>
          ))}
        </div>
      </div>

      {rivers.length === 0 ? (
        <p className="text-slate-600 text-sm">No rivers configured.</p>
      ) : (
        rivers.map((river) => (
          <RiverSection key={river.id} river={river} layers={layers} />
        ))
      )}
    </div>
  )
}
