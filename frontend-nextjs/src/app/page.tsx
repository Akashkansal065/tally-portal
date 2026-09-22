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
  ArrowUpRight,
  Shield,
  Clock,
  FileSpreadsheet,
  X,
  Search,
  Calendar,
  CalendarCheck,
  Edit3,
  Filter,
  RefreshCw,
  Check,
  Users,
  TrendingUp,
  Loader2,
  PieChart as PieChartIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts'

const AGING_COLORS: Record<string, string> = {
  '0-30 Days': '#10b981',
  '31-60 Days': '#f59e0b',
  '61-90 Days': '#f97316',
  '90+ Days': '#f43f5e',
}

const EXPENSE_COLORS = [
  '#6366f1',
  '#ec4899',
  '#f59e0b',
  '#10b981',
  '#06b6d4',
  '#8b5cf6',
  '#ef4444',
  '#14b8a6',
]

const formatCurrency = (val: number | undefined | null) => {
  if (val === undefined || val === null || isNaN(val)) return '₹0'
  return '₹' + Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })
}

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
  const isAdmin = Boolean(
    permissions?.isAdmin ||
    user?.role?.toLowerCase() === 'admin' ||
    user?.role?.toLowerCase() === 'owner' ||
    user?.role?.toLowerCase() === 'superadmin'
  )
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

  // Analytics charts states (gated by permissions.showReports)
  const [mounted, setMounted] = useState(false)
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [topCustomersData, setTopCustomersData] = useState<any[]>([])
  const [analyticsLoading, setAnalyticsLoading] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    setFromDate(globalFrom)
    setToDate(globalTo)
  }, [globalFrom, globalTo])

  const applyPeriodChanges = (fDate: string, tDate: string) => {
    setPeriod(fDate, tDate)
    loadDashboard(fDate, tDate)
    loadAnalytics(fDate, tDate)
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
      const res = await fetch(url, { headers: authHeaders(token) }).catch(() => null)
      if (res && res.ok) {
        const data = await res.json().catch(() => null)
        if (data) setDashboardData(data)
      }
    } catch (e) {
      console.warn('Dashboard summary temporarily unavailable:', e)
    } finally {
      setFetchingSummary(false)
    }
  }

  const loadAnalytics = async (fDate?: string, tDate?: string) => {
    if (!token || !permissions.showReports) return
    const targetFrom = fDate || globalFrom
    const targetTo = tDate || globalTo
    setAnalyticsLoading(true)
    try {
      const queryParams: string[] = []
      if (targetFrom) queryParams.push(`from_date=${targetFrom}`)
      if (targetTo) queryParams.push(`to_date=${targetTo}`)
      const qs = queryParams.length > 0 ? `?${queryParams.join('&')}` : ''

      const [resAnalytics, resTopCustomers] = await Promise.all([
        fetch(`${API_BASE}/reports/executive-analytics${qs}`, { headers: authHeaders(token) }).catch(() => null),
        fetch(`${API_BASE}/reports/top-customers${qs}`, { headers: authHeaders(token) }).catch(() => null),
      ])

      if (resAnalytics && resAnalytics.ok) {
        const data = await resAnalytics.json().catch(() => null)
        if (data) setAnalyticsData(data)
      }
      if (resTopCustomers && resTopCustomers.ok) {
        const data = await resTopCustomers.json().catch(() => null)
        if (Array.isArray(data)) setTopCustomersData(data)
      }
    } catch (e) {
      console.warn('Executive analytics temporarily unavailable:', e)
    } finally {
      setAnalyticsLoading(false)
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
    if (!permissions.showReports) return
    setDetailModal(category)
    setDetailLoading(true)

    setDetailData([])
    setSearchTerm('')
    try {
      const res = await fetch(`${API_BASE}/reports/dashboard-details?category=${category}`, {
        headers: authHeaders(token)
      }).catch(() => null)
      if (res && res.ok) {
        const data = await res.json().catch(() => null)
        if (data) setDetailData(data)
      }
    } catch (e) {
      console.warn('Dashboard detail category temporarily unavailable:', e)
    } finally {
      setDetailLoading(false)
    }
  }
  
  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login')
    } else if (user && permissions.showReports) {
      loadDashboard(globalFrom, globalTo)
      loadAnalytics(globalFrom, globalTo)
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
      show: Boolean(permissions.showVouchers ?? permissions.showReceipts),
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
      href: '/customers',
      label: 'Customer Directory',
      description: 'Filter shops by locality, navigate with Google Maps & audit visits',
      icon: Users,
      color: 'text-violet-600',
      bgColor: 'bg-violet-500/10 border-violet-500/20',
      show: Boolean(permissions.showCustomers || isAdmin),
    },
    {
      href: '/stocks',
      label: 'Stocks & Inventory',
      description: 'Browse warehouse items, closing rates, and batch values',
      icon: Layers,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      show: permissions.showStocks && permissions.stockScope !== 'catalog_only',
    },
    {
      href: '/inventory/bom',
      label: 'BOM & Manufacturing',
      description: 'Bill of Materials recipe designer and manufacturing stock journals',
      icon: Layers,
      color: 'text-cyan-600',
      bgColor: 'bg-cyan-500/10 border-cyan-500/20',
      show: permissions.showStocks && permissions.stockScope !== 'catalog_only',
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
      href: '/planner',
      label: 'Daily Beat Planner',
      description: 'Route beat assignments, TSP auto-route stops & EOD scorecard',
      icon: CalendarCheck,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-500/10 border-indigo-500/20',
      show: permissions.showCheckIn,
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
    <div className="p-4 space-y-6 max-w-5xl mx-auto">
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
                {dashboardData?.current_period || (fromDate && toDate ? `${new Date(fromDate).toLocaleDateString('en-GB', {day: 'numeric', month:'short', year:'2-digit'})} to ${new Date(toDate).toLocaleDateString('en-GB', {day: 'numeric', month:'short', year:'2-digit'})}` : '1-Apr-26 to 31-Mar-27')}
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
              {dashboardData?.company_name || user?.allowedCompanies?.find(c => c.company_id === user?.company_id)?.name || user?.company_name || 'Sneh Distributors'}
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

{/* Metrics Row (Gated by permissions.showReports) */}
      {permissions.showReports && dashboardData && typeof dashboardData.total_sales === 'number' && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">

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

      {/* ─── Executive Analytics Charts (Gated by permissions.showReports) ─── */}
      {permissions.showReports && (
        <div className="space-y-5 my-6">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold">
                <BarChart3 className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-base font-extrabold text-foreground tracking-tight flex items-center gap-2">
                  Executive Analytics & Trends
                  {analyticsLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600" />}
                </h2>
                <p className="text-[11px] text-muted-foreground">
                  Visual performance indicators, cash flow trends & debtors aging
                </p>
              </div>
            </div>
            <Link
              href="/reports"
              className="text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 shrink-0"
            >
              <span>Full Reports</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {/* Chart 1: Monthly Sales vs Receipts Trend AreaChart */}
          <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-border/50 pb-3">
              <div>
                <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  Monthly Sales vs Cash Receipts
                </h3>
                <p className="text-[11px] text-muted-foreground">
                  Billed turnover vs actual receipts across financial months
                </p>
              </div>
              <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider bg-emerald-500/10 px-2 py-0.5 rounded-md self-start sm:self-auto">
                Revenue & Inflow
              </span>
            </div>

            <div className="h-64 sm:h-72 w-full pt-2">
              {mounted && analyticsData?.monthly_trend && analyticsData.monthly_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={analyticsData.monthly_trend}>
                    <defs>
                      <linearGradient id="salesGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="receiptGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.12} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="#888888" />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      stroke="#888888"
                      tickFormatter={(v) => `₹${v >= 100000 ? (v / 100000).toFixed(1) + 'L' : (v / 1000).toFixed(0) + 'k'}`}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(23, 23, 23, 0.95)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '12px',
                        color: '#fff',
                        fontSize: '12px',
                      }}
                      formatter={(val: any) => [formatCurrency(Number(val)), '']}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Area
                      type="monotone"
                      dataKey="sales"
                      name="Sales Billed"
                      stroke="#10b981"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#salesGrad)"
                    />
                    <Area
                      type="monotone"
                      dataKey="receipts"
                      name="Cash Collected"
                      stroke="#3b82f6"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#receiptGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                  {analyticsLoading ? 'Loading monthly trend...' : 'No trend data available for selected period'}
                </div>
              )}
            </div>
          </div>

          {/* Row 2: Aging Donut + Expense Category Pie Chart */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Chart 2: Outstanding Receivables Aging Donut */}
            <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                      <Clock className="w-4 h-4 text-amber-500" />
                      Receivables Aging Breakdown
                    </h3>
                    <p className="text-[11px] text-muted-foreground">
                      Overdue customer debt by age bracket
                    </p>
                  </div>
                  <Link
                    href="/outstanding"
                    className="text-[11px] font-bold text-emerald-600 hover:underline flex items-center gap-0.5"
                  >
                    <span>Aging Hub</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </Link>
                </div>

                <div className="h-60 w-full pt-2">
                  {mounted && analyticsData?.receivables_aging && analyticsData.receivables_aging.some((b: any) => b.amount > 0) ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={analyticsData.receivables_aging}
                          dataKey="amount"
                          nameKey="bucket"
                          cx="50%"
                          cy="50%"
                          innerRadius={52}
                          outerRadius={78}
                          paddingAngle={3}
                        >
                          {analyticsData.receivables_aging.map((entry: any, index: number) => (
                            <Cell
                              key={`aging-${index}`}
                              fill={AGING_COLORS[entry.bucket] || '#94a3b8'}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'rgba(23, 23, 23, 0.95)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '12px',
                            color: '#fff',
                            fontSize: '12px',
                          }}
                          formatter={(val: any) => [formatCurrency(Number(val)), 'Pending']}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                      {analyticsLoading ? 'Calculating receivables...' : 'No overdue receivables recorded'}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Chart 3: Expense Categories Donut Chart */}
            <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                      <Wallet className="w-4 h-4 text-purple-500" />
                      Operating Expense Breakdown
                    </h3>
                    <p className="text-[11px] text-muted-foreground">
                      Overhead, operational costs & tax debits
                    </p>
                  </div>
                  <Link
                    href="/expenses"
                    className="text-[11px] font-bold text-emerald-600 hover:underline flex items-center gap-0.5"
                  >
                    <span>Expenses</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </Link>
                </div>

                <div className="h-60 w-full pt-2">
                  {mounted && analyticsData?.expense_breakdown && analyticsData.expense_breakdown.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={analyticsData.expense_breakdown}
                          dataKey="amount"
                          nameKey="category"
                          cx="50%"
                          cy="50%"
                          innerRadius={48}
                          outerRadius={76}
                          paddingAngle={3}
                        >
                          {analyticsData.expense_breakdown.map((_: any, index: number) => (
                            <Cell
                              key={`exp-${index}`}
                              fill={EXPENSE_COLORS[index % EXPENSE_COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'rgba(23, 23, 23, 0.95)',
                            border: '1px solid rgba(255, 255, 255, 0.1)',
                            borderRadius: '12px',
                            color: '#fff',
                            fontSize: '12px',
                          }}
                          formatter={(val: any) => [formatCurrency(Number(val)), 'Expense']}
                        />
                        <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '6px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                      {analyticsLoading ? 'Loading expenses...' : 'No expense entries in selected period'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Chart 4: Top 10 Customers Horizontal BarChart */}
          <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-border/50 pb-3">
              <div>
                <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-sky-500" />
                  Top 10 Customers by Sales Volume
                </h3>
                <p className="text-[11px] text-muted-foreground">
                  Debtors ranked by total sales turnover for this period
                </p>
              </div>
              {Boolean(permissions.showCustomers || isAdmin) && (
                <Link
                  href="/customers"
                  className="text-[11px] font-bold text-emerald-600 hover:underline flex items-center gap-0.5 self-start sm:self-auto"
                >
                  <span>Directory</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              )}
            </div>

            <div className="h-72 sm:h-80 w-full pt-2">
              {mounted && topCustomersData && topCustomersData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topCustomersData}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" opacity={0.12} horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10 }}
                      stroke="#888888"
                      tickFormatter={(v) => `₹${v >= 100000 ? (v / 100000).toFixed(1) + 'L' : (v / 1000).toFixed(0) + 'k'}`}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={125}
                      tick={{ fontSize: 10 }}
                      stroke="#888888"
                      tickFormatter={(name) => (name && name.length > 18 ? name.slice(0, 16) + '…' : name || '')}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(23, 23, 23, 0.95)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '12px',
                        color: '#fff',
                        fontSize: '12px',
                      }}
                      formatter={(val: any) => [formatCurrency(Number(val)), 'Sales Volume']}
                      labelFormatter={(label) => `Customer: ${label}`}
                    />
                    <Bar
                      dataKey="total_sales"
                      name="Sales Volume"
                      fill="#0ea5e9"
                      radius={[0, 6, 6, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                  {analyticsLoading ? 'Loading top customers...' : 'No customer sales recorded in selected period'}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Dashboard grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">

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

      {/* Detail Drill-down Modal (Gated by permissions.showReports) */}
      {permissions.showReports && detailModal && (
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
