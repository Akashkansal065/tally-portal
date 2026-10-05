'use client'

import { useEffect, useState } from 'react'
import { Loader2, MessageCircle } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import {
  getDeadStock,
  remember,
  remembered,
  rupees,
  rupeesShort,
  whatsappLink,
  type DeadStock,
  type DeadStockItem,
} from '@/lib/report-insights'

const DAY_CHOICES = [60, 90, 180, 365]
const PAGE = 40

const BAND_TONE: Record<string, string> = {
  'Under 180 days': 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
  '180–365 days': 'bg-orange-500/10 text-orange-800 dark:text-orange-300',
  'Over 365 days': 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
  'Never sold': 'bg-muted text-foreground',
}

const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })

/** Watchlists → Dead stock: what to clear, how long it has sat, and who bought it before (to offer it to). */
export function DeadStockClearance() {
  const { token } = useAuth()
  // Shared with the "No sale for" picker on Company Stock → Dead stock
  const [days, setDays] = useState(() => remembered('dead_stock', { days: 90 }).days)
  const [data, setData] = useState<DeadStock | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [shown, setShown] = useState(PAGE)

  useEffect(() => {
    if (!token) return
    let current = true
    getDeadStock(token, days)
      .then(d => { if (current) { setData(d); setError(null) } })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load dead stock') })
    return () => { current = false }
  }, [token, days])

  const choose = (next: number) => {
    remember('dead_stock', { days: next })
    setData(null)
    setShown(PAGE)
    setDays(next)
  }

  return (
    <section aria-labelledby="dead-title" className="space-y-3">
      <div>
        <h2 id="dead-title" className="text-lg font-extrabold">Dead stock</h2>
        <p className="text-sm text-muted-foreground">In stock with no sale for {days} days, or never sold. Value at cost.</p>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="No sale for">
        {DAY_CHOICES.map(d => (
          <button
            key={d}
            type="button"
            aria-pressed={days === d}
            onClick={() => choose(d)}
            className={cn('min-h-10 rounded-full border px-3.5 text-sm font-semibold cursor-pointer',
              days === d ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted')}
          >
            {d} days
          </button>
        ))}
      </div>

      {error ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
      ) : !data ? (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card p-8 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading…
        </div>
      ) : data.count === 0 ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Everything in stock has sold within the last {days} days.
        </p>
      ) : (
        <>
          <div className="rounded-2xl border border-border bg-card p-4">
            <p className="text-2xl font-black tabular-nums">
              {rupees(data.total_value)}
              <span className="ml-1.5 text-sm font-semibold text-muted-foreground">locked in {data.count} items</span>
            </p>
            <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
              {data.bands.filter(b => b.count > 0).map(b => (
                <li key={b.band} className={cn('rounded-full px-2 py-0.5 font-semibold', BAND_TONE[b.band])}>
                  {b.band}: {rupeesShort(b.value)} · {b.count}
                </li>
              ))}
            </ul>
            <Trend data={data} />
          </div>

          <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
            {data.items.slice(0, shown).map(item => <DeadItem key={item.stock_item_id} item={item} />)}
          </ul>
          {data.items.length > shown && (
            <button
              type="button"
              onClick={() => setShown(s => s + PAGE)}
              className="min-h-12 w-full rounded-2xl border border-border bg-card text-sm font-semibold hover:bg-muted cursor-pointer"
            >
              Show more ({data.items.length - shown} left)
            </button>
          )}
        </>
      )}
    </section>
  )
}

function Trend({ data }: { data: DeadStock }) {
  const points = data.trend.filter(t => t.value !== null)
  if (points.length < 2) {
    return (
      <p className="mt-2 text-xs text-muted-foreground">
        The trend of money locked (at {data.trend_days} days) starts today and builds up day by day.
      </p>
    )
  }
  const first = points[0].value!, last = points[points.length - 1].value!
  const diff = last - first
  return (
    <p className={cn('mt-2 text-xs font-semibold', diff <= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400')}>
      {diff <= 0 ? 'Down' : 'Up'} {rupeesShort(Math.abs(diff))} since {shortDate(points[0].day)} (measured at {data.trend_days} days)
    </p>
  )
}

function DeadItem({ item }: { item: DeadStockItem }) {
  const offer = (name: string) =>
    `Hello ${name}, we have ${item.name} in stock at a special price. Would you like some? Reply with the quantity.`
  return (
    <li className="space-y-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-bold">{item.name}</p>
          <p className="text-xs text-muted-foreground">
            {item.group ? `${item.group} · ` : ''}{item.stock} {item.unit} ·{' '}
            {item.last_sold
              ? `last sold ${item.days_since_sale} days ago`
              : item.in_stock_since ? `never sold, in stock since ${shortDate(item.in_stock_since)}` : 'never sold'}
          </p>
        </div>
        <span className="shrink-0 text-base font-black tabular-nums">{rupeesShort(item.value)}</span>
      </div>
      {item.buyers.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold text-muted-foreground">Bought before by</p>
          <ul className="flex flex-wrap gap-2">
            {item.buyers.map(b => (
              <li key={b.ledger_id}>
                {b.phone ? (
                  <a
                    href={whatsappLink(b.phone, offer(b.name))}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-400"
                    title={`Offer on WhatsApp (bought ${b.quantity} ${item.unit})`}
                  >
                    <MessageCircle className="h-4 w-4" /> {b.name}
                  </a>
                ) : (
                  <span className="inline-flex min-h-10 items-center rounded-xl border border-dashed border-border px-3 text-sm">{b.name}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  )
}
