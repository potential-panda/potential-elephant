import { useState, useEffect, useRef } from 'react'
import { startDive, listDives, getDiveLatest, getJob } from '../api'

function Spinner({ small }) {
  return (
    <div className={['flex items-center gap-2 text-slate-500', small ? '' : 'py-8'].join(' ')}>
      <div className="w-4 h-4 border-t-2 border-emerald-400 rounded-full animate-spin shrink-0" />
      {!small && 'Loading...'}
    </div>
  )
}

function ErrorMsg({ msg }) {
  return (
    <div className="text-red-400 bg-red-950/30 border border-red-800/50 rounded px-4 py-3 text-sm">
      Error: {msg}
    </div>
  )
}

export default function Dive() {
  const [ticker, setTicker] = useState('')
  const [diving, setDiving] = useState(false)
  const [diveError, setDiveError] = useState(null)
  const [result, setResult] = useState(null)
  const [resultTicker, setResultTicker] = useState(null)
  const [resultDate, setResultDate] = useState(null)

  const [dives, setDives] = useState([])
  const [divesLoading, setDivesLoading] = useState(true)
  const [divesError, setDivesError] = useState(null)

  const pollRef = useRef(null)

  const fetchDives = () =>
    listDives()
      .then((d) => setDives(d))
      .catch((e) => setDivesError(e.message))
      .finally(() => setDivesLoading(false))

  useEffect(() => {
    fetchDives()
    return () => clearInterval(pollRef.current)
  }, [])

  const handleDive = (e) => {
    e.preventDefault()
    const t = ticker.trim().toUpperCase()
    if (!t) return
    setDiving(true)
    setDiveError(null)
    setResult(null)

    startDive(t)
      .then(({ job_id }) => {
        pollRef.current = setInterval(() => {
          getJob(job_id)
            .then((job) => {
              if (job.status === 'done') {
                clearInterval(pollRef.current)
                setDiving(false)
                const normalizedTicker = job.ticker || t
                getDiveLatest(normalizedTicker)
                  .then((d) => {
                    setResult(d.content)
                    setResultTicker(d.ticker)
                    setResultDate(d.date)
                  })
                  .catch((e) => setDiveError(e.message))
                fetchDives()
              } else if (job.status === 'error') {
                clearInterval(pollRef.current)
                setDiving(false)
                setDiveError(job.error || 'Job failed')
              }
            })
            .catch((e) => {
              clearInterval(pollRef.current)
              setDiving(false)
              setDiveError(e.message)
            })
        }, 2000)
      })
      .catch((e) => {
        setDiving(false)
        setDiveError(e.message)
      })
  }

  const loadDive = (d) => {
    getDiveLatest(d.ticker)
      .then((data) => {
        setResult(data.content)
        setResultTicker(data.ticker)
        setResultDate(data.date)
        setDiveError(null)
      })
      .catch((e) => setDiveError(e.message))
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Dive</h2>

        <form onSubmit={handleDive} className="flex gap-2 items-stretch mb-4">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker (e.g. 9984)"
            className="flex-1 max-w-xs bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-600 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50"
          />
          <button
            type="submit"
            disabled={diving || !ticker.trim()}
            className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-md transition-colors"
          >
            {diving && (
              <div className="w-3 h-3 border-t-2 border-white/70 rounded-full animate-spin" />
            )}
            {diving ? 'Diving...' : 'Dive'}
          </button>
        </form>

        {diveError && <ErrorMsg msg={diveError} />}
      </div>

      {result && (
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono font-semibold text-emerald-400">{resultTicker}</span>
            {resultDate && <span className="text-slate-500 text-xs">{resultDate}</span>}
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
            <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
              {result}
            </pre>
          </div>
        </div>
      )}

      {/* Past dives */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Past Dives
        </h3>
        {divesLoading ? (
          <Spinner small />
        ) : divesError ? (
          <ErrorMsg msg={divesError} />
        ) : dives.length === 0 ? (
          <p className="text-slate-600 text-sm">No past dives.</p>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            {dives.map((d, i) => (
              <button
                key={i}
                onClick={() => loadDive(d)}
                className={[
                  'w-full flex items-center justify-between px-4 py-2.5 text-sm text-left hover:bg-slate-800/50 transition-colors',
                  i !== dives.length - 1 ? 'border-b border-slate-800' : '',
                ].join(' ')}
              >
                <span className="font-mono font-semibold text-emerald-400">{d.ticker}</span>
                <span className="text-slate-500 text-xs font-mono">{d.date}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
