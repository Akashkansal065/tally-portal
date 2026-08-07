'use client'

import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { usePeriod } from '@/context/PeriodContext'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'
import {
  FileText,
  BookOpen,
  Layers,
  BarChart3,
  ShoppingCart,
  IndianRupee,
  MapPin,
  Wallet,
  ArrowRight,
  Shield,
  Clock,
  FileSpreadsheet,
  X,
  Search,
  Calendar,
  Edit3,
  Filter,
  RefreshCw,
  Check
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface DashboardCard {
  href: string
  label: string
  description: string
  icon: React.ElementType
  color: string
  bgColor: string
  show?: boolean
}

export default function DashboardPage() {
  const { user, token, permissions, isLoading } = useAuth()
  const { startDate: globalFrom, endDate: globalTo, setPeriod } = usePeriod()
  const router = useRouter()

  const [dashboardData, setDashboardData] = useState<any>(null)
  const [detailModal, setDetailModal] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  // Period control states synced with global PeriodContext
  const [fromDate, setFromDate] = useState<string>(globalFrom)
  const [toDate, setToDate] = useState<string>(globalTo)
  const [periodModalOpen, setPeriodModalOpen] = useState(false)
  const [fetchingSummary, setFetchingSummary] = useState(false)

  useEffect(() => {
    setFromDate(globalFrom)
    setToDate(globalTo)
  }, [globalFrom, globalTo])

  const applyPeriodChanges = (fDate: string, tDate: string) => {
    setPeriod(fDate, tDate)
    loadDashboard(fDate, tDate)
    setPeriodModalOpen(false)
  }

  const loadDashboard = async (fDate?: string, tDate?: string) => {
    if (!token || !permissions.showReports) return
    const targetFrom = fDate || globalFrom
    const targetTo = tDate || globalTo
    setFetchingSummary(true)
    try {
      let url = `${API_BASE}/reports/dashboard-summary`
      const queryParams: string[] = []
      if (targetFrom) queryParams.push(`from_date=${targetFrom}`)
      if (targetTo) queryParams.push(`to_date=${targetTo}`)
      if (queryParams.length > 0) {
        url += `?${queryParams.join('&')}`
      }
      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setDashboardData(data)
      }
    } catch (e) {
      console.error('Failed to load dashboard:', e)
    } finally {
      setFetchingSummary(false)
    }
  }



  const [activePreset, setActivePreset] = useState<string>('current_fy')

  const selectPreset = (type: string) => {
    const now = new Date()
    const currentYear = now.getFullYear()
    const currentMonth = now.getMonth() // 0-indexed (0=Jan, 3=Apr)
    const fyStartYear = currentMonth >= 3 ? currentYear : currentYear - 1

    let startStr = ''
    let endStr = ''

    if (type === 'current_fy') {
      // Dynamic running Current FY (e.g., 2026-04-01 to 2027-03-31)
      startStr = `${fyStartYear}-04-01`
      endStr = `${fyStartYear + 1}-03-31`
    } else if (type === 'prev_fy') {
      // Previous Financial Year (e.g., 2025-04-01 to 2026-03-31)
      startStr = `${fyStartYear - 1}-04-01`
      endStr = `${fyStartYear}-03-31`
    } else if (type === 'this_month') {
      const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
      const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0)
      startStr = firstDay.toISOString().split('T')[0]
      endStr = lastDay.toISOString().split('T')[0]
    } else if (type === 'last_month') {
      const firstDay = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const lastDay = new Date(now.getFullYear(), now.getMonth(), 0)
      startStr = firstDay.toISOString().split('T')[0]
      endStr = lastDay.toISOString().split('T')[0]
    } else if (type === 'all_time') {
      startStr = '2000-01-01'
      endStr = '2099-12-31'
    } else if (type.startsWith('q')) {
      const qNum = parseInt(type.replace('q', ''))
      if (qNum === 1) {
        startStr = `${fyStartYear}-04-01`
        endStr = `${fyStartYear}-06-30`
      } else if (qNum === 2) {
        startStr = `${fyStartYear}-07-01`
        endStr = `${fyStartYear}-09-30`
      } else if (qNum === 3) {
        startStr = `${fyStartYear}-10-01`
        endStr = `${fyStartYear}-12-31`
      } else if (qNum === 4) {
        startStr = `${fyStartYear + 1}-01-01`
        endStr = `${fyStartYear + 1}-03-31`
      }
    }

    setActivePreset(type)
    setFromDate(startStr)
    setToDate(endStr)
  }

  const openDetail = async (category: string) => {
    setDetailModal(category)
    setDetailLoading(true)
    setDetailData([])
    setSearchTerm('')
    try {
      const res = await fetch(`${API_BASE}/reports/dashboard-details?category=${category}`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setDetailData(data)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setDetailLoading(false)
    }
  }
  
  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login')
    } else if (user && permissions.showReports) {
      loadDashboard(globalFrom, globalTo)
    }
  }, [user, isLoading, router, token, permissions.showReports, globalFrom, globalTo])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) return null

  const cards: DashboardCard[] = [
    {
      href: '/vouchers',
      label: 'Vouchers',
      description: 'View and post sales, payment, and journal entries',
      icon: FileText,
      color: 'text-blue-600',
      bgColor: 'bg-blue-500/10 border-blue-500/20',
      show: permissions.showSalesLedgers || permissions.showPurchaseLedgers || permissions.showReceipts || permissions.showPayments,
    },
    {
      href: '/ledgers',
      label: 'Ledgers',
      description: 'Check account balances and party statements',
      icon: BookOpen,
      color: 'text-primary',
      bgColor: 'bg-primary/10 border-primary/20',
      show: permissions.showLedger,
    },
    {
      href: '/stocks',
      label: 'Stocks & Inventory',
      description: 'Browse warehouse items, closing rates, and batch values',
      icon: Layers,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      show: permissions.showStocks,
    },
    {
      href: '/temporders',
      label: 'Temporary Orders',
      description: 'Create and manage pre-Tally customer orders',
      icon: ShoppingCart,
      color: 'text-amber-600',
      bgColor: 'bg-amber-500/10 border-amber-500/20',
      show: permissions.showOrders,
    },
    {
      href: '/payments',
      label: 'Payments',
      description: 'Collect cash, cheque, or online payments from shops',
      icon: IndianRupee,
      color: 'text-teal-600',
      bgColor: 'bg-teal-500/10 border-teal-500/20',
      show: permissions.showPayments,
    },
    {
      href: '/check-in',
      label: 'Shop Check-In',
      description: 'GPS verify shop visits with photo proof',
      icon: MapPin,
      color: 'text-rose-600',
      bgColor: 'bg-rose-500/10 border-rose-500/20',
      show: permissions.showCheckIn,
    },
    {
      href: '/expenses',
      label: 'Expenses',
      description: 'Submit business expense claims with receipt uploads',
      icon: Wallet,
      color: 'text-purple-600',
      bgColor: 'bg-purple-500/10 border-purple-500/20',
      show: permissions.showExpenses,
    },
    {
      href: '/attendance',
      label: 'Attendance Log',
      description: 'Daily punch-in, punch-out, and shift logs',
      icon: Clock,
      color: 'text-sky-600',
      bgColor: 'bg-sky-500/10 border-sky-500/20',
      show: permissions.showAttendance,
    },
    {
      href: '/reports',
      label: 'Reports',
      description: 'Day book, outstanding, stock reports and PDF exports',
      icon: BarChart3,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-500/10 border-indigo-500/20',
      show: permissions.showReports,
    },
    {
      href: '/gst',
      label: 'GST Returns',
      description: 'Manage GSTR-1, GSTR-3B filings, track eligible ITC, and export GST JSONs',
      icon: FileSpreadsheet,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      show: permissions.showGst,
    },
    {
      href: '/admin',
      label: 'Admin Panel',
      description: 'Manage users, devices, and system settings',
      icon: Shield,
      color: 'text-slate-600',
      bgColor: 'bg-slate-500/10 border-slate-500/20',
      show: permissions.isAdmin,
    },
  ].filter(c => c.show)

  return (
    <div className="p-4 space-y-6 max-w-2xl mx-auto">
      {/* Welcome block */}
      <div className="pt-2 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">
            Welcome, <span className="text-primary">{user.username}</span>
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time synchronization with Tally Prime
          </p>
        </div>
      </div>

      {/* Tally Prime Style Header Banner */}
      <div className="bg-card border border-sky-300/60 dark:border-sky-800/60 rounded-2xl p-4 shadow-sm space-y-3 font-sans relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 rounded-full blur-2xl pointer-events-none" />
        <div className="flex justify-between items-start border-b border-sky-100 dark:border-sky-900/40 pb-3">
          <div 
            onClick={() => setPeriodModalOpen(true)}
            className="cursor-pointer group flex items-center gap-2 transition-opacity hover:opacity-90"
            title="Click to Change Period"
          >
            <div>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider block">CURRENT PERIOD</span>
              </div>
              <span className="text-base font-extrabold text-foreground tracking-tight flex items-center gap-1.5">
                {dashboardData?.current_period || '1-Apr-25 to 31-Mar-26'}
                <Edit3 className="w-3.5 h-3.5 text-sky-500 opacity-70 group-hover:opacity-100" />
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider block">CURRENT DATE</span>
            <span className="text-base font-extrabold text-foreground tracking-tight">
              {dashboardData?.current_date || new Date().toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>
        </div>

        <div className="flex justify-between items-end pt-1">
          <div>
            <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider block">NAME OF COMPANY</span>
            <span className="text-lg font-black text-foreground tracking-tight">
              {dashboardData?.company_name || user?.company_name || 'Bhrama Enterprises'}
            </span>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider block">DATE OF LAST ENTRY</span>
            <span className="text-lg font-black text-foreground tracking-tight">
              {dashboardData?.date_of_last_entry || 'No Entries'}
            </span>
          </div>
        </div>
      </div>

{/* Metrics Row */}
      {dashboardData && typeof dashboardData.total_sales === 'number' && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div 
            onClick={() => openDetail('sales')}
            className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-emerald-600 tracking-wider">Total Sales</span>
            <span className="text-xl font-black text-emerald-700">₹{dashboardData.total_sales?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('receipts')}
            className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">Total Receipts</span>
            <span className="text-xl font-black text-blue-700">₹{dashboardData.total_receipts?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('receivables')}
            className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-amber-600 tracking-wider">To Receive</span>
            <span className="text-xl font-black text-amber-700">₹{dashboardData.outstanding_receivables?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('payables')}
            className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-rose-600 tracking-wider">To Pay</span>
            <span className="text-xl font-black text-rose-700">₹{dashboardData.outstanding_payables?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
        </div>
      )}

      {/* Dashboard grid */}
      <div className="grid grid-cols-2 gap-3">
        {cards.map(card => {
          const Icon = card.icon
          return (
            <Link key={card.href} href={card.href} className="group">
              <div
                className={cn(
                  'relative rounded-2xl border p-4 h-full flex flex-col gap-3 transition-all duration-200',
                  'hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.97]',
                  card.bgColor
                )}
              >
                <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center', card.bgColor)}>
                  <Icon className={cn('h-5 w-5', card.color)} />
                </div>
                <div className="flex-1">
                  <h2 className={cn('text-sm font-bold flex items-center gap-1 group-hover:underline', card.color)}>
                    {card.label}
                    <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h2>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                    {card.description}
                  </p>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Detail Drill-down Modal */}
      {detailModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setDetailModal(null)}
        >
          <div 
            className="bg-card border border-border w-full max-w-md rounded-2xl p-6 shadow-2xl relative flex flex-col max-h-[80vh] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div>
                <h3 className="text-base font-black text-foreground capitalize">
                  {detailModal === 'sales' && 'Total Sales Breakdown'}
                  {detailModal === 'receipts' && 'Total Receipts Breakdown'}
                  {detailModal === 'receivables' && 'Receivables Breakdown'}
                  {detailModal === 'payables' && 'Payables Breakdown'}
                </h3>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Detailed ledger balances contributing to summary
                </p>
              </div>
              <button 
                onClick={() => setDetailModal(null)}
                className="w-8 h-8 rounded-full border border-border flex items-center justify-center hover:bg-muted text-muted-foreground transition-colors"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            {/* Search filter */}
            <div className="mt-4 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search ledgers or groups..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-border rounded-xl text-xs bg-background text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Ledger list container */}
            <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-2.5 divide-y divide-border/30">
              {detailLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-2">
                  <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <p className="text-[10px] text-muted-foreground">Fetching ledger accounts...</p>
                </div>
              ) : (
                (() => {
                  const filtered = detailData.filter(item => 
                    item.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                    item.group_name.toLowerCase().includes(searchTerm.toLowerCase())
                  )
                  
                  if (filtered.length === 0) {
                    return (
                      <p className="text-center text-xs text-muted-foreground py-8">
                        No ledger accounts found.
                      </p>
                    )
                  }
                  
                  const isCreditHeavy = detailModal === 'sales' || detailModal === 'payables'
                  
                  return filtered.map((item, idx) => {
                    const balanceSign = isCreditHeavy 
                      ? (item.balance >= 0 ? 'Cr' : 'Dr') 
                      : (item.balance >= 0 ? 'Dr' : 'Cr')
                      
                    return (
                      <div key={item.ledger_id} className={cn("flex items-center justify-between gap-3 text-xs", idx > 0 ? "pt-2.5" : "")}>
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-foreground truncate">{item.name}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{item.group_name}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className={cn(
                            "font-black text-sm",
                            detailModal === 'sales' || detailModal === 'receipts' ? "text-emerald-600" :
                            detailModal === 'receivables' ? "text-amber-600" : "text-rose-600"
                          )}>
                            ₹{Math.abs(item.balance).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                          <p className="text-[9px] text-muted-foreground/80 mt-0.5 uppercase tracking-wider">
                            {balanceSign}
                          </p>
                        </div>
                      </div>
                    )
                  })
                })()
              )}
            </div>
          </div>
        </div>
      )}

      {/* CHANGE PERIOD MODAL */}
      {periodModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-150">
          <div className="bg-card border border-border rounded-3xl max-w-md w-full p-5 space-y-5 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-2xl bg-sky-500/10 text-sky-600">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-lg text-foreground">Change Period</h3>
                  <p className="text-xs text-muted-foreground">Select reporting date range</p>
                </div>
              </div>
              <button 
                onClick={() => setPeriodModalOpen(false)}
                className="p-2 hover:bg-secondary rounded-full transition-colors text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Presets */}
            <div>
              <label className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-2 block">Quick Presets</label>
              <div className="grid grid-cols-5 gap-1.5">
                <button
                  type="button"
                  onClick={() => selectPreset('current_fy')}
                  className={cn(
                    "px-1 py-2 text-[10px] sm:text-[11px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'current_fy'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Current FY
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('prev_fy')}
                  className={cn(
                    "px-1 py-2 text-[10px] sm:text-[11px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'prev_fy'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Prev FY
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('this_month')}
                  className={cn(
                    "px-1 py-2 text-[10px] sm:text-[11px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'this_month'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  This Month
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('last_month')}
                  className={cn(
                    "px-1 py-2 text-[10px] sm:text-[11px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'last_month'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Last Month
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('all_time')}
                  className={cn(
                    "px-1 py-2 text-[10px] sm:text-[11px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'all_time'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  All Time
                </button>
              </div>
              <div className="grid grid-cols-4 gap-1.5 mt-1.5">
                <button
                  type="button"
                  onClick={() => selectPreset('q1')}
                  className={cn(
                    "px-1.5 py-1.5 text-[10px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'q1'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Q1 (Apr-Jun)
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('q2')}
                  className={cn(
                    "px-1.5 py-1.5 text-[10px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'q2'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Q2 (Jul-Sep)
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('q3')}
                  className={cn(
                    "px-1.5 py-1.5 text-[10px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'q3'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Q3 (Oct-Dec)
                </button>
                <button
                  type="button"
                  onClick={() => selectPreset('q4')}
                  className={cn(
                    "px-1.5 py-1.5 text-[10px] font-bold rounded-xl transition-colors text-center cursor-pointer",
                    activePreset === 'q4'
                      ? "bg-sky-600 text-white shadow-sm"
                      : "bg-secondary hover:bg-sky-500/20 text-foreground"
                  )}
                >
                  Q4 (Jan-Mar)
                </button>
              </div>
            </div>

            {/* Custom Dates Inputs */}
            <div className="space-y-3 pt-2 border-t border-border">
              <div>
                <label className="text-xs font-bold text-foreground block mb-1">Starting Date (From)</label>
                <input
                  type="date"
                  value={fromDate}
                  onChange={e => {
                    setFromDate(e.target.value)
                    setActivePreset('custom')
                  }}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:ring-2 focus:ring-sky-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-foreground block mb-1">Ending Date (To)</label>
                <input
                  type="date"
                  value={toDate}
                  onChange={e => {
                    setToDate(e.target.value)
                    setActivePreset('custom')
                  }}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:ring-2 focus:ring-sky-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setActivePreset('current_fy')
                  applyPeriodChanges('2025-04-01', '2026-03-31')
                }}
                className="flex-1 px-4 py-2.5 text-xs font-bold border border-border rounded-xl hover:bg-secondary transition-colors cursor-pointer"
              >
                Reset Default
              </button>
              <button
                type="button"
                onClick={() => applyPeriodChanges(fromDate, toDate)}
                className="flex-1 px-4 py-2.5 text-xs font-bold bg-sky-600 hover:bg-sky-700 text-white rounded-xl shadow-md transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                <Check className="w-4 h-4" />
                Apply Period
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
