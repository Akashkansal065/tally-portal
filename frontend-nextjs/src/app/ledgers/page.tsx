'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, RefreshCw, Plus, Edit2, Trash2, FolderTree } from 'lucide-react'
import { cn } from '@/lib/utils'
import LedgerFormModal, { LedgerFormData } from '@/components/LedgerFormModal'
import DeleteLedgerModal from '@/components/DeleteLedgerModal'

type Ledger = {
  ledger_id: number
  group_id?: number
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
  pincode?: string
  country?: string
  contact_person?: string
  pan_number?: string
  credit_limit?: number
  credit_period_days?: number
  address?: string
}

export default function LedgersPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<'customers' | 'suppliers'>('customers')
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [loading, setLoading] = useState(true)

  // Modal States
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editLedgerData, setEditLedgerData] = useState<LedgerFormData | null>(null)
  
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [deleteLedgerId, setDeleteLedgerId] = useState<number | null>(null)
  const [deleteLedgerName, setDeleteLedgerName] = useState('')

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showLedger) { router.replace('/'); return }
    
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const q = params.get('search')
      if (q) setSearchQuery(q)
      const tab = params.get('tab')
      if (tab === 'customers' || tab === 'suppliers') {
        setActiveTab(tab)
        return
      }
    }

    if (!permissions.showSalesLedgers && permissions.showPurchaseLedgers) {
      setActiveTab('suppliers')
    } else if (permissions.showSalesLedgers && !permissions.showPurchaseLedgers) {
      setActiveTab('customers')
    }
  }, [user, permissions, router])
  
  // Interactive filters
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

  const handleOpenCreateModal = () => {
    setEditLedgerData(null)
    setIsFormOpen(true)
  }

  const handleOpenEditModal = (ledger: Ledger, e: React.MouseEvent) => {
    e.stopPropagation()
    const autoPan = ledger.pan_number || (ledger.gstin && ledger.gstin.length >= 12 ? ledger.gstin.substring(2, 12).toUpperCase() : '')
    setEditLedgerData({
      ledger_id: ledger.ledger_id,
      name: ledger.name,
      group_id: ledger.group_id || 0,
      opening_balance: Math.abs(ledger.opening_balance || 0).toString(),
      opening_balance_type: (ledger.opening_balance_type as 'Dr' | 'Cr') || 'Dr',
      gstin: ledger.gstin || '',
      pan_number: autoPan,
      aadhar_number: (ledger as any).aadhar_number || '',
      address: ledger.address || '',
      state: ledger.state || 'Haryana',
      pincode: (ledger as any).pincode || '',
      country: (ledger as any).country || 'India',
      mobile: ledger.mobile || '',
      phone: (ledger as any).phone || '',
      email: ledger.email || (ledger as any).email || '',
      contact_person: (ledger as any).contact_person || '',
      credit_limit: ledger.credit_limit ? ledger.credit_limit.toString() : '',
      credit_period_days: ledger.credit_period_days ? ledger.credit_period_days.toString() : '',
      is_billwise_on: true
    })
    setIsFormOpen(true)
  }

  const handleOpenDeleteModal = (ledger: Ledger, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeleteLedgerId(ledger.ledger_id)
    setDeleteLedgerName(ledger.name)
    setIsDeleteOpen(true)
  }

  // Admin / Management Permission check
  const canManageLedgers = useMemo(() => {
    if (!user) return false
    return user.role?.toLowerCase() === 'admin' || permissions?.isAdmin === true
  }, [user, permissions])

  const [isSyncing, setIsSyncing] = useState(false)

  const handleTriggerSync = async () => {
    if (!token) return
    setIsSyncing(true)
    try {
      const res = await fetch(`${API_BASE}/sync/run-once`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        setTimeout(() => {
          fetchData()
        }, 1500)
      }
    } catch (err) {
      console.error('Failed to trigger sync:', err)
    } finally {
      setTimeout(() => setIsSyncing(false), 2000)
    }
  }

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Header bar with Add Ledger & Sync Actions */}
      <div className="px-4 py-3 bg-card border-b border-border flex items-center justify-between shadow-xs">
        <div>
          <h1 className="text-base font-black text-foreground tracking-tight">Ledger Masters</h1>
          <p className="text-[11px] text-muted-foreground font-semibold">Manage Customer & Supplier accounts</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleTriggerSync}
            disabled={isSyncing}
            className="px-3 py-2 border border-border bg-background hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
            title="Force Instant Sync with Tally Prime"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isSyncing && "animate-spin text-emerald-600")} />
            {isSyncing ? 'Syncing...' : 'Sync Tally'}
          </button>
          
          <button
            onClick={() => router.push('/ledgers/groups')}
            className="px-3.5 py-2 border border-border bg-background hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer hidden sm:flex"
            title="Manage Group Master Hierarchy"
          >
            <FolderTree className="w-4 h-4" />
            Group Master
          </button>
          {canManageLedgers && (
            <button
              onClick={handleOpenCreateModal}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-extrabold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer active:scale-95"
            >
              <Plus className="w-4 h-4" />
              + Create Ledger
            </button>
          )}
        </div>
      </div>

      {/* Tabs Selector */}
      {(permissions.showSalesLedgers && permissions.showPurchaseLedgers) && (
        <div className="px-4 py-2 bg-background border-b border-border">
          <div className="bg-muted p-1 rounded-xl flex gap-1 border border-border/40 max-w-xl mx-auto">
            <button
              onClick={() => setActiveTab('customers')}
              className={cn(
                'flex-1 py-2 text-xs font-extrabold rounded-lg transition-all text-center cursor-pointer',
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
                'flex-1 py-2 text-xs font-extrabold rounded-lg transition-all text-center cursor-pointer',
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
            <div className="text-center py-12 text-muted-foreground text-xs italic bg-card border border-border rounded-2xl p-6">
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
                  className="bg-card border border-border rounded-2xl p-4 space-y-3 shadow-sm hover:border-emerald-500/40 transition-all hover:shadow-md cursor-pointer group"
                >
                  <div className="flex justify-between items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-bold text-[15px] text-foreground leading-tight tracking-tight group-hover:text-emerald-600 transition-colors">
                        {ledger.name}
                      </h3>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase mt-0.5 tracking-wider">
                        {labelGroup}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Action Buttons (Admin Only) */}
                      {canManageLedgers && (
                        <>
                          <button
                            onClick={e => handleOpenEditModal(ledger, e)}
                            title="Edit Ledger"
                            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-emerald-600 hover:bg-emerald-50 hover:border-emerald-200 transition-all cursor-pointer"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={e => handleOpenDeleteModal(ledger, e)}
                            title="Delete Ledger"
                            className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-rose-600 hover:bg-rose-50 hover:border-rose-200 transition-all cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}

                      {/* Balance Badge */}
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

      {/* Create / Edit Ledger Modal */}
      <LedgerFormModal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        onSuccess={fetchData}
        initialData={editLedgerData}
        token={token}
        defaultGroupType={activeTab === 'customers' ? 'customer' : 'supplier'}
      />

      {/* Delete Ledger Modal */}
      <DeleteLedgerModal
        isOpen={isDeleteOpen}
        ledgerId={deleteLedgerId}
        ledgerName={deleteLedgerName}
        onClose={() => setIsDeleteOpen(false)}
        onSuccess={fetchData}
        token={token}
      />
    </div>
  )
}
