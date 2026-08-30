'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import {
  BarChart3, TrendingUp, TrendingDown, Package, Layers, BookOpen, FileText,
  DollarSign, PieChart as PieChartIcon, Calendar, Download, RefreshCw, Search,
  ArrowUpRight, ArrowDownRight, Layers3, Users, Building2, Info, HelpCircle, Check, X,
  CheckCircle2, Sparkles, AlertCircle, ExternalLink, Filter, ShoppingBag, Landmark, Clock
} from 'lucide-react'
import { cn } from '@/lib/utils'

import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid
} from 'recharts'
import ProjectedFinancials from '@/components/ProjectedFinancials'

type TabType = 'executive' | 'financial' | 'sales' | 'inventory' | 'compliance'
type PresetType = 'month' | 'quarter' | 'current_fy' | 'prev_fy' | 'year' | 'custom'
type ExplanationKey = 'revenue_trend' | 'aging' | 'expense' | 'top_customers' | 'inventory' | 'trial_balance' | null
type KpiModalKey = 'sales' | 'receipts' | 'purchases' | 'payments' | 'receivables' | 'payables' | null

const getFiscalYearInfo = (date = new Date()) => {
  const currentMonth = date.getMonth() // 0 = Jan, 3 = Apr, 11 = Dec
  const currentYear = date.getFullYear()
  
  // Current Indian FY start year (April 1)
  const curFyStartYear = currentMonth >= 3 ? currentYear : currentYear - 1
  const curFyEndYear = curFyStartYear + 1
  const curFyLabel = `FY ${curFyStartYear}-${String(curFyEndYear).slice(-2)}`
  
  // Previous FY start year
  const prevFyStartYear = curFyStartYear - 1
  const prevFyEndYear = curFyStartYear
  const prevFyLabel = `FY ${prevFyStartYear}-${String(prevFyEndYear).slice(-2)}`

  return {
    curFyStartYear,
    curFyEndYear,
    curFyLabel,
    curFyFrom: `${curFyStartYear}-04-01`,
    curFyTo: `${curFyEndYear}-03-31`,
    prevFyStartYear,
    prevFyEndYear,
    prevFyLabel,
    prevFyFrom: `${prevFyStartYear}-04-01`,
    prevFyTo: `${prevFyEndYear}-03-31`,
  }
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#6366f1']

const getVoucherTypeBadge = (type: string) => {
  const t = (type || '').toLowerCase()
  if (t.includes('receipt')) {
    return {
      badge: 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-900 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700 font-extrabold shadow-2xs',
      amount: 'text-emerald-700 dark:text-emerald-400 font-extrabold'
    }
  }
  if (t.includes('sales') || t.includes('sale')) {
    return {
      badge: 'bg-teal-100 dark:bg-teal-950/80 text-teal-900 dark:text-teal-300 border border-teal-300 dark:border-teal-700 font-extrabold shadow-2xs',
      amount: 'text-teal-700 dark:text-teal-400 font-extrabold'
    }
  }
  if (t.includes('payment')) {
    return {
      badge: 'bg-rose-100 dark:bg-rose-950/80 text-rose-900 dark:text-rose-300 border border-rose-300 dark:border-rose-700 font-extrabold shadow-2xs',
      amount: 'text-rose-700 dark:text-rose-400 font-extrabold'
    }
  }
  if (t.includes('purchase')) {
    return {
      badge: 'bg-purple-100 dark:bg-purple-950/80 text-purple-900 dark:text-purple-300 border border-purple-300 dark:border-purple-700 font-extrabold shadow-2xs',
      amount: 'text-purple-700 dark:text-purple-400 font-extrabold'
    }
  }
  return {
    badge: 'bg-muted text-muted-foreground border border-border font-bold',
    amount: 'text-foreground font-bold'
  }
}

const EXPLANATIONS = {
  revenue_trend: {
    title: 'Monthly Revenue & Collection Trend Explained',
    badge: 'Evaluation Method: Total Monthly Accumulation',
    summary: 'Calculated by summing all Sales Vouchers issued vs all Receipt Vouchers deposited into Cash/Bank accounts in each calendar month across all customers.',
    lines: [
      { name: 'Evaluation Method', desc: 'Total Monthly Accumulation (Monthly Sales Sum vs Monthly Cash Received Sum).' },
      { name: 'Sales Billed (Green Line)', desc: 'Sum of all sales invoices issued to customers during that month.' },
      { name: 'Cash Collected (Blue Line)', desc: 'Sum of all payment receipts deposited into Cash/Bank ledgers during that month.' }
    ],
    example: {
      title: 'Real-world Example (July 2026)',
      period: 'Jul 2026 Monthly Totals',
      sales: '₹7,45,646.02 (Sales Billed)',
      receipts: '₹7,74,918.00 (Cash Collected)',
      explanation: 'In July 2026, total sales billed across all customers was ₹7.45 Lakhs. Total cash collected in bank accounts was ₹7.75 Lakhs. Cash Collected is higher because customers cleared ₹29,271.98 of older outstanding invoices from previous months along with their July bills!'
    },
    takeaways: [
      'Tracks overall monthly cash conversion speed across your entire customer base.',
      'Cash Collected > Sales Billed indicates strong collection performance on past due balances.'
    ]
  },
  aging: {
    title: 'Outstanding Debt Aging Breakdown Explained',
    badge: 'EVALUATION METHOD: FIFO (OLDEST INVOICE SETTLED FIRST)',
    summary: 'Evaluated using FIFO (First-In, First-Out)! When a customer makes a payment, earlier/older bills are closed first. Remaining customer debt is allocated against their newest invoices.',
    lines: [
      { name: 'Evaluation Method', desc: 'FIFO Allocation (Oldest Bills Settled First).' },
      { name: 'Payment Settlement', desc: 'Customer receipts automatically clear the oldest outstanding invoices first.' },
      { name: 'Age Bucket Assignment', desc: 'Remaining unpaid customer balance is assigned to their most recent sales invoices (0-30, 31-60, 61-90, 90+ Days).' }
    ],
    example: {
      title: 'FIFO Settlement Example',
      period: 'Oldest Bill Settlement Allocation',
      sales: '0-30 Days: Recent Unpaid Invoices',
      receipts: 'Older Invoices: Cleared by Payment',
      explanation: 'Customer A has Bill #1 (₹50,000, 90 days old) and Bill #2 (₹1,00,000, 15 days old). When Customer A pays ₹50,000, the payment automatically closes older Bill #1 (90+ Days). The remaining ₹1,00,000 balance moves into the 0-30 Days bucket (Bill #2)!'
    },
    takeaways: [
      'FIFO settlement ensures accurate customer aging by clearing older bills first.',
      'Remaining debt in 60+ or 90+ day buckets represents customers who have not made enough total payments to clear their historic invoices.'
    ]
  },
  expense: {
    title: 'Operating Expense Distribution Explained',
    badge: 'Cost & Budget Control',
    summary: 'Visualizes operational expenses, administrative overhead, taxes, and bank charges to highlight where company money is spent.',
    lines: [
      { name: 'Direct/Indirect Expenses', desc: 'Salaries, shop rent, freight, electricity, office maintenance.' },
      { name: 'Taxes & Bank Charges', desc: 'GST/TDS liabilities, payment gateway MDR fees, bank charges.' }
    ],
    example: {
      title: 'Real-world Expense Example',
      period: 'Monthly Cost Distribution',
      sales: 'Shop Rent & Salaries: 60%',
      receipts: 'Bank Charges & Gateway Fees: 15%',
      explanation: 'Seeing that 15% of expenses go to bank charges helps you negotiate better payment gateway MDR rates or encourage direct UPI bank transfers.'
    },
    takeaways: [
      'Monitor expense proportions monthly to control operating overhead.',
      'Identify cost spikes before they erode gross profit margins.'
    ]
  },
  top_customers: {
    title: 'Top 10 Customers by Revenue Explained',
    badge: 'Client Concentration Risk',
    summary: 'Ranks your top customer ledgers by total sales volume, invoice count, and average bill size.',
    lines: [
      { name: 'Total Sales Volume', desc: 'Cumulative invoice value billed to this specific customer.' },
      { name: 'Average Invoice Size', desc: 'Average billing value per invoice for this client.' }
    ],
    example: {
      title: 'Real-world Client Example',
      period: 'Sharda Kitchen Emporium',
      sales: '27 Invoices Billed',
      receipts: 'Total Volume: ₹4,06,339.00',
      explanation: 'Sharda Kitchen Emporium is your #1 client contributing ₹4.06L across 27 invoices (Avg ~₹15,049 per bill). If 60% of revenue comes from 1 client, losing that client poses a revenue risk.'
    },
    takeaways: [
      'Nurture relationships with top 10 clients while expanding new accounts.',
      'Avoid heavy dependence on a single client for cash flow.'
    ]
  },
  inventory: {
    title: 'Capital Locked by Stock Group Explained',
    badge: 'Working Capital Health',
    summary: 'Calculates the total monetary value of closing inventory stock on hand across main stock categories.',
    lines: [
      { name: 'Stock Group Valuation', desc: 'Sum of (Quantity on Hand × Unit Rate) for all items in a category.' }
    ],
    example: {
      title: 'Real-world Stock Example',
      period: 'Appliances vs Spares',
      sales: 'Appliances Stock: ₹12,50,000',
      receipts: 'Spare Parts Stock: ₹1,20,000',
      explanation: '₹12.5 Lakhs of capital is currently tied up in Appliances stock on hand. If those items sell slowly, your cash is locked in inventory.'
    },
    takeaways: [
      'Maintain balanced reorder points for fast-moving items.',
      'Liquidate slow-moving stock to free up working capital.'
    ]
  },
  trial_balance: {
    title: 'Account Group Trial Balance Explained',
    badge: 'Accounting Double-Entry Check',
    summary: 'Lists net Debit (Dr) and Credit (Cr) balances for all primary account groups (Assets, Liabilities, Income, Expenses).',
    lines: [
      { name: 'Debit (Dr) Balances', desc: 'Assets (Bank, Cash, Debtors, Stock) & Expenses.' },
      { name: 'Credit (Cr) Balances', desc: 'Liabilities (Creditors, Loans) & Sales Income.' }
    ],
    example: {
      title: 'Real-world Double-Entry Example',
      period: 'Trial Balance Check',
      sales: 'Total Debits: ₹45,00,000',
      receipts: 'Total Credits: ₹45,00,000',
      explanation: 'When Total Debits equal Total Credits, double-entry accounting integrity is verified and accounts are ready for P&L & Balance Sheet generation.'
    },
    takeaways: [
      'Verify trial balance equality before filing monthly GST returns.',
      'Check group balances to detect misplaced ledger accounts.'
    ]
  }
}

const ACCOUNT_GROUP_DESCRIPTIONS: Record<string, { desc: string; drCr: string; example: string }> = {
  'Purchase Accounts': {
    desc: 'Tracks cost of inventory, stock items, and raw materials bought for resale or manufacturing.',
    drCr: 'Debit (Dr) balance represents net total cost of goods purchased.',
    example: 'Buying ₹5,00,000 worth of electrical appliances from distributors to stock in warehouse.'
  },
  'Unsecured Loans': {
    desc: 'Private loans taken from friends, family, partners, or non-banking sources without collateral.',
    drCr: 'Credit (Cr) balance represents total pending loan amount owed to private lenders.',
    example: 'Borrowing ₹10,00,000 from a partner to support temporary working capital requirements.'
  },
  'Sales Accounts': {
    desc: 'Primary business turnover generated from selling products or rendering services to customers.',
    drCr: 'Credit (Cr) balance represents cumulative top-line sales turnover.',
    example: 'Issuing a sales invoice of ₹50,000 for supplying LED TVs to a retail buyer.'
  },
  'Capital Account': {
    desc: 'Owners equity and capital funds contributed into the business by proprietors or partners.',
    drCr: 'Credit (Cr) balance represents net owner capital invested in the enterprise.',
    example: 'Proprietor depositing ₹15,00,000 personal savings into company bank account.'
  },
  'Sundry Debtors': {
    desc: 'Trade customers who purchased goods on credit and owe payment to your business.',
    drCr: 'Debit (Dr) balance represents outstanding money pending collection from customers.',
    example: 'Supplying ₹1,20,000 goods to J.D. Electronics with 30-day payment terms.'
  },
  'Duties & Taxes': {
    desc: 'Tax liability & credit ledgers (CGST, SGST, IGST, TDS, TCS, Cess).',
    drCr: 'Debit (Dr) = Input Tax Credit (ITC) available. Credit (Cr) = Tax Payable to Government.',
    example: 'CGST & SGST collected on customer invoices minus tax paid on supplier purchases.'
  },
  'Bank Accounts': {
    desc: 'All company checking, current, and savings bank accounts.',
    drCr: 'Debit (Dr) = Positive bank cash balance. Credit (Cr) = Bank Overdraft (OD/CC) balance.',
    example: 'Funds maintained in HDFC or ICICI Bank Current Accounts.'
  },
  'Cash-in-Hand': {
    desc: 'Physical currency bills and coins held in company cash drawer, safe, or petty cash box.',
    drCr: 'Debit (Dr) = Available physical cash balance for daily office/shop expenses.',
    example: '₹15,000 cash balance available in shop cash register counter.'
  },
  'Sundry Creditors': {
    desc: 'Trade suppliers and vendors from whom you bought stock or services on credit.',
    drCr: 'Credit (Cr) = Pending payables owed to vendors for credit purchases.',
    example: 'Owing ₹80,000 to Bajaj Electricals Ltd for inventory delivered.'
  },
  'Indirect Expenses': {
    desc: 'General operating overheads, administrative, and selling costs not tied to production.',
    drCr: 'Debit (Dr) = Total administrative and operational overhead expenses paid.',
    example: 'Office rent, electricity bills, staff salaries, internet, and bank charges.'
  },
  'Direct Expenses': {
    desc: 'Manufacturing and handling expenses directly incurred to bring stock into saleable condition.',
    drCr: 'Debit (Dr) = Total direct handling and freight cost incurred.',
    example: 'Freight inward, carriage, factory power, and daily wage labor.'
  },
  'Primary': {
    desc: 'Top-level root account group umbrella in Tally chart of accounts.',
    drCr: 'Sum of unassigned or top-level parent ledger balances.',
    example: 'System root group for custom unclassified ledgers.'
  }
}

export default function ReportsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<TabType>('executive')
  const [financialSubTab, setFinancialSubTab] = useState<'pnl' | 'bs' | 'cf' | 'ratios' | 'projected'>('pnl')
  const [activePreset, setActivePreset] = useState<PresetType>('month')
  const [loading, setLoading] = useState(false)
  const [lastUpdatedMessage, setLastUpdatedMessage] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [explanationKey, setExplanationKey] = useState<ExplanationKey>(null)
  
  // GST Display Toggle (GROSS vs NET) - Default: GROSS (With GST) Enabled
  const [isGrossGst, setIsGrossGst] = useState(true)

  // Account Group Info Modal State
  const [selectedGroupInfo, setSelectedGroupInfo] = useState<string | null>(null)

  // KPI Drilldown Modal State
  const [kpiModalKey, setKpiModalKey] = useState<KpiModalKey>(null)
  const [kpiSearchQuery, setKpiSearchQuery] = useState('')

  // Aging Bucket Drilldown Modal State
  const [agingModalBucket, setAgingModalBucket] = useState<string | null>(null)
  const [agingSearchQuery, setAgingSearchQuery] = useState('')

  // Date Range State (Default: 1st of Current Month → Today)
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date()
    d.setDate(1)
    return d.toISOString().slice(0, 10)
  })
  const [toDate, setToDate] = useState(() => new Date().toISOString().slice(0, 10))

  // Data States
  const [summary, setSummary] = useState<any>(null)
  const [execData, setExecData] = useState<any>(null)
  const [topCustomers, setTopCustomers] = useState<any[]>([])
  const [inventoryData, setInventoryData] = useState<any>(null)
  const [salesRegister, setSalesRegister] = useState<any[]>([])
  const [daybook, setDaybook] = useState<any[]>([])
  const [trialBalance, setTrialBalance] = useState<any[]>([])
  const [pnlData, setPnlData] = useState<any>(null)
  const [balanceSheetData, setBalanceSheetData] = useState<any>(null)
  const [cashFlowData, setCashFlowData] = useState<any>(null)
  const [ratiosData, setRatiosData] = useState<any>(null)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showReports && !permissions.isAdmin) { router.replace('/'); return }
  }, [user, permissions, router])

  const fetchReportsData = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const headers = authHeaders(token)
      const q = `from_date=${fromDate}&to_date=${toDate}`
      
      const results = await Promise.allSettled([
        fetch(`${API_BASE}/reports/dashboard-summary?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/executive-analytics?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/top-customers?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/inventory-analytics`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/sales-register?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/daybook?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/trial-balance`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/profit-loss?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/balance-sheet`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/cash-flow?${q}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API_BASE}/reports/ratio-analysis`, { headers }).then(r => r.ok ? r.json() : null),
      ])

      if (results[0].status === 'fulfilled' && results[0].value) setSummary(results[0].value)
      if (results[1].status === 'fulfilled' && results[1].value) setExecData(results[1].value)
      if (results[2].status === 'fulfilled' && results[2].value) setTopCustomers(results[2].value)
      if (results[3].status === 'fulfilled' && results[3].value) setInventoryData(results[3].value)
      if (results[4].status === 'fulfilled' && results[4].value) setSalesRegister(results[4].value)
      if (results[5].status === 'fulfilled' && results[5].value) setDaybook(results[5].value)
      if (results[6].status === 'fulfilled' && results[6].value) setTrialBalance(results[6].value)
      if (results[7].status === 'fulfilled' && results[7].value) setPnlData(results[7].value)
      if (results[8].status === 'fulfilled' && results[8].value) setBalanceSheetData(results[8].value)
      if (results[9].status === 'fulfilled' && results[9].value) setCashFlowData(results[9].value)
      if (results[10].status === 'fulfilled' && results[10].value) setRatiosData(results[10].value)

      setLastUpdatedMessage(`Updated data for period: ${formatDate(fromDate)} to ${formatDate(toDate)}`)
    } catch (err) {
      console.error('Failed to load reports:', err)
    } finally {
      setLoading(false)
    }
  }, [token, fromDate, toDate])

  useEffect(() => {
    fetchReportsData()
  }, [fetchReportsData])

  const setDatePreset = (preset: PresetType) => {
    setActivePreset(preset)
    const today = new Date()
    const to = today.toISOString().slice(0, 10)
    let from = new Date()
    const fy = getFiscalYearInfo(today)

    if (preset === 'month') {
      from.setDate(1)
    } else if (preset === 'quarter') {
      from.setMonth(from.getMonth() - 3)
      from.setDate(1)
    } else if (preset === 'current_fy' || preset === 'year') {
      setFromDate(fy.curFyFrom)
      setToDate(to)
      return
    } else if (preset === 'prev_fy') {
      setFromDate(fy.prevFyFrom)
      setToDate(fy.prevFyTo)
      return
    }
    
    if (preset !== 'custom') {
      setFromDate(from.toISOString().slice(0, 10))
      setToDate(to)
    }
  }

  const exportToCsv = (filename: string, rows: any[]) => {
    if (!rows || rows.length === 0) return
    const headers = Object.keys(rows[0]).join(',')
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers, ...rows.map(r => Object.values(r).map(v => `"${v}"`).join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `${filename}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const currentExp = explanationKey ? EXPLANATIONS[explanationKey] : null

  // Helpers for KPI Modal Data
  const getKpiModalDetails = () => {
    if (!kpiModalKey) return null
    if (kpiModalKey === 'sales') {
      const rows = salesRegister.filter(r => (r.party_name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()))
      return {
        title: isGrossGst ? 'Total Billed Sales (With GST)' : 'Total Revenue (Without GST)',
        total: isGrossGst ? (summary?.total_sales_gross ?? 0) : (summary?.total_sales ?? 0),
        badgeColor: 'emerald',
        headers: ['Voucher #', 'Date', 'Customer Name', 'Amount'],
        rows,
        renderRow: (r: any, idx: number) => (
          <tr key={idx} className="hover:bg-muted/30 transition-colors">
            <td className="py-2.5 px-3 font-mono font-bold">
              <Link
                href={`/vouchers/${r.id}`}
                className="text-primary hover:underline hover:text-indigo-600 font-bold"
                title="Click to view voucher details"
              >
                <span>{r.voucher_number || `#${r.id}`}</span>
              </Link>
            </td>
            <td className="py-2.5 px-3 text-muted-foreground">{formatDate(r.date)}</td>
            <td className="py-2.5 px-3 font-semibold">
              <Link
                href={`/ledgers?search=${encodeURIComponent(r.party_name)}`}
                className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                title={`Search ${r.party_name} in ledgers`}
              >
                {toTitleCase(r.party_name)}
              </Link>
            </td>
            <td className="py-2.5 px-3 text-right font-bold text-emerald-600">{formatCurrency(r.amount)}</td>
          </tr>
        )
      }
    } else if (kpiModalKey === 'receipts') {
      const receipts = daybook.filter(r => r.type === 'Receipt' && ((r.party_name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(kpiSearchQuery.toLowerCase())))
      return {
        title: 'Cash Receipts & Bank Collections Journal',
        total: summary?.total_receipts ?? 0,
        badgeColor: 'blue',
        headers: ['Voucher #', 'Date', 'Type', 'Party / Account', 'Amount'],
        rows: receipts,
        renderRow: (r: any, idx: number) => {
          const typeStyle = getVoucherTypeBadge(r.type)
          return (
            <tr key={idx} className="hover:bg-muted/30 transition-colors">
              <td className="py-2.5 px-3 font-mono font-bold">
                <Link
                  href={`/vouchers/${r.id}`}
                  className="text-primary hover:underline hover:text-indigo-600 font-bold"
                  title="Click to view voucher details"
                >
                  <span>{r.voucher_number || `#${r.id}`}</span>
                </Link>
              </td>
              <td className="py-2.5 px-3 text-muted-foreground">{formatDate(r.date)}</td>
              <td className="py-2.5 px-3">
                <span className={cn('px-2.5 py-1 rounded-full text-[10px] font-extrabold border', typeStyle.badge)}>
                  {r.type}
                </span>
              </td>
              <td className="py-2.5 px-3 font-semibold">
                <Link
                  href={`/ledgers?search=${encodeURIComponent(r.party_name)}`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Search ${r.party_name} in ledgers`}
                >
                  {toTitleCase(r.party_name)}
                </Link>
              </td>
              <td className={cn('py-2.5 px-3 text-right font-bold', typeStyle.amount)}>{formatCurrency(r.amount)}</td>
            </tr>
          )
        }
      }
    } else if (kpiModalKey === 'purchases') {
      const purchases = daybook.filter(r => r.type === 'Purchase' && ((r.party_name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(kpiSearchQuery.toLowerCase())))
      return {
        title: 'Vendor Purchases & Inward Bills Register',
        total: summary?.total_purchases ?? 0,
        badgeColor: 'purple',
        headers: ['Voucher #', 'Date', 'Type', 'Supplier / Vendor Name', 'Amount'],
        rows: purchases,
        renderRow: (r: any, idx: number) => {
          const typeStyle = getVoucherTypeBadge(r.type)
          return (
            <tr key={idx} className="hover:bg-muted/30 transition-colors">
              <td className="py-2.5 px-3 font-mono font-bold">
                <Link
                  href={`/vouchers/${r.id}`}
                  className="text-primary hover:underline hover:text-indigo-600 font-bold"
                  title="Click to view voucher details"
                >
                  <span>{r.voucher_number || `#${r.id}`}</span>
                </Link>
              </td>
              <td className="py-2.5 px-3 text-muted-foreground">{formatDate(r.date)}</td>
              <td className="py-2.5 px-3">
                <span className={cn('px-2.5 py-1 rounded-full text-[10px] font-extrabold border', typeStyle.badge)}>
                  {r.type}
                </span>
              </td>
              <td className="py-2.5 px-3 font-semibold">
                <Link
                  href={`/ledgers?search=${encodeURIComponent(r.party_name)}&tab=suppliers`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Search ${r.party_name} in suppliers`}
                >
                  {toTitleCase(r.party_name)}
                </Link>
              </td>
              <td className={cn('py-2.5 px-3 text-right font-bold', typeStyle.amount)}>{formatCurrency(r.amount)}</td>
            </tr>
          )
        }
      }
    } else if (kpiModalKey === 'payments') {
      const payments = daybook.filter(r => r.type === 'Payment' && ((r.party_name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(kpiSearchQuery.toLowerCase())))
      return {
        title: 'Outward Cash & Bank Payments Journal',
        total: summary?.total_payments ?? 0,
        badgeColor: 'rose',
        headers: ['Voucher #', 'Date', 'Type', 'Party / Account Paid', 'Amount'],
        rows: payments,
        renderRow: (r: any, idx: number) => {
          const typeStyle = getVoucherTypeBadge(r.type)
          return (
            <tr key={idx} className="hover:bg-muted/30 transition-colors">
              <td className="py-2.5 px-3 font-mono font-bold">
                <Link
                  href={`/vouchers/${r.id}`}
                  className="text-primary hover:underline hover:text-indigo-600 font-bold"
                  title="Click to view voucher details"
                >
                  <span>{r.voucher_number || `#${r.id}`}</span>
                </Link>
              </td>
              <td className="py-2.5 px-3 text-muted-foreground">{formatDate(r.date)}</td>
              <td className="py-2.5 px-3">
                <span className={cn('px-2.5 py-1 rounded-full text-[10px] font-extrabold border', typeStyle.badge)}>
                  {r.type}
                </span>
              </td>
              <td className="py-2.5 px-3 font-semibold">
                <Link
                  href={`/ledgers?search=${encodeURIComponent(r.party_name)}`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Search ${r.party_name} in ledgers`}
                >
                  {toTitleCase(r.party_name)}
                </Link>
              </td>
              <td className={cn('py-2.5 px-3 text-right font-bold', typeStyle.amount)}>{formatCurrency(r.amount)}</td>
            </tr>
          )
        }
      }
    } else if (kpiModalKey === 'receivables') {
      const debtors = topCustomers.filter(r => (r.name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()))
      return {
        title: 'Outstanding Debtors & Receivables Ledger',
        total: summary?.outstanding_receivables ?? 0,
        badgeColor: 'amber',
        headers: ['Customer / Debtor Ledger Name', 'Total Invoiced Volume', 'Status'],
        rows: debtors,
        renderRow: (r: any, idx: number) => (
          <tr key={idx} className="hover:bg-muted/30 transition-colors">
            <td className="py-2.5 px-3 font-semibold flex items-center gap-2">
              <Users className="h-4 w-4 text-amber-500 shrink-0" />
              {r.ledger_id ? (
                <Link
                  href={`/ledgers/${r.ledger_id}`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Open ${r.name} ledger statement`}
                >
                  {toTitleCase(r.name)}
                </Link>
              ) : (
                <Link
                  href={`/ledgers?search=${encodeURIComponent(r.name)}`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Search ${r.name} in ledgers`}
                >
                  {toTitleCase(r.name)}
                </Link>
              )}
            </td>
            <td className="py-2.5 px-3 font-bold text-amber-600">{formatCurrency(r.total_sales)}</td>
            <td className="py-2.5 px-3">
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20">
                Pending Payment
              </span>
            </td>
          </tr>
        )
      }
    } else if (kpiModalKey === 'payables') {
      const creditors = daybook.filter(r => (r.type === 'Purchase' || r.type === 'Payment') && ((r.party_name || '').toLowerCase().includes(kpiSearchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(kpiSearchQuery.toLowerCase())))
      return {
        title: 'Outstanding Vendor Creditors & Payables Journal',
        total: summary?.outstanding_payables ?? 0,
        badgeColor: 'rose',
        headers: ['Voucher #', 'Date', 'Type', 'Vendor / Supplier Name', 'Amount Owed'],
        rows: creditors,
        renderRow: (r: any, idx: number) => {
          const typeStyle = getVoucherTypeBadge(r.type || 'Purchase')
          return (
            <tr key={idx} className="hover:bg-muted/30 transition-colors">
              <td className="py-2.5 px-3 font-mono font-bold">
                <Link
                  href={`/vouchers/${r.id}`}
                  className="text-primary hover:underline hover:text-indigo-600 font-bold"
                  title="Click to view voucher details"
                >
                  <span>{r.voucher_number || `#${r.id}`}</span>
                </Link>
              </td>
              <td className="py-2.5 px-3 text-muted-foreground">{formatDate(r.date)}</td>
              <td className="py-2.5 px-3">
                <span className={cn('px-2.5 py-1 rounded-full text-[10px] font-extrabold border', typeStyle.badge)}>
                  {r.type || 'Purchase'}
                </span>
              </td>
              <td className="py-2.5 px-3 font-semibold">
                <Link
                  href={`/ledgers?search=${encodeURIComponent(r.party_name)}&tab=suppliers`}
                  className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                  title={`Search ${r.party_name} in suppliers`}
                >
                  {toTitleCase(r.party_name)}
                </Link>
              </td>
              <td className={cn('py-2.5 px-3 text-right font-bold', typeStyle.amount)}>{formatCurrency(r.amount)}</td>
            </tr>
          )
        }
      }
    }
    return null
  }

  const kpiModalData = getKpiModalDetails()

  return (
    <div className="p-4 space-y-6 max-w-7xl mx-auto pb-28">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10">
            <BarChart3 className="h-6 w-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">Executive Reports Hub</h1>
            <p className="text-xs text-muted-foreground">Financial Analytics, Visual Trends, Debt Aging & Stock Reports</p>
          </div>
        </div>

        {/* Date Filter & Presets */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-xl border border-border">
            <button
              onClick={() => setDatePreset('month')}
              className={cn(
                'px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5',
                activePreset === 'month' ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-background text-muted-foreground hover:text-foreground'
              )}
            >
              {activePreset === 'month' && <Check className="h-3 w-3" />}
              This Month
            </button>
            <button
              onClick={() => setDatePreset('quarter')}
              className={cn(
                'px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5',
                activePreset === 'quarter' ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-background text-muted-foreground hover:text-foreground'
              )}
            >
              {activePreset === 'quarter' && <Check className="h-3 w-3" />}
              Last Quarter
            </button>
            <button
              onClick={() => setDatePreset('current_fy')}
              className={cn(
                'px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5',
                activePreset === 'current_fy' || activePreset === 'year' ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-background text-muted-foreground hover:text-foreground'
              )}
            >
              {(activePreset === 'current_fy' || activePreset === 'year') && <Check className="h-3 w-3" />}
              {getFiscalYearInfo().curFyLabel} (Current FY)
            </button>
            <button
              onClick={() => setDatePreset('prev_fy')}
              className={cn(
                'px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5',
                activePreset === 'prev_fy' ? 'bg-primary text-primary-foreground shadow-sm' : 'hover:bg-background text-muted-foreground hover:text-foreground'
              )}
            >
              {activePreset === 'prev_fy' && <Check className="h-3 w-3" />}
              {getFiscalYearInfo().prevFyLabel} (Last FY)
            </button>
          </div>

          {/* GROSS vs NET GST Mode Toggle Switch */}
          <button
            onClick={() => setIsGrossGst(!isGrossGst)}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer shadow-2xs select-none',
              isGrossGst
                ? 'bg-emerald-600 text-white border-emerald-700 ring-2 ring-emerald-500/20'
                : 'bg-card border-border text-foreground hover:bg-muted/50'
            )}
            title="Toggle between Gross Sales (With GST) and Net Taxable Sales (Without GST)"
          >
            <div className={cn(
              'w-7 h-4 rounded-full p-0.5 transition-colors flex items-center',
              isGrossGst ? 'bg-white/30 justify-end' : 'bg-muted-foreground/30 justify-start'
            )}>
              <div className="w-3 h-3 rounded-full bg-white shadow-xs" />
            </div>
            <span>{isGrossGst ? 'GROSS (With GST)' : 'NET (Without GST)'}</span>
          </button>

          <div className={cn(
            'flex items-center gap-2 bg-card border px-3 py-1.5 rounded-xl text-xs transition-all select-none',
            activePreset === 'custom' ? 'border-primary ring-2 ring-primary/20' : 'border-border'
          )}>
            <div
              className="flex items-center gap-1.5 cursor-pointer"
              onClick={() => {
                const el = document.getElementById('report-from-date') as HTMLInputElement
                if (el) { try { el.showPicker() } catch (_) { el.focus() } }
              }}
            >
              <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <input
                id="report-from-date"
                type="date"
                value={fromDate}
                onClick={e => { try { e.currentTarget.showPicker() } catch (_) {} }}
                onChange={e => { setFromDate(e.target.value); setActivePreset('custom') }}
                className="bg-transparent font-medium focus:outline-none cursor-pointer"
              />
            </div>
            <span className="text-muted-foreground">→</span>
            <div
              className="flex items-center gap-1.5 cursor-pointer"
              onClick={() => {
                const el = document.getElementById('report-to-date') as HTMLInputElement
                if (el) { try { el.showPicker() } catch (_) { el.focus() } }
              }}
            >
              <input
                id="report-to-date"
                type="date"
                value={toDate}
                onClick={e => { try { e.currentTarget.showPicker() } catch (_) {} }}
                onChange={e => { setToDate(e.target.value); setActivePreset('custom') }}
                className="bg-transparent font-medium focus:outline-none cursor-pointer"
              />
            </div>
          </div>

          <button
            onClick={fetchReportsData}
            disabled={loading}
            className="p-2.5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl transition-all shadow-sm cursor-pointer disabled:opacity-50 flex items-center gap-1.5 text-xs font-bold"
            title="Refresh reports data"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
            <span>Update</span>
          </button>
        </div>
      </div>

      {/* Date Update Feedback Banner */}
      {lastUpdatedMessage && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 px-3.5 py-2 rounded-xl text-xs font-bold flex items-center justify-between transition-all animate-in fade-in">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-emerald-500" />
            <span>{lastUpdatedMessage}</span>
          </div>
          {loading && <span className="text-[10px] text-emerald-600 animate-pulse font-medium">Fetching latest vouchers...</span>}
        </div>
      )}

      {/* Primary Navigation Tabs */}
      <div className="flex gap-1.5 bg-muted/50 p-1 rounded-xl overflow-x-auto no-scrollbar border border-border">
        {[
          { id: 'executive', label: 'Executive Analytics', icon: TrendingUp, desc: 'Revenue Trends, Cash Flow & Debt Aging' },
          { id: 'financial', label: 'Financial Statements', icon: BarChart3, desc: 'P&L, Balance Sheet, Cash Flow & Ratios' },
          { id: 'sales', label: 'Sales & Customers', icon: BookOpen, desc: 'Top Debtors & Invoicing Register' },
          { id: 'inventory', label: 'Inventory Valuation', icon: Layers, desc: 'Stock Group Capital & Item Valuation' },
          { id: 'compliance', label: 'Audit & Trial Balance', icon: FileText, desc: 'Double-Entry Trial Balance & Daybook' }
        ].map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap cursor-pointer text-left',
                isActive ? 'bg-background shadow-sm text-foreground border border-border' : 'text-muted-foreground hover:text-foreground hover:bg-background/40'
              )}
            >
              <Icon className="h-4 w-4 shrink-0 text-indigo-500" />
              <div>
                <p className="font-extrabold">{tab.label}</p>
                <p className="text-[10px] text-muted-foreground font-normal">{tab.desc}</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Interactive KPI Cards Bar (Click card to open itemized data modal) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <KpiCard
          title={isGrossGst ? "Total Revenue" : "Taxable Sales"}
          value={isGrossGst ? (summary?.total_sales_gross ?? 0) : (summary?.total_sales ?? 0)}
          icon={TrendingUp}
          color="emerald"
          info="Total Sales Billed for period."
          onClick={() => { setKpiModalKey('sales'); setKpiSearchQuery('') }}
        />
        <KpiCard
          title="Cash Receipts"
          value={summary?.total_receipts ?? 0}
          icon={DollarSign}
          color="blue"
          info="Money collected into bank/cash."
          onClick={() => { setKpiModalKey('receipts'); setKpiSearchQuery('') }}
        />
        <KpiCard
          title="Total Purchases"
          value={summary?.total_purchases ?? 0}
          icon={ShoppingBag}
          color="purple"
          info="Vendor Purchase Invoices."
          onClick={() => { setKpiModalKey('purchases'); setKpiSearchQuery('') }}
        />
        <KpiCard
          title="Vendor Payments"
          value={summary?.total_payments ?? 0}
          icon={ArrowDownRight}
          color="rose"
          info="Outward Cash & Bank Payments."
          onClick={() => { setKpiModalKey('payments'); setKpiSearchQuery('') }}
        />
        <KpiCard
          title="Outstanding Debtors"
          value={summary?.outstanding_receivables ?? 0}
          icon={ArrowUpRight}
          color="amber"
          info="Pending customer receivables."
          onClick={() => { setKpiModalKey('receivables'); setKpiSearchQuery('') }}
        />
        <KpiCard
          title="Outstanding Creditors"
          value={summary?.outstanding_payables ?? 0}
          icon={Users}
          color="slate"
          info="Unpaid vendor payables."
          onClick={() => { setKpiModalKey('payables'); setKpiSearchQuery('') }}
        />
      </div>

      {/* TAB 1: EXECUTIVE ANALYTICS */}
      {activeTab === 'executive' && (
        <div className="space-y-6">
          {/* Chart 1: Revenue vs Receipts vs Purchases */}
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/50 pb-3">
              <div className="flex items-center gap-2">
                <div>
                  <h3 className="font-extrabold text-base flex items-center gap-2 text-foreground">
                    <TrendingUp className="h-4 w-4 text-emerald-500" /> Monthly Revenue & Collection Trend
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">Comparative trajectory of monthly Sales Billed vs Cash Receipts Collected</p>
                </div>
                <button
                  onClick={() => setExplanationKey('revenue_trend')}
                  className="p-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-600 transition-colors cursor-pointer"
                  title="Click for chart explanation & example"
                >
                  <Info className="h-4 w-4" />
                </button>
              </div>

              <button
                onClick={() => setExplanationKey('revenue_trend')}
                className="bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 border border-emerald-300 dark:border-emerald-800 text-emerald-950 dark:text-emerald-200 px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-2 cursor-pointer transition-all shadow-2xs"
              >
                <HelpCircle className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>Click here for Chart Meaning & Example</span>
              </button>
            </div>

            <div className="h-72 w-full pt-2">
              {execData?.monthly_trend && execData.monthly_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={execData.monthly_trend}>
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
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(val: any) => [formatCurrency(Number(val)), '']} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    <Area type="monotone" dataKey="sales" name="Sales Billed" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#salesGrad)" />
                    <Area type="monotone" dataKey="receipts" name="Cash Collected" stroke="#3b82f6" strokeWidth={2.5} fillOpacity={1} fill="url(#receiptGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">No voucher trend data available for selected period</div>
              )}
            </div>
          </div>

          {/* Grid: Aging Breakdown & Expense Pie Chart */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Chart 2: Receivables Aging */}
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-extrabold text-base flex items-center gap-2">
                      <BarChart3 className="h-4 w-4 text-amber-500" /> Outstanding Debt Aging Breakdown
                    </h3>
                    <p className="text-xs text-muted-foreground">Categorizes pending customer debt (settling oldest bills first) into 0-30, 31-60, 61-90, and 90+ day buckets</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Link
                      href="/outstanding"
                      className="px-2.5 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 text-xs font-bold transition-all flex items-center gap-1 shadow-2xs cursor-pointer active:scale-95"
                      title="Open Debtors Aging & WhatsApp Reminders Hub"
                    >
                      <Clock className="h-3.5 w-3.5" />
                      <span>Send Reminders</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </Link>
                    <button
                      onClick={() => setExplanationKey('aging')}
                      className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 transition-colors cursor-pointer"
                      title="Click for aging explanation"
                    >
                      <Info className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div className="h-60 w-full pt-4">
                  {execData?.receivables_aging ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={execData.receivables_aging}
                        onClick={(state: any) => {
                          if (state && state.activePayload && state.activePayload.length > 0) {
                            const clickedBucket = state.activePayload[0].payload.bucket
                            setAgingModalBucket(clickedBucket)
                            setAgingSearchQuery('')
                          }
                        }}
                      >
                        <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                        <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                        <Tooltip
                          formatter={(val: any) => [formatCurrency(Number(val)), 'Pending Debt (Click candle to view bills)']}
                          cursor={{ fill: 'rgba(245, 158, 11, 0.12)' }}
                        />
                        <Bar
                          dataKey="amount"
                          name="Receivables (Debtors)"
                          fill="#f59e0b"
                          radius={[6, 6, 0, 0]}
                          className="cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={(data: any) => {
                            if (data && data.bucket) {
                              setAgingModalBucket(data.bucket)
                              setAgingSearchQuery('')
                            }
                          }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">No open bill aging data available</div>
                  )}
                </div>
              </div>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2">
                <button
                  onClick={() => setExplanationKey('aging')}
                  className="flex-1 bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-900/50 border border-amber-300 dark:border-amber-800 text-amber-950 dark:text-amber-200 p-2.5 rounded-xl text-xs font-bold flex items-center gap-2 text-left cursor-pointer transition-all shadow-2xs"
                >
                  <HelpCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <span>How aging helps recover 60+ and 90+ day debts</span>
                </button>
                <Link
                  href="/outstanding"
                  className="px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-xs shrink-0 active:scale-95"
                >
                  <Clock className="w-3.5 h-3.5" />
                  <span>Reminders Hub</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>

            {/* Chart 3: Expense Categories Donut Chart */}
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-extrabold text-base flex items-center gap-2">
                      <PieChartIcon className="h-4 w-4 text-rose-500" /> Operating Expense Distribution
                    </h3>
                    <p className="text-xs text-muted-foreground">Categorized breakdown of administrative overhead, taxes & bank charges</p>
                  </div>
                  <button
                    onClick={() => setExplanationKey('expense')}
                    className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 transition-colors cursor-pointer"
                    title="Click for expense breakdown explanation"
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </div>
                <div className="h-60 w-full flex items-center justify-center pt-2">
                  {execData?.expense_breakdown && execData.expense_breakdown.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={execData.expense_breakdown}
                          dataKey="amount"
                          nameKey="category"
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={4}
                        >
                          {execData.expense_breakdown.map((_: any, index: number) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(val: any) => [formatCurrency(Number(val)), 'Amount']} />
                        <Legend wrapperStyle={{ fontSize: '11px' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="text-xs text-muted-foreground text-center">No expense debits recorded in selected period</div>
                  )}
                </div>
              </div>
              <button
                onClick={() => setExplanationKey('expense')}
                className="bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 dark:hover:bg-rose-900/50 border border-rose-300 dark:border-rose-800 text-rose-950 dark:text-rose-200 p-3 rounded-xl text-xs font-bold flex items-center gap-2 text-left cursor-pointer transition-all shadow-2xs"
              >
                <HelpCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
                <span>Click to see how expense tracking controls company costs and budget leaks.</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: FINANCIAL STATEMENTS (P&L, Balance Sheet, Cash Flow & Ratios) */}
      {activeTab === 'financial' && (
        <div className="space-y-6">
          {/* Sub-navigation bar inside Financial Statements */}
          <div className="flex gap-2 border-b border-border pb-2 overflow-x-auto no-scrollbar">
            <button
              onClick={() => setFinancialSubTab('pnl')}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer',
                financialSubTab === 'pnl' ? 'bg-emerald-500 text-white shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              <FileText className="h-3.5 w-3.5" /> Profit & Loss Statement
            </button>
            <button
              onClick={() => setFinancialSubTab('bs')}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer',
                financialSubTab === 'bs' ? 'bg-emerald-500 text-white shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              <Landmark className="h-3.5 w-3.5" /> Balance Sheet
            </button>
            <button
              onClick={() => setFinancialSubTab('cf')}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer',
                financialSubTab === 'cf' ? 'bg-emerald-500 text-white shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              <DollarSign className="h-3.5 w-3.5" /> Cash Flow Statement
            </button>
            <button
              onClick={() => setFinancialSubTab('ratios')}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer',
                financialSubTab === 'ratios' ? 'bg-emerald-500 text-white shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
              )}
            >
              <TrendingUp className="h-3.5 w-3.5" /> Key Financial Ratios
            </button>
            <button
              onClick={() => setFinancialSubTab('projected')}
              className={cn(
                'px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 cursor-pointer',
                financialSubTab === 'projected' ? 'bg-emerald-600 text-white shadow-sm' : 'bg-amber-100 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-800 hover:bg-amber-200'
              )}
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-500" /> Projected Statements & Bank PDF
            </button>
          </div>

          {/* Sub-Tab 1: Profit & Loss Statement */}
          {financialSubTab === 'pnl' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* P&L Executive Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Trading Turnover</p>
                  <p className="text-lg font-black text-emerald-600">{formatCurrency(pnlData?.total_sales || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">Gross Revenue Sales Billed</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Cost of Goods Sold (COGS)</p>
                  <p className="text-lg font-black text-rose-600">{formatCurrency(pnlData?.total_cogs || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">Purchases & Direct Freight</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Gross Profit</p>
                  <p className={cn("text-lg font-black", (pnlData?.gross_profit || 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                    {formatCurrency(pnlData?.gross_profit || 0)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Turnover minus COGS</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Net Operating Profit</p>
                  <p className={cn("text-lg font-black", (pnlData?.net_profit || 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                    {formatCurrency(pnlData?.net_profit || 0)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Final Net Earnings</p>
                </div>
              </div>

              {/* Two-Column P&L Ledger Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Left Column: Incomes */}
                <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                  <div className="flex items-center justify-between border-b border-border/50 pb-3">
                    <h4 className="font-extrabold text-sm text-emerald-600 uppercase tracking-wider flex items-center gap-1.5">
                      <span>Incomes & Revenue Accounts</span>
                    </h4>
                    <span className="text-xs font-black text-emerald-600">
                      Total: {formatCurrency((pnlData?.total_sales || 0) + (pnlData?.total_indirect_income || 0))}
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <p className="font-bold text-muted-foreground uppercase text-[10px] mb-1.5">Direct Trading Revenue</p>
                      {pnlData?.trading_income && pnlData.trading_income.length > 0 ? (
                        pnlData.trading_income.map((item: any, idx: number) => (
                          <div key={idx} className="flex justify-between py-1.5 border-b border-border/40 font-medium">
                            <span>{item.ledger} <span className="text-[10px] text-muted-foreground">({item.group})</span></span>
                            <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                          </div>
                        ))
                      ) : (
                        <p className="text-muted-foreground italic py-1">No trading revenue recorded.</p>
                      )}
                    </div>

                    <div className="pt-2">
                      <p className="font-bold text-muted-foreground uppercase text-[10px] mb-1.5">Indirect Incomes</p>
                      {pnlData?.indirect_income && pnlData.indirect_income.length > 0 ? (
                        pnlData.indirect_income.map((item: any, idx: number) => (
                          <div key={idx} className="flex justify-between py-1.5 border-b border-border/40 font-medium">
                            <span>{item.ledger} <span className="text-[10px] text-muted-foreground">({item.group})</span></span>
                            <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                          </div>
                        ))
                      ) : (
                        <p className="text-muted-foreground italic py-1">No indirect income ledgers.</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Column: Expenses */}
                <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                  <div className="flex items-center justify-between border-b border-border/50 pb-3">
                    <h4 className="font-extrabold text-sm text-rose-600 uppercase tracking-wider flex items-center gap-1.5">
                      <span>Expenses & Operating Costs</span>
                    </h4>
                    <span className="text-xs font-black text-rose-600">
                      Total: {formatCurrency((pnlData?.total_cogs || 0) + (pnlData?.total_indirect_expenses || 0))}
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <p className="font-bold text-muted-foreground uppercase text-[10px] mb-1.5">Trading Expenses / COGS</p>
                      {pnlData?.trading_expenses && pnlData.trading_expenses.length > 0 ? (
                        pnlData.trading_expenses.map((item: any, idx: number) => (
                          <div key={idx} className="flex justify-between py-1.5 border-b border-border/40 font-medium">
                            <span>{item.ledger} <span className="text-[10px] text-muted-foreground">({item.group})</span></span>
                            <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                          </div>
                        ))
                      ) : (
                        <p className="text-muted-foreground italic py-1">No trading expenses recorded.</p>
                      )}
                    </div>

                    <div className="pt-2">
                      <p className="font-bold text-muted-foreground uppercase text-[10px] mb-1.5">Indirect & Administrative Expenses</p>
                      {pnlData?.indirect_expenses && pnlData.indirect_expenses.length > 0 ? (
                        pnlData.indirect_expenses.map((item: any, idx: number) => (
                          <div key={idx} className="flex justify-between py-1.5 border-b border-border/40 font-medium">
                            <span>{item.ledger} <span className="text-[10px] text-muted-foreground">({item.group})</span></span>
                            <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                          </div>
                        ))
                      ) : (
                        <p className="text-muted-foreground italic py-1">No indirect operating expenses recorded.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Tab 2: Balance Sheet */}
          {financialSubTab === 'bs' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Balance Sheet Summary Banner */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Total Company Assets</p>
                  <p className="text-lg font-black text-emerald-600">{formatCurrency(balanceSheetData?.total_assets || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">Fixed & Current Assets</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Total Liabilities & Capital</p>
                  <p className="text-lg font-black text-blue-600">{formatCurrency(balanceSheetData?.total_liabilities || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">Capital, Loans & Payables</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Net Working Capital</p>
                  <p className={cn("text-lg font-black", (balanceSheetData?.working_capital || 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                    {formatCurrency(balanceSheetData?.working_capital || 0)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Assets minus Liabilities</p>
                </div>
              </div>

              {/* Two-Column Balance Sheet Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Liabilities Column */}
                <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                  <div className="flex items-center justify-between border-b border-border/50 pb-3">
                    <h4 className="font-extrabold text-sm text-blue-600 uppercase tracking-wider">Capital & Liabilities</h4>
                    <span className="text-xs font-black text-blue-600">{formatCurrency(balanceSheetData?.total_liabilities || 0)}</span>
                  </div>
                  <div className="space-y-2 text-xs divide-y divide-border/40">
                    {balanceSheetData?.liabilities && balanceSheetData.liabilities.length > 0 ? (
                      balanceSheetData.liabilities.map((item: any, idx: number) => (
                        <div key={idx} className="flex justify-between py-2 font-medium">
                          <div>
                            <p className="font-bold text-foreground">{item.ledger}</p>
                            <p className="text-[10px] text-muted-foreground">{item.group}</p>
                          </div>
                          <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-muted-foreground italic py-3">No liability accounts found.</p>
                    )}
                  </div>
                </div>

                {/* Assets Column */}
                <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
                  <div className="flex items-center justify-between border-b border-border/50 pb-3">
                    <h4 className="font-extrabold text-sm text-emerald-600 uppercase tracking-wider">Assets & Investments</h4>
                    <span className="text-xs font-black text-emerald-600">{formatCurrency(balanceSheetData?.total_assets || 0)}</span>
                  </div>
                  <div className="space-y-2 text-xs divide-y divide-border/40">
                    {balanceSheetData?.assets && balanceSheetData.assets.length > 0 ? (
                      balanceSheetData.assets.map((item: any, idx: number) => (
                        <div key={idx} className="flex justify-between py-2 font-medium">
                          <div>
                            <p className="font-bold text-foreground">{item.ledger}</p>
                            <p className="text-[10px] text-muted-foreground">{item.group}</p>
                          </div>
                          <span className="font-bold text-foreground">{formatCurrency(item.amount)}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-muted-foreground italic py-3">No asset accounts found.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Tab 3: Cash Flow Statement */}
          {financialSubTab === 'cf' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-emerald-600 tracking-wider">Cash Receipts (Inflow)</p>
                  <p className="text-lg font-black text-emerald-600">{formatCurrency(cashFlowData?.operating_activities?.cash_receipts_from_customers || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">From Customer Collections</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-rose-600 tracking-wider">Cash Payments (Outflow)</p>
                  <p className="text-lg font-black text-rose-600">{formatCurrency(cashFlowData?.operating_activities?.cash_paid_to_suppliers_expenses || 0)}</p>
                  <p className="text-[10px] text-muted-foreground">Paid to Vendors & Operations</p>
                </div>
                <div className="bg-card border border-border rounded-2xl p-4 space-y-1 shadow-sm">
                  <p className="text-[10px] font-extrabold uppercase text-blue-600 tracking-wider">Net Operating Cash Flow</p>
                  <p className={cn("text-lg font-black", (cashFlowData?.operating_activities?.net_cash_from_operating || 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                    {formatCurrency(cashFlowData?.operating_activities?.net_cash_from_operating || 0)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">Inflows minus Outflows</p>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Tab 4: Financial Ratios */}
          {financialSubTab === 'ratios' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-card border border-border rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex justify-between items-center">
                    <span className="font-extrabold text-sm text-foreground">Current Ratio</span>
                    <span className="text-base font-black text-emerald-600">{ratiosData?.current_ratio ?? '—'}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Measures company liquidity & ability to cover short-term debts. Benchmark: &gt; 1.5.
                  </p>
                </div>

                <div className="bg-card border border-border rounded-2xl p-5 space-y-2 shadow-sm">
                  <div className="flex justify-between items-center">
                    <span className="font-extrabold text-sm text-foreground">Quick Acid-Test Ratio</span>
                    <span className="text-base font-black text-blue-600">{ratiosData?.quick_ratio ?? '—'}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Measures immediate cash liquidity excluding inventory stock. Benchmark: &gt; 1.0.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Sub-Tab 5: Projected Financial Statements & Bank PDF */}
          {financialSubTab === 'projected' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <ProjectedFinancials companyName={user?.company_name || 'M/S SNEH DISTRIBUTORS'} initialData={pnlData} />
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SALES & CUSTOMER ANALYTICS */}
      {activeTab === 'sales' && (
        <div className="space-y-6">
          {/* Top Customers Bar Chart */}
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-3">
              <div className="flex items-center gap-2">
                <div>
                  <h3 className="font-extrabold text-base flex items-center gap-2">
                    <Users className="h-4 w-4 text-blue-500" /> Top 10 Customers by Revenue
                  </h3>
                  <p className="text-xs text-muted-foreground">Ranks your highest volume customer ledgers to measure client concentration</p>
                </div>
                <button
                  onClick={() => setExplanationKey('top_customers')}
                  className="p-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 transition-colors cursor-pointer"
                  title="Click for client concentration explanation"
                >
                  <Info className="h-4 w-4" />
                </button>
              </div>

              <button
                onClick={() => exportToCsv('Top_Customers', topCustomers)}
                className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer self-start sm:self-center"
              >
                <Download className="h-3.5 w-3.5" /> CSV Export
              </button>
            </div>

            <div className="h-72 w-full pt-2">
              {topCustomers.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topCustomers} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={140} />
                    <Tooltip formatter={(val: any) => [formatCurrency(Number(val)), 'Total Sales']} />
                    <Bar dataKey="total_sales" fill="#3b82f6" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">No customer sales data available</div>
              )}
            </div>
          </div>

          {/* Detailed Sales Register Table */}
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-3">
              <div>
                <h3 className="font-extrabold text-base">Sales Register Invoice Journal</h3>
                <p className="text-xs text-muted-foreground">Itemized invoice ledger entries for selected date period</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search party or voucher #..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1.5 bg-muted/40 border border-border rounded-lg text-xs font-medium focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                </div>
                <button
                  onClick={() => exportToCsv('Sales_Register', salesRegister)}
                  className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Download className="h-3.5 w-3.5" /> CSV
                </button>
              </div>
            </div>

            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-left">
                    <th className="py-2.5 px-2 font-bold">Voucher #</th>
                    <th className="py-2.5 px-2 font-bold">Date</th>
                    <th className="py-2.5 px-2 font-bold">Party / Customer Name</th>
                    <th className="py-2.5 px-2 font-bold text-right">Total Invoice Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {salesRegister
                    .filter(r => (r.party_name || '').toLowerCase().includes(searchQuery.toLowerCase()) || (r.voucher_number || '').toLowerCase().includes(searchQuery.toLowerCase()))
                    .map((row, idx) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-2 font-mono font-bold">
                          <Link
                            href={`/vouchers/${row.id}`}
                            className="text-primary hover:underline hover:text-indigo-600 font-bold"
                            title="Click to open voucher details"
                          >
                            <span>{row.voucher_number || `#${row.id}`}</span>
                          </Link>
                        </td>
                        <td className="py-2.5 px-2 text-muted-foreground">{formatDate(row.date)}</td>
                        <td className="py-2.5 px-2 font-semibold">
                          <Link
                            href={`/ledgers?search=${encodeURIComponent(row.party_name)}`}
                            className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                            title={`Search ${row.party_name} in ledgers`}
                          >
                            {toTitleCase(row.party_name)}
                          </Link>
                        </td>
                        <td className="py-2.5 px-2 text-right font-bold text-emerald-600">{formatCurrency(row.amount)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: INVENTORY ANALYTICS */}
      {activeTab === 'inventory' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Stock Group Valuation Chart */}
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-extrabold text-base flex items-center gap-2">
                      <Layers3 className="h-4 w-4 text-amber-500" /> Capital Locked by Stock Group
                    </h3>
                    <p className="text-xs text-muted-foreground">Inventory valuation distributed across main stock categories</p>
                  </div>
                  <button
                    onClick={() => setExplanationKey('inventory')}
                    className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 transition-colors cursor-pointer"
                    title="Click for stock valuation explanation"
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </div>
                <div className="h-64 w-full pt-2">
                  {inventoryData?.group_valuation && inventoryData.group_valuation.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={inventoryData.group_valuation}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                        <XAxis dataKey="group_name" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                        <Tooltip formatter={(val: any) => [formatCurrency(Number(val)), isGrossGst ? 'Valuation (With GST)' : 'Valuation (Without GST)']} />
                        <Bar dataKey={isGrossGst ? "total_value_gross" : "total_value"} fill="#f59e0b" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">No stock inventory valuation data</div>
                  )}
                </div>
              </div>
              <button
                onClick={() => setExplanationKey('inventory')}
                className="bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-900/50 border border-amber-300 dark:border-amber-800 text-amber-950 dark:text-amber-200 p-3 rounded-xl text-xs font-bold flex items-center gap-2 text-left cursor-pointer transition-all shadow-2xs"
              >
                <HelpCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                <span>Click to see how stock valuation prevents tied-up inventory capital.</span>
              </button>
            </div>

            {/* Top Valuable Stock Items List */}
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div>
                    <h3 className="font-extrabold text-base flex items-center gap-2">
                      <Package className="h-4 w-4 text-indigo-500" /> Highest Valuation Stock Items ({isGrossGst ? 'With GST' : 'Without GST'})
                    </h3>
                    <p className="text-xs text-muted-foreground">Ranks individual items by closing inventory valuation (Qty × Rate)</p>
                  </div>
                  <button onClick={() => exportToCsv('Inventory_Valuation', inventoryData?.top_items || [])} className="p-1.5 bg-muted hover:bg-background border border-border text-xs rounded-lg transition-colors cursor-pointer">
                    <Download className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="divide-y divide-border/50 max-h-64 overflow-y-auto pr-1 pt-2">
                  {[...(inventoryData?.top_items || [])]
                    .sort((a: any, b: any) => (isGrossGst ? (b.total_value_gross || b.total_value) - (a.total_value_gross || a.total_value) : b.total_value - a.total_value))
                    .slice(0, 15)
                    .map((item: any) => {
                      const itemVal = isGrossGst ? (item.total_value_gross ?? item.total_value) : item.total_value
                      const itemRate = isGrossGst ? (item.rate_gross ?? item.rate) : item.rate
                      return (
                        <div key={item.item_id} className="py-2 flex items-center justify-between text-xs">
                          <div>
                            <p className="font-bold text-foreground">{item.name}</p>
                            <p className="text-[10px] text-muted-foreground">{item.group_name} • {item.quantity} {item.uom}</p>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-indigo-600">{formatCurrency(itemVal)}</p>
                            <p className="text-[10px] text-muted-foreground">
                              @ {formatCurrency(itemRate)}/{item.uom} {isGrossGst && item.gst_rate_percent ? `(incl. ${item.gst_rate_percent}% GST)` : ''}
                            </p>
                          </div>
                        </div>
                      )
                    })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: AUDIT & TRIAL BALANCE */}
      {activeTab === 'compliance' && (
        <div className="space-y-6">
          {/* Trial Balance Group Summary Table */}
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-3">
              <div className="flex items-center gap-2">
                <div>
                  <h3 className="font-extrabold text-base flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-emerald-500" /> Account Group Trial Balance
                  </h3>
                  <p className="text-xs text-muted-foreground">Summarizes closing Debit (Dr) and Credit (Cr) balances across all primary account groups</p>
                </div>
                <button
                  onClick={() => setExplanationKey('trial_balance')}
                  className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 transition-colors cursor-pointer"
                  title="Click for Trial Balance explanation"
                >
                  <Info className="h-4 w-4" />
                </button>
              </div>
              <button onClick={() => exportToCsv('Trial_Balance', trialBalance)} className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer self-start sm:self-center">
                <Download className="h-3.5 w-3.5" /> CSV Export
              </button>
            </div>

            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-left">
                    <th className="py-2.5 px-2 font-bold">Account Group Name</th>
                    <th className="py-2.5 px-2 font-bold text-right">Total Debit (Dr)</th>
                    <th className="py-2.5 px-2 font-bold text-right">Total Credit (Cr)</th>
                    <th className="py-2.5 px-2 font-bold text-right">Net Closing Balance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {trialBalance.map((row, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-2 font-semibold flex items-center gap-2">
                        <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span>{row.name}</span>
                        <button
                          onClick={() => setSelectedGroupInfo(row.name)}
                          className="p-1 rounded-md text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors cursor-pointer"
                          title={`Click for info about ${row.name}`}
                        >
                          <Info className="h-3.5 w-3.5" />
                        </button>
                      </td>
                      <td className="py-2.5 px-2 text-right font-medium text-emerald-700 dark:text-emerald-400">
                        {formatCurrency(row.debit || 0)}
                      </td>
                      <td className="py-2.5 px-2 text-right font-medium text-blue-700 dark:text-blue-400">
                        {formatCurrency(row.credit || 0)}
                      </td>
                      <td className={cn('py-2.5 px-2 text-right font-bold', row.balance >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400')}>
                        {formatCurrency(Math.abs(row.balance))} {row.balance >= 0 ? 'Dr' : 'Cr'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Day Book Chronological Audit Stream */}
          <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-3">
              <div>
                <h3 className="font-extrabold text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-blue-500" /> Day Book Transaction Register
                </h3>
                <p className="text-xs text-muted-foreground">Chronological audit stream of all transaction vouchers (Sales, Purchases, Receipts, Payments)</p>
              </div>
              <button onClick={() => exportToCsv('Daybook', daybook)} className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer self-start sm:self-center">
                <Download className="h-3.5 w-3.5" /> Export Daybook CSV
              </button>
            </div>

            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground text-left">
                    <th className="py-2.5 px-2 font-bold">Date</th>
                    <th className="py-2.5 px-2 font-bold">Voucher #</th>
                    <th className="py-2.5 px-2 font-bold">Voucher Type</th>
                    <th className="py-2.5 px-2 font-bold">Party / Account</th>
                    <th className="py-2.5 px-2 font-bold text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {daybook.map((row, idx) => {
                    const typeStyle = getVoucherTypeBadge(row.type)
                    return (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-2 text-muted-foreground">{formatDate(row.date)}</td>
                        <td className="py-2.5 px-2 font-mono font-bold">
                          <Link
                            href={`/vouchers/${row.id}`}
                            className="text-primary hover:underline hover:text-indigo-600 font-bold"
                            title="Click to open voucher details"
                          >
                            <span>{row.voucher_number || `#${row.id}`}</span>
                          </Link>
                        </td>
                        <td className="py-2.5 px-2">
                          <span className={cn('px-2.5 py-0.5 rounded-full text-[10px] font-extrabold border', typeStyle.badge)}>
                            {row.type}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 font-semibold">
                          <Link
                            href={`/ledgers?search=${encodeURIComponent(row.party_name)}`}
                            className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                            title={`Search ${row.party_name} in ledgers`}
                          >
                            {toTitleCase(row.party_name)}
                          </Link>
                        </td>
                        <td className={cn('py-2.5 px-2 text-right font-bold', typeStyle.amount)}>{formatCurrency(row.amount)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* KPI ITEMIZE DRILLDOWN MODAL */}
      {kpiModalData && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-card w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden border border-border flex flex-col max-h-[85vh] animate-in zoom-in-95">
            {/* Header */}
            <div className="px-5 py-4 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/30">
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-muted-foreground">Itemized KPI Breakdown</span>
                <h3 className="font-extrabold text-base text-foreground flex items-center gap-2">
                  {kpiModalData.title}
                </h3>
              </div>
              <div className="flex items-center gap-3 self-end sm:self-center">
                <span className="text-sm font-black px-3 py-1 rounded-xl bg-primary/10 text-primary border border-primary/20">
                  {formatCurrency(kpiModalData.total)}
                </span>
                <button
                  onClick={() => exportToCsv(kpiModalData.title.replace(/\s+/g, '_'), kpiModalData.rows)}
                  className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Download className="h-3.5 w-3.5" /> CSV
                </button>
                <button
                  onClick={() => setKpiModalKey(null)}
                  className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Search Filter Bar */}
            <div className="p-3 border-b border-border bg-card flex items-center justify-between gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Filter by customer, party or voucher #..."
                  value={kpiSearchQuery}
                  onChange={e => setKpiSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-muted/40 border border-border rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <span className="text-[11px] text-muted-foreground font-bold px-2">
                Showing {kpiModalData.rows.length} entries
              </span>
            </div>

            {/* Data Table */}
            <div className="p-4 overflow-y-auto max-h-96">
              {kpiModalData.rows.length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground text-left">
                      {kpiModalData.headers.map((h, i) => (
                        <th key={i} className={cn('py-2.5 px-3 font-bold', i === kpiModalData.headers.length - 1 && 'text-right')}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {kpiModalData.rows.map((row: any, idx: number) => kpiModalData.renderRow(row, idx))}
                  </tbody>
                </table>
              ) : (
                <div className="py-12 text-center text-xs text-muted-foreground space-y-1">
                  <p className="font-bold">No entries found matching your search</p>
                  <p className="text-[11px]">Try searching a different party name or clear the date filter</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-border bg-muted/20 flex justify-between items-center text-xs text-muted-foreground font-medium">
              <span>Date Period: {formatDate(fromDate)} to {formatDate(toDate)}</span>
              <button
                onClick={() => setKpiModalKey(null)}
                className="px-4 py-1.5 bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-bold rounded-xl transition-colors cursor-pointer"
              >
                Close List
              </button>
            </div>
          </div>
        </div>
      )}

      {/* INTERACTIVE EXPLANATION MODAL */}
      {currentExp && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-card w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden border border-border flex flex-col max-h-[90vh] animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600">
                  <Info className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-sm text-foreground">{currentExp.title}</h3>
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600 bg-indigo-500/10 px-2 py-0.5 rounded-full">
                    {currentExp.badge}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setExplanationKey(null)}
                className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4 text-xs">
              {/* Summary */}
              <div className="bg-muted/40 p-3.5 rounded-xl border border-border/60 text-muted-foreground leading-relaxed">
                <p className="font-medium">{currentExp.summary}</p>
              </div>

              {/* Metrics Breakdown */}
              <div className="space-y-2">
                <h4 className="font-extrabold text-xs uppercase tracking-wider text-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-500" /> Metrics Breakdown
                </h4>
                <div className="grid gap-2">
                  {currentExp.lines.map((line, idx) => (
                    <div key={idx} className="p-2.5 rounded-xl bg-card border border-border flex flex-col gap-0.5">
                      <span className="font-extrabold text-foreground">{line.name}</span>
                      <span className="text-muted-foreground text-[11px]">{line.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Concrete Real-World Example */}
              <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-2xl p-4 space-y-3 shadow-xs">
                <div className="flex items-center justify-between border-b border-emerald-200 dark:border-emerald-800 pb-2">
                  <h4 className="font-extrabold text-xs flex items-center gap-1.5 text-emerald-900 dark:text-emerald-300">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" /> {currentExp.example.title}
                  </h4>
                  <span className="text-[10px] font-mono font-extrabold bg-emerald-100 dark:bg-emerald-900/60 text-emerald-900 dark:text-emerald-200 px-2 py-0.5 rounded-md border border-emerald-300 dark:border-emerald-700">
                    {currentExp.example.period}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono font-extrabold">
                  <div className="bg-white dark:bg-slate-900 p-2.5 rounded-xl border border-emerald-300 dark:border-emerald-800 text-emerald-950 dark:text-emerald-200 shadow-2xs">
                    {currentExp.example.sales}
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-2.5 rounded-xl border border-blue-300 dark:border-blue-800 text-blue-950 dark:text-blue-200 shadow-2xs">
                    {currentExp.example.receipts}
                  </div>
                </div>
                <p className="text-xs leading-relaxed font-semibold text-slate-900 dark:text-slate-100 bg-white/70 dark:bg-slate-900/70 p-3 rounded-xl border border-emerald-200 dark:border-emerald-800/60">
                  {currentExp.example.explanation}
                </p>
              </div>

              {/* Business Takeaways */}
              <div className="space-y-1.5 pt-1">
                <h4 className="font-extrabold text-xs uppercase tracking-wider text-foreground flex items-center gap-1.5">
                  <AlertCircle className="h-3.5 w-3.5 text-amber-500" /> Executive Business Takeaways
                </h4>
                <ul className="space-y-1 text-[11px] text-muted-foreground pl-1">
                  {currentExp.takeaways.map((take, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-indigo-500 font-bold">•</span>
                      <span>{take}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-border bg-muted/20 flex justify-end">
              <button
                onClick={() => setExplanationKey(null)}
                className="px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-bold rounded-xl transition-colors cursor-pointer"
              >
                Got It! Close Explanation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Account Group Explanation Modal */}
      {selectedGroupInfo && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl relative animate-in zoom-in-95">
            <button
              onClick={() => setSelectedGroupInfo(null)}
              className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-border/50 pb-3">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600">
                <Building2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-base">{selectedGroupInfo}</h3>
                <p className="text-xs text-muted-foreground">Tally Account Group Definition & Impact</p>
              </div>
            </div>

            {(() => {
              const info = ACCOUNT_GROUP_DESCRIPTIONS[selectedGroupInfo] || {
                desc: `Account group for managing ${selectedGroupInfo} ledgers.`,
                drCr: 'Debit represents Dr balance; Credit represents Cr balance.',
                example: `Standard accounting entries posted under ${selectedGroupInfo}.`
              }
              return (
                <div className="space-y-3.5 text-xs">
                  <div className="bg-amber-100/80 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-700 p-3.5 rounded-2xl space-y-1.5 shadow-2xs">
                    <p className="font-black text-amber-950 dark:text-amber-300 text-xs flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4 text-amber-700 dark:text-amber-400 shrink-0" />
                      <span>What is {selectedGroupInfo}?</span>
                    </p>
                    <p className="text-slate-900 dark:text-slate-100 font-bold text-xs leading-relaxed">{info.desc}</p>
                  </div>

                  <div className="bg-emerald-100/80 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-700 p-3.5 rounded-2xl space-y-1.5 shadow-2xs">
                    <p className="font-black text-emerald-950 dark:text-emerald-300 text-xs flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-700 dark:text-emerald-400 shrink-0" />
                      <span>Dr / Cr Balance Accounting Meaning</span>
                    </p>
                    <p className="text-slate-900 dark:text-slate-100 font-bold text-xs leading-relaxed">{info.drCr}</p>
                  </div>

                  <div className="bg-blue-100/80 dark:bg-blue-950/60 border border-blue-300 dark:border-blue-700 p-3.5 rounded-2xl space-y-1.5 shadow-2xs">
                    <p className="font-black text-blue-950 dark:text-blue-300 text-xs flex items-center gap-1.5">
                      <Info className="h-4 w-4 text-blue-700 dark:text-blue-400 shrink-0" />
                      <span>Real-world Business Example</span>
                    </p>
                    <p className="text-slate-900 dark:text-slate-100 font-bold text-xs leading-relaxed">{info.example}</p>
                  </div>
                </div>
              )
            })()}

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedGroupInfo(null)}
                className="px-4 py-2 bg-primary text-primary-foreground font-bold text-xs rounded-xl hover:bg-primary/90 transition-all cursor-pointer"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Aging Bucket Drilldown Modal */}
      {agingModalBucket && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl relative overflow-hidden animate-in zoom-in-95">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-600 border border-amber-500/20">
                  <BarChart3 className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base flex items-center gap-2">
                    <span>Outstanding Debtors Breakdown</span>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
                      {agingModalBucket}
                    </span>
                  </h3>
                  <p className="text-xs text-muted-foreground">Itemized sales invoices pending under FIFO settlement allocation</p>
                </div>
              </div>

              <button
                onClick={() => setAgingModalBucket(null)}
                className="p-1.5 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Search Bar & Actions */}
            <div className="p-4 border-b border-border bg-background flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="relative w-full sm:w-72">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search customer or invoice #..."
                  value={agingSearchQuery}
                  onChange={(e) => setAgingSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-muted/40 border border-border rounded-xl text-xs focus:outline-hidden focus:ring-2 focus:ring-amber-500/30"
                />
              </div>

              {(() => {
                const bucketItems = (execData?.receivables_aging_details || []).filter(
                  (item: any) => item.bucket === agingModalBucket
                )
                const totalBucketAmt = bucketItems.reduce((acc: number, item: any) => acc + (item.amount || 0), 0)

                return (
                  <div className="flex items-center gap-3 self-end sm:self-center">
                    <span className="text-xs font-bold text-muted-foreground">
                      Total Debt: <strong className="text-amber-600 dark:text-amber-400 font-extrabold text-sm">{formatCurrency(totalBucketAmt)}</strong>
                    </span>
                    <button
                      onClick={() => exportToCsv(`Debtors_Aging_${agingModalBucket.replace(/\s+/g, '_')}`, bucketItems)}
                      className="px-3 py-1.5 bg-muted hover:bg-background border border-border text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <Download className="h-3.5 w-3.5" /> CSV Export
                    </button>
                    <Link
                      href={`/outstanding?bucket=${encodeURIComponent(agingModalBucket.replace(' Days', '').replace('+', ''))}`}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                    >
                      <Clock className="h-3.5 w-3.5" />
                      <span>Send Reminders</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                )
              })()}
            </div>

            {/* Itemized Table */}
            <div className="overflow-y-auto flex-1 p-6">
              {(() => {
                const filteredItems = (execData?.receivables_aging_details || []).filter((item: any) => {
                  if (item.bucket !== agingModalBucket) return false
                  if (!agingSearchQuery) return true
                  const q = agingSearchQuery.toLowerCase()
                  return (
                    item.party_name.toLowerCase().includes(q) ||
                    (item.voucher_number && item.voucher_number.toLowerCase().includes(q))
                  )
                })

                if (filteredItems.length === 0) {
                  return (
                    <div className="py-12 text-center text-xs text-muted-foreground">
                      No customer bills found matching &quot;{agingSearchQuery}&quot; in the {agingModalBucket} bucket.
                    </div>
                  )
                }

                return (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-muted-foreground text-left">
                        <th className="py-2.5 px-2 font-bold">Customer / Debtor Name</th>
                        <th className="py-2.5 px-2 font-bold">Voucher / Invoice #</th>
                        <th className="py-2.5 px-2 font-bold">Invoice Date</th>
                        <th className="py-2.5 px-2 font-bold text-center">Age</th>
                        <th className="py-2.5 px-2 font-bold text-right">Unpaid Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {filteredItems.map((item: any, idx: number) => (
                        <tr key={idx} className="hover:bg-muted/30 transition-colors">
                          <td className="py-2.5 px-2 font-semibold text-foreground">
                            {item.ledger_id ? (
                              <Link
                                href={`/ledgers/${item.ledger_id}`}
                                className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                                title={`Open ${item.party_name} ledger statement`}
                              >
                                {item.party_name}
                              </Link>
                            ) : (
                              <Link
                                href={`/ledgers?search=${encodeURIComponent(item.party_name)}`}
                                className="text-foreground hover:text-primary hover:underline font-bold transition-colors"
                                title={`Search ${item.party_name} in ledgers`}
                              >
                                {item.party_name}
                              </Link>
                            )}
                          </td>
                          <td className="py-2.5 px-2 font-medium">
                            {item.id > 0 ? (
                              <Link
                                href={`/vouchers/${item.id}`}
                                className="text-primary hover:underline font-bold"
                              >
                                <span>{item.voucher_number}</span>
                              </Link>
                            ) : (
                              <span className="text-muted-foreground italic">{item.voucher_number}</span>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-muted-foreground">
                            {item.date ? new Date(item.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
                          </td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
                              {item.days} Days
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-black text-amber-600 dark:text-amber-400">
                            {formatCurrency(item.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )
              })()}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-border bg-muted/20 flex justify-end">
              <button
                onClick={() => setAgingModalBucket(null)}
                className="px-4 py-2 bg-primary text-primary-foreground font-bold text-xs rounded-xl hover:bg-primary/90 transition-all cursor-pointer"
              >
                Close Breakdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function KpiCard({ title, value, icon: Icon, color, info, onClick }: { title: string; value: number; icon: any; color: string; info: string; onClick?: () => void }) {
  const colorMap: Record<string, string> = {
    emerald: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 group-hover:bg-emerald-500/20',
    blue: 'bg-blue-500/10 text-blue-600 border-blue-500/20 group-hover:bg-blue-500/20',
    purple: 'bg-purple-500/10 text-purple-600 border-purple-500/20 group-hover:bg-purple-500/20',
    amber: 'bg-amber-500/10 text-amber-600 border-amber-500/20 group-hover:bg-amber-500/20',
    rose: 'bg-rose-500/10 text-rose-600 border-rose-500/20 group-hover:bg-rose-500/20',
    slate: 'bg-slate-500/10 text-slate-600 border-slate-500/20 group-hover:bg-slate-500/20'
  }

  return (
    <div
      onClick={onClick}
      className="bg-card border border-border rounded-2xl p-4 flex flex-col justify-between shadow-sm hover:shadow-md hover:border-primary/50 transition-all space-y-2 group cursor-pointer relative overflow-hidden"
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-extrabold text-muted-foreground uppercase tracking-wider">{title}</span>
        <div className={cn('p-2 rounded-xl border transition-colors', colorMap[color])}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div>
        <h2 className="text-xl font-black tracking-tight">{formatCurrency(value)}</h2>
        <div className="flex items-center justify-between mt-1">
          <p className="text-[10px] text-muted-foreground font-normal leading-tight group-hover:text-foreground transition-colors">{info}</p>
          <span className="text-[10px] font-bold text-primary opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5 shrink-0 ml-1">
            View List ➔
          </span>
        </div>
      </div>
    </div>
  )
}
