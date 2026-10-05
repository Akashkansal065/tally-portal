'use client'

import { useEffect, useMemo, useState } from 'react'
import { Check, Loader2, MapPin, Settings2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { isAdminUser } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import {
  getCityMapping,
  getCityReport,
  rupees,
  rupeesShort,
  setCustomerCity,
  setPincodeCity,
  type CityMapping,
  type CityReport as CityReportData,
  type CityRow,
} from '@/lib/report-insights'

type View = 'sales' | 'growth'

const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

/** Reports → Cities: sales per city this month against the same days last month, and where there's room to grow. */
export function CityReport() {
  const { token, user, permissions } = useAuth()
  const isAdmin = isAdminUser(permissions, user?.role)
  const [data, setData] = useState<CityReportData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<View>('sales')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!token) return
    let current = true
    getCityReport(token)
      .then(d => { if (current) { setData(d); setError(null) } })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load the city report') })
    return () => { current = false }
  }, [token, reloadKey])

  const rows = useMemo(() => {
    if (!data) return []
    const list = [...data.cities]
    if (view === 'growth') {
      list.sort((a, b) => (b.not_buying + b.leads) - (a.not_buying + a.leads) || b.customers - a.customers)
    }
    return list
  }, [data, view])

  return (
    <section aria-labelledby="cities-title" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="cities-title" className="text-lg font-extrabold">Cities</h2>
          {data && (
            <p className="text-sm text-muted-foreground">
              Net sales before GST, {shortDate(data.period.from)}–{shortDate(data.period.to)}, compared with{' '}
              {shortDate(data.compared_with.from)}–{shortDate(data.compared_with.to)}. All companies.
            </p>
          )}
        </div>
        {isAdmin && (
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer"
          >
            <Settings2 className="h-4 w-4" /> Set cities
          </button>
        )}
      </div>

      <div className="inline-flex rounded-xl bg-muted p-1" role="tablist" aria-label="City view">
        {([['sales', 'Sales'], ['growth', 'Room to grow']] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={view === id}
            onClick={() => setView(id)}
            className={cn('min-h-10 rounded-lg px-3.5 text-sm font-semibold cursor-pointer',
              view === id ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          >
            {label}
          </button>
        ))}
      </div>

      {error ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
      ) : !data ? (
        <div className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card p-8 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading…
        </div>
      ) : (
        <>
          <p className="text-sm">
            <span className="font-bold">{rupees(data.total_sales)}</span> this month
            {data.cash_sales !== 0 && <span className="text-muted-foreground"> · {rupeesShort(data.cash_sales)} with no customer on the bill</span>}
          </p>
          {view === 'growth' && (
            <p className="text-sm text-muted-foreground">
              Cities with the most customers who didn&apos;t buy this month, plus leads not yet in Tally. &ldquo;Worth&rdquo; is what a buying customer
              there spends on average, a guide to what each new one could bring.
            </p>
          )}
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {rows.map(row => <CityCard key={row.city} row={row} view={view} />)}
          </ul>
        </>
      )}

      {isAdmin && token && (
        <CitySettings
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          token={token}
          onChanged={() => setReloadKey(k => k + 1)}
        />
      )}
    </section>
  )
}

