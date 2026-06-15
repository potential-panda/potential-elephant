import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Tickers from './components/Tickers'
import Digest from './components/Digest'
import Schedule from './components/Schedule'
import Tree from './components/Tree'
import Dive from './components/Dive'
import Query from './components/Query'
import Stats from './components/Stats'
import Detail from './components/Detail'
import Candidates from './components/Candidates'
import Watchlist from './components/Watchlist'
import Maintenance from './components/Maintenance'

const TAB_COMPONENTS = {
  candidates: Candidates,
  maintenance: Maintenance,
  watchlist:  Watchlist,
  tickers: Tickers,
  digest: Digest,
  schedule: Schedule,
  tree: Tree,
  dive: Dive,
  query: Query,
  stats: Stats,
  detail: Detail,
}

function tabFromHash() {
  const hash = window.location.hash.slice(1).split('/')[0]
  return TAB_COMPONENTS[hash] ? hash : 'digest'
}

export default function App() {
  const [activeTab, setActiveTab] = useState(tabFromHash)

  useEffect(() => {
    const onHashChange = () => setActiveTab(tabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleTabChange = (tab) => {
    window.location.hash = tab
    setActiveTab(tab)
  }

  const ActiveComponent = TAB_COMPONENTS[activeTab] || Tickers

  return (
    <Layout activeTab={activeTab} onTabChange={handleTabChange}>
      <ActiveComponent />
    </Layout>
  )
}
