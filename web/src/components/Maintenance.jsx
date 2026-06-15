import { useState, useEffect } from 'react'
import { APP_BASE } from '../app-base'

const TRIGGER_LABELS = {
  thin_layer: 'Thin Layer',
  stale_node: 'Stale Node',
  proposed_node: 'Proposed Node',
  proposed_river: 'Proposed River',
  duplicate_node: 'Duplicate Node',
  multi_river_conflict: 'Multi-River Conflict',
  missing_what_would_change_our_mind: 'Missing Falsification',
  demotion_review: 'Demotion Review',
  removal_review: 'Removal Review',
}

const PRIORITY_COLORS = {
  high: '#f87171',
  medium: '#f59e0b',
  low: '#5a7080',
}

const ACTIONS = [
  'reviewed_no_change',
  'added_nodes',
  'approved',
  'rejected',
  'demoted',
  'promoted',
  'marked_dormant',
  'merged',
  'added_falsification',
  'acknowledged',
]

function MaintenanceItem({ item, onResolve }) {
  const [resolving, setResolving] = useState(false)
  const [action, setAction] = useState(ACTIONS[0])
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState(null)
  const priorityColor = PRIORITY_COLORS[item.priority] || '#5a7080'
  const typeLabel = TRIGGER_LABELS[item.trigger_type] || item.trigger_type

  const handleResolve = () => {
    if (!action) return
    onResolve(item.maintenance_id, action, reason, setMsg)
    setResolving(false)
    setReason('')
  }

  return (
    <div style={{
      border: `1px solid rgba(255,255,255,0.06)`,
      borderLeft: `3px solid ${priorityColor}`,
      borderRadius: 6,
      padding: 12,
      marginBottom: 8,
      background: 'rgba(0,0,0,0.15)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 10, fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.08em',
          color: priorityColor, border: `1px solid ${priorityColor}33`, borderRadius: 3,
          padding: '2px 6px',
        }}>{item.priority.toUpperCase()}</span>
        <span style={{ fontSize: 11, color: '#bfcfdf', fontWeight: 600 }}>{typeLabel}</span>
        {item.ticker && (
          <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#00dc96' }}>{item.ticker}</span>
        )}
        {item.river_id && (
          <span style={{ fontSize: 11, color: '#5a7080' }}>
            {item.river_name || item.river_id}
            {item.layer && <span style={{ color: '#3a5060' }}>/{item.layer}</span>}
          </span>
        )}
        <span style={{ fontSize: 10, color: '#3a5060', fontFamily: 'monospace', marginLeft: 'auto' }}>
          #{item.maintenance_id}
        </span>
      </div>

      <div style={{ color: '#8a9aaa', fontSize: 12, marginBottom: 6 }}>{item.reason}</div>

      {item.recommended_actions?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {item.recommended_actions.map((a, i) => (
            <div key={i} style={{ color: '#5a7080', fontSize: 11, paddingLeft: 8, borderLeft: '2px solid rgba(255,255,255,0.06)' }}>
              {a}
            </div>
          ))}
        </div>
      )}

      {msg && (
        <div style={{ color: '#00dc96', fontSize: 11, marginBottom: 6 }}>{msg}</div>
      )}

      {!resolving ? (
        <button
          onClick={() => setResolving(true)}
          style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.2)', color: '#00dc96', background: 'transparent', cursor: 'pointer' }}>
          Resolve
        </button>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={action}
            onChange={e => setAction(e.target.value)}
            style={{ fontSize: 11, padding: '3px 6px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)', background: '#0a0f14', color: '#bfcfdf' }}>
            {ACTIONS.map(a => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
          </select>
          <input
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder="Reason (optional)"
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: '#bfcfdf', width: 200 }}
          />
          <button onClick={handleResolve}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.3)', color: '#00dc96', background: 'rgba(0,220,150,0.06)', cursor: 'pointer' }}>
            Confirm
          </button>
          <button onClick={() => setResolving(false)}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.1)', color: '#5a7080', background: 'transparent', cursor: 'pointer' }}>
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}

function TriggerGroup({ triggerType, items, onResolve }) {
  const label = TRIGGER_LABELS[triggerType] || triggerType
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ color: '#bfcfdf', fontSize: 13, fontWeight: 600 }}>{label}</span>
        <span style={{ color: '#3a5060', fontSize: 12 }}>{items.length}</span>
      </div>
      {items.map(item => (
        <MaintenanceItem key={item.maintenance_id} item={item} onResolve={onResolve} />
      ))}
    </div>
  )
}

export default function Maintenance() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetch(`${APP_BASE}/api/maintenance`)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json()
      })
      .then(data => {
        setItems(Array.isArray(data) ? data : [])
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const handleResolve = (maintenanceId, action, reason, setMsg) => {
    fetch(`${APP_BASE}/api/maintenance/${maintenanceId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, reason }),
    })
      .then(r => r.json())
      .then(() => {
        setMsg && setMsg(`Resolved: ${action}`)
        setTimeout(load, 500)
      })
      .catch(e => { setMsg && setMsg(`Error: ${e}`) })
  }

  // Group by trigger_type preserving priority order
  const grouped = {}
  for (const item of items) {
    if (!grouped[item.trigger_type]) grouped[item.trigger_type] = []
    grouped[item.trigger_type].push(item)
  }

  const highCount = items.filter(i => i.priority === 'high').length
  const medCount = items.filter(i => i.priority === 'medium').length
  const lowCount = items.filter(i => i.priority === 'low').length

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h1 style={{ color: '#e2eaf2', fontSize: 20, fontWeight: 700, margin: 0 }}>Maintenance</h1>
        <span style={{ fontSize: 11, color: '#5a7080', fontFamily: 'monospace' }}>Queue D</span>
        <button onClick={load}
          style={{ fontSize: 11, padding: '4px 12px', borderRadius: 4, border: '1px solid rgba(0,220,150,0.2)', color: '#00dc96', background: 'transparent', cursor: 'pointer', fontFamily: 'monospace' }}>
          Refresh
        </button>
      </div>

      {loading && <div style={{ color: '#5a7080', fontSize: 14 }}>Loading maintenance items…</div>}
      {error && <div style={{ color: '#f87171', fontSize: 14 }}>Error: {error}</div>}

      {!loading && !error && (
        <>
          {items.length === 0 ? (
            <div style={{ color: '#3a5060', fontSize: 14 }}>No maintenance items — tree is in good shape.</div>
          ) : (
            <>
              <div style={{ color: '#5a7080', fontSize: 12, marginBottom: 20, fontFamily: 'monospace' }}>
                {items.length} items ·{' '}
                {highCount > 0 && <span style={{ color: '#f87171' }}>{highCount} high </span>}
                {medCount > 0 && <span style={{ color: '#f59e0b' }}>{medCount} medium </span>}
                {lowCount > 0 && <span style={{ color: '#5a7080' }}>{lowCount} low</span>}
              </div>
              {Object.entries(grouped).map(([type, typeItems]) => (
                <TriggerGroup key={type} triggerType={type} items={typeItems} onResolve={handleResolve} />
              ))}
            </>
          )}
        </>
      )}
    </div>
  )
}
