'use client'

import { useAuth } from '@/context/AuthContext'
import { describeFreshness, useCompanySyncStatus, whenText } from '@/lib/sync-status'

/** A quiet line on screens people read figures from, shown only when the figures may be out of date:
 *  a balance read from stale books is the costly mistake. Nothing is shown while the company is synced. */
export function DataFreshnessNote({ className = '' }: { className?: string }) {
  const { user, token } = useAuth()
  const status = useCompanySyncStatus(token)?.find(s => s.company_id === user?.company_id)
  if (!status || status.freshness === 'live') return null
  const asOf = status.last_synced_at ? `Data as of ${whenText(status.last_synced_at)}.` : 'This company has not synced with Tally yet.'
  const why = status.freshness === 'behind' ? '' : ` ${describeFreshness(status).text.split('.')[0]}.`
  return (
    <p role="status" className={`rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-900 dark:text-amber-200 ${className}`}>
      {asOf}{why}
    </p>
  )
}
