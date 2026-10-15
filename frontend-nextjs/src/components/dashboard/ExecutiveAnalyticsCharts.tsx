'use client'

import Link from 'next/link'
import {
  BarChart3,
  TrendingUp,
  Clock,
  Wallet,
  Users,
  Loader2,
  ArrowRight,
  ArrowUpRight,
} from 'lucide-react'
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
import { UserPermissions } from '@/context/AuthContext'

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

export interface MonthlyTrendItem {
  month: string
  sales: number
  receipts: number
}

export interface ReceivablesAgingItem {
  bucket: string
  amount: number
}

export interface ExpenseBreakdownItem {
  category: string
  amount: number
}

export interface TopCustomerItem {
  name: string
  total_sales: number
}

export interface ExecutiveAnalyticsData {
  monthly_trend?: MonthlyTrendItem[]
  receivables_aging?: ReceivablesAgingItem[]
  expense_breakdown?: ExpenseBreakdownItem[]
}

interface ExecutiveAnalyticsChartsProps {
  analyticsData: ExecutiveAnalyticsData | null
  topCustomersData: TopCustomerItem[]
  analyticsLoading: boolean
  permissions: UserPermissions
  can: (module: string, action: 'create' | 'read' | 'update' | 'delete') => boolean
}

export default function ExecutiveAnalyticsCharts({
  analyticsData,
  topCustomersData,
  analyticsLoading,
  permissions,
  can,
}: ExecutiveAnalyticsChartsProps) {
  return (
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
          {analyticsData?.monthly_trend && analyticsData.monthly_trend.length > 0 ? (
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
                  tickFormatter={(v: number) => `₹${v >= 100000 ? (v / 100000).toFixed(1) + 'L' : (v / 1000).toFixed(0) + 'k'}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(23, 23, 23, 0.95)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                  formatter={(val: unknown) => [formatCurrency(typeof val === 'number' ? val : Number(val)), '']}
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
              {analyticsData?.receivables_aging && analyticsData.receivables_aging.some((b: ReceivablesAgingItem) => b.amount > 0) ? (
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
                      {analyticsData.receivables_aging.map((entry: ReceivablesAgingItem, index: number) => (
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
                      formatter={(val: unknown) => [formatCurrency(typeof val === 'number' ? val : Number(val)), 'Pending']}
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
              {analyticsData?.expense_breakdown && analyticsData.expense_breakdown.length > 0 ? (
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
                      {analyticsData.expense_breakdown.map((_: ExpenseBreakdownItem, index: number) => (
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
                      formatter={(val: unknown) => [formatCurrency(typeof val === 'number' ? val : Number(val)), 'Expense']}
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
          {topCustomersData && topCustomersData.length > 0 ? (
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
                  tickFormatter={(v: number) => `₹${v >= 100000 ? (v / 100000).toFixed(1) + 'L' : (v / 1000).toFixed(0) + 'k'}`}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={125}
                  tick={{ fontSize: 10 }}
                  stroke="#888888"
                  tickFormatter={(name: string) => (name && name.length > 18 ? name.slice(0, 16) + '…' : name || '')}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(23, 23, 23, 0.95)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                  formatter={(val: unknown) => [formatCurrency(typeof val === 'number' ? val : Number(val)), 'Sales Volume']}
                  labelFormatter={(label: unknown) => `Customer: ${label}`}
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
  )
}
