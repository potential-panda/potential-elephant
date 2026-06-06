import { useState } from 'react'
import Layout from './components/Layout'
import Tickers from './components/Tickers'
import Digest from './components/Digest'
import Schedule from './components/Schedule'
import Tree from './components/Tree'
import Dive from './components/Dive'
import Query from './components/Query'
import Stats from './components/Stats'

const TAB_COMPONENTS = {
  tickers: Tickers,
  digest: Digest,
  schedule: Schedule,
  tree: Tree,
  dive: Dive,
  query: Query,
  stats: Stats,
}

export default function App() {
  const [activeTab, setActiveTab] = useState('tickers')

  const ActiveComponent = TAB_COMPONENTS[activeTab] || Tickers

  return (
    <Layout activeTab={activeTab} onTabChange={setActiveTab}>
      <ActiveComponent />
    </Layout>
  )
}
