import { appHashHref } from '../app-base'

export default function TickerLink({ ticker, className = '', children, title }) {
  if (!ticker) return <span className={className}>—</span>

  return (
    <a
      href={appHashHref(`/detail/${encodeURIComponent(ticker)}`)}
      className={className}
      title={title || ticker}
    >
      {children || ticker}
    </a>
  )
}
