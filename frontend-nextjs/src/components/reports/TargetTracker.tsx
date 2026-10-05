'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Archive, ChevronRight, Loader2, Package, Pencil, Target, UserMinus } from 'lucide-react'
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { isAdminUser } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import {
  getDeadStock,
  getReorderAlerts,
  getSalesTarget,
  getWatchlist,
  remembered,
  rupees,
  rupeesShort,
  updateReportSettings,
  type SalesTarget,
} from '@/lib/report-insights'
import { DEFAULT_WATCHLIST, REORDER_DEFAULT } from '@/components/reports/Watchlists'

const monthName = (month: string) =>
  new Date(`${month}-01T00:00:00`).toLocaleDateString('en-IN', { month: 'long' })

/**
 * Home's first card: this month's net sales (before GST, all companies) against the monthly target, what's
 * needed per remaining day, and where the month ends at the current pace. Admins can change the target here.
 */
export function TargetTracker() {
  const { token, user, permissions } = useAuth()
  const isAdmin = isAdminUser(permissions, user?.role)
  const [data, setData] = useState<SalesTarget | null>(null)
  const [failed, setFailed] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!token) return
    let current = true
    getSalesTarget(token)
      .then(d => { if (current) { setData(d); setFailed(false) } })
      .catch(() => { if (current) setFailed(true) })
    return () => { current = false }
  }, [token, reloadKey])

  const saveTarget = async () => {
    const value = Number(draft.replace(/[^\d.]/g, ''))
    if (!token || !Number.isFinite(value) || value <= 0) {
      toast.error('Enter the monthly target in rupees')
      return
    }
    setSaving(true)
    try {
      await updateReportSettings(token, { monthly_sales_target: value })
      setEditing(false)
      setReloadKey(k => k + 1)
      toast.success('Target saved')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save the target')
    } finally {
      setSaving(false)
    }
  }

  if (failed) return null
  if (!data) {
    return (
      <div className="flex h-44 items-center justify-center rounded-2xl border border-border bg-card" role="status">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        <span className="sr-only">Loading the sales target</span>
      </div>
    )
  }

  const pct = data.achieved_pct ?? 0
  const short = data.on_track === false
  const multiCompany = data.companies.length > 1

  return (
    <section aria-labelledby="target-title" className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="target-title" className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            <Target className="h-3.5 w-3.5" aria-hidden="true" />
            {monthName(data.month)} target
            {multiCompany && <span className="normal-case tracking-normal font-semibold">· all companies</span>}
          </h2>
          <p className="mt-1 text-2xl font-black tracking-tight tabular-nums">
            {rupees(data.sales)}
            <span className="ml-1.5 text-sm font-semibold text-muted-foreground">of {rupeesShort(data.target)}</span>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <span className={cn('text-xl font-black tabular-nums', pct >= 100 ? 'text-emerald-600 dark:text-emerald-400' : 'text-foreground')}>
            {Math.round(pct)}%
          </span>
          {isAdmin && (
            <button
              type="button"
              onClick={() => { setDraft(String(Math.round(data.target))); setEditing(true) }}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer"
              aria-label="Change monthly target"
            >
              <Pencil className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div
        className="mt-3 h-2.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(100, Math.round(pct))}
        aria-label="Share of the monthly target reached"
      >
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <dt className="text-xs text-muted-foreground">Need per day</dt>
          <dd className="text-base font-bold tabular-nums">
            {data.remaining > 0 ? rupees(data.needed_per_day) : 'Target met'}
          </dd>
          <dd className="text-xs text-muted-foreground">
            {data.days_left} day{data.days_left === 1 ? '' : 's'} left, today included
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Projected month-end</dt>
          <dd className="text-base font-bold tabular-nums">{rupeesShort(data.projected)}</dd>
          {data.on_track !== null && (
            <dd className={cn('text-xs font-semibold', short ? 'text-amber-700 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400')}>
              {short ? `Short by ${rupeesShort(data.target - data.projected)} at this pace` : 'On track'}
            </dd>
          )}
        </div>
      </dl>

      {data.daily.length > 1 && (
        <div className="mt-3 h-20" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data.daily} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" hide />
              <Tooltip
                formatter={(value, name) => [rupees(Number(value)), name === 'cumulative' ? 'Sales so far' : 'Target pace']}
                labelFormatter={label => new Date(`${label}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                contentStyle={{ borderRadius: 12, fontSize: 12 }}
              />
              <Area type="monotone" dataKey="cumulative" stroke="var(--color-primary)" fill="var(--color-primary)" fillOpacity={0.15} strokeWidth={2} />
              <Line type="linear" dataKey="target_cumulative" stroke="#94a3b8" strokeDasharray="4 4" dot={false} strokeWidth={1.5} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {multiCompany && (
        <p className="mt-2 text-xs text-muted-foreground">
          {data.companies.map(c => `${c.name} ${rupeesShort(c.sales)}`).join(' · ')}
        </p>
      )}
      <p className="mt-1 text-xs text-muted-foreground">Net sales before GST, after returns.</p>

      <BottomSheet
        open={editing}
        onOpenChange={setEditing}
        title="Monthly sales target"
        description="Net sales before GST, across all companies. Applies to every month."
        footer={
          <button
            type="button"
            onClick={saveTarget}
            disabled={saving}
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-60 cursor-pointer"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save target
          </button>
        }
      >
        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold">Target (₹)</span>
          <input
            inputMode="numeric"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            className="h-12 w-full rounded-xl border border-border bg-background px-3 text-lg font-bold tabular-nums focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          {Number(draft) > 0 && <span className="mt-1 block text-sm text-muted-foreground">{rupeesShort(Number(draft))} a month</span>}
        </label>
      </BottomSheet>
    </section>
  )
}

/** Counts from the watchlists, linking to them: customers buying less and items about to run out. */
export function NeedsAttention() {
  const { token } = useAuth()
  const [counts, setCounts] = useState<{ customers: number; items: number; deadValue: number; deadItems: number } | null>(null)

  useEffect(() => {
    if (!token) return
    let current = true
    // Same thresholds the person last used on the Watchlists tab
    const criteria = remembered('watchlist_criteria', DEFAULT_WATCHLIST)
    const reorder = remembered('reorder_criteria', REORDER_DEFAULT)
    const deadDays = remembered('dead_stock', { days: 90 }).days
    Promise.all([getWatchlist(token, criteria), getReorderAlerts(token, reorder.cover_days), getDeadStock(token, deadDays)])
      .then(([w, r, d]) => {
        if (current) setCounts({ customers: w.customers.length, items: r.items.length, deadValue: d.total_value, deadItems: d.count })
      })
      .catch(() => {})
    return () => { current = false }
  }, [token])

  if (!counts || (counts.customers === 0 && counts.items === 0 && counts.deadItems === 0)) return null

  const tile = 'flex min-h-14 items-center gap-3 rounded-2xl border border-border bg-card px-3.5 py-2.5 hover:bg-muted/60'
  return (
    <section aria-label="Needs attention" className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {counts.customers > 0 && (
        <Link href="/reports?tab=watchlists&sub=customers" className={tile}>
          <UserMinus className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          <span className="min-w-0 flex-1 text-sm">
            <span className="font-bold">{counts.customers} customer{counts.customers === 1 ? '' : 's'}</span> buying less or later than usual
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Link>
      )}
      {counts.deadItems > 0 && (
        <Link href="/reports?tab=watchlists&sub=dead" className={tile}>
          <Archive className="h-5 w-5 shrink-0 text-orange-600 dark:text-orange-400" aria-hidden="true" />
          <span className="min-w-0 flex-1 text-sm">
            <span className="font-bold">{rupeesShort(counts.deadValue)}</span> locked in {counts.deadItems} dead stock item{counts.deadItems === 1 ? '' : 's'}
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Link>
      )}
      {counts.items > 0 && (
        <Link href="/reports?tab=watchlists&sub=reorder" className={tile}>
          <Package className="h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" aria-hidden="true" />
          <span className="min-w-0 flex-1 text-sm">
            <span className="font-bold">{counts.items} item{counts.items === 1 ? '' : 's'}</span> running out soon
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        </Link>
      )}
    </section>
  )
}
