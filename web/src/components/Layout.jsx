const TABS = [
  { id: 'candidates',  label: 'Candidates'  },
  { id: 'tree',       label: 'Tree'       },
  { id: 'watchlist',   label: 'Watchlist'   },
  { id: 'tickers',    label: 'Tickers'    },
  { id: 'system',     label: 'System'     },
]

export default function Layout({ activeTab, onTabChange, children }) {
  return (
    <div className="flex flex-col w-full min-h-screen">
      {/* Top bar */}
      <header
        className="flex items-center gap-5 px-7 h-[54px] sticky top-0 z-50 shrink-0"
        style={{
          background: 'rgba(7, 10, 14, 0.92)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(0, 220, 150, 0.1)',
        }}
      >
        {/* Logo */}
        <div
          className="flex items-center gap-2.5 font-mono font-bold uppercase shrink-0"
          style={{ color: '#00dc96', fontSize: '15px', letterSpacing: '0.25em' }}
        >
          <span
            className="rounded-full shrink-0"
            style={{
              width: 7, height: 7,
              background: '#00dc96',
              boxShadow: '0 0 8px rgba(0,220,150,0.5)',
            }}
          />
          ELEPHANT
          <span
            className="font-light normal-case"
            style={{ color: '#5a7080', fontSize: '12px', letterSpacing: '0.08em' }}
          >
            Stock Research
          </span>
        </div>

        {/* Nav tabs — scrollable on narrow screens */}
        <nav className="flex items-center gap-1 overflow-x-auto flex-1" style={{ scrollbarWidth: 'none' }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className="shrink-0 font-mono font-semibold uppercase rounded transition-all duration-180 whitespace-nowrap"
              style={{
                padding: '5px 12px',
                fontSize: '10px',
                letterSpacing: '0.12em',
                border: activeTab === tab.id
                  ? '1px solid #00dc96'
                  : '1px solid transparent',
                color: activeTab === tab.id ? '#00dc96' : '#5a7080',
                background: activeTab === tab.id ? 'rgba(0,220,150,0.08)' : 'transparent',
                boxShadow: activeTab === tab.id ? '0 0 10px rgba(0,220,150,0.2)' : 'none',
              }}
              onMouseEnter={e => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.color = '#bfcfdf'
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'
                }
              }}
              onMouseLeave={e => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.color = '#5a7080'
                  e.currentTarget.style.borderColor = 'transparent'
                }
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1100px] mx-auto px-7 py-7 pb-16">
          {children}
        </div>
      </main>
    </div>
  )
}
