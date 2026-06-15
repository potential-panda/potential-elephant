import { useState, useEffect } from 'react'
import { APP_BASE } from '../app-base'

const QUEUE_LABELS = {
  A: { label: 'River Candidates', color: '#00dc96', bg: 'rgba(0,220,150,0.08)', border: 'rgba(0,220,150,0.3)' },
  B: { label: 'Known Node / Monitor', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.3)' },
  C: { label: 'Crowd Heat / Noise', color: '#5a7080', bg: 'rgba(90,112,128,0.06)', border: 'rgba(90,112,128,0.2)' },
  suppressed: { label: 'Suppressed', color: '#3a5060', bg: 'rgba(58,80,96,0.06)', border: 'rgba(58,80,96,0.2)' },
}

function pct(v) {
  if (v == null) return <span style={{ color: '#3a5060' }}>—</span>
  const c = v > 0 ? '#00dc96' : v < 0 ? '#f87171' : '#bfcfdf'
  return <span style={{ color: c }}>{v > 0 ? '+' : ''}{v.toFixed(1)}%</span>
}

function Score({ label, value, max, color = '#bfcfdf' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
      <span style={{ color: '#5a7080', fontSize: 10, fontFamily: 'monospace' }}>{label}</span>
      <span style={{ color, fontSize: 12, fontFamily: 'monospace', fontWeight: 600 }}>{typeof value === 'number' ? value.toFixed(value % 1 === 0 ? 0 : 1) : '—'}</span>
      {max != null && <span style={{ color: '#3a5060', fontSize: 10 }}>/{max}</span>}
    </div>
  )
}

