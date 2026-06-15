import { useState, useEffect } from 'react'
import { APP_BASE } from '../app-base'

function pct(v, opts = {}) {
  if (v == null) return <span style={{ color: '#3a5060' }}>—</span>
  const color = v > 0 ? '#00dc96' : v < 0 ? '#f87171' : '#bfcfdf'
  const text = `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
  return <span style={{ color, ...opts.style }}>{text}</span>
}

function Delta({ snap, cur }) {
  if (snap == null || cur == null) return null
  const d = cur - snap
  if (Math.abs(d) < 0.1) return null
  const color = d > 0 ? '#00dc96' : '#f87171'
  return (
    <span style={{ color, fontSize: 10, marginLeft: 4, opacity: 0.7 }}>
      {d > 0 ? '▲' : '▼'}{Math.abs(d).toFixed(1)}%
    </span>
  )
}

function MetricRow({ label, snap, cur }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ color: '#3a5060', fontSize: 11, width: 80, flexShrink: 0 }}>{label}</span>
      <span style={{ width: 80, textAlign: 'right', fontFamily: 'monospace', fontSize: 12 }}>
        {pct(snap)}
      </span>
      <span style={{ color: '#3a5060', fontSize: 10, width: 24, textAlign: 'center' }}>→</span>
      <span style={{ width: 80, textAlign: 'right', fontFamily: 'monospace', fontSize: 12 }}>
        {pct(cur)}
        <Delta snap={snap} cur={cur} />
      </span>
    </div>
  )
}

function PositionCard({ pos, onRemove }) {
  const snap = pos.snapshot || {}
  const cur = pos.current || {}

  const daysLabel = pos.days_since === 0 ? 'today'
    : pos.days_since === 1 ? '1 day ago'
    : pos.days_since != null ? `${pos.days_since} days ago`
    : ''

  const sinceColor = pos.since_flag == null ? '#3a5060'
    : pos.since_flag > 0 ? '#00dc96'
    : pos.since_flag < 0 ? '#f87171'
    : '#bfcfdf'

  return (
    <div style={{
      border: '1px solid rgba(0,220,150,0.15)',
      borderRadius: 10,
      padding: '16px 20px',
      background: 'rgba(0,220,150,0.03)',
      marginBottom: 16,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: '#e2eaf2', fontFamily: 'monospace', fontSize: 16, fontWeight: 700 }}>
              {pos.ticker}
            </span>
            {snap.market && (
              <span style={{ fontSize: 10, color: '#3a5060', fontFamily: 'monospace',
                border: '1px solid rgba(255,255,255,0.08)', borderRadius: 3, padding: '1px 5px' }}>
                {snap.market}
              </span>
            )}
            {snap.river_id && (
              <span style={{ fontSize: 10, color: '#00dc96', fontFamily: 'monospace' }}>
                {snap.river_id}{snap.layer ? <span style={{ color: '#3a6050' }}>/{snap.layer}</span> : null}
              </span>
            )}
          </div>
          <div style={{ marginTop: 4, fontSize: 11, color: '#3a5060' }}>
            flagged {daysLabel}
            {pos.flagged_date && <span style={{ marginLeft: 6, opacity: 0.6 }}>{pos.flagged_date}</span>}
          </div>
          {snap.queue_reason && (
            <div style={{ marginTop: 4, fontSize: 11, color: '#5a7080', maxWidth: 420 }}>
              {snap.queue_reason}
            </div>
          )}
        </div>

        {/* Since-flag return — the headline number */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          {pos.since_flag != null ? (
            <>
              <div style={{ color: sinceColor, fontFamily: 'monospace', fontSize: 22, fontWeight: 700, lineHeight: 1 }}>
                {pos.since_flag > 0 ? '+' : ''}{pos.since_flag.toFixed(1)}%
              </div>
              <div style={{ color: '#3a5060', fontSize: 10, marginTop: 3 }}>since flag</div>
            </>
          ) : (
            <div style={{ color: '#3a5060', fontSize: 11 }}>no price data</div>
          )}
        </div>
      </div>

      {/* Metrics grid: at-flag vs today */}
      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 264 }}>
          {/* Column headers */}
          <div style={{ display: 'flex', marginBottom: 4 }}>
            <span style={{ width: 80, fontSize: 9, color: '#3a5060', fontFamily: 'monospace', letterSpacing: '0.08em' }}></span>
            <span style={{ width: 80, textAlign: 'right', fontSize: 9, color: '#3a5060', fontFamily: 'monospace', letterSpacing: '0.08em' }}>AT FLAG</span>
            <span style={{ width: 24 }}></span>
            <span style={{ width: 80, textAlign: 'right', fontSize: 9, color: '#3a5060', fontFamily: 'monospace', letterSpacing: '0.08em' }}>TODAY</span>
          </div>
          <MetricRow label="1m return" snap={snap.return_1m} cur={cur.return_1m} />
          <MetricRow label="3m return" snap={snap.return_3m} cur={cur.return_3m} />
          <MetricRow label="1y return" snap={snap.return_1y} cur={cur.return_1y} />
        </div>

        {/* Right: context metrics from snapshot */}
        <div style={{ fontSize: 11, color: '#5a7080' }}>
          {snap.score != null && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#3a5060' }}>Score at flag: </span>
              <span style={{ color: '#bfcfdf', fontFamily: 'monospace' }}>{snap.score}</span>
            </div>
          )}
          {snap.laggard_gap_1y != null && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#3a5060' }}>Lag gap at flag: </span>
              <span style={{ color: '#f59e0b', fontFamily: 'monospace' }}>
                {snap.laggard_gap_1y > 0 ? '+' : ''}{snap.laggard_gap_1y.toFixed(1)}%
              </span>
            </div>
          )}
          {snap.bull_pct != null && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#3a5060' }}>Bull% at flag: </span>
              <span style={{ color: snap.bull_pct > 55 ? '#00dc96' : '#bfcfdf', fontFamily: 'monospace' }}>
                {snap.bull_pct}%
              </span>
            </div>
          )}
          {snap.last_close != null && (
            <div style={{ marginBottom: 4 }}>
              <span style={{ color: '#3a5060' }}>Price at flag: </span>
              <span style={{ color: '#bfcfdf', fontFamily: 'monospace' }}>{snap.last_close.toFixed(2)}</span>
              {cur.last_close != null && (
                <span style={{ color: '#5a7080', marginLeft: 6 }}>→ {cur.last_close.toFixed(2)}</span>
              )}
            </div>
          )}
          {cur.price_date && (
            <div style={{ color: '#3a5060', fontSize: 10 }}>price as of {cur.price_date}</div>
          )}
        </div>
      </div>

      {/* Footer actions */}
      <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => onRemove(pos.ticker)}
          style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4,
            border: '1px solid rgba(248,113,113,0.2)', color: '#f87171',
            background: 'transparent', cursor: 'pointer', opacity: 0.6 }}
        >
          Remove
        </button>
      </div>
    </div>
  )
}

export default function Watchlist() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetch(`${APP_BASE}/api/watchlist`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(rows => {
        if (!Array.isArray(rows)) throw new Error('unexpected response')
        setData(rows)
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const handleRemove = (ticker) => {
    fetch(`${APP_BASE}/api/decisions/${ticker}`, { method: 'DELETE' })
      .then(() => load())
      .catch(() => load())
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h1 style={{ color: '#e2eaf2', fontSize: 20, fontWeight: 700, margin: 0 }}>Watchlist</h1>
        <button onClick={load}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 4,
            border: '1px solid rgba(0,220,150,0.2)', color: '#00dc96',
            background: 'transparent', cursor: 'pointer', fontFamily: 'monospace' }}>
          Refresh
        </button>
        {!loading && !error && (
          <span style={{ fontSize: 12, color: '#3a5060', fontFamily: 'monospace' }}>
            {data.length} position{data.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {loading && <div style={{ color: '#5a7080', fontSize: 14 }}>Loading…</div>}
      {error && <div style={{ color: '#f87171', fontSize: 14 }}>Error: {error}</div>}

      {!loading && !error && data.length === 0 && (
        <div style={{ color: '#3a5060', fontSize: 14, fontFamily: 'monospace', paddingTop: 40, textAlign: 'center' }}>
          No positions yet.<br />
          <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
            Click "River Candidate" on any stock in the Candidates tab to track it here.
          </span>
        </div>
      )}

      {!loading && !error && data.map(pos => (
        <PositionCard key={pos.ticker} pos={pos} onRemove={handleRemove} />
      ))}
    </div>
  )
}
