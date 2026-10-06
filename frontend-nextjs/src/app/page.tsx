'use client'

import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { usePeriod } from '@/context/PeriodContext'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'
import {
  BarChart3,
  Wallet,
  ArrowRight,
  ArrowUpRight,
  Clock,
  Search,
  Edit3,
  Check,
  Users,
  TrendingUp,
  Loader2,
  LayoutGrid,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { MoreSheet, moduleTileClass } from '@/components/MoreSheet'
import { NeedsAttention, TargetTracker } from '@/components/reports/TargetTracker'
import { isAdminUser, quickModules } from '@/lib/navigation'
import { useOfflinePending } from '@/hooks/useOfflinePending'
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

// Buckets are days past each bill's due date (invoice date + the customer's credit days)
const AGING_COLORS: Record<string, string> = {
  'Not due': '#94a3b8',
  '1-30 Days': '#10b981',
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

/** yyyy-mm-dd in the device's own time zone (toISOString would shift 1 Apr to 31 Mar in India). */
const toDateInput = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Parse yyyy-mm-dd as a local date, so labels never show the day before. */
const fromDateInput = (s: string) => {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

const shortDate = (s: string) =>
  fromDateInput(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' })

type PeriodPreset = 'current_fy' | 'prev_fy' | 'this_month' | 'last_month' | 'all_time' | 'q1' | 'q2' | 'q3' | 'q4'

const PERIOD_PRESETS: { id: PeriodPreset; label: string }[] = [
  { id: 'current_fy', label: 'Current FY' },
  { id: 'prev_fy', label: 'Previous FY' },
  { id: 'this_month', label: 'This month' },
  { id: 'last_month', label: 'Last month' },
  { id: 'all_time', label: 'All time' },
]

const QUARTER_PRESETS: { id: PeriodPreset; label: string }[] = [
  { id: 'q1', label: 'Q1 · Apr–Jun' },
  { id: 'q2', label: 'Q2 · Jul–Sep' },
  { id: 'q3', label: 'Q3 · Oct–Dec' },
  { id: 'q4', label: 'Q4 · Jan–Mar' },
]

/** Start and end dates for a preset, using the Indian financial year (April to March). */
function presetRange(preset: PeriodPreset, now = new Date()): [string, string] {
  const fy = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1
  const month = (offset: number): [string, string] => [
    toDateInput(new Date(now.getFullYear(), now.getMonth() + offset, 1)),
    toDateInput(new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)),
  ]
  switch (preset) {
    case 'current_fy': return [`${fy}-04-01`, `${fy + 1}-03-31`]
    case 'prev_fy': return [`${fy - 1}-04-01`, `${fy}-03-31`]
    case 'this_month': return month(0)
    case 'last_month': return month(-1)
    case 'all_time': return ['2000-01-01', '2099-12-31']
    case 'q1': return [`${fy}-04-01`, `${fy}-06-30`]
    case 'q2': return [`${fy}-07-01`, `${fy}-09-30`]
    case 'q3': return [`${fy}-10-01`, `${fy}-12-31`]
    case 'q4': return [`${fy + 1}-01-01`, `${fy + 1}-03-31`]
  }
}

/** The preset a saved period matches, or 'custom'. */
function matchPreset(from: string, to: string): PeriodPreset | 'custom' {
  const all = [...PERIOD_PRESETS, ...QUARTER_PRESETS]
  return all.find(({ id }) => {
    const [start, end] = presetRange(id)
    return start === from && end === to
  })?.id ?? 'custom'
}

type DetailCategory = 'sales' | 'receipts' | 'receivables' | 'payables'

const DETAIL_TITLES: Record<DetailCategory, string> = {
  sales: 'Total sales breakdown',
  receipts: 'Total receipts breakdown',
  receivables: 'Receivables breakdown',
  payables: 'Payables breakdown',
}

const DETAIL_AMOUNT_COLOR: Record<DetailCategory, string> = {
  sales: 'text-emerald-700 dark:text-emerald-400',
  receipts: 'text-emerald-700 dark:text-emerald-400',
  receivables: 'text-amber-700 dark:text-amber-400',
  payables: 'text-rose-700 dark:text-rose-400',
}

const BANNER_LABEL = 'block text-xs font-bold uppercase tracking-wider text-sky-700 dark:text-sky-400'

export default function DashboardPage() {
  const { user, token, permissions, isLoading, can } = useAuth()
  const { startDate: globalFrom, endDate: globalTo, setPeriod } = usePeriod()
  const router = useRouter()

  const [dashboardData, setDashboardData] = useState<any>(null)
  const [detailCategory, setDetailCategory] = useState<DetailCategory>('sales')
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailData, setDetailData] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [moreOpen, setMoreOpen] = useState(false)

  // Draft dates for the period sheet; copied from PeriodContext each time the sheet opens
  const [fromDate, setFromDate] = useState<string>(globalFrom)
  const [toDate, setToDate] = useState<string>(globalTo)
  const [activePreset, setActivePreset] = useState<PeriodPreset | 'custom'>('current_fy')
  const [periodModalOpen, setPeriodModalOpen] = useState(false)
  const [fetchingSummary, setFetchingSummary] = useState(false)

  const offlinePending = useOfflinePending()
  const quickAccess = useMemo(
    () => quickModules({ permissions, can, isAdmin: isAdminUser(permissions, user?.role), offlinePending }, 7),
    [permissions, can, user?.role, offlinePending],
  )

  // Analytics charts states (gated by permissions.showReports)
  const [mounted, setMounted] = useState(false)
  const [analyticsData, setAnalyticsData] = useState<any>(null)
  const [topCustomersData, setTopCustomersData] = useState<any[]>([])
  const [analyticsLoading, setAnalyticsLoading] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const openPeriodSheet = () => {
    setFromDate(globalFrom)
    setToDate(globalTo)
    setActivePreset(matchPreset(globalFrom, globalTo))
    setPeriodModalOpen(true)
  }

  // The effect below reloads the dashboard when the global period changes
  const applyPeriodChanges = (fDate: string, tDate: string) => {
    setPeriod(fDate, tDate)
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



  const selectPreset = (preset: PeriodPreset) => {
    const [start, end] = presetRange(preset)
    setActivePreset(preset)
    setFromDate(start)
    setToDate(end)
  }

  const openDetail = async (category: DetailCategory) => {
    if (!permissions.showReports) return
    setDetailCategory(category)
    setDetailOpen(true)
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

  const periodLabel = dashboardData?.current_period
    || (globalFrom && globalTo ? `${shortDate(globalFrom)} to ${shortDate(globalTo)}` : '')
  const companyName = dashboardData?.company_name
    || user.allowedCompanies?.find(c => c.company_id === user.company_id)?.name
    || user.company_name
    || 'Sneh Distributors'

  const metrics: { category: DetailCategory; label: string; value: number | undefined; box: string; text: string }[] = dashboardData
    ? [
        { category: 'sales', label: 'Total sales', value: dashboardData.total_sales,
          box: 'bg-emerald-500/10 border-emerald-500/20', text: 'text-emerald-700 dark:text-emerald-400' },
        { category: 'receipts', label: 'Total receipts', value: dashboardData.total_receipts,
          box: 'bg-blue-500/10 border-blue-500/20', text: 'text-blue-700 dark:text-blue-400' },
        { category: 'receivables', label: 'To receive', value: dashboardData.outstanding_receivables,
          box: 'bg-amber-500/10 border-amber-500/20', text: 'text-amber-700 dark:text-amber-400' },
        { category: 'payables', label: 'To pay', value: dashboardData.outstanding_payables,
          box: 'bg-rose-500/10 border-rose-500/20', text: 'text-rose-700 dark:text-rose-400' },
      ]
    : []

  return (
    <div className="p-4 space-y-6 max-w-5xl mx-auto">
      {/* Welcome block */}
      <div className="pt-2">
        <h1 className="text-xl md:text-2xl font-extrabold tracking-tight">
          Welcome, <span className="text-primary">{user.username}</span>
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Real-time synchronization with Tally Prime
        </p>
      </div>

      {/* Monthly target and what needs attention: the first things to check each day */}
      {permissions.showReports && (
        <div className="space-y-3">
          <TargetTracker />
          <NeedsAttention />
        </div>
      )}

      {/* Tally Prime style header. Phones skip the company (it's in the top bar) and today's date. */}
      <section
        aria-label="Company and period"
        className="bg-card border border-sky-300/60 dark:border-sky-800/60 rounded-2xl p-4 shadow-sm relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 rounded-full blur-2xl pointer-events-none" />
        <dl className="relative grid gap-x-4 gap-y-2 md:grid-cols-2 md:gap-y-3">
          <div className="min-w-0">
            <dt className={BANNER_LABEL}>Current period</dt>
            <dd>
              <button
                type="button"
                onClick={openPeriodSheet}
                aria-label={`Change period, currently ${periodLabel}`}
                className="group -mx-2 flex min-h-11 items-center gap-1.5 rounded-xl px-2 text-left text-base font-extrabold tracking-tight text-foreground hover:bg-sky-500/10 cursor-pointer"
              >
                <span>{periodLabel}</span>
                <Edit3 className="h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400 opacity-80 group-hover:opacity-100" aria-hidden="true" />
              </button>
            </dd>
          </div>
          <div className="max-md:hidden min-w-0 text-right">
            <dt className={BANNER_LABEL}>Current date</dt>
            <dd className="flex min-h-11 items-center justify-end text-base font-extrabold tracking-tight">
              {dashboardData?.current_date || new Date().toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })}
            </dd>
          </div>
          <div className="max-md:hidden min-w-0">
            <dt className={BANNER_LABEL}>Name of company</dt>
            <dd className="text-lg font-black tracking-tight">{companyName}</dd>
          </div>
          {dashboardData && (
            <div className="min-w-0 md:text-right">
              <dt className={BANNER_LABEL}>Last entry</dt>
              <dd className="text-base md:text-lg font-black tracking-tight">
                {dashboardData.date_of_last_entry || 'No entries'}
              </dd>
            </div>
          )}
        </dl>
      </section>

      {/* Metrics row (gated by permissions.showReports) */}
      {permissions.showReports && dashboardData && typeof dashboardData.total_sales === 'number' && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {metrics.map(metric => (
            <button
              key={metric.category}
              type="button"
              onClick={() => openDetail(metric.category)}
              aria-haspopup="dialog"
              className={cn(
                'flex min-h-[76px] flex-col items-start gap-1 rounded-2xl border p-3.5 sm:p-4 text-left cursor-pointer transition-transform duration-100 hover:shadow-sm active:scale-[0.98]',
                metric.box,
              )}
            >
              <span className={cn('text-xs font-bold uppercase tracking-wider', metric.text)}>{metric.label}</span>
              <span className={cn('text-lg sm:text-xl font-black leading-tight tabular-nums break-all', metric.text)}>
                {formatCurrency(metric.value)}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Quick access: the next screens for this role after the tab bar, plus a way into every screen */}
      <section aria-labelledby="quick-access-title">
        <h2 id="quick-access-title" className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Quick access
        </h2>
        <ul className="grid grid-cols-4 gap-2 sm:grid-cols-8">
          {quickAccess.map(module => {
            const Icon = module.icon
            return (
              <li key={module.id}>
                <Link href={module.href} className={moduleTileClass()}>
                  <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                  <span className="text-xs font-semibold leading-tight">{module.label}</span>
                </Link>
              </li>
            )
          })}
          <li>
            <button type="button" onClick={() => setMoreOpen(true)} aria-haspopup="dialog" className={moduleTileClass()}>
              <LayoutGrid className="h-5 w-5 shrink-0" aria-hidden="true" />
              <span className="text-xs font-semibold leading-tight">All screens</span>
            </button>
          </li>
        </ul>
      </section>

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
                <p className="text-xs text-muted-foreground">
                  Visual performance indicators, cash flow trends & debtors aging
                </p>
              </div>
            </div>
            <Link
              href="/reports"
              className="-my-3 inline-flex min-h-11 shrink-0 items-center gap-1 text-xs font-bold text-emerald-700 dark:text-emerald-400 hover:underline"
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
                <p className="text-xs text-muted-foreground">
                  Billed turnover vs actual receipts across financial months
                </p>
              </div>
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400 uppercase tracking-wider bg-emerald-500/10 px-2 py-0.5 rounded-md self-start sm:self-auto">
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
                    <p className="text-xs text-muted-foreground">
                      Days past due, using each customer&apos;s credit days
                    </p>
                  </div>
                  {can('outstanding', 'read') && (
                    <Link
                      href="/outstanding"
                      className="-my-3 inline-flex min-h-11 shrink-0 items-center gap-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-400 hover:underline"
                    >
                      <span>Aging Hub</span>
                      <ArrowUpRight className="w-3 h-3" />
                    </Link>
                  )}
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
                    <p className="text-xs text-muted-foreground">
                      Overhead, operational costs & tax debits
                    </p>
                  </div>
                  <Link
                    href="/expenses"
                    className="-my-3 inline-flex min-h-11 shrink-0 items-center gap-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-400 hover:underline"
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
                <p className="text-xs text-muted-foreground">
                  Debtors ranked by total sales turnover for this period
                </p>
              </div>
              {Boolean(permissions.showCustomers && can('customers', 'read')) && (
                <Link
                  href="/customers"
                  className="-my-3 inline-flex min-h-11 items-center gap-0.5 self-start text-xs font-bold text-emerald-700 dark:text-emerald-400 hover:underline sm:self-auto"
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

      {/* Drill-down behind each metric (gated by permissions.showReports) */}
      {permissions.showReports && (
        <BottomSheet
          open={detailOpen}
          onOpenChange={setDetailOpen}
          title={DETAIL_TITLES[detailCategory]}
          description="Ledger balances that make up this total"
        >
          <div className="sticky top-0 z-10 -mx-5 bg-card px-5 pb-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <input
                type="search"
                placeholder="Search ledgers or groups…"
                aria-label="Search ledgers or groups"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="h-11 w-full rounded-xl border border-border bg-background pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </div>

          {detailLoading ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12" role="status">
              <Loader2 className="h-6 w-6 animate-spin text-primary" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">Fetching ledger accounts…</p>
            </div>
          ) : (() => {
            const term = searchTerm.toLowerCase()
            const filtered = detailData.filter(item =>
              item.name.toLowerCase().includes(term) || item.group_name.toLowerCase().includes(term)
            )
            if (filtered.length === 0) {
              return <p className="py-8 text-center text-sm text-muted-foreground">No ledger accounts found.</p>
            }
            const isCreditHeavy = detailCategory === 'sales' || detailCategory === 'payables'
            return (
              <ul className="divide-y divide-border/50">
                {filtered.map(item => {
                  const balanceSign = isCreditHeavy
                    ? (item.balance >= 0 ? 'Cr' : 'Dr')
                    : (item.balance >= 0 ? 'Dr' : 'Cr')
                  return (
                    <li key={item.ledger_id} className="flex min-h-14 items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-foreground">{item.name}</p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.group_name}</p>
                      </div>
                      <p className="shrink-0 text-right">
                        <span className={cn('text-sm font-black tabular-nums', DETAIL_AMOUNT_COLOR[detailCategory])}>
                          {formatCurrency(Math.abs(item.balance))}
                        </span>
                        <span className="ml-1 text-xs font-semibold text-muted-foreground">{balanceSign}</span>
                      </p>
                    </li>
                  )
                })}
              </ul>
            )
          })()}
        </BottomSheet>
      )}

      {/* Change period */}
      <BottomSheet
        open={periodModalOpen}
        onOpenChange={setPeriodModalOpen}
        title="Change period"
        description="Reporting dates used across the app"
        footer={
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => applyPeriodChanges(...presetRange('current_fy'))}
              className="min-h-12 rounded-xl border border-border px-4 text-sm font-bold text-foreground hover:bg-muted cursor-pointer"
            >
              Reset to current FY
            </button>
            <button
              type="button"
              onClick={() => applyPeriodChanges(fromDate, toDate)}
              disabled={!fromDate || !toDate || fromDate > toDate}
              className="flex min-h-12 items-center justify-center gap-2 rounded-xl bg-sky-600 px-4 text-sm font-bold text-white shadow-sm hover:bg-sky-700 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Apply period
            </button>
          </div>
        }
      >
        <div className="space-y-5">
          {[
            { title: 'Quick presets', presets: PERIOD_PRESETS },
            { title: 'Quarters of this FY', presets: QUARTER_PRESETS },
          ].map(({ title, presets }) => (
            <fieldset key={title}>
              <legend className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">{title}</legend>
              <div className="flex flex-wrap gap-2">
                {presets.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => selectPreset(id)}
                    aria-pressed={activePreset === id}
                    className={cn(
                      'min-h-11 rounded-full border px-4 text-sm font-semibold transition-colors cursor-pointer',
                      activePreset === id
                        ? 'border-sky-600 bg-sky-600 text-white'
                        : 'border-border bg-background text-foreground hover:bg-sky-500/10',
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </fieldset>
          ))}

          <fieldset className="border-t border-border pt-4">
            <legend className="sr-only">Custom dates</legend>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-sm font-bold text-foreground">From</span>
                <input
                  type="date"
                  value={fromDate}
                  onChange={e => {
                    setFromDate(e.target.value)
                    setActivePreset('custom')
                  }}
                  className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-bold text-foreground">To</span>
                <input
                  type="date"
                  value={toDate}
                  min={fromDate || undefined}
                  onChange={e => {
                    setToDate(e.target.value)
                    setActivePreset('custom')
                  }}
                  className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </label>
            </div>
            {fromDate && toDate && fromDate > toDate && (
              <p className="mt-2 text-sm text-destructive" role="alert">The start date is after the end date.</p>
            )}
          </fieldset>
        </div>
      </BottomSheet>

      <MoreSheet open={moreOpen} onOpenChange={setMoreOpen} />
    </div>
  )
}
