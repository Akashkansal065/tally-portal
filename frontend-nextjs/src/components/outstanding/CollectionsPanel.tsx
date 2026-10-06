'use client'

import { useEffect, useState } from 'react'
import { BellRing, Loader2, MessageCircle, Phone } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { getCollections, rupees, rupeesShort, type Collections } from '@/lib/report-insights'

const SHOWN = 8

const monthLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { month: 'short' })

/**
 * Outstanding → who to chase first (overdue amount weighted by how late it is) and how long customers take
 * to pay (days sales outstanding, DSO) by month-end. Reminders reuse the screen's WhatsApp reminder flow.
 */
export function CollectionsPanel({ reloadKey, onRemind, onSchedule }: {
  reloadKey: number
  onRemind: (ledgerId: number) => void
  /** Automatic email / WhatsApp reminders for this customer */
  onSchedule?: (ledgerId: number, name: string) => void
}) {
  const { token } = useAuth()
  const [data, setData] = useState<Collections | null>(null)
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    // reloadKey starts at 0 and is bumped after the page's own load, so this loads once alongside it
    if (!token || reloadKey === 0) return
    let current = true
    getCollections(token).then(d => { if (current) setData(d) }).catch(() => {})
    return () => { current = false }
  }, [token, reloadKey])

  if (!data) {
    return (
      <div className="flex h-32 items-center justify-center rounded-2xl border border-border bg-card" role="status">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <span className="sr-only">Loading collections</span>
      </div>
    )
  }

  const dso = data.dso
  const previous = data.dso_last_month_end
  const better = dso !== null && previous !== null && dso <= previous
  const trend = data.dso_trend.filter(t => t.dso !== null)
  const highest = Math.max(1, ...trend.map(t => t.dso as number))
  const overduePoints = data.overdue_trend.filter(t => t.overdue !== null)
  const list = showAll ? data.chase : data.chase.slice(0, SHOWN)

  return (
    <section aria-labelledby="collections-title" className="rounded-2xl border border-border bg-card shadow-sm">
      <div className="grid gap-4 border-b border-border p-4 sm:grid-cols-2">
        <div>
          <h2 id="collections-title" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Days to get paid</h2>
          <p className="mt-1 text-2xl font-black tabular-nums">
            {dso !== null ? `${Math.round(dso)} days` : '—'}
          </p>
          {dso !== null && previous !== null && (
            <p className={cn('text-xs font-semibold', better ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400')}>
              {better ? '↓' : '↑'} {Math.abs(Math.round(dso - previous))} days vs last month-end ({Math.round(previous)}) · {better ? 'better' : 'slower'}
            </p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">What customers owe ÷ the last 90 days&apos; billing × 90.</p>
        </div>
        {trend.length > 1 && (
          <div aria-label="Days to get paid at each month-end" role="img">
            <div className="flex h-16 items-end gap-1.5">
              {trend.map((t, i) => (
                <div key={t.day} className="flex flex-1 flex-col items-center gap-1">
                  <div
                    className={cn('w-full rounded-t-md', i === trend.length - 1 ? 'bg-primary' : 'bg-muted-foreground/30')}
                    style={{ height: `${Math.max(6, ((t.dso as number) / highest) * 56)}px` }}
                    title={`${Math.round(t.dso as number)} days`}
                  />
                </div>
              ))}
            </div>
            <div className="mt-1 flex gap-1.5 text-center text-xs text-muted-foreground">
              {trend.map((t, i) => <span key={t.day} className="flex-1">{i === trend.length - 1 ? 'Now' : monthLabel(t.day)}</span>)}
            </div>
          </div>
        )}
      </div>

      <div className="p-4">
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <h3 className="font-bold">Chase first</h3>
          <span className="text-xs text-muted-foreground">
            {rupees(data.overdue)} overdue · {data.overdue_customers} customer{data.overdue_customers === 1 ? '' : 's'}
            {overduePoints.length > 1 && (() => {
              const diff = (overduePoints[overduePoints.length - 1].overdue as number) - (overduePoints[0].overdue as number)
              return <> · {diff <= 0 ? '↓' : '↑'} {rupeesShort(Math.abs(diff))} since {new Date(`${overduePoints[0].day}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</>
            })()}
          </span>
        </div>
        {data.chase.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nobody is past their credit days.</p>
        ) : (
          <ol className="divide-y divide-border">
            {list.map((c, i) => (
              <li key={c.ledger_id} className="flex gap-3 py-3">
                <span className="w-5 shrink-0 pt-0.5 text-sm font-bold text-muted-foreground">{i + 1}</span>
                <div className="min-w-0 flex-1 sm:flex sm:items-center sm:justify-between sm:gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">{c.name}</p>
                  <p className="text-xs text-muted-foreground">
                    <span className="font-semibold text-foreground">{rupees(c.overdue)}</span> overdue · on average {c.average_days_late} days late
                    (oldest {c.oldest_days_late}) · credit {c.credit_days}d
                  </p>
                </div>
                <div className="mt-2 flex shrink-0 gap-2 sm:mt-0">
                  {c.phone && (
                    <a href={`tel:${c.phone}`} className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border hover:bg-muted" aria-label={`Call ${c.name}`}>
                      <Phone className="h-4 w-4" />
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => onRemind(c.ledger_id)}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-emerald-600 px-3 text-sm font-semibold text-white hover:bg-emerald-700 cursor-pointer"
                  >
                    <MessageCircle className="h-4 w-4" /> Remind
                  </button>
                  {onSchedule && (
                    <button
                      type="button"
                      onClick={() => onSchedule(c.ledger_id, c.name)}
                      className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer"
                      aria-label={`Automatic reminders for ${c.name}`}
                    >
                      <BellRing className="h-4 w-4" /> Auto
                    </button>
                  )}
                </div>
                </div>
              </li>
            ))}
          </ol>
        )}
        {data.chase.length > SHOWN && (
          <button
            type="button"
            onClick={() => setShowAll(s => !s)}
            className="mt-2 min-h-10 w-full rounded-xl border border-border text-sm font-semibold hover:bg-muted cursor-pointer"
          >
            {showAll ? 'Show fewer' : `Show all ${data.chase.length}`}
          </button>
        )}
      </div>
    </section>
  )
}
