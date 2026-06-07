import { useState } from 'react'

const TABS = [
  { id: 'digest', label: 'Digest' },
  { id: 'detail', label: 'Detail' },
  { id: 'dive', label: 'Dive' },
  { id: 'query', label: 'Query' },
  { id: 'tree', label: 'Tree' },
  { id: 'tickers', label: 'Tickers' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'stats', label: 'Stats' },
]

export default function Layout({ activeTab, onTabChange, children }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex w-full min-h-screen">
      {/* Sidebar */}
      <aside
        className={[
          'shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col fixed top-0 left-0 h-screen z-20 transition-all duration-200',
          open ? 'w-48' : 'w-10',
        ].join(' ')}
      >
        {/* Toggle button */}
        <button
          onClick={() => setOpen(v => !v)}
          className="w-full flex items-center justify-center h-10 text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 transition-colors shrink-0"
          title={open ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {open ? '«' : '»'}
        </button>

        {open && (
          <>
            <div className="px-4 py-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 text-xl font-bold">&#9650;</span>
                <span className="text-slate-100 font-semibold tracking-wide text-base">
                  Elephant
                </span>
              </div>
              <p className="text-slate-500 text-xs mt-1">Stock Research</p>
            </div>

            <nav className="flex-1 py-3 overflow-y-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  className={[
                    'w-full text-left px-4 py-2.5 text-sm font-medium transition-colors duration-150',
                    activeTab === tab.id
                      ? 'bg-slate-800 text-emerald-400 border-l-2 border-emerald-400'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50 border-l-2 border-transparent',
                  ].join(' ')}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="px-4 py-3 border-t border-slate-800">
              <p className="text-slate-600 text-xs">v0.1.0</p>
            </div>
          </>
        )}
      </aside>

      {/* Main content — offset matches sidebar width */}
      <main
        className={[
          'flex-1 min-h-screen overflow-y-auto bg-slate-950 transition-all duration-200',
          open ? 'ml-48' : 'ml-10',
        ].join(' ')}
      >
        <div className="p-6">{children}</div>
      </main>
    </div>
  )
}
