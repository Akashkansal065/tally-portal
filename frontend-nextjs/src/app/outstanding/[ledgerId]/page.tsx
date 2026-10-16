'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, ChevronDown, ChevronLeft, ChevronRight, FileText, Loader2, Phone, Search, SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn, formatCurrency } from '@/lib/utils'
import { getBranding, type Branding } from '@/lib/branding'
import { buildOutstandingPdf, outstandingFileName, viewPdf } from '@/lib/outstanding-pdf'

interface Bill {
  bill_id: number
  voucher_id?: number | null
  bill_reference: string
  bill_date: string
  due_date?: string | null
  bill_amount: number
  outstanding_amount: number
  days_overdue: number
}

interface Customer {
  party_ledger_id: number
  party_name: string
  phone?: string | null
  address?: string | null
  gstin?: string | null
  credit_period_days: number
  total_outstanding: number
  bills: Bill[]
}

const FILTERS = [
  { key: 'all', label: 'All', test: () => true },
  { key: 'overdue', label: 'Overdue', test: (b: Bill) => b.days_overdue > 0 },
  { key: 'not-due', label: 'Not due', test: (b: Bill) => b.days_overdue <= 0 },
  { key: '1-30', label: '1-30 days', test: (b: Bill) => b.days_overdue > 0 && b.days_overdue <= 30 },
  { key: '31-60', label: '31-60 days', test: (b: Bill) => b.days_overdue > 30 && b.days_overdue <= 60 },
  { key: '61-90', label: '61-90 days', test: (b: Bill) => b.days_overdue > 60 && b.days_overdue <= 90 },
  { key: '90+', label: '90+ days', test: (b: Bill) => b.days_overdue > 90 },
] as const
type FilterKey = typeof FILTERS[number]['key']

const PAGE_SIZES = [10, 25, 50, 100]

