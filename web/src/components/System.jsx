import { useEffect, useState } from 'react'
import Query from './Query'
import Schedule from './Schedule'
import Stats from './Stats'

const SYSTEM_TABS = [
  { id: 'query', label: 'Query', Component: Query },
  { id: 'schedule', label: 'Schedule', Component: Schedule },
  { id: 'stats', label: 'Stats', Component: Stats },
]

const SYSTEM_TAB_IDS = new Set(SYSTEM_TABS.map((tab) => tab.id))

function tabFromHash() {
  const parts = window.location.hash.slice(1).replace(/^\/+/, '').split('/')
  if (parts[0] === 'system' && SYSTEM_TAB_IDS.has(parts[1])) return parts[1]
  if (SYSTEM_TAB_IDS.has(parts[0])) return parts[0]
  return 'query'
}

export default function System() {
  const [tab, setTab] = useState(tabFromHash)

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const active = SYSTEM_TABS.find((item) => item.id === tab) || SYSTEM_TABS[0]
  const ActiveComponent = active.Component

  const handleTabChange = (next) => {
    window.location.hash = `/system/${next}`
    setTab(next)
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">System</h2>
          <p className="text-sm text-slate-600 mt-1">Query, schedule, and stats live here.</p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-5 border-b border-slate-800">
        {SYSTEM_TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => handleTabChange(item.id)}
            className={[
              'px-3 py-1.5 rounded-t border-b-2 text-xs uppercase tracking-wider font-semibold transition-colors',
              tab === item.id
                ? 'text-emerald-400 border-emerald-400 bg-slate-900'
                : 'text-slate-500 border-transparent hover:text-slate-300 hover:border-slate-600',
            ].join(' ')}
          >
            {item.label}
          </button>
        ))}
      </div>

      <ActiveComponent />
    </div>
  )
}
