'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePeriod } from '@/context/PeriodContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { Loader2, Package, Search, Undo2 } from 'lucide-react'

type ItemHistory = {
  stock_item_id: number
  name: string
  group: string | null
  unit: string
  times_bought: number
  quantity: number
  amount: number
  returned_quantity: number
  returned_amount: number
  first_bought: string | null
  last_bought: string | null
  last_rate: number | null
  last_discount_percent: number | null
  last_voucher_id: number | null
  last_voucher_number: string | null
  average_rate: number | null
  days_since_bought: number | null
}

type ItemHistoryResponse = {
  from_date: string
  to_date: string
  total_amount: number
  items: ItemHistory[]
}

const SORTS = [
  { value: 'last_bought', label: 'Latest first' },
  { value: 'amount', label: 'Most value' },
  { value: 'quantity', label: 'Most quantity' },
  { value: 'times_bought', label: 'Most often' },
  { value: 'name', label: 'Name' },
] as const

const qty = (n: number, unit: string) => `${n.toLocaleString('en-IN', { maximumFractionDigits: 3 })} ${unit}`

/** Every item the customer bought in the selected period, with the rate and discount on their latest invoice,
 *  so staff can quote the price they last paid. */
export default function CustomerItemsTab({ ledgerId, token }: { ledgerId: number | null; token: string | null }) {
  const { startDate, endDate } = usePeriod()
  const [sortBy, setSortBy] = useState<string>('last_bought')
  const [search, setSearch] = useState('')
  // Each answer remembers the request it belongs to, so a request still on its way shows as loading
  const [result, setResult] = useState<{ url: string; data?: ItemHistoryResponse; error?: string } | null>(null)

  const url = useMemo(() => {
    if (!ledgerId) return null
    const q = new URLSearchParams({ sort_by: sortBy })
    if (startDate) q.set('from_date', startDate)
    if (endDate) q.set('to_date', endDate)
    return `${API_BASE}/reports/customer-items/${ledgerId}?${q}`
  }, [ledgerId, sortBy, startDate, endDate])

  useEffect(() => {
    if (!url || !token) return
    let current = true
    fetch(url, { headers: authHeaders(token) })
      .then(r => {
        if (r.status === 403) throw new Error('You do not have permission to view reports.')
        if (!r.ok) throw new Error('Could not load what this customer buys.')
        return r.json()
      })
      .then(data => { if (current) setResult({ url, data }) })
      .catch(e => { if (current) setResult({ url, error: e.message }) })
    return () => { current = false }
  }, [url, token])

  const loading = Boolean(url) && result?.url !== url
  const data = loading ? null : result?.data ?? null
  const error = loading ? '' : result?.error ?? ''

  const items = useMemo(() => {
    const term = search.trim().toLowerCase()
    const all = data?.items ?? []
    return term ? all.filter(i => i.name.toLowerCase().includes(term) || (i.group ?? '').toLowerCase().includes(term)) : all
  }, [data, search])

  return (
    <div className="bg-card border border-border rounded-3xl p-4 sm:p-8 shadow-sm space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-primary/10 text-primary">
            <Package className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-extrabold text-foreground">What they buy</h2>
            <p className="text-xs text-muted-foreground">
              {data
                ? `${formatDate(data.from_date)} – ${formatDate(data.to_date)} · ${data.items.length} items · ${formatCurrency(data.total_amount)}`
                : 'Items on their sales invoices, with the last rate and discount'}
            </p>
          </div>
        </div>
        {ledgerId && (
          <div className="flex items-center gap-2">
            <div className="relative flex-1 sm:w-56">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search items"
                className="w-full pl-9 pr-3 py-2 rounded-xl border border-border bg-background text-sm"
              />
            </div>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              aria-label="Sort items"
              className="py-2 px-3 rounded-xl border border-border bg-background text-sm font-semibold"
            >
              {SORTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        )}
      </div>

      {!ledgerId ? (
        <p className="py-16 text-center text-sm text-muted-foreground">
          Link this customer to a Tally ledger to see what they buy.
        </p>
      ) : loading ? (
        <div className="py-16 flex justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
        </div>
      ) : error ? (
        <p className="py-16 text-center text-sm text-muted-foreground">{error}</p>
      ) : items.length === 0 ? (
        <p className="py-16 text-center text-sm text-muted-foreground">
          {search ? 'No items match your search.' : 'No items sold to this customer in this period.'}
        </p>
      ) : (
        <>
          {/* Desktop */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border whitespace-nowrap">
                  <th className="text-left py-2 px-2">Item</th>
                  <th className="text-right py-2 px-2">Last rate</th>
                  <th className="text-right py-2 px-2">Last disc.</th>
                  <th className="text-left py-2 px-2">Last bought</th>
                  <th className="text-right py-2 px-2">Times</th>
                  <th className="text-right py-2 px-2">Quantity</th>
                  <th className="text-right py-2 px-2">Value</th>
                </tr>
              </thead>
              <tbody>
                {items.map(i => (
                  <tr key={i.stock_item_id} className="border-b border-border/60 hover:bg-muted/40">
                    <td className="py-2.5 px-2">
                      <p className="font-semibold text-foreground">{i.name}</p>
                      {i.group && <p className="text-[11px] text-muted-foreground">{i.group}</p>}
                    </td>
                    <td className="py-2.5 px-2 text-right font-mono tabular-nums font-bold">
                      {i.last_rate != null ? `${formatCurrency(i.last_rate)}/${i.unit}` : '—'}
                    </td>
                    <td className="py-2.5 px-2 text-right font-mono tabular-nums">
                      {i.last_discount_percent ? `${i.last_discount_percent}%` : '—'}
                    </td>
                    <td className="py-2.5 px-2">
                      {i.last_bought ? (
                        <>
                          <span>{formatDate(i.last_bought)}</span>
                          {i.last_voucher_id && (
                            <Link href={`/vouchers/${i.last_voucher_id}`} className="block text-[11px] text-primary hover:underline">
                              {i.last_voucher_number}
                            </Link>
                          )}
                        </>
                      ) : '—'}
                    </td>
                    <td className="py-2.5 px-2 text-right tabular-nums">{i.times_bought}</td>
                    <td className="py-2.5 px-2 text-right tabular-nums">
                      {qty(i.quantity, i.unit)}
                      {i.returned_quantity > 0 && (
                        <span className="block text-[11px] text-amber-600 dark:text-amber-400">
                          {qty(i.returned_quantity, i.unit)} returned
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-2 text-right font-mono tabular-nums">{formatCurrency(i.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile */}
          <div className="md:hidden space-y-2">
            {items.map(i => (
              <div key={i.stock_item_id} className="border border-border rounded-2xl p-3 space-y-1.5">
                <div className="flex justify-between gap-3">
                  <p className="font-semibold text-sm text-foreground min-w-0 break-words">{i.name}</p>
                  <p className="font-mono font-bold text-sm tabular-nums shrink-0">
                    {i.last_rate != null ? `${formatCurrency(i.last_rate)}/${i.unit}` : '—'}
                  </p>
                </div>
                <div className="flex justify-between gap-3 text-xs text-muted-foreground">
                  <span>
                    {i.last_bought ? `Last ${formatDate(i.last_bought)}` : 'Not bought in period'}
                    {i.last_discount_percent ? ` · ${i.last_discount_percent}% off` : ''}
                  </span>
                  <span className="shrink-0">{i.times_bought}× · {qty(i.quantity, i.unit)}</span>
                </div>
                {i.returned_quantity > 0 && (
                  <p className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                    <Undo2 className="w-3 h-3" /> {qty(i.returned_quantity, i.unit)} returned
                  </p>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
