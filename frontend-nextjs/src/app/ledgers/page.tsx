'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

type Ledger = {
  ledger_id: number
  name: string
  group_name: string
  opening_balance: number
  opening_balance_type: string
  closing_balance?: number
  is_active: boolean
  gstin?: string
  mobile?: string
  email?: string
  state?: string
}

export default function LedgersPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<'customers' | 'suppliers'>('customers')
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showLedger) { router.replace('/'); return }
    if (!permissions.showSalesLedgers && permissions.showPurchaseLedgers) {
      setActiveTab('suppliers')
    } else if (permissions.showSalesLedgers && !permissions.showPurchaseLedgers) {
      setActiveTab('customers')
    }
  }, [user, permissions, router])
  
  // Interactive filters matching screenshot
  const [searchQuery, setSearchQuery] = useState('')
  const [filterBalance, setFilterBalance] = useState('all') // all | nonzero | zero | dr | cr
  const [sortBy, setSortBy] = useState('name-asc') // name-asc | name-desc | balance-desc | balance-asc

  // Pagination states
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
      const data = await res.json()
      setLedgers(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchData()
  }, [user, token])

  // Filter and sort ledgers
  const processedData = useMemo(() => {
    let result = ledgers.filter(ledger => {
      const gName = (ledger.group_name || '').toLowerCase()
      if (activeTab === 'customers') {
        return gName.includes('debtor') || gName === 'customers'
      } else {
        return gName.includes('creditor') || gName === 'suppliers'
      }
    })

    // 1. Apply search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        l =>
          l.name.toLowerCase().includes(query) ||
          (l.gstin && l.gstin.toLowerCase().includes(query)) ||
          (l.mobile && l.mobile.toLowerCase().includes(query))
      )
    }

    // 2. Apply balance filter
    if (filterBalance !== 'all') {
      result = result.filter(l => {
        const bal = parseFloat((l.closing_balance ?? l.opening_balance ?? 0).toString())
        if (filterBalance === 'nonzero') return Math.abs(bal) > 0.001
        if (filterBalance === 'zero') return Math.abs(bal) <= 0.001
        if (filterBalance === 'dr') return bal > 0.001
        if (filterBalance === 'cr') return bal < -0.001
        return true
      })
    }

    // 3. Apply sorting
    result = [...result].sort((a, b) => {
      const [key, direction] = sortBy.split('-')
      const mult = direction === 'asc' ? 1 : -1

      if (key === 'name') {
        return a.name.localeCompare(b.name) * mult
      }

      if (key === 'balance') {
        const balA = parseFloat((a.closing_balance ?? a.opening_balance ?? 0).toString())
        const balB = parseFloat((b.closing_balance ?? b.opening_balance ?? 0).toString())
        return (balA - balB) * mult
      }

      return 0
    })

    return result
  }, [ledgers, activeTab, searchQuery, filterBalance, sortBy])

  // Pagination subset
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize
    return processedData.slice(startIndex, startIndex + pageSize)
  }, [processedData, currentPage])

  const totalPages = Math.ceil(processedData.length / pageSize)

  // Reset page on tab/filter change
  useEffect(() => {
    setCurrentPage(1)
  }, [activeTab, searchQuery, filterBalance, sortBy])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Tabs Selector matching mockup */}
      {(permissions.showSalesLedgers && permissions.showPurchaseLedgers) && (
        <div className="px-4 py-2.5 bg-background border-b border-border">
          <div className="bg-muted p-1 rounded-xl flex gap-1 border border-border/40">
            <button
              onClick={() => setActiveTab('customers')}
              className={cn(
                'flex-1 py-2 text-xs font-extrabold rounded-lg transition-all text-center',
                activeTab === 'customers'
                  ? 'bg-emerald-500 text-white shadow-sm font-black'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Customers
            </button>
            <button
              onClick={() => setActiveTab('suppliers')}
              className={cn(
                'flex-1 py-2 text-xs font-extrabold rounded-lg transition-all text-center',
                activeTab === 'suppliers'
                  ? 'bg-emerald-500 text-white shadow-sm font-black'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Suppliers
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 pt-3 pb-6 max-w-xl mx-auto w-full space-y-4">
        {/* Interactive Search & Filters Card */}
        <div className="bg-card border border-border rounded-2xl p-4 space-y-3.5 shadow-sm">
          {/* Search Field */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search name, GSTIN, phone..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          {/* Balance Selector Row */}
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="font-extrabold text-muted-foreground tracking-wider">BALANCE:</span>
            <select
              value={filterBalance}
              onChange={e => setFilterBalance(e.target.value)}
              className="bg-background border border-border rounded-xl px-3 py-1.5 text-xs font-bold text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer min-w-[150px]"
            >
              <option value="all">All Balances</option>
              <option value="nonzero">Non-Zero Only</option>
              <option value="zero">Zero Balance</option>
              <option value="dr">Debit Only (Dr)</option>
              <option value="cr">Credit Only (Cr)</option>
            </select>
          </div>

          {/* Sort By Row */}
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="font-extrabold text-muted-foreground tracking-wider">SORT BY:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="bg-background border border-border rounded-xl px-3 py-1.5 text-xs font-bold text-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer min-w-[150px]"
            >
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
              <option value="balance-desc">Balance (High-Low)</option>
              <option value="balance-asc">Balance (Low-High)</option>
            </select>
          </div>
        </div>

        {/* Ledger Cards Grid */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : paginatedData.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-xs italic">
              No ledgers match current filters
            </div>
          ) : (
            paginatedData.map(ledger => {
              const bal = parseFloat((ledger.closing_balance ?? ledger.opening_balance ?? 0).toString())
              const isDebit = bal >= 0
              const isNonZero = Math.abs(bal) > 0.001
              const labelGroup = ledger.group_name || (activeTab === 'customers' ? 'SUNDRY DEBTORS' : 'SUNDRY CREDITORS')
              return (
                <div
                  key={ledger.ledger_id}
                  onClick={() => router.push(`/ledgers/${ledger.ledger_id}`)}
                  className="bg-card border border-border rounded-2xl p-4 space-y-3 shadow-sm hover:border-emerald-500/40 transition-all hover:shadow-md cursor-pointer"
                >
                  <div className="flex justify-between items-start gap-3">
                    <div className="min-w-0">
                      <h3 className="font-bold text-[15px] text-foreground leading-tight tracking-tight">
                        {ledger.name}
                      </h3>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase mt-0.5 tracking-wider">
                        {labelGroup}
                      </p>
                    </div>
                    {/* Red badge for non-zero Debit (Dr) balances, blue badge for Credit (Cr) balances, gray otherwise */}
                    <div className={cn(
                      "shrink-0 font-black text-xs font-mono px-2.5 py-1.5 rounded-lg border text-right",
                      isNonZero
                        ? isDebit
                          ? "bg-rose-50 border-rose-200 text-rose-800"
                          : "bg-blue-50 border-blue-200 text-blue-800"
                        : "bg-muted/60 text-muted-foreground border-border"
                    )}>
                      {formatCurrency(Math.abs(bal))}
                      <span className="text-[10px] font-bold ml-1">
                        {!isNonZero ? '' : isDebit ? 'Dr' : 'Cr'}
                      </span>
                    </div>
                  </div>

                  {/* Card Divider & Meta Info */}
                  {(ledger.gstin || ledger.mobile || ledger.state) && (
                    <div className="pt-3 border-t border-border/60 space-y-1.5 text-xs text-muted-foreground leading-normal">
                      {ledger.gstin && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-semibold text-muted-foreground uppercase w-12">GSTIN:</span>
                          <span className="font-bold text-foreground font-mono">{ledger.gstin}</span>
                        </div>
                      )}
                      {ledger.state && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-semibold text-muted-foreground uppercase w-12">STATE:</span>
                          <span className="font-bold text-foreground truncate">{ledger.state}</span>
                        </div>
                      )}
                      {ledger.mobile && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-semibold text-muted-foreground uppercase w-12">MOBILE:</span>
                          <span className="font-bold text-foreground">{ledger.mobile}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Pagination Controls */}
        {!loading && processedData.length > 0 && (
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(p - 1, 1))}
              disabled={currentPage === 1}
              className="px-3.5 py-1.5 border border-border rounded-xl text-xs font-bold bg-card text-foreground disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            >
              Previous
            </button>
            <div className="text-xs text-muted-foreground font-bold">
              Page {currentPage} of {totalPages || 1}
            </div>
            <button
              onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="px-3.5 py-1.5 border border-border rounded-xl text-xs font-bold bg-card text-foreground disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Footer counter */}
      {!loading && (
        <footer className="shrink-0 text-center py-2 text-[11px] font-medium text-muted-foreground bg-muted/20 border-t border-border">
          {processedData.length} of {ledgers.length} ledgers
        </footer>
      )}
    </div>
  )
}
