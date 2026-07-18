'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { Search, FileText, ChevronRight, X, Loader2, SlidersHorizontal, Phone, Download, FileDown, Plus, BellRing } from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

type Voucher = {
  voucher_id: number
  date: string
  voucher_type: string
  voucher_number: string
  reference_number: string | null
  narration: string | null
  party_name: string
  amount: number
  total_amount: number
}

const TYPE_COLORS: Record<string, string> = {
  Sales: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
  Purchase: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  Payment: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400',
  Receipt: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  Journal: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400',
  Contra: 'bg-slate-100 text-slate-700 dark:bg-slate-700/40 dark:text-slate-400',
  'Credit Note': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-400',
  'Debit Note': 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400',
}

const CATEGORIES = ['All', 'Sales', 'Purchase', 'Receipt', 'Payment']

// Financial year month helper
function getFinancialYearMonths() {
  const now = new Date()
  const currentMonth = now.getMonth() // 0-indexed
  let fyStartYear = now.getFullYear()
  if (currentMonth < 3) fyStartYear -= 1
  const fyEndYear = fyStartYear + 1

  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const months: { label: string; year: number; month: number }[] = []

  const iterDate = new Date(now)
  iterDate.setDate(1)
  const limitDate = new Date(fyStartYear, 3, 1) // April 1 of FY start

  while (iterDate >= limitDate) {
    months.push({
      label: `${monthNames[iterDate.getMonth()]}'${String(iterDate.getFullYear()).slice(-2)}`,
      year: iterDate.getFullYear(),
      month: iterDate.getMonth(),
    })
    iterDate.setMonth(iterDate.getMonth() - 1)
  }

  return {
    fyLabel: `FY ${String(fyStartYear).slice(-2)}-${String(fyEndYear).slice(-2)}`,
    fyStartYear,
    fyEndYear,
    months,
  }
}