function CityCard({ row, view }: { row: CityRow; view: View }) {
  const unset = row.city === 'City not set'
  return (
    <li className={cn('rounded-2xl border border-border bg-card p-4', unset && 'border-dashed')}>
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-1.5 font-bold">
          <MapPin className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          {row.city}
        </p>
        {row.share_pct > 0 && <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold">{row.share_pct}% of sales</span>}
      </div>
      {view === 'sales' ? (
        <>
          <p className="mt-1 text-xl font-black tabular-nums">
            {rupees(row.sales)}
            {row.change_pct !== null && (
              <span className={cn('ml-2 text-sm font-bold', row.change_pct >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400')}>
                {row.change_pct >= 0 ? '↑' : '↓'} {Math.abs(Math.round(row.change_pct))}%
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground">Same days last month: {rupees(row.sales_previous)}</p>
        </>
      ) : (
        <p className="mt-1 text-xl font-black tabular-nums">
          {row.not_buying + row.leads}
          <span className="ml-1.5 text-sm font-semibold text-muted-foreground">to win</span>
        </p>
      )}
      <ul className="mt-2 flex flex-wrap gap-1.5 text-xs">
        <li className="rounded-full bg-muted px-2 py-0.5">{row.buying} of {row.customers} customer{row.customers === 1 ? '' : 's'} bought</li>
        {row.leads > 0 && <li className="rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-800 dark:text-sky-300">{row.leads} lead{row.leads === 1 ? '' : 's'} not in Tally</li>}
        {view === 'sales' && row.average_invoice !== null && <li className="rounded-full bg-muted px-2 py-0.5">Avg invoice {rupeesShort(row.average_invoice)}</li>}
        {view === 'growth' && row.sales_per_buying_customer !== null && (
          <li className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-800 dark:text-emerald-300">Worth {rupeesShort(row.sales_per_buying_customer)} each</li>
        )}
        {row.overdue > 0 && <li className="rounded-full bg-rose-500/10 px-2 py-0.5 text-rose-700 dark:text-rose-400">{rupeesShort(row.overdue)} overdue</li>}
      </ul>
    </li>
  )
}

/** Admin: correct the city for each pincode, and give a city to customers who have none. */
function CitySettings({ open, onOpenChange, token, onChanged }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  token: string
  onChanged: () => void
}) {
  const [mapping, setMapping] = useState<CityMapping | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let current = true
    getCityMapping(token).then(m => { if (current) setMapping(m) }).catch(() => toast.error('Could not load cities'))
    return () => { current = false }
  }, [open, token])

  const save = async (key: string, action: () => Promise<unknown>) => {
    setSaving(key)
    try {
      await action()
      setMapping(await getCityMapping(token))
      setDrafts(d => { const next = { ...d }; delete next[key]; return next })
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(null)
    }
  }

  const input = 'h-10 min-w-0 flex-1 rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'
  const saveButton = (key: string, onClick: () => void) => (
    <button
      type="button"
      onClick={onClick}
      disabled={saving !== null}
      className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-60 cursor-pointer"
      aria-label="Save"
    >
      {saving === key ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
    </button>
  )

  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Set cities"
      description="A customer's city is their MyTally profile city, else their pincode's city below."
    >
      {!mapping ? (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /> Loading…</div>
      ) : (
        <div className="space-y-6">
          <section>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Pincodes</h3>
            <ul className="space-y-2">
              {mapping.pincodes.map(p => {
                const key = `pin-${p.pincode}`
                const value = drafts[key] ?? p.city ?? ''
                return (
                  <li key={p.pincode}>
                    <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                      <span className="font-mono font-semibold text-foreground">{p.pincode}</span>
                      <span>
                        {p.customers} customer{p.customers === 1 ? '' : 's'} ·{' '}
                        {p.source === 'set' ? 'set by admin' : p.source === 'proposed' ? 'proposed, please check' : 'no city yet'}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <input
                        value={value}
                        onChange={e => setDrafts(d => ({ ...d, [key]: e.target.value }))}
                        placeholder="City"
                        aria-label={`City for pincode ${p.pincode}`}
                        className={input}
                      />
                      {(drafts[key] !== undefined || p.source === 'proposed') &&
                        saveButton(key, () => save(key, () => setPincodeCity(token, p.pincode, value.trim() || null)))}
                    </div>
                  </li>
                )
              })}
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Customers without a city ({mapping.customers_without_city.length})
            </h3>
            {mapping.customers_without_city.length === 0 ? (
              <p className="text-sm text-muted-foreground">Every customer has a city.</p>
            ) : (
              <ul className="space-y-3">
                {mapping.customers_without_city.map(c => {
                  const key = `cust-${c.ledger_id}`
                  const value = drafts[key] ?? ''
                  return (
                    <li key={c.ledger_id}>
                      <p className="text-sm font-semibold">{c.name}</p>
                      {c.address && <p className="mb-1 line-clamp-2 text-xs text-muted-foreground">{c.address}</p>}
                      <div className="flex gap-2">
                        <input
                          value={value}
                          onChange={e => setDrafts(d => ({ ...d, [key]: e.target.value }))}
                          placeholder="City"
                          aria-label={`City for ${c.name}`}
                          className={input}
                        />
                        {value.trim() && saveButton(key, () => save(key, () => setCustomerCity(token, c.ledger_id, value.trim())))}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </div>
      )}
    </BottomSheet>
  )
}