const showDate = (iso?: string | null) => {
  if (!iso) return '—'
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`)
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

/**
 * Outstanding → one customer's pending bills, oldest first (like LiveKeeping's Collect Payments), with a
 * printable "Outstanding Vouchers Report" PDF of the bills in the current filter.
 */
export default function CustomerPendingBillsPage() {
  const { token, user, can } = useAuth()
  const router = useRouter()
  const ledgerId = Number(useParams()?.ledgerId)
  const allowed = can('outstanding', 'read')

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [branding, setBranding] = useState<Branding | null>(null)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [search, setSearch] = useState('')
  const [pageSize, setPageSize] = useState(10)
  const [page, setPage] = useState(1)
  // Phones only: filters stay folded away so the bills get the screen (always shown on wider screens)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    if (user && !allowed) router.replace('/')
  }, [user, allowed, router])

  useEffect(() => {
    if (!token || !allowed || !ledgerId) return
    let current = true
    setLoading(true)
    fetch(`${API_BASE}/payment/aging/dashboard?party_ledger_id=${ledgerId}`, { headers: authHeaders(token) })
      .then(async res => {
        if (!res.ok) throw new Error('Could not load this customer’s bills')
        const json = await res.json()
        if (current) setCustomer(json.customers?.[0] ?? null)
      })
      .catch(err => { if (current) setError(err.message) })
      .finally(() => { if (current) setLoading(false) })
    getBranding(token, user?.company_id).then(b => { if (current) setBranding(b) }).catch(() => {})
    return () => { current = false }
  }, [token, allowed, ledgerId, user?.company_id])

  // Oldest first; the opening / pre-sync balance (no date) is the oldest of all
  const bills = useMemo(() => [...(customer?.bills ?? [])].sort((a, b) =>
    (a.bill_date || '0000').localeCompare(b.bill_date || '0000') || (a.voucher_id ?? 0) - (b.voucher_id ?? 0)
  ), [customer])

  const filtered = useMemo(() => {
    const test = FILTERS.find(f => f.key === filter)!.test
    const q = search.trim().toLowerCase()
    return bills.filter(b => test(b) && (!q || b.bill_reference.toLowerCase().includes(q)))
  }, [bills, filter, search])

  useEffect(() => { setPage(1) }, [filter, search, pageSize])

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const shown = filtered.slice((page - 1) * pageSize, page * pageSize)
  const overdue = bills.filter(b => b.days_overdue > 0).reduce((s, b) => s + b.outstanding_amount, 0)
  const activeLabel = FILTERS.find(f => f.key === filter)!.label
  const filteredTotal = filtered.reduce((s, b) => s + b.outstanding_amount, 0)

  const handleViewPdf = () => {
    if (!customer) return
    try {
      const c = branding?.company
      const place = c ? [...c.address_lines, c.state].filter(Boolean).join(', ') : ''
      const doc = buildOutstandingPdf({
        company: {
          name: c?.name || user?.company_name || '',
          address: c?.pincode && place ? `${place} - ${c.pincode}` : place,
          gstin: c?.gstin,
        },
        party: { name: customer.party_name, address: customer.address, gstin: customer.gstin },
        bills: filtered,
        total: customer.total_outstanding,
        overdue: filter === 'all' ? overdue : filtered.filter(b => b.days_overdue > 0).reduce((s, b) => s + b.outstanding_amount, 0),
        label: filter === 'all' ? 'All' : FILTERS.find(f => f.key === filter)!.label,
      })
      viewPdf(doc, outstandingFileName(customer.party_name))
    } catch (err) {
      console.error('Outstanding PDF failed', err)
      toast.error('Could not make the PDF')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" role="status">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
        <span className="sr-only">Loading bills</span>
      </div>
    )
  }

  const back = (
    <button
      type="button"
      onClick={() => (window.history.length > 1 ? router.back() : router.push('/outstanding'))}
      className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl hover:bg-muted cursor-pointer"
      aria-label="Back to Outstanding"
    >
      <ArrowLeft className="h-5 w-5" />
    </button>
  )

  if (error || !customer) {
    return (
      <div className="mx-auto max-w-6xl p-4">
        {back}
        <p className="py-16 text-center text-muted-foreground">
          {error || 'This customer has no pending bills.'}{' '}
          <Link href="/outstanding" className="font-semibold text-emerald-600 hover:underline">Back to Outstanding</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl px-2 pb-20 pt-3 sm:px-4 sm:pt-5">
      {/* Header: name, total, filters */}
      <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-center gap-2">
          {back}
          <div className="min-w-0">
            <h1 className="truncate text-lg font-black uppercase tracking-tight sm:text-xl">{customer.party_name}</h1>
            <p className="text-sm text-muted-foreground">
              Total: <span className="font-bold text-foreground tabular-nums">{formatCurrency(customer.total_outstanding)}</span>
              {overdue > 0 && <> · Overdue: <span className="font-bold text-rose-600 dark:text-rose-400 tabular-nums">{formatCurrency(overdue)}</span></>}
              {' '}· credit {customer.credit_period_days}d
            </p>
          </div>
        </div>
        {/* Phones: one slim row; the filters, search and page size open only when asked for */}
        <div className="flex items-center gap-2 sm:hidden">
          <button
            type="button"
            onClick={() => setShowFilters(s => !s)}
            aria-expanded={showFilters}
            aria-controls="bill-filters"
            className="inline-flex h-10 min-w-0 flex-1 items-center gap-2 rounded-xl border border-border bg-card px-3 text-sm font-semibold cursor-pointer"
          >
            <SlidersHorizontal className="h-4 w-4 shrink-0" />
            <span className="truncate">
              {showFilters ? 'Hide filters' : `Filters · ${activeLabel}${search.trim() ? ` · “${search.trim()}”` : ''}`}
            </span>
            <ChevronDown className={cn('ml-auto h-4 w-4 shrink-0 transition-transform', showFilters && 'rotate-180')} />
          </button>
          {customer.phone && (
            <a href={`tel:${customer.phone}`} className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card" aria-label={`Call ${customer.party_name}`}>
              <Phone className="h-4 w-4" />
            </a>
          )}
          <button
            type="button"
            onClick={handleViewPdf}
            disabled={filtered.length === 0}
            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl border border-border bg-card px-3 text-sm font-semibold disabled:opacity-50 cursor-pointer"
          >
            <FileText className="h-4 w-4 text-rose-600" /> PDF
          </button>
        </div>
        <div
          id="bill-filters"
          className={cn('flex-wrap gap-1 rounded-xl bg-muted p-1 sm:flex', showFilters ? 'flex' : 'hidden')}
          role="tablist"
          aria-label="Show bills"
        >
          {FILTERS.map(f => (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                'min-h-9 rounded-lg px-3 text-sm font-semibold cursor-pointer',
                filter === f.key ? 'bg-card shadow-sm ring-1 ring-border' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm">
        {/* Toolbar (on phones, part of the filters that open on request) */}
        <div className={cn('flex-col gap-3 border-b border-border p-3 sm:flex sm:flex-row sm:items-center sm:justify-between sm:p-4', showFilters ? 'flex' : 'hidden')}>
          <div className="flex flex-wrap items-center gap-3">
            <label className="relative flex-1 sm:flex-none">
              <span className="sr-only">Search voucher number</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search"
                className="h-10 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500/40 sm:w-56"
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              Rows per page
              <select
                value={pageSize}
                onChange={e => setPageSize(Number(e.target.value))}
                className="h-10 rounded-xl border border-border bg-background px-2 text-sm text-foreground"
              >
                {PAGE_SIZES.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {customer.phone && (
              <a href={`tel:${customer.phone}`} className="hidden h-10 w-10 items-center justify-center rounded-xl border border-border hover:bg-muted sm:inline-flex" aria-label={`Call ${customer.party_name}`}>
                <Phone className="h-4 w-4" />
              </a>
            )}
            <Link href={`/ledgers/${customer.party_ledger_id}`} className="inline-flex h-10 items-center rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted">
              Ledger statement
            </Link>
            <button
              type="button"
              onClick={handleViewPdf}
              disabled={filtered.length === 0}
              className="hidden h-10 items-center gap-2 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted disabled:opacity-50 cursor-pointer sm:inline-flex"
            >
              <FileText className="h-4 w-4 text-rose-600" /> View PDF
            </button>
          </div>
        </div>

        {/* Bills */}
        {filtered.length === 0 ? (
          <p className="p-10 text-center text-sm text-muted-foreground">No bills match.</p>
        ) : (
          <>
            {/* Phones: one card per bill */}
            <ul className="divide-y divide-border sm:hidden">
              {shown.map(b => (
                <li key={`${b.voucher_id ?? 'opening'}-${b.bill_reference}`} className="flex items-start justify-between gap-3 p-3">
                  <div className="min-w-0">
                    {b.voucher_id ? (
                      <Link href={`/vouchers/${b.voucher_id}`} className="font-semibold text-emerald-700 hover:underline dark:text-emerald-400">{b.bill_reference}</Link>
                    ) : <span className="font-semibold">{b.bill_reference}</span>}
                    <p className="text-xs text-muted-foreground">{showDate(b.bill_date)} · due {showDate(b.due_date)}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold tabular-nums">{formatCurrency(b.outstanding_amount)}</p>
                    <p className={cn('text-xs', b.days_overdue > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-muted-foreground')}>
                      {b.days_overdue > 0 ? `${b.days_overdue} days overdue` : 'Not due'}
                    </p>
                  </div>
                </li>
              ))}
            </ul>

            {/* Wider screens: table */}
            <div className="hidden overflow-x-auto sm:block">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-left text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Voucher No</th>
                    <th className="px-4 py-3 font-semibold">Date</th>
                    <th className="px-4 py-3 font-semibold">Due Date</th>
                    <th className="px-4 py-3 text-right font-semibold">Overdue by</th>
                    <th className="px-4 py-3 text-right font-semibold">Bill Amount</th>
                    <th className="px-4 py-3 text-right font-semibold">Pending</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {shown.map(b => (
                    <tr key={`${b.voucher_id ?? 'opening'}-${b.bill_reference}`} className="hover:bg-muted/30">
                      <td className="px-4 py-3">
                        {b.voucher_id ? (
                          <Link href={`/vouchers/${b.voucher_id}`} className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">{b.bill_reference}</Link>
                        ) : <span className="font-medium">{b.bill_reference}</span>}
                      </td>
                      <td className="px-4 py-3 tabular-nums">{showDate(b.bill_date)}</td>
                      <td className="px-4 py-3 tabular-nums">{showDate(b.due_date)}</td>
                      <td className={cn('px-4 py-3 text-right tabular-nums', b.days_overdue > 0 ? 'font-semibold text-rose-600 dark:text-rose-400' : 'text-muted-foreground')}>
                        {b.days_overdue > 0 ? `${b.days_overdue} days` : 'Not due'}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">{formatCurrency(b.bill_amount)}</td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">{formatCurrency(b.outstanding_amount)} Dr</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Footer: count, filtered total, pages */}
        <div className="flex flex-col gap-2 border-t border-border p-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-4">
          <span className="text-muted-foreground">
            {filtered.length === 0 ? '0' : `${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, filtered.length)}`} of {filtered.length}
            {filter !== 'all' && <> · <span className="font-semibold text-foreground tabular-nums">{formatCurrency(filteredTotal)}</span></>}
          </span>
          {pages > 1 && (
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => setPage(p => p - 1)} disabled={page === 1} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border disabled:opacity-40 cursor-pointer" aria-label="Previous page">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="px-2 tabular-nums">Page {page} of {pages}</span>
              <button type="button" onClick={() => setPage(p => p + 1)} disabled={page === pages} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border disabled:opacity-40 cursor-pointer" aria-label="Next page">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
