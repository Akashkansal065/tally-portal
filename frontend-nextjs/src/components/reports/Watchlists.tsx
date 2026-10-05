'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Archive, Loader2, MessageCircle, Package, Phone, SlidersHorizontal, UserMinus } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { DeadStockClearance } from '@/components/reports/DeadStockClearance'
import { cn } from '@/lib/utils'
import {
  getReorderAlerts,
  getWatchlist,
  remember,
  remembered,
  rupees,
  rupeesShort,
  whatsappLink,
  type ReorderItem,
  type WatchlistCriteria,
  type WatchlistCustomer,
} from '@/lib/report-insights'

export const DEFAULT_WATCHLIST: WatchlistCriteria = { drop_pct: 50, gap_multiplier: 2, window_days: 90, min_gap_days: 30 }
export const REORDER_DEFAULT = { cover_days: 14, lookback_days: 30 }

export type WatchlistView = 'customers' | 'reorder' | 'dead'

const formatDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

/** "sells 2.5 a day", or for slow items "sells about 1 every 3 days" */
const salesRate = (perDay: number, unit: string) =>
  perDay >= 1
    ? `sells ${Number(perDay.toFixed(1))} ${unit} a day`
    : `sells about 1 every ${Math.round(1 / perDay)} days`


/** Reports → Watchlists: customers buying less or later than usual, and items about to run out. */
export function Watchlists({ view, onViewChange }: { view: WatchlistView; onViewChange: (view: WatchlistView) => void }) {
  return (
    <div className="space-y-4">
      <div className="flex max-w-full overflow-x-auto rounded-xl bg-muted p-1 [scrollbar-width:none] sm:inline-flex" role="tablist" aria-label="Watchlist">
        {([
          { id: 'customers', label: 'Customers buying less', icon: UserMinus },
          { id: 'reorder', label: 'Running out', icon: Package },
          { id: 'dead', label: 'Dead stock', icon: Archive },
        ] as const).map(tab => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={view === tab.id}
            onClick={() => onViewChange(tab.id)}
            className={cn(
              'inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg px-3.5 text-sm font-semibold transition-colors cursor-pointer',
              view === tab.id ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <tab.icon className="h-4 w-4" aria-hidden="true" />
            {tab.label}
          </button>
        ))}
      </div>
      {view === 'customers' ? <CustomerWatchlist /> : view === 'reorder' ? <ReorderAlerts /> : <DeadStockClearance />}
    </div>
  )
}

// ─── Customers buying less ───────────────────────────────────────────────────

function CustomerWatchlist() {
  const { token } = useAuth()
  const [criteria, setCriteria] = useState<WatchlistCriteria>(() => remembered('watchlist_criteria', DEFAULT_WATCHLIST))
  const [data, setData] = useState<{ customers: WatchlistCustomer[]; checked: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (!token) return
    let current = true
    getWatchlist(token, criteria)
      .then(d => { if (current) { setData(d); setError(null) } })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load the watchlist') })
    return () => { current = false }
  }, [token, criteria])

  const apply = (next: WatchlistCriteria) => {
    remember('watchlist_criteria', next)
    setData(null)
    setCriteria(next)
    setEditing(false)
  }

  return (
    <section aria-labelledby="watchlist-title" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="watchlist-title" className="text-lg font-extrabold">Customers buying less</h2>
          <p className="text-sm text-muted-foreground">
            Sales down more than {criteria.drop_pct}% vs the previous {criteria.window_days} days, or no order for
            longer than {criteria.gap_multiplier}× their usual gap (at least {criteria.min_gap_days} days).
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer"
        >
          <SlidersHorizontal className="h-4 w-4" /> Conditions
        </button>
      </div>

      {error ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
      ) : !data ? (
        <Loading />
      ) : data.customers.length === 0 ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          All {data.checked} customers are buying at their usual pace.
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {data.customers.map(c => (
            <li key={c.ledger_id} className="space-y-2 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <Link href={`/customers/tally_${c.ledger_id}`} className="font-bold hover:underline">{c.name}</Link>
                  <p className="text-xs text-muted-foreground">
                    {[c.city, c.pincode && !c.city ? c.pincode : null].filter(Boolean).join(' · ') || 'City not set'}
                    {' · '}last order {formatDay(c.last_invoice)}
                  </p>
                </div>
                {c.change_pct !== null && c.change_pct < 0 && (
                  <span className="shrink-0 rounded-full bg-rose-500/10 px-2 py-0.5 text-sm font-bold text-rose-700 dark:text-rose-400">
                    ↓ {Math.abs(Math.round(c.change_pct))}%
                  </span>
                )}
              </div>
              <ul className="flex flex-wrap gap-1.5 text-xs">
                {c.reasons.includes('dropped') && (
                  <li className="rounded-full bg-muted px-2 py-0.5">
                    {rupeesShort(c.recent_sales)} in the last {criteria.window_days} days (was {rupeesShort(c.previous_sales)})
                  </li>
                )}
                {c.reasons.includes('late') && (
                  <li className="rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-800 dark:text-amber-300">
                    {c.days_since_last} days since last order
                    {c.usual_gap_days ? ` (usually every ${Math.round(c.usual_gap_days)})` : ''}
                  </li>
                )}
                {c.outstanding > 0 && (
                  <li className={cn('rounded-full px-2 py-0.5', c.overdue > 0 ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400' : 'bg-muted')}>
                    Owes {rupees(c.outstanding)}{c.overdue > 0 ? ` · ${rupees(c.overdue)} overdue` : ''}
                  </li>
                )}
              </ul>
              {c.phone && (
                <div className="flex gap-2 pt-1">
                  <a href={`tel:${c.phone}`} className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted">
                    <Phone className="h-4 w-4" /> Call
                  </a>
                  <a
                    href={whatsappLink(c.phone)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-400"
                  >
                    <MessageCircle className="h-4 w-4" /> WhatsApp
                  </a>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <ConditionsSheet
        open={editing}
        onOpenChange={setEditing}
        title="Watchlist conditions"
        fields={[
          { key: 'drop_pct', label: 'Sales dropped by more than (%)', min: 1, max: 100, presets: [30, 50, 70] },
          { key: 'window_days', label: 'Compare the last … days with the … days before', min: 7, max: 365, presets: [30, 60, 90, 180] },
          { key: 'gap_multiplier', label: 'Late when the wait is more than … × their usual gap', min: 1, max: 10, step: 0.5, presets: [1.5, 2, 3] },
          { key: 'min_gap_days', label: 'Never flag a wait shorter than (days)', min: 1, max: 365, presets: [15, 30, 45] },
        ]}
        values={criteria}
        defaults={DEFAULT_WATCHLIST}
        onApply={values => apply(values as unknown as WatchlistCriteria)}
      />
    </section>
  )
}

// ─── Items about to run out ──────────────────────────────────────────────────

function ReorderAlerts() {
  const { token } = useAuth()
  const [criteria, setCriteria] = useState(() => remembered('reorder_criteria', REORDER_DEFAULT))
  const [items, setItems] = useState<ReorderItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    if (!token) return
    let current = true
    getReorderAlerts(token, criteria.cover_days, criteria.lookback_days)
      .then(d => { if (current) { setItems(d.items); setError(null) } })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load reorder alerts') })
    return () => { current = false }
  }, [token, criteria])

  return (
    <section aria-labelledby="reorder-title" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="reorder-title" className="text-lg font-extrabold">Running out</h2>
          <p className="text-sm text-muted-foreground">
            Items whose stock lasts under {criteria.cover_days} days at their average sales over the last {criteria.lookback_days} days.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer"
        >
          <SlidersHorizontal className="h-4 w-4" /> Conditions
        </button>
      </div>

      {error ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
      ) : !items ? (
        <Loading />
      ) : items.length === 0 ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Nothing selling is due to run out within {criteria.cover_days} days.
        </p>
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
          {items.map(i => (
            <li key={i.stock_item_id} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="truncate font-bold">{i.name}</p>
                <p className="text-xs text-muted-foreground">
                  {i.group ? `${i.group} · ` : ''}{i.stock} {i.unit} left · {salesRate(i.per_day, i.unit)}
                </p>
                {i.suggested_order > 0 && (
                  <p className="text-xs font-semibold">Order about {i.suggested_order} {i.unit} for 30 days</p>
                )}
              </div>
              <span
                className={cn(
                  'shrink-0 rounded-full px-2.5 py-1 text-sm font-bold tabular-nums',
                  i.out_of_stock || i.days_left < 3
                    ? 'bg-rose-500/10 text-rose-700 dark:text-rose-400'
                    : 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
                )}
              >
                {i.out_of_stock ? 'Out of stock' : `${Math.max(1, Math.floor(i.days_left))} day${Math.floor(i.days_left) === 1 ? '' : 's'}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      <ConditionsSheet
        open={editing}
        onOpenChange={setEditing}
        title="Running-out conditions"
        fields={[
          { key: 'cover_days', label: 'Alert when stock lasts fewer than (days)', min: 1, max: 365, presets: [7, 14, 30] },
          { key: 'lookback_days', label: 'Average sales over the last (days)', min: 7, max: 365, presets: [14, 30, 60, 90] },
        ]}
        values={criteria}
        defaults={REORDER_DEFAULT}
        onApply={values => {
          const next = values as typeof REORDER_DEFAULT
          remember('reorder_criteria', next)
          setItems(null)
          setCriteria(next)
          setEditing(false)
        }}
      />
    </section>
  )
}

// ─── Shared pieces ───────────────────────────────────────────────────────────

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card p-8 text-sm text-muted-foreground" role="status">
      <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading…
    </div>
  )
}

interface ConditionField {
  key: string
  label: string
  min: number
  max: number
  step?: number
  presets: number[]
}

/** Edit report conditions: quick-pick values or type one, with a reset to the defaults. */
function ConditionsSheet({ open, onOpenChange, title, fields, values, defaults, onApply }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  fields: ConditionField[]
  values: object
  defaults: object
  onApply: (values: Record<string, number>) => void
}) {
  const [draft, setDraft] = useState<Record<string, string>>({})
  const current = values as Record<string, number>

  const valueOf = (f: ConditionField) => draft[f.key] ?? String(current[f.key])
  const invalid = fields.some(f => {
    const n = Number(valueOf(f))
    return !Number.isFinite(n) || n < f.min || n > f.max
  })

  return (
    <BottomSheet
      open={open}
      onOpenChange={next => { if (!next) setDraft({}); onOpenChange(next) }}
      title={title}
      headerAction={
        <button
          type="button"
          onClick={() => setDraft(Object.fromEntries(Object.entries(defaults).map(([k, v]) => [k, String(v)])))}
          className="min-h-11 rounded-lg px-2 text-sm font-semibold text-primary cursor-pointer"
        >
          Reset
        </button>
      }
      footer={
        <button
          type="button"
          disabled={invalid}
          onClick={() => { onApply(Object.fromEntries(fields.map(f => [f.key, Number(valueOf(f))]))); setDraft({}) }}
          className="flex min-h-12 w-full items-center justify-center rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer"
        >
          Apply
        </button>
      }
    >
      <div className="space-y-5">
        {fields.map(f => (
          <fieldset key={f.key}>
            <legend className="mb-2 text-sm font-semibold">{f.label}</legend>
            <div className="flex flex-wrap items-center gap-2">
              {f.presets.map(p => (
                <button
                  key={p}
                  type="button"
                  aria-pressed={Number(valueOf(f)) === p}
                  onClick={() => setDraft(d => ({ ...d, [f.key]: String(p) }))}
                  className={cn(
                    'min-h-10 min-w-12 rounded-full border px-3 text-sm font-semibold cursor-pointer',
                    Number(valueOf(f)) === p ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted',
                  )}
                >
                  {p}
                </button>
              ))}
              <input
                type="number"
                inputMode="decimal"
                min={f.min}
                max={f.max}
                step={f.step ?? 1}
                value={valueOf(f)}
                onChange={e => setDraft(d => ({ ...d, [f.key]: e.target.value }))}
                aria-label={f.label}
                className="h-10 w-24 rounded-xl border border-border bg-background px-3 text-sm tabular-nums focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </fieldset>
        ))}
      </div>
    </BottomSheet>
  )
}
