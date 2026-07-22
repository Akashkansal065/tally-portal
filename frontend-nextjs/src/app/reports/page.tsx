'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { BarChart3, FileText, TrendingUp, TrendingDown, Package, Layers, BookOpen } from 'lucide-react'
import { cn } from '@/lib/utils'

type ReportCategory = {
  id: string
  label: string
  description: string
  icon: React.ElementType
  color: string
  endpoint: string
}

const REPORT_CATEGORIES: ReportCategory[] = [
  { id: 'daybook', label: 'Day Book', description: 'All vouchers in a date range', icon: FileText, color: 'text-blue-600', endpoint: '/reports/daybook' },
  { id: 'outstanding-receivables', label: 'Outstanding Receivables', description: 'Open sales bills by party', icon: TrendingUp, color: 'text-emerald-600', endpoint: '/payment/outstanding' },
  { id: 'outstanding-payables', label: 'Outstanding Payables', description: 'Open purchase bills by party', icon: TrendingDown, color: 'text-rose-600', endpoint: '/reports/outstanding-payables' },
  { id: 'stock-summary', label: 'Stock Summary', description: 'Current inventory grouped by category', icon: Layers, color: 'text-amber-600', endpoint: '/inventory/items' },
  { id: 'sales-register', label: 'Sales Register', description: 'All sales vouchers in period', icon: BookOpen, color: 'text-teal-600', endpoint: '/reports/sales-register' },
  { id: 'trial-balance', label: 'Trial Balance', description: 'Group-level balance summary', icon: Package, color: 'text-indigo-600', endpoint: '/reports/trial-balance' },
]

export default function ReportsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [active, setActive] = useState<ReportCategory | null>(null)
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10)
  })
  const [toDate, setToDate] = useState(() => new Date().toISOString().slice(0, 10))

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showReports && !permissions.isAdmin) { router.replace('/'); return }
  }, [user, permissions, router])

  const loadReport = async (cat: ReportCategory) => {
    setActive(cat); setData([]); setLoading(true)
    try {
      const url = `${API_BASE}${cat.endpoint}?from=${fromDate}&to=${toDate}`
      const res = await fetch(url, { headers: authHeaders(token) })
      if (!res.ok) throw new Error('Failed to load report')
      const d = await res.json()
      setData(Array.isArray(d) ? d : (d?.data ?? Object.values(d) ?? []))
    } catch { setData([]) } finally { setLoading(false) }
  }

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      <h1 className="text-xl font-extrabold flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-indigo-500" /> Reports Hub
      </h1>

      {/* Date range picker */}
      <div className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
        <div className="flex-1">
          <label className="text-[10px] text-muted-foreground font-semibold uppercase">From</label>
          <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-xl border border-border bg-muted/40 text-sm" />
        </div>
        <div className="flex-1">
          <label className="text-[10px] text-muted-foreground font-semibold uppercase">To</label>
          <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-xl border border-border bg-muted/40 text-sm" />
        </div>
      </div>

      {/* Category grid */}
      <div className="grid grid-cols-2 gap-3">
        {REPORT_CATEGORIES.map(cat => {
          const Icon = cat.icon
          const isActive = active?.id === cat.id
          return (
            <button
              key={cat.id}
              onClick={() => loadReport(cat)}
              className={cn(
                'rounded-2xl border p-4 text-left transition-all active:scale-[0.97] flex flex-col gap-2',
                isActive ? 'border-primary/50 bg-primary/5' : 'border-border bg-card hover:bg-muted/30'
              )}
            >
              <Icon className={cn('h-5 w-5', cat.color)} />
              <div>
                <p className={cn('font-bold text-sm', isActive ? 'text-primary' : '')}>{cat.label}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{cat.description}</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Results */}
      {active && (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-muted/30">
            <h2 className="font-bold text-sm">{active.label}</h2>
            <p className="text-xs text-muted-foreground">{fromDate} → {toDate}</p>
          </div>
          {loading ? (
            <div className="flex justify-center py-8"><div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" /></div>
          ) : data.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">No data for selected period</div>
          ) : (
            <div className="divide-y divide-border">
              {data.slice(0, 50).map((row, i) => (
                <div key={i} className="px-4 py-3 flex items-start justify-between gap-2 text-sm">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">
                      {row.name || row.ledger_name || row.party_name
                        ? toTitleCase(row.name || row.ledger_name || row.party_name)
                        : (row.voucher_number || JSON.stringify(row).slice(0, 40))}
                    </p>
                    {(row.date || row.created_at) && <p className="text-xs text-muted-foreground">{formatDate(row.date || row.created_at)}</p>}
                  </div>
                  {(row.amount || row.balance || row.closing_value || row.pending_amount) !== undefined && (
                    <p className="font-bold text-primary shrink-0">{formatCurrency(row.amount ?? row.balance ?? row.closing_value ?? row.pending_amount ?? 0)}</p>
                  )}
                </div>
              ))}
              {data.length > 50 && <div className="text-center py-2 text-xs text-muted-foreground">Showing first 50 of {data.length} rows</div>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