function formatIndianNumber(num: number) {
  const absNum = Math.abs(num)
  if (absNum >= 100000) {
    const lacs = absNum / 100000
    return `₹${lacs.toFixed(lacs % 1 === 0 ? 0 : 2)}L`
  }
  if (absNum >= 1000) {
    const thousands = absNum / 1000
    return `₹${thousands.toFixed(thousands % 1 === 0 ? 0 : 1)}K`
  }
  return `₹${absNum.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

export default function VouchersPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [allVouchers, setAllVouchers] = useState<Voucher[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchExpanded, setSearchExpanded] = useState(false)
  const [activeCategory, setActiveCategory] = useState('All')
  const [activeDateFilter, setActiveDateFilter] = useState('All')
  const [grossEnabled, setGrossEnabled] = useState(true)
  const [sortBy, setSortBy] = useState<'date_desc' | 'date_asc' | 'amount_desc' | 'amount_asc'>('date_desc')
  const [statusFilter, setStatusFilter] = useState<'all' | 'paid' | 'unpaid'>('all')
  const [filterModalOpen, setFilterModalOpen] = useState(false)

  const { fyLabel, fyStartYear, fyEndYear, months: fyMonths } = useMemo(() => getFinancialYearMonths(), [])

  const hasAnyVoucherPermission = permissions.isAdmin || 
    permissions.showSalesLedgers || 
    permissions.showPurchaseLedgers || 
    permissions.showReceipts || 
    permissions.showPayments

  const allowedCategories = useMemo(() => {
    if (permissions.isAdmin) return ['All', 'Sales', 'Purchase', 'Receipt', 'Payment']
    const cats = ['All']
    if (permissions.showSalesLedgers) cats.push('Sales')
    if (permissions.showPurchaseLedgers) cats.push('Purchase')
    if (permissions.showReceipts) cats.push('Receipt')
    if (permissions.showPayments) cats.push('Payment')
    return cats
  }, [permissions])

  // Fetch all vouchers once on mount
  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!hasAnyVoucherPermission) { router.replace('/'); return }
    fetch(`${API_BASE}/vouchers`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => setAllVouchers(Array.isArray(data) ? data : []))
      .catch(() => setAllVouchers([]))
      .finally(() => setLoading(false))
  }, [user, token, router, hasAnyVoucherPermission])

  // Client-side filtering and sorting
  const filtered = useMemo(() => {
    let list = [...allVouchers]

    // Category filter
    if (activeCategory !== 'All') {
      list = list.filter(v =>
        v.voucher_type.toLowerCase().includes(activeCategory.toLowerCase())
      )
    }

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(v =>
        (v.party_name || '').toLowerCase().includes(q) ||
        (v.voucher_number || '').toLowerCase().includes(q) ||
        (v.narration || '').toLowerCase().includes(q)
      )
    }

    // Status filter (Paid / Unpaid)
    if (statusFilter !== 'all') {
      list = list.filter(v => {
        const isPaid = v.voucher_type.toLowerCase().includes('receipt') || v.voucher_type.toLowerCase().includes('payment')
        return statusFilter === 'paid' ? isPaid : !isPaid
      })
    }

    // Date filter
    if (activeDateFilter !== 'All') {
      list = list.filter(v => {
        if (!v.date) return false
        const d = new Date(v.date)
        const today = new Date()
        today.setHours(0, 0, 0, 0)

        if (activeDateFilter === 'Today') {
          return d.toDateString() === today.toDateString()
        }
        if (activeDateFilter === 'Yesterday') {
          const yesterday = new Date(today)
          yesterday.setDate(yesterday.getDate() - 1)
          return d.toDateString() === yesterday.toDateString()
        }
        if (activeDateFilter === 'FY') {
          const fyStart = new Date(`${fyStartYear}-04-01`)
          const fyEnd = new Date(`${fyEndYear}-03-31`)
          return d >= fyStart && d <= fyEnd
        }
        // Monthly filter: "Jul'26"
        const match = activeDateFilter.match(/([A-Za-z]+)'(\d+)/)
        if (match) {
          const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
          const monthIdx = monthNames.indexOf(match[1])
          const year = 2000 + parseInt(match[2])
          if (monthIdx !== -1) {
            return d.getFullYear() === year && d.getMonth() === monthIdx
          }
        }
        return true
      })
    }

    // Sort
    list.sort((a, b) => {
      const amtA = grossEnabled ? a.amount : a.total_amount
      const amtB = grossEnabled ? b.amount : b.total_amount
      if (sortBy === 'date_desc') return new Date(b.date).getTime() - new Date(a.date).getTime()
      if (sortBy === 'date_asc') return new Date(a.date).getTime() - new Date(b.date).getTime()
      if (sortBy === 'amount_desc') return Math.abs(amtB) - Math.abs(amtA)
      if (sortBy === 'amount_asc') return Math.abs(amtA) - Math.abs(amtB)
      return 0
    })

    return list
  }, [allVouchers, activeCategory, search, statusFilter, activeDateFilter, sortBy, grossEnabled, fyStartYear, fyEndYear])

  // Compute summaries from allVouchers (client-side, like tally-web)
  const summaries = useMemo(() => {
    const catVouchers = activeCategory === 'All'
      ? allVouchers
      : allVouchers.filter(v => v.voucher_type.toLowerCase().includes(activeCategory.toLowerCase()))

    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    let todayTotal = 0, yesterdayTotal = 0, fyTotal = 0
    const monthTotals: Record<string, number> = {}

    for (const v of catVouchers) {
      const d = new Date(v.date)
      const amt = Math.abs(grossEnabled ? v.amount : v.total_amount)

      if (d.toDateString() === today.toDateString()) todayTotal += amt
      if (d.toDateString() === yesterday.toDateString()) yesterdayTotal += amt

      const fyStart = new Date(`${fyStartYear}-04-01`)
      const fyEnd = new Date(`${fyEndYear}-03-31`)
      if (d >= fyStart && d <= fyEnd) fyTotal += amt

      for (const m of fyMonths) {
        if (d.getFullYear() === m.year && d.getMonth() === m.month) {
          monthTotals[m.label] = (monthTotals[m.label] || 0) + amt
        }
      }
    }

    return {
      today: todayTotal,
      yesterday: yesterdayTotal,
      fy: fyTotal,
      months: fyMonths.map(m => ({ label: m.label, total: monthTotals[m.label] || 0 })),
    }
  }, [allVouchers, activeCategory, grossEnabled, fyStartYear, fyEndYear, fyMonths])

  // WhatsApp share handler
  const triggerWhatsAppShare = (e: React.MouseEvent, v: Voucher) => {
    e.stopPropagation()
    const isPaid = v.voucher_type.toLowerCase().includes('receipt') || v.voucher_type.toLowerCase().includes('payment')
    const formattedAmt = Math.abs(v.amount).toLocaleString('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 0 })
    const shareText = `*Sneh Distributors*\n\n*Voucher Detail*\nNo: ${v.voucher_number}\nCustomer: ${toTitleCase(v.party_name)}\nDate: ${formatDate(v.date)}\nAmount: ${formattedAmt}\nStatus: ${isPaid ? "Paid" : "Unpaid"}\n\nPlease find the copy of your voucher. Thank you!`
    const shareUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(shareText)}`
    window.open(shareUrl, '_blank')
    toast.success('Opening WhatsApp share...')
  }

  // Export PDF Report handler
  const handleExportFilteredVouchersPdf = () => {
    toast.success('Generating vouchers list report PDF...')
    setTimeout(() => {
      window.print()
    }, 500)
  }

  return (
    <div className="flex flex-col h-full bg-background pb-20">
      {/* Sticky Header Controls Panel */}
      <div className="bg-card border-b border-border p-4 sticky top-0 z-40 shadow-sm space-y-3.5">
        <div className="flex flex-col gap-3.5 max-w-lg mx-auto">
          {/* Row A: Navbar / Search triggers */}
          <div className="flex items-center justify-between gap-3">
            {searchExpanded ? (
              <div className="flex items-center gap-2 w-full animate-in slide-in-from-top-1 duration-200">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    autoFocus
                    placeholder="Search Vouchers.."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="w-full pl-9 h-8 bg-muted/40 text-xs border border-border/80 rounded-full focus:outline-none focus:ring-2 focus:ring-emerald-500 px-3"
                  />
                </div>
                <button
                  onClick={() => { setSearch(''); setSearchExpanded(false) }}
                  className="text-xs text-emerald-500 font-semibold shrink-0"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                {/* Segment switcher */}
                <div className="inline-flex rounded-lg p-1 bg-muted/60 border text-xs font-semibold shrink-0">
                  <button className="px-4 py-1.5 rounded-md bg-emerald-500 text-white shadow-sm flex items-center gap-1.5 transition-all">
                    Vouchers
                  </button>
                  <button
                    onClick={() => router.push("/ledgers")}
                    className="px-4 py-1.5 rounded-md text-muted-foreground hover:text-foreground transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    Ledgers
                  </button>
                </div>

                {/* Compact Search Trigger Icon Button */}
                <button
                  onClick={() => setSearchExpanded(true)}
                  className="h-8 w-8 flex items-center justify-center border border-border/80 text-muted-foreground hover:text-foreground hover:bg-muted rounded-full shrink-0"
                >
                  <Search className="h-4.5 w-4.5" />
                </button>

                {/* Switch & Download PDF Icon */}
                <div className="flex items-center gap-2 shrink-0">
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] font-bold text-muted-foreground tracking-wider">GROSS</span>
                    <label className="relative inline-flex items-center cursor-pointer scale-75">
                      <input
                        type="checkbox"
                        checked={grossEnabled}
                        onChange={(e) => setGrossEnabled(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
                    </label>
                  </div>
                  <button 
                    onClick={handleExportFilteredVouchersPdf}
                    className="h-8 w-8 flex items-center justify-center hover:bg-muted text-red-500 rounded-full shrink-0"
                    title="Export PDF Report"
                  >
                    <FileDown className="h-4.5 w-4.5" />
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Row B: Voucher Type Selector */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1.5 scrollbar-none shrink-0">
            {allowedCategories.map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={cn(
                  'px-4 py-1.5 rounded-full text-xs font-medium border transition-all shrink-0 cursor-pointer',
                  activeCategory === cat
                    ? 'bg-emerald-500 text-white border-emerald-500 shadow-sm'
                    : 'bg-card text-muted-foreground border-border hover:bg-muted/50'
                )}
              >
                {cat}
              </button>
            ))}
            <button 
              onClick={() => setFilterModalOpen(true)}
              className="h-7 w-7 flex items-center justify-center border border-border bg-card shrink-0 ml-auto rounded-full hover:bg-emerald-500/10 hover:text-emerald-500 cursor-pointer"
            >
              <SlidersHorizontal className="h-3 w-3" />
            </button>
          </div>

          {/* Row C: Horizontal Scrollable Period Summaries */}
          <div className="flex items-center gap-2.5 overflow-x-auto pb-1.5 scrollbar-none shrink-0">
            {/* Card: All */}
            <button
              onClick={() => setActiveDateFilter('All')}
              className={cn(
                'flex flex-col p-2.5 rounded-xl border text-left min-w-[90px] transition-all cursor-pointer shrink-0',
                activeDateFilter === 'All'
                  ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 shadow-sm ring-1 ring-emerald-500'
                  : 'bg-card border-border hover:bg-muted/20'
              )}
            >
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">All</span>
              <span className="text-xs font-extrabold text-foreground mt-1">View All</span>
            </button>

            {/* Card: Today */}
            <button
              onClick={() => setActiveDateFilter('Today')}
              className={cn(
                'flex flex-col p-2.5 rounded-xl border text-left min-w-[95px] transition-all cursor-pointer shrink-0',
                activeDateFilter === 'Today'
                  ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 shadow-sm ring-1 ring-emerald-500'
                  : 'bg-card border-border hover:bg-muted/20'
              )}
            >
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Today</span>
              <span className="text-xs font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">
                {formatIndianNumber(summaries.today)}
              </span>
            </button>

            {/* Card: Yesterday */}
            <button
              onClick={() => setActiveDateFilter('Yesterday')}
              className={cn(
                'flex flex-col p-2.5 rounded-xl border text-left min-w-[95px] transition-all cursor-pointer shrink-0',
                activeDateFilter === 'Yesterday'
                  ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 shadow-sm ring-1 ring-emerald-500'
                  : 'bg-card border-border hover:bg-muted/20'
              )}
            >
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Yesterday</span>
              <span className="text-xs font-extrabold text-foreground mt-1">
                {formatIndianNumber(summaries.yesterday)}
              </span>
            </button>

            {/* Dynamic Month Cards */}
            {summaries.months.map((m) => (
              <button
                key={m.label}
                onClick={() => setActiveDateFilter(m.label)}
                className={cn(
                  'flex flex-col p-2.5 rounded-xl border text-left min-w-[95px] transition-all cursor-pointer shrink-0',
                  activeDateFilter === m.label
                    ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 shadow-sm ring-1 ring-emerald-500'
                    : 'bg-card border-border hover:bg-muted/20'
                )}
              >
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{m.label}</span>
                <span className="text-xs font-extrabold text-foreground mt-1">
                  {formatIndianNumber(m.total)}
                </span>
              </button>
            ))}

            {/* Card: FY */}
            <button
              onClick={() => setActiveDateFilter('FY')}
              className={cn(
                'flex flex-col p-2.5 rounded-xl border text-left min-w-[95px] transition-all cursor-pointer shrink-0',
                activeDateFilter === 'FY'
                  ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-500 shadow-sm ring-1 ring-emerald-500'
                  : 'bg-card border-border hover:bg-muted/20'
              )}
            >
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{fyLabel}</span>
              <span className="text-xs font-extrabold text-foreground mt-1">
                {formatIndianNumber(summaries.fy)}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Container */}
      <div className="max-w-lg mx-auto px-4 py-4 space-y-5 w-full">
        {/* Voucher items listing */}
        <div className="space-y-3.5">
          {loading ? (
            <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-emerald-500" />
              Loading records...
            </div>
          ) : filtered.length === 0 ? (
            <div className="bg-card border border-border/80 rounded-xl p-8 text-center text-xs text-muted-foreground">
              No matching vouchers found.
            </div>
          ) : (
            filtered.map((voucher) => {
              const formattedDate = voucher.date
                ? new Date(voucher.date).toLocaleDateString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: '2-digit'
                  }).replace(/ /g, ' ')
                : 'N/A';

              const isPaid = voucher.voucher_type.toLowerCase().includes('receipt') || 
                             voucher.voucher_type.toLowerCase().includes('payment');

              return (
                <div
                  key={voucher.voucher_id}
                  onClick={() => router.push(`/vouchers/${voucher.voucher_id}`)}
                  className="bg-card border border-border/60 hover:border-emerald-500/30 transition-all rounded-xl p-4 shadow-sm flex flex-col justify-between cursor-pointer active:scale-[0.99]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1.5 min-w-0">
                      {/* Sub-header text and status badges */}
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] font-bold text-muted-foreground font-mono">
                          {voucher.voucher_number}
                        </span>
                        <span className="text-[9px] px-1.5 py-0 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-md font-medium border-none shrink-0 scale-95">
                          Not Shared
                        </span>
                        {isPaid ? (
                          <span className="text-[9px] px-1.5 py-0 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 rounded-md font-semibold border-none shrink-0 scale-95">
                            Paid
                          </span>
                        ) : (
                          <span className="text-[9px] px-1.5 py-0 bg-red-50 dark:bg-red-950/30 text-red-500 dark:text-red-400 rounded-md font-semibold border-none shrink-0 scale-95">
                            Unpaid
                          </span>
                        )}
                      </div>

                      {/* Main Title / Customer Name */}
                      <h3 className="text-xs font-bold text-foreground truncate">
                        {voucher.party_name ? toTitleCase(voucher.party_name) : 'Cash Account'}
                      </h3>

                      {/* Subtitle / Date */}
                      <p className="text-[10px] text-muted-foreground font-mono">
                        {formattedDate} • <span className="font-semibold text-slate-400 font-mono">{voucher.voucher_type}</span>
                      </p>
                    </div>

                    {/* Right side amount & actions */}
                    <div className="flex flex-col items-end gap-3 shrink-0">
                      {/* Amount */}
                      <span className="text-xs font-extrabold text-foreground tracking-tight font-mono">
                        {Math.abs(grossEnabled ? voucher.amount : voucher.total_amount).toLocaleString('en-IN', {
                          style: 'currency',
                          currency: 'INR',
                          minimumFractionDigits: 0
                        })}
                      </span>

                      {/* Social/Export actions row */}
                      <div className="flex items-center gap-2">
                        {/* WhatsApp share */}
                        <button
                          onClick={(e) => triggerWhatsAppShare(e, voucher)}
                          className="h-7 w-7 flex items-center justify-center rounded-full border border-emerald-500/20 text-emerald-600 hover:bg-emerald-500/10 cursor-pointer transition-colors"
                          title="Share on WhatsApp"
                        >
                          <Phone className="h-3.5 w-3.5" />
                        </button>

                        {/* PDF download trigger */}
                        <button
                          onClick={(e) => { e.stopPropagation(); router.push(`/vouchers/${voucher.voucher_id}`) }}
                          className="h-7 w-7 flex items-center justify-center rounded-full border border-red-500/20 text-red-500 hover:bg-red-50 cursor-pointer transition-colors"
                          title="View PDF / Print"
                        >
                          <Download className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
        {/* Spacer to allow scrolling past bottom nav and CTA buttons */}
        <div className="h-32" />
      </div>

      {/* Sticky Floating CTA Buttons */}
      <div className="fixed bottom-20 left-0 right-0 z-40 px-4 md:hidden">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <button
            onClick={() => router.push('/payments/new')}
            className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-xs shadow-md rounded-xl h-11 border-none cursor-pointer flex items-center justify-center gap-1.5 transition-transform active:scale-95"
          >
            <BellRing className="h-4.5 w-4.5 animate-bounce" />
            Collect Payment
          </button>
          <button
            onClick={() => router.push('/temporders/new')}
            className="flex-1 bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 font-extrabold text-xs shadow-md rounded-xl h-11 border-none cursor-pointer flex items-center justify-center gap-1.5 transition-transform active:scale-95"
          >
            <Plus className="h-4.5 w-4.5" />
            Create Entries
          </button>
        </div>
      </div>

      {/* Advanced Filter Modal Overlay */}
      {filterModalOpen && (
        <div 
          onClick={() => setFilterModalOpen(false)}
          className="fixed inset-0 bg-black/60 z-[100] flex items-end justify-center p-4 pb-24 md:pb-4 animate-in fade-in duration-200"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-card w-full max-w-md rounded-2xl p-6 space-y-6 animate-in slide-in-from-bottom duration-250 border border-border shadow-2xl"
          >
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                <SlidersHorizontal className="h-4.5 w-4.5 text-emerald-500" />
                Advanced Filters
              </h3>
              <button 
                onClick={() => setFilterModalOpen(false)}
                className="text-xs font-semibold text-muted-foreground hover:text-foreground cursor-pointer"
              >
                Close
              </button>
            </div>

            {/* Sort Options */}
            <div className="space-y-2.5">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Sort Transactions</h4>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setSortBy("date_desc")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    sortBy === "date_desc"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Date: New to Old
                </button>
                <button
                  onClick={() => setSortBy("date_asc")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    sortBy === "date_asc"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Date: Old to New
                </button>
                <button
                  onClick={() => setSortBy("amount_desc")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    sortBy === "amount_desc"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Amount: High to Low
                </button>
                <button
                  onClick={() => setSortBy("amount_asc")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    sortBy === "amount_asc"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Amount: Low to High
                </button>
              </div>
            </div>

            {/* Status Options */}
            <div className="space-y-2.5">
              <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Payment Status</h4>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setStatusFilter("all")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    statusFilter === "all"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  All
                </button>
                <button
                  onClick={() => setStatusFilter("paid")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    statusFilter === "paid"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Paid Only
                </button>
                <button
                  onClick={() => setStatusFilter("unpaid")}
                  className={cn(
                    "px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all cursor-pointer",
                    statusFilter === "unpaid"
                      ? "bg-emerald-500 text-white border-emerald-500 shadow-sm"
                      : "bg-muted/40 text-muted-foreground border-border hover:bg-muted/75"
                  )}
                >
                  Unpaid Only
                </button>
              </div>
            </div>

            <button
              onClick={() => setFilterModalOpen(false)}
              className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-2.5 rounded-xl border-none cursor-pointer transition-colors"
            >
              Apply Filters
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
