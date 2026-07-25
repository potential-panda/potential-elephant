import { APP_BASE } from './app-base.js'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${APP_BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

async function api2Fetch(path, options = {}) {
  const res = await fetch(`${APP_BASE}/api2${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}

export const getTickers = () => apiFetch('/tickers')
export const getTickersV2 = () => api2Fetch('/tickers')
export const getTickersOverview = () => api2Fetch('/tickers/overview')
export const getCandidatesV2 = () => api2Fetch('/candidates')
export const getDetail = (ticker) => api2Fetch(`/detail/${encodeURIComponent(ticker)}`)

export const getDigestLatest = () => apiFetch('/digest/latest')
export const getDigestList = () => apiFetch('/digest/list')
export const getDigestByDate = (date) => apiFetch(`/digest/${date}`)
export const generateDigest = () =>
  apiFetch('/digest/generate', { method: 'POST', body: '{}' })

export const getScheduleStatus = () => apiFetch('/schedule/status')
export const getSchedulePlan = () => apiFetch('/schedule/plan')
export const getSourceSchedulerStatus = () => api2Fetch('/source-scheduler/status')
export const getSourceSchedulerPlan = () => api2Fetch('/source-scheduler/plan')
export const getSourceRuns = (limit = 20) => api2Fetch(`/source-runs?limit=${encodeURIComponent(limit)}`)
export const getSourceRegistry = () => api2Fetch('/source-registry')
export const getSourceDefinitions = (scope = 'ticker') => api2Fetch(`/sources?scope=${encodeURIComponent(scope)}`)

export const getAtlas = () => api2Fetch('/atlas')

export const startDive = (ticker) =>
  apiFetch('/dive', { method: 'POST', body: JSON.stringify({ ticker }) })
export const startDiveV2 = (ticker) =>
  api2Fetch('/dive', { method: 'POST', body: JSON.stringify({ ticker }) })
export const listDives = () => apiFetch('/dive/list')
export const getDiveLatest = (ticker) => apiFetch(`/dive/${ticker}/latest`)
export const recordDecision = ({ ticker, decision, reason = '', snapshot = {}, what_would_change = '', suppress_days = 30 }) =>
  apiFetch('/decisions', {
    method: 'POST',
    body: JSON.stringify({ ticker, decision, reason, snapshot, what_would_change, suppress_days }),
  })

export const getJob = (jobId) => apiFetch(`/jobs/${jobId}`)
export const getJobV2 = (jobId) => api2Fetch(`/jobs/${jobId}`)

export const getPriceChanges = (tickers) =>
  api2Fetch(`/prices?tickers=${encodeURIComponent(tickers.join(','))}`)

export const getStats = () => api2Fetch('/stats')
export const getWatchlistV2 = () => api2Fetch('/watchlist')
export const recordDecisionV2 = ({ ticker, decision, reason = '', snapshot = {}, what_would_change = '', suppress_days = 30 }) =>
  api2Fetch('/decisions', {
    method: 'POST',
    body: JSON.stringify({ ticker, decision, reason, snapshot, what_would_change, suppress_days }),
  })
export const removeDecisionV2 = (ticker) =>
  api2Fetch(`/decisions/${encodeURIComponent(ticker)}`, { method: 'DELETE' })


export const queryDataset = ({ dataset, ticker, keyword, limit = 50 }) => {
  const params = new URLSearchParams({ dataset, limit })
  if (ticker) params.set('ticker', ticker)
  if (keyword) params.set('keyword', keyword)
  return apiFetch(`/query?${params}`)
}
