async function apiFetch(path, options = {}) {
  const res = await fetch(`/api${path}`, {
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

export const getDigestLatest = () => apiFetch('/digest/latest')
export const getDigestList = () => apiFetch('/digest/list')
export const getDigestByDate = (date) => apiFetch(`/digest/${date}`)
export const generateDigest = () =>
  apiFetch('/digest/generate', { method: 'POST', body: '{}' })

export const getScheduleStatus = () => apiFetch('/schedule/status')
export const getSchedulePlan = () => apiFetch('/schedule/plan')

export const getTree = () => apiFetch('/tree')

export const startDive = (ticker) =>
  apiFetch('/dive', { method: 'POST', body: JSON.stringify({ ticker }) })
export const listDives = () => apiFetch('/dive/list')
export const getDiveLatest = (ticker) => apiFetch(`/dive/${ticker}/latest`)

export const getJob = (jobId) => apiFetch(`/jobs/${jobId}`)

export const getStats = () => apiFetch('/stats')

export const queryDataset = ({ dataset, ticker, keyword, limit = 50 }) => {
  const params = new URLSearchParams({ dataset, limit })
  if (ticker) params.set('ticker', ticker)
  if (keyword) params.set('keyword', keyword)
  return apiFetch(`/query?${params}`)
}
