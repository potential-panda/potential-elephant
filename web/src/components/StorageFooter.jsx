export default function StorageFooter({ paths }) {
  if (!paths || paths.length === 0) return null
  const list = Array.isArray(paths) ? paths : [paths]
  return (
    <div className="mt-6 pt-4 border-t border-slate-800">
      <p className="text-xs text-slate-600">
        {list.map((p, i) => (
          <span key={p}>
            {i > 0 && <span className="mx-2 text-slate-700">·</span>}
            <span className="font-mono text-slate-500">{p}</span>
          </span>
        ))}
      </p>
    </div>
  )
}
