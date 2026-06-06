import { useState, useEffect, useRef } from 'react'
import { getDigestLatest, getDigestList, generateDigest, getJob } from '../api'

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

function DigestContent({ content }) {
  if (!content) return null
  const parts = content.split(/\n---+\n/)
  const jpPart = parts[0] || ''
  const enPart = parts.slice(1).join('\n---\n')

  return (
    <div className="space-y-4">
      {jpPart && (
        <div className="bg-amber-950/20 border border-amber-900/30 rounded-lg p-4">
          <p className="text-xs text-amber-600/80 uppercase tracking-wider mb-3 font-medium">
            Japanese
          </p>
          <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
            {jpPart.trim()}
          </pre>
        </div>
      )}
      {enPart && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3 font-medium">
            English
          </p>
          <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
            {enPart.trim()}
          </pre>
        </div>
      )}
      {!enPart && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
          <pre className="text-slate-300 text-xs leading-relaxed whitespace-pre-wrap font-mono break-words">
            {content.trim()}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function Digest() {
  const [digest, setDigest] = useState(null)
  const [digestList, setDigestList] = useState([])
  const [loading, setLoading] = useState(true)
  const [listLoading, setListLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState(null)
  const pollRef = useRef(null)

  const fetchLatest = () =>
    getDigestLatest()
      .then((d) => setDigest(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))

  const fetchList = () =>
    getDigestList()
      .then((d) => setDigestList(d))
      .catch(() => {})
      .finally(() => setListLoading(false))

  useEffect(() => {
    fetchLatest()
    fetchList()
  }, [])

  const handleGenerate = () => {
    setGenerating(true)
    setGenError(null)
    generateDigest()
      .then(({ job_id }) => {
        pollRef.current = setInterval(() => {
          getJob(job_id)
            .then((job) => {
              if (job.status === 'done') {
                clearInterval(pollRef.current)
                setGenerating(false)
                setLoading(true)
                fetchLatest()
                fetchList()
              } else if (job.status === 'error') {
                clearInterval(pollRef.current)
                setGenerating(false)
                setGenError(job.error || 'Job failed')
              }
            })
            .catch((e) => {
              clearInterval(pollRef.current)
              setGenerating(false)
              setGenError(e.message)
            })
        }, 2000)
      })
      .catch((e) => {
        setGenerating(false)
        setGenError(e.message)
      })
  }

  useEffect(() => () => clearInterval(pollRef.current), [])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Digest</h2>
          {digest?.date && (
            <p className="text-xs text-slate-500 mt-0.5">{digest.date}</p>
          )}
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-md transition-colors"
        >
          {generating && (
            <div className="w-3 h-3 border-t-2 border-white/70 rounded-full animate-spin" />
          )}
          {generating ? 'Generating...' : 'Regenerate'}
        </button>
      </div>

      {genError && <ErrorMsg msg={genError} />}

      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorMsg msg={error} />
      ) : digest ? (
        <DigestContent content={digest.content} />
      ) : (
        <div className="text-slate-600 text-sm py-8">No digest available.</div>
      )}

      {/* Past digests list */}
      <div className="mt-8">
        <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">
          Past Digests
        </h3>
        {listLoading ? (
          <Spinner small />
        ) : digestList.length === 0 ? (
          <p className="text-slate-600 text-sm">No past digests.</p>
        ) : (
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            {digestList.map((d, i) => (
              <div
                key={d.date}
                className={[
                  'flex items-center justify-between px-4 py-2.5 text-sm',
                  i !== digestList.length - 1 ? 'border-b border-slate-800' : '',
                ].join(' ')}
              >
                <span className="font-mono text-slate-300">{d.date}</span>
                <span className="text-slate-600 text-xs font-mono">
                  {d.size != null ? `${(d.size / 1024).toFixed(1)} KB` : '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