function EvidenceItem({ item }) {
  const roleColors = { catalyst: '#a78bfa', evidence: '#00dc96', context: '#60a5fa', attention: '#f59e0b', risk: '#f87171' }
  const color = roleColors[item.role] || '#bfcfdf'
  return (
    <div style={{ padding: '4px 8px', border: `1px solid ${color}22`, borderRadius: 4, marginBottom: 4, background: `${color}08` }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
        <span style={{ color, fontSize: 10, fontFamily: 'monospace', fontWeight: 700 }}>{item.role?.toUpperCase()}</span>
        <span style={{ color: '#5a7080', fontSize: 10 }}>tier {item.source_tier} · {item.source}</span>
        {item.freshness_days != null && (
          <span style={{ color: '#3a5060', fontSize: 10 }}>{item.freshness_days}d ago</span>
        )}
        <span style={{ color: '#bfcfdf', fontSize: 10, fontFamily: 'monospace' }}>+{typeof item.raw_points === 'number' ? item.raw_points : '?'}pts</span>
      </div>
      {item.title && <div style={{ color: '#8a9aaa', fontSize: 11 }}>{item.title}</div>}
    </div>
  )
}

function ScoreBreakdown({ row }) {
  const adj = row.decision_memory_adjustment || 0
  const noise = row.noise_penalty || 0
  return (
    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: 12, marginBottom: 8 }}>
      <div style={{ color: '#5a7080', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.1em', marginBottom: 8 }}>SCORE BREAKDOWN</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px 16px', marginBottom: 8 }}>
        <Score label="D1 river fit" value={row.d1_river_fit} max={25} color={row.d1_river_fit > 0 ? '#00dc96' : '#3a5060'} />
        <Score label="D2 layer alpha" value={row.d2_layer_alpha} max={15} />
        <Score label="D3 laggard" value={row.d3_relative_laggard} max={20} />
        <Score label="D4 catalyst" value={row.d4_catalyst} max={20} color={row.d4_catalyst > 0 ? '#a78bfa' : '#3a5060'} />
        <Score label="D5 attention" value={row.d5_attention_change} max={10} />
        <Score label="D6 coverage gap" value={row.d6_coverage_gap} max={10} />
      </div>
      <div style={{ display: 'flex', gap: 16, alignItems: 'baseline', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
        <Score label="raw" value={row.raw_score} />
        {adj !== 0 && <Score label="memory adj" value={adj} color={adj < 0 ? '#f87171' : '#00dc96'} />}
        {noise !== 0 && <Score label="noise" value={noise} color={noise < 0 ? '#f87171' : '#bfcfdf'} />}
        <div style={{ marginLeft: 'auto' }}>
          <Score label="final" value={row.score} color={row.score >= 70 ? '#00dc96' : row.score >= 40 ? '#f59e0b' : '#bfcfdf'} />
        </div>
      </div>
      {row.weak_peer_set && (
        <div style={{ color: '#f59e0b', fontSize: 10, marginTop: 6 }}>D3=0 · weak_peer_set (fewer than 3 active/weak peers with price history)</div>
      )}
      {row.queue_gate_blocked && (
        <div style={{ color: '#f87171', fontSize: 10, marginTop: 4 }}>Blocked: {row.queue_gate_blocked}</div>
      )}
      {row.node_status && (
        <div style={{ color: '#5a7080', fontSize: 10, marginTop: 4 }}>Node status: <span style={{ color: '#bfcfdf' }}>{row.node_status}</span></div>
      )}
      {row.suppress_until && (
        <div style={{ color: '#f87171', fontSize: 10, marginTop: 4 }}>
          Suppressed until {row.suppress_until} · pass #{row.pass_count}
        </div>
      )}
    </div>
  )
}

function CandidateRow({ row, onDecision }) {
  const qc = QUEUE_LABELS[row.queue] || QUEUE_LABELS.C
  const [expanded, setExpanded] = useState(false)
  const [reasonInput, setReasonInput] = useState('')

  const handleDecision = (decision) => {
    onDecision(row.ticker, decision, row, reasonInput)
    setReasonInput('')
  }

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
        className="hover:bg-white/5 transition-colors"
      >
        <td className="py-2 pl-3 pr-2" style={{ minWidth: 120 }}>
          <div style={{ color: '#e2eaf2', fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}>{row.ticker}</div>
          {row.name && <div style={{ color: '#5a7080', fontSize: 11, marginTop: 1 }}>{row.name}</div>}
        </td>
        <td className="py-2 px-2 text-right" style={{ color: '#bfcfdf', fontSize: 12, fontFamily: 'monospace' }}>
          {row.score}
        </td>
        <td className="py-2 px-2" style={{ fontSize: 11 }}>
          {row.river_id
            ? <span style={{ color: '#00dc96' }}>{row.river_id}<span style={{ color: '#3a6050' }}>/{row.layer}</span></span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        <td className="py-2 px-2 text-right font-mono text-xs">
          {row.laggard_gap_1y != null
            ? <span style={{ color: row.laggard_gap_1y <= -10 ? '#f59e0b' : '#bfcfdf' }}>{row.laggard_gap_1y > 0 ? '+' : ''}{row.laggard_gap_1y.toFixed(1)}%</span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_1m)}</td>
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_3m)}</td>
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_1y)}</td>
        <td className="py-2 px-2 text-right font-mono text-xs">
          {row.bull_pct != null
            ? <span style={{ color: row.bull_pct > 60 ? '#00dc96' : row.bull_pct < 40 ? '#f87171' : '#bfcfdf' }}>{row.bull_pct}%</span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: '#bfcfdf' }}>
          {row.bbs_rank != null ? `#${row.bbs_rank}` : <span style={{ color: '#3a5060' }}>—</span>}
          {row.bbs_today && <span style={{ color: '#00dc96', marginLeft: 3 }}>●</span>}
        </td>
        <td className="py-2 px-2 text-center font-mono text-xs" style={{ color: '#5a7080' }}>
          {row.has_tdnet_48h && <span style={{ color: '#a78bfa', marginRight: 4 }}>TD</span>}
          {row.has_minkabu && <span style={{ color: '#60a5fa' }}>MK</span>}
        </td>
      </tr>
      {expanded && (
        <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
          <td colSpan={10} className="px-4 py-3">
            <ScoreBreakdown row={row} />

            {/* Evidence packet */}
            {row.evidence_packet?.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ color: '#5a7080', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.1em', marginBottom: 6 }}>EVIDENCE PACKET</div>
                {row.evidence_packet.map((item, i) => <EvidenceItem key={i} item={item} />)}
              </div>
            )}

            {/* Context */}
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 11, marginBottom: 8 }}>
              {row.queue_reason && (
                <div><span style={{ color: '#5a7080' }}>Reason: </span><span style={{ color: '#bfcfdf' }}>{row.queue_reason}</span></div>
              )}
              {row.price_date && (
                <div><span style={{ color: '#5a7080' }}>Price: </span><span style={{ color: '#bfcfdf' }}>{row.price_date}</span></div>
              )}
              {row.speed_latest != null && (
                <div><span style={{ color: '#5a7080' }}>BBS: </span><span style={{ color: '#bfcfdf' }}>{row.speed_latest.toFixed(1)} c/h {row.speed_trend && `(${row.speed_trend})`}</span></div>
              )}
            </div>

            {/* Decision actions */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
              <input
                value={reasonInput}
                onChange={e => setReasonInput(e.target.value)}
                placeholder="Reason (optional)"
                onClick={e => e.stopPropagation()}
                style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: '#bfcfdf', marginBottom: 6, width: 240 }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={e => { e.stopPropagation(); handleDecision('pass') }}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(248,113,113,0.3)', color: '#f87171', background: 'rgba(248,113,113,0.06)', cursor: 'pointer' }}>
                  Pass
                </button>
                <button onClick={e => { e.stopPropagation(); handleDecision('watch') }}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(245,158,11,0.3)', color: '#f59e0b', background: 'rgba(245,158,11,0.06)', cursor: 'pointer' }}>
                  Watch
                </button>
                <button onClick={e => { e.stopPropagation(); handleDecision('river_candidate') }}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.3)', color: '#00dc96', background: 'rgba(0,220,150,0.06)', cursor: 'pointer' }}>
                  River Candidate
                </button>
                <button onClick={e => { e.stopPropagation(); handleDecision('needs_manual_research') }}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(167,139,250,0.3)', color: '#a78bfa', background: 'rgba(167,139,250,0.06)', cursor: 'pointer' }}>
                  Research
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function QueueTable({ rows, queue, onDecision }) {
  const qc = QUEUE_LABELS[queue]
  if (!rows.length) return null
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{
          fontFamily: 'monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
          color: qc.color, border: `1px solid ${qc.border}`, borderRadius: 4,
          padding: '3px 9px', background: qc.bg,
        }}>{queue.toUpperCase()}</span>
        <span style={{ color: qc.color, fontSize: 14, fontWeight: 600 }}>{qc.label}</span>
        <span style={{ color: '#3a5060', fontSize: 12 }}>{rows.length} tickers</span>
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
              {['Ticker', 'Score', 'River/Layer', 'Lag 1y', '1m', '3m', '1y', 'Bull%', 'BBS', 'Catalyst'].map(h => (
                <th key={h} className="py-2 px-2 text-left"
                  style={{ color: '#3a5060', fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.08em', fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => <CandidateRow key={row.ticker} row={row} onDecision={onDecision} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Candidates() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [decisionMsg, setDecisionMsg] = useState(null)
  const [showSuppressed, setShowSuppressed] = useState(false)

  const load = (includeSuppressed = showSuppressed) => {
    setLoading(true)
    setError(null)
    const qs = includeSuppressed ? '?include_suppressed=true' : ''
    fetch(`${APP_BASE}/api/candidates${qs}`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(rows => {
        if (!Array.isArray(rows)) throw new Error('unexpected response format')
        setData(rows)
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const handleDecision = (ticker, decision, row = null, reason = '') => {
    fetch(`${APP_BASE}/api/decisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, decision, reason, snapshot: row || {} }),
    })
      .then(r => r.json())
      .then(() => {
        setDecisionMsg(`${ticker} → ${decision}`)
        setTimeout(() => setDecisionMsg(null), 3000)
        load()
      })
      .catch(e => setDecisionMsg(`Error: ${e}`))
  }

  const toggleSuppressed = () => {
    const next = !showSuppressed
    setShowSuppressed(next)
    load(next)
  }

  const queueA = data.filter(r => r.queue === 'A')
  const queueB = data.filter(r => r.queue === 'B')
  const queueC = data.filter(r => r.queue === 'C')
  const queueSuppressed = data.filter(r => r.queue === 'suppressed')

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <h1 style={{ color: '#e2eaf2', fontSize: 20, fontWeight: 700, margin: 0 }}>Candidates</h1>
        <button onClick={() => load()}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.2)', color: '#00dc96', background: 'transparent', cursor: 'pointer', fontFamily: 'monospace' }}>
          Refresh
        </button>
        <button onClick={toggleSuppressed}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 4, border: '1px solid rgba(90,112,128,0.3)', color: showSuppressed ? '#bfcfdf' : '#5a7080', background: showSuppressed ? 'rgba(90,112,128,0.1)' : 'transparent', cursor: 'pointer', fontFamily: 'monospace' }}>
          {showSuppressed ? 'Hide suppressed' : 'Show suppressed'}
        </button>
        {decisionMsg && (
          <span style={{ fontSize: 12, color: '#00dc96' }}>{decisionMsg}</span>
        )}
      </div>

      {loading && <div style={{ color: '#5a7080', fontSize: 14 }}>Loading candidates…</div>}
      {error && <div style={{ color: '#f87171', fontSize: 14 }}>Error: {error}</div>}

      {!loading && !error && (
        <>
          <div style={{ color: '#5a7080', fontSize: 12, marginBottom: 20, fontFamily: 'monospace' }}>
            {data.length} tickers · {queueA.length} river · {queueB.length} monitor · {queueC.length} crowd
            {showSuppressed && ` · ${queueSuppressed.length} suppressed`}
          </div>
          <QueueTable rows={queueA} queue="A" onDecision={handleDecision} />
          <QueueTable rows={queueB} queue="B" onDecision={handleDecision} />
          <QueueTable rows={queueC} queue="C" onDecision={handleDecision} />
          {showSuppressed && <QueueTable rows={queueSuppressed} queue="suppressed" onDecision={handleDecision} />}
        </>
      )}
    </div>
  )
}
