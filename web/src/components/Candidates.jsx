import { useState, useEffect } from 'react'

const QUEUE_LABELS = {
  A: { label: 'River Candidates', color: '#00dc96', bg: 'rgba(0,220,150,0.08)', border: 'rgba(0,220,150,0.3)' },
  B: { label: 'Holding Signals',  color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.3)' },
  C: { label: 'Crowd Heat',       color: '#5a7080', bg: 'rgba(90,112,128,0.06)', border: 'rgba(90,112,128,0.2)' },
}

function pct(v) {
  if (v == null) return <span style={{ color: '#3a5060' }}>—</span>
  const c = v > 0 ? '#00dc96' : v < 0 ? '#f87171' : '#bfcfdf'
  return <span style={{ color: c }}>{v > 0 ? '+' : ''}{v.toFixed(1)}%</span>
}

function num(v, suffix = '') {
  if (v == null) return <span style={{ color: '#3a5060' }}>—</span>
  return <span>{v}{suffix}</span>
}

function CandidateRow({ row, onDecision }) {
  const qc = QUEUE_LABELS[row.queue] || QUEUE_LABELS.C
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.04)' }}
        className="hover:bg-white/5 transition-colors"
      >
        {/* Ticker / name */}
        <td className="py-2 pl-3 pr-2" style={{ minWidth: 120 }}>
          <div style={{ color: '#e2eaf2', fontFamily: 'monospace', fontSize: 13, fontWeight: 600 }}>{row.ticker}</div>
          {row.name && <div style={{ color: '#5a7080', fontSize: 11, marginTop: 1 }}>{row.name}</div>}
        </td>
        {/* Queue */}
        <td className="py-2 px-2" style={{ whiteSpace: 'nowrap' }}>
          <span style={{
            fontFamily: 'monospace', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
            color: qc.color, border: `1px solid ${qc.border}`, borderRadius: 3, padding: '2px 6px',
            background: qc.bg,
          }}>{row.queue}</span>
        </td>
        {/* Score */}
        <td className="py-2 px-2 text-right" style={{ color: '#bfcfdf', fontSize: 12, fontFamily: 'monospace' }}>
          {row.score}
        </td>
        {/* River / layer */}
        <td className="py-2 px-2" style={{ fontSize: 11 }}>
          {row.river_id
            ? <span style={{ color: '#00dc96' }}>{row.river_id}<span style={{ color: '#3a6050' }}>/{row.layer}</span></span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        {/* Laggard gap */}
        <td className="py-2 px-2 text-right font-mono text-xs">
          {row.laggard_gap_1y != null
            ? <span style={{ color: row.laggard_gap_1y <= -10 ? '#f59e0b' : '#bfcfdf' }}>{row.laggard_gap_1y > 0 ? '+' : ''}{row.laggard_gap_1y.toFixed(1)}%</span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        {/* Returns */}
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_1m)}</td>
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_3m)}</td>
        <td className="py-2 px-2 text-right font-mono text-xs">{pct(row.return_1y)}</td>
        {/* Bull% */}
        <td className="py-2 px-2 text-right font-mono text-xs">
          {row.bull_pct != null
            ? <span style={{ color: row.bull_pct > 60 ? '#00dc96' : row.bull_pct < 40 ? '#f87171' : '#bfcfdf' }}>{row.bull_pct}%</span>
            : <span style={{ color: '#3a5060' }}>—</span>}
        </td>
        {/* BBS rank */}
        <td className="py-2 px-2 text-right font-mono text-xs" style={{ color: '#bfcfdf' }}>
          {row.bbs_rank != null ? `#${row.bbs_rank}` : <span style={{ color: '#3a5060' }}>—</span>}
          {row.bbs_today && <span style={{ color: '#00dc96', marginLeft: 3 }}>●</span>}
        </td>
        {/* Catalyst flags */}
        <td className="py-2 px-2 text-center font-mono text-xs" style={{ color: '#5a7080' }}>
          {row.has_tdnet_48h && <span style={{ color: '#a78bfa', marginRight: 4 }}>TD</span>}
          {row.has_minkabu && <span style={{ color: '#60a5fa' }}>MK</span>}
        </td>
        {/* Suppressed */}
        {row.suppressed && (
          <td className="py-2 px-2 text-xs" style={{ color: '#5a7080' }}>suppressed</td>
        )}
      </tr>
      {expanded && (
        <tr style={{ background: 'rgba(0,0,0,0.2)' }}>
          <td colSpan={11} className="px-4 py-3">
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 12 }}>
              <div>
                <span style={{ color: '#5a7080' }}>Reason: </span>
                <span style={{ color: '#bfcfdf' }}>{row.queue_reason}</span>
              </div>
              {row.price_date && (
                <div><span style={{ color: '#5a7080' }}>Price date: </span><span style={{ color: '#bfcfdf' }}>{row.price_date}</span></div>
              )}
              {row.eval_scraped_at && (
                <div><span style={{ color: '#5a7080' }}>Eval: </span><span style={{ color: '#bfcfdf' }}>{row.eval_scraped_at}</span></div>
              )}
              {row.layer_avg_1y != null && (
                <div><span style={{ color: '#5a7080' }}>Layer avg 1y: </span><span style={{ color: '#bfcfdf' }}>{row.layer_avg_1y > 0 ? '+' : ''}{row.layer_avg_1y}%</span></div>
              )}
              {row.speed_latest != null && (
                <div><span style={{ color: '#5a7080' }}>BBS speed: </span><span style={{ color: '#bfcfdf' }}>{row.speed_latest.toFixed(1)} c/h {row.speed_trend && `(${row.speed_trend})`}</span></div>
              )}
            </div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button onClick={e => { e.stopPropagation(); onDecision(row.ticker, 'pass') }}
                style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(248,113,113,0.3)', color: '#f87171', background: 'rgba(248,113,113,0.06)', cursor: 'pointer' }}>
                Pass
              </button>
              <button onClick={e => { e.stopPropagation(); onDecision(row.ticker, 'watch') }}
                style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(245,158,11,0.3)', color: '#f59e0b', background: 'rgba(245,158,11,0.06)', cursor: 'pointer' }}>
                Watch
              </button>
              <button onClick={e => { e.stopPropagation(); onDecision(row.ticker, 'river_candidate') }}
                style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.3)', color: '#00dc96', background: 'rgba(0,220,150,0.06)', cursor: 'pointer' }}>
                River Candidate
              </button>
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
        }}>{queue}</span>
        <span style={{ color: qc.color, fontSize: 14, fontWeight: 600 }}>{qc.label}</span>
        <span style={{ color: '#3a5060', fontSize: 12 }}>{rows.length} tickers</span>
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
              {['Ticker', 'Q', 'Score', 'River/Layer', 'Lag 1y', '1m', '3m', '1y', 'Bull%', 'BBS', 'Catalyst'].map(h => (
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

  const load = () => {
    setLoading(true)
    fetch('/api/candidates')
      .then(r => r.json())
      .then(rows => { setData(rows); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const handleDecision = (ticker, decision) => {
    fetch('/api/decisions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, decision }),
    })
      .then(r => r.json())
      .then(() => {
        setDecisionMsg(`${ticker} → ${decision}`)
        setTimeout(() => setDecisionMsg(null), 3000)
        load()
      })
      .catch(e => setDecisionMsg(`Error: ${e}`))
  }

  const queueA = data.filter(r => r.queue === 'A')
  const queueB = data.filter(r => r.queue === 'B')
  const queueC = data.filter(r => r.queue === 'C')

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h1 style={{ color: '#e2eaf2', fontSize: 20, fontWeight: 700, margin: 0 }}>Candidates</h1>
        <button onClick={load}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.2)', color: '#00dc96', background: 'transparent', cursor: 'pointer', fontFamily: 'monospace' }}>
          Refresh
        </button>
        {decisionMsg && (
          <span style={{ fontSize: 12, color: '#00dc96', marginLeft: 8 }}>{decisionMsg}</span>
        )}
      </div>

      {loading && <div style={{ color: '#5a7080', fontSize: 14 }}>Loading candidates…</div>}
      {error && <div style={{ color: '#f87171', fontSize: 14 }}>Error: {error}</div>}

      {!loading && !error && (
        <>
          <div style={{ color: '#5a7080', fontSize: 12, marginBottom: 20, fontFamily: 'monospace' }}>
            {data.length} tickers · {queueA.length} river · {queueB.length} holding · {queueC.length} crowd
          </div>
          <QueueTable rows={queueA} queue="A" onDecision={handleDecision} />
          <QueueTable rows={queueB} queue="B" onDecision={handleDecision} />
          <QueueTable rows={queueC} queue="C" onDecision={handleDecision} />
        </>
      )}
    </div>
  )
}
