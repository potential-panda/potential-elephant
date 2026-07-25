import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Tickers from './components/Tickers'
import Atlas from './components/Atlas'
import Dive from './components/Dive'
import Detail from './components/Detail'
import Candidates from './components/Candidates'
import Watchlist from './components/Watchlist'
import System from './components/System'

const TAB_COMPONENTS = {
  candidates: Candidates,
  atlas: Atlas,
  watchlist: Watchlist,
  tickers: Tickers,
  dive: Dive,
  system: System,
  detail: Detail,
}

function tabFromHash() {
  const hash = window.location.hash.slice(1).replace(/^\/+/, '').split('/')[0]
  if (hash === 'query' || hash === 'schedule' || hash === 'stats') return 'system'
  return TAB_COMPONENTS[hash] ? hash : 'candidates'
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash)

  useEffect(() => {
    const onHashChange = () => setActiveTab(tabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleTabChange = (tab) => {
    if (tab === 'tickers') {
      window.location.hash = '/tickers/JP'
    } else if (tab === 'system') {
      window.location.hash = '/system/query'
    } else {
      window.location.hash = `/${tab}`
    }
    setActiveTab(tab)
  }

  const ActiveComponent = TAB_COMPONENTS[activeTab] || Candidates

  return (
    <Layout activeTab={activeTab} onTabChange={handleTabChange}>
      <ActiveComponent />
    </Layout>
  )
}
