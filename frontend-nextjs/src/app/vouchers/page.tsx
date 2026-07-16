'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { Search, Filter, Plus, ArrowLeft, FileText, ChevronRight, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type VoucherEntry = {
  entry_type: 'Debit' | 'Credit'
  ledger_name: string
  amount: number
}

type Voucher = {
  voucher_id: number
  voucher_number: string
  date: string
  type: string
  narration: string
  entries: VoucherEntry[]
}

const TYPE_COLORS: Record<string, string> = {
  Sales: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
  Purchase: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  Payment: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400',
  Receipt: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  Journal: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400',
  Contra: 'bg-slate-100 text-slate-700 dark:bg-slate-700/40 dark:text-slate-400',
}

const TYPES = ['All', 'Sales', 'Purchase', 'Payment', 'Receipt', 'Journal', 'Contra']

export default function VouchersPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  const [vouchers, setVouchers] = useState<Voucher[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [selected, setSelected] = useState<Voucher | null>(null)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetch(`${API_BASE}/vouchers`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => setVouchers(Array.isArray(data) ? data : []))
      .catch(() => setVouchers([]))
      .finally(() => setLoading(false))
  }, [user, token, router])

  const filtered = useMemo(() => {
    return vouchers.filter(v => {
      const entries: VoucherEntry[] = (v as any).entries || (v as any).items || []
      const parties = entries.map(e => e.ledger_name).join(' ').toLowerCase()
      const matchSearch = v.voucher_number.toLowerCase().includes(search.toLowerCase()) ||
        parties.includes(search.toLowerCase())
      const matchType = typeFilter === 'All' || v.type === typeFilter
      return matchSearch && matchType
    })
  }, [vouchers, search, typeFilter])

  const getAmount = (v: Voucher) => {
    const entries: VoucherEntry[] = (v as any).entries || (v as any).items || []
    const debit = entries.find(e => e.entry_type === 'Debit')
    const credit = entries.find(e => e.entry_type === 'Credit')
    return debit?.amount || credit?.amount || 0
  }

  const getParty = (v: Voucher) => {
    const entries: VoucherEntry[] = (v as any).entries || (v as any).items || []
    const debit = entries.find(e => e.entry_type === 'Debit')
    const credit = entries.find(e => e.entry_type === 'Credit')
    const name = debit?.ledger_name || credit?.ledger_name
    return name ? toTitleCase(name) : '—'
  }

  if (selected) {
    const entries: VoucherEntry[] = (selected as any).entries || (selected as any).items || []
    return (
      <div className="p-4 max-w-2xl mx-auto space-y-4">
        <button onClick={() => setSelected(null)} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to Vouchers
        </button>
        <div className="bg-card rounded-2xl border border-border p-5 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold">{selected.voucher_number}</h2>
              <p className="text-xs text-muted-foreground">{formatDate(selected.date)}</p>
            </div>
            <span className={cn('px-2.5 py-1 rounded-full text-xs font-bold', TYPE_COLORS[selected.type] || 'bg-muted text-muted-foreground')}>
              {selected.type}
            </span>
          </div>

          {selected.narration && (
            <p className="text-sm text-muted-foreground border-t border-border pt-3">{selected.narration}</p>
          )}

          <div className="border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-muted-foreground text-xs uppercase">
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Ledger</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={i} className="border-t border-border">
                    <td className="px-3 py-2.5">
                      <span className={cn('text-xs font-bold', e.entry_type === 'Debit' ? 'text-rose-600' : 'text-emerald-600')}>
                        {e.entry_type === 'Debit' ? 'Dr' : 'Cr'}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-medium">{toTitleCase(e.ledger_name)}</td>
                    <td className="px-3 py-2.5 text-right font-bold">{formatCurrency(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search + filter bar */}
      <div className="sticky top-0 bg-background/95 backdrop-blur z-10 px-4 pt-4 pb-3 space-y-3 border-b border-border">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search vouchers or parties..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>
        {/* Type pills */}
        <div className="flex gap-2 overflow-x-auto scrollbar-none pb-1">
          {TYPES.map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={cn(
                'flex-shrink-0 px-3 py-1 rounded-full text-xs font-semibold transition-all',
                typeFilter === t
                  ? 'bg-primary text-white'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 pt-3 pb-2 space-y-2">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm">No vouchers found</p>
          </div>
        ) : (
          filtered.map(v => (
            <button
              key={v.voucher_id}
              onClick={() => setSelected(v)}
              className="w-full text-left bg-card border border-border rounded-2xl p-4 flex items-center gap-3 hover:bg-muted/30 active:scale-[0.98] transition-all"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-sm">{v.voucher_number}</span>
                  <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-bold', TYPE_COLORS[v.type] || 'bg-muted text-muted-foreground')}>
                    {v.type}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground truncate">{getParty(v)}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{formatDate(v.date)}</p>
              </div>
              <div className="text-right shrink-0">
                <p className="font-bold text-sm">{formatCurrency(getAmount(v))}</p>
                <ChevronRight className="h-4 w-4 text-muted-foreground ml-auto mt-1" />
              </div>
            </button>
          ))
        )}
      </div>

      {/* Count badge */}
      {!loading && (
        <div className="px-4 py-2 text-center text-xs text-muted-foreground border-t border-border">
          {filtered.length} of {vouchers.length} vouchers
        </div>
      )}
    </div>
  )
}
