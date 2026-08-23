'use client'

import { useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import {
  Users,
  AlertTriangle,
  Clock,
  Send,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  MessageCircle,
  Mail,
  Copy,
  Check,
  CreditCard,
  DollarSign,
  TrendingDown,
  Layers,
  ArrowUpRight,
  Filter,
  X,
  FileText,
  Building,
  PhoneCall,
  Sparkles
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CustomerAgingBill {
  bill_id: number
  voucher_id?: number
  bill_reference: string
  bill_date: string
  due_date?: string
  bill_amount: number
  settled_amount: number
  outstanding_amount: number
  days_overdue: number
  status: string
}

interface CustomerAgingSummary {
  party_ledger_id: number
  party_name: string
  phone?: string
  email?: string
  credit_period_days: number
  total_outstanding: number
  current_not_due: number
  days_1_30: number
  days_31_60: number
  days_61_90: number
  days_90_plus: number
  open_bills_count: number
  overdue_bills_count: number
  dunning_level: 'CURRENT' | 'GENTLE' | 'FORMAL' | 'URGENT'
  bills: CustomerAgingBill[]
}

interface AgingKPISummary {
  total_receivables: number
  total_overdue: number
  total_current: number
  bucket_0_30: number
  bucket_31_60: number
  bucket_61_90: number
  bucket_90_plus: number
  total_debtors_count: number
  overdue_debtors_count: number
}

interface AgingDashboardData {
  kpis: AgingKPISummary
  customers: CustomerAgingSummary[]
  upi_vpa: string
  merchant_name: string
}

interface ReminderPreview {
  party_ledger_id: number
  party_name: string
  phone?: string
  email?: string
  total_due: number
  overdue_bills_count: number
  dunning_level: string
  message_text: string
  whatsapp_url?: string
  upi_uri: string
  upi_vpa: string
}

export default function DebtorsAgingPage() {
  const { token, user } = useAuth()
  const [data, setData] = useState<AgingDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters & State
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedBucket, setSelectedBucket] = useState<'ALL' | '0-30' | '31-60' | '61-90' | '90+' | 'OVERDUE'>('ALL')
  const [dunningFilter, setDunningFilter] = useState<'ALL' | 'URGENT' | 'FORMAL' | 'GENTLE' | 'CURRENT'>('ALL')
  const [expandedPartyIds, setExpandedPartyIds] = useState<Set<number>>(new Set())

  // Reminder Modal State
  const [reminderModalOpen, setReminderModalOpen] = useState(false)
  const [previewData, setPreviewData] = useState<ReminderPreview | null>(null)
  const [isGeneratingReminder, setIsGeneratingReminder] = useState(false)
  const [selectedDunningLevel, setSelectedDunningLevel] = useState<string>('auto')
  const [isCopied, setIsCopied] = useState(false)

  // Bulk Reminders Modal State
  const [bulkModalOpen, setBulkModalOpen] = useState(false)
  const [bulkBucket, setBulkBucket] = useState<string>('ALL_OVERDUE')
  const [bulkResults, setBulkResults] = useState<ReminderPreview[]>([])
  const [isGeneratingBulk, setIsGeneratingBulk] = useState(false)

  const fetchAgingData = async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/payment/aging/dashboard`, {
        headers: authHeaders(token)
      })
      if (!res.ok) {
        throw new Error('Failed to load debtors aging report')
      }
      const json: AgingDashboardData = await res.json()
      setData(json)
    } catch (err: any) {
      setError(err.message || 'Error fetching aging data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAgingData()
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const bParam = params.get('bucket')
      if (bParam) {
        if (bParam.includes('90')) setSelectedBucket('90+')
        else if (bParam.includes('61') || bParam.includes('60-90') || bParam.includes('61-90')) setSelectedBucket('61-90')
        else if (bParam.includes('31') || bParam.includes('30-60') || bParam.includes('31-60')) setSelectedBucket('31-60')
        else if (bParam.includes('0-30') || bParam.includes('30')) setSelectedBucket('0-30')
        else if (bParam.toLowerCase() === 'overdue') setSelectedBucket('OVERDUE')
      }
    }
  }, [token])

  const toggleExpand = (partyId: number) => {
    setExpandedPartyIds((prev) => {
      const next = new Set(prev)
      if (next.has(partyId)) next.delete(partyId)
      else next.add(partyId)
      return next
    })
  }

  const handleOpenReminder = async (partyId: number, level: string = 'auto') => {
    if (!token) return
    setIsGeneratingReminder(true)
    setSelectedDunningLevel(level)
    try {
      const res = await fetch(`${API_BASE}/payment/reminders/generate-whatsapp`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          party_ledger_id: partyId,
          dunning_level: level,
          channel: 'whatsapp'
        })
      })
      if (!res.ok) throw new Error('Failed to generate reminder message')
      const preview: ReminderPreview = await res.json()
      setPreviewData(preview)
      setReminderModalOpen(true)
    } catch (err: any) {
      alert(err.message || 'Error generating reminder')
    } finally {
      setIsGeneratingReminder(false)
    }
  }

  const handleCopyMessage = () => {
    if (previewData?.message_text) {
      navigator.clipboard.writeText(previewData.message_text)
      setIsCopied(true)
      setTimeout(() => setIsCopied(false), 2000)
    }
  }

  const handleOpenBulkModal = async () => {
    if (!token) return
    setIsGeneratingBulk(true)
    setBulkModalOpen(true)
    try {
      const res = await fetch(`${API_BASE}/payment/reminders/bulk`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          aging_bucket: bulkBucket,
          channel: 'whatsapp'
        })
      })
      if (!res.ok) throw new Error('Failed to generate bulk reminders')
      const json = await res.json()
      setBulkResults(json.reminders || [])
    } catch (err: any) {
      alert(err.message || 'Error generating bulk reminders')
    } finally {
      setIsGeneratingBulk(false)
    }
  }

  const filteredCustomers = useMemo(() => {
    if (!data?.customers) return []
    return data.customers.filter((c) => {
      // Search
      const matchesSearch =
        c.party_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.phone && c.phone.includes(searchTerm)) ||
        (c.email && c.email.toLowerCase().includes(searchTerm.toLowerCase()))

      if (!matchesSearch) return false

      // Bucket Filter
      if (selectedBucket === 'OVERDUE' && c.overdue_bills_count === 0) return false
      if (selectedBucket === '0-30' && c.days_1_30 <= 0) return false
      if (selectedBucket === '31-60' && c.days_31_60 <= 0) return false
      if (selectedBucket === '61-90' && c.days_61_90 <= 0) return false
      if (selectedBucket === '90+' && c.days_90_plus <= 0) return false

      // Dunning Filter
      if (dunningFilter !== 'ALL' && c.dunning_level !== dunningFilter) return false

      return true
    })
  }, [data?.customers, searchTerm, selectedBucket, dunningFilter])

  return (
    <div className="min-h-screen bg-muted/20 pb-20">
      {/* Top Banner Header */}
      <div className="bg-card border-b border-border/80 px-4 lg:px-8 py-6">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center border border-emerald-500/20 shadow-xs">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <h1 className="text-xl lg:text-2xl font-black text-foreground tracking-tight">
                  Debtors Aging & Automated Overdue Reminders
                </h1>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Track overdue customer balances and dispatch 1-click WhatsApp payment reminders with direct NPCI UPI payment links{data?.upi_vpa ? <> (VPA: <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">{data.upi_vpa}</span>)</> : ''}.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5 self-start md:self-auto">
            <button
              onClick={handleOpenBulkModal}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-2 cursor-pointer active:scale-95"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Bulk WhatsApp Reminders</span>
            </button>

            <button
              onClick={fetchAgingData}
              className="px-3.5 py-2 border border-border bg-card hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
              title="Refresh Aging Data"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 lg:px-8 mt-6 space-y-6">
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Receivables */}
          <div className="bg-card border border-border/80 rounded-2xl p-5 shadow-xs bg-gradient-to-br from-blue-500/5 via-card to-card">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Receivables</span>
              <div className="w-8 h-8 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center border border-blue-500/20">
                <DollarSign className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-foreground">
                {formatCurrency(data?.kpis.total_receivables || 0)}
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] text-muted-foreground font-medium">
                  {data?.kpis.total_debtors_count || 0} Customers with open balance
                </span>
              </div>
            </div>
          </div>

          {/* Overdue Receivables */}
          <div className="bg-card border border-rose-500/20 rounded-2xl p-5 shadow-xs bg-gradient-to-br from-rose-500/5 via-card to-card">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wider">Total Overdue</span>
              <div className="w-8 h-8 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center border border-rose-500/20">
                <AlertTriangle className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-rose-600 dark:text-rose-400">
                {formatCurrency(data?.kpis.total_overdue || 0)}
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] text-rose-600 font-bold">
                  {data?.kpis.overdue_debtors_count || 0} Customers Overdue
                </span>
              </div>
            </div>
          </div>

          {/* Current / Not Due */}
          <div className="bg-card border border-emerald-500/20 rounded-2xl p-5 shadow-xs bg-gradient-to-br from-emerald-500/5 via-card to-card">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Current (Within Credit)</span>
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center border border-emerald-500/20">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                {formatCurrency(data?.kpis.total_current || 0)}
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] text-muted-foreground font-medium">On-time payments</span>
              </div>
            </div>
          </div>

          {/* Critical 90+ Days */}
          <div className="bg-card border border-purple-500/20 rounded-2xl p-5 shadow-xs bg-gradient-to-br from-purple-500/5 via-card to-card">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-purple-600 dark:text-purple-400 uppercase tracking-wider">Overdue &gt; 90 Days</span>
              <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 flex items-center justify-center border border-purple-500/20">
                <TrendingDown className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-black text-purple-600 dark:text-purple-400">
                {formatCurrency(data?.kpis.bucket_90_plus || 0)}
              </span>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-[11px] text-purple-600 font-bold">Urgent attention needed</span>
              </div>
            </div>
          </div>
        </div>

        {/* Aging Buckets Filter Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { id: '0-30', label: '1–30 Days Overdue', amount: data?.kpis.bucket_0_30 || 0, color: 'emerald' },
            { id: '31-60', label: '31–60 Days Overdue', amount: data?.kpis.bucket_31_60 || 0, color: 'amber' },
            { id: '61-90', label: '61–90 Days Overdue', amount: data?.kpis.bucket_61_90 || 0, color: 'orange' },
            { id: '90+', label: '90+ Days Overdue', amount: data?.kpis.bucket_90_plus || 0, color: 'rose' }
          ].map((bucket) => {
            const isSelected = selectedBucket === bucket.id
            return (
              <button
                key={bucket.id}
                onClick={() => setSelectedBucket(isSelected ? 'ALL' : (bucket.id as any))}
                className={cn(
                  "p-3.5 rounded-2xl border text-left transition-all cursor-pointer flex flex-col justify-between active:scale-98",
                  isSelected
                    ? "bg-foreground text-background border-foreground shadow-md"
                    : "bg-card border-border/80 hover:border-border text-foreground hover:bg-muted/40 shadow-xs"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className={cn("text-[11px] font-extrabold", isSelected ? "text-background/80" : "text-muted-foreground")}>
                    {bucket.label}
                  </span>
                  <span className={cn("w-2 h-2 rounded-full", `bg-${bucket.color}-500`)} />
                </div>
                <span className="text-base font-black mt-2 font-mono">
                  {formatCurrency(bucket.amount)}
                </span>
              </button>
            )
          })}
        </div>

        {/* Main Customer Aging Table Container */}
        <div className="bg-card border border-border/80 rounded-2xl shadow-xs overflow-hidden">
          {/* Table Toolbar */}
          <div className="p-3.5 sm:p-4 border-b border-border/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/20">
            <div className="flex items-center gap-2 flex-wrap">
              <Users className="w-4 h-4 text-emerald-500 shrink-0" />
              <h3 className="font-extrabold text-sm text-foreground">
                Debtors Accounts ({filteredCustomers.length})
              </h3>
              {selectedBucket !== 'ALL' && (
                <button
                  onClick={() => setSelectedBucket('ALL')}
                  className="px-2 py-0.5 rounded-md bg-muted text-[11px] font-bold text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer"
                >
                  <span>Bucket: {selectedBucket} Days</span>
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full sm:w-auto">
              {/* Dunning Severity Filter */}
              <div className="flex items-center gap-1 bg-muted/60 p-1 rounded-xl border border-border/60 overflow-x-auto no-scrollbar max-w-full">
                {(['ALL', 'URGENT', 'FORMAL', 'GENTLE', 'CURRENT'] as const).map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setDunningFilter(lvl)}
                    className={cn(
                      "px-2.5 py-1 rounded-lg text-[11px] font-extrabold whitespace-nowrap transition-all cursor-pointer shrink-0",
                      dunningFilter === lvl
                        ? "bg-foreground text-background shadow-xs"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {lvl === 'ALL' ? 'All Severities' : lvl}
                  </button>
                ))}
              </div>

              {/* Search Bar */}
              <div className="relative w-full sm:w-52">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search customer, phone..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-background border border-border rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/20 text-foreground"
                />
              </div>
            </div>
          </div>

          {/* Loading & Empty States */}
          {loading ? (
            <div className="flex justify-center items-center py-20">
              <RefreshCw className="w-8 h-8 animate-spin text-emerald-500" />
            </div>
          ) : filteredCustomers.length === 0 ? (
            <div className="text-center py-20 space-y-2">
              <CheckCircle2 className="w-10 h-10 text-emerald-500/60 mx-auto" />
              <p className="text-sm font-bold text-foreground">No Outstanding Debtors Found</p>
              <p className="text-xs text-muted-foreground">All customer accounts match current filters or are fully settled.</p>
            </div>
          ) : (
            <>
              {/* MOBILE CARD VIEW (Rendered on screens < 768px) */}
              <div className="block md:hidden divide-y divide-border/60">
                {filteredCustomers.map((cust) => {
                  const isExpanded = expandedPartyIds.has(cust.party_ledger_id)
                  const total = cust.total_outstanding || 1

                  return (
                    <div key={cust.party_ledger_id} className="p-4 space-y-3 bg-card hover:bg-muted/20 transition-colors">
                      {/* Customer Header + Dunning Badge */}
                      <div className="flex items-start justify-between gap-2">
                        <div className="space-y-0.5">
                          <Link
                            href={`/ledgers/${cust.party_ledger_id}`}
                            className="font-extrabold text-sm text-foreground hover:text-emerald-600 transition-colors hover:underline block leading-tight"
                          >
                            {cust.party_name}
                          </Link>
                          <div className="flex items-center gap-2.5 text-[11px] text-muted-foreground font-mono">
                            {cust.phone && (
                              <span className="flex items-center gap-1">
                                <PhoneCall className="w-3 h-3 text-muted-foreground" />
                                {cust.phone}
                              </span>
                            )}
                            <span>Credit: {cust.credit_period_days}d</span>
                          </div>
                        </div>

                        <div>
                          {cust.dunning_level === 'URGENT' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20 whitespace-nowrap">
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                              URGENT (61d+)
                            </span>
                          ) : cust.dunning_level === 'FORMAL' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-500/10 text-amber-600 border border-amber-500/20 whitespace-nowrap">
                              FORMAL (31-60d)
                            </span>
                          ) : cust.dunning_level === 'GENTLE' ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black bg-blue-500/10 text-blue-600 border border-blue-500/20 whitespace-nowrap">
                              GENTLE (1-30d)
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 whitespace-nowrap">
                              CURRENT
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Financial Metrics Summary */}
                      <div className="grid grid-cols-2 gap-2 p-2.5 rounded-xl bg-muted/40 border border-border/60">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-muted-foreground block">Total Due</span>
                          <span className="text-base font-black font-mono text-foreground">
                            {formatCurrency(cust.total_outstanding)}
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] uppercase font-bold text-muted-foreground block">Open Bills</span>
                          <span className="text-xs font-bold font-mono text-foreground">
                            {cust.open_bills_count} bills
                          </span>
                        </div>
                      </div>

                      {/* Aging Progress Bar */}
                      <div>
                        <div className="w-full bg-muted/60 h-2 rounded-full overflow-hidden flex shadow-2xs">
                          {cust.current_not_due > 0 && (
                            <div
                              style={{ width: `${(cust.current_not_due / total) * 100}%` }}
                              className="bg-emerald-500 h-full"
                            />
                          )}
                          {cust.days_1_30 > 0 && (
                            <div
                              style={{ width: `${(cust.days_1_30 / total) * 100}%` }}
                              className="bg-blue-500 h-full"
                            />
                          )}
                          {cust.days_31_60 > 0 && (
                            <div
                              style={{ width: `${(cust.days_31_60 / total) * 100}%` }}
                              className="bg-amber-500 h-full"
                            />
                          )}
                          {cust.days_61_90 > 0 && (
                            <div
                              style={{ width: `${(cust.days_61_90 / total) * 100}%` }}
                              className="bg-orange-500 h-full"
                            />
                          )}
                          {cust.days_90_plus > 0 && (
                            <div
                              style={{ width: `${(cust.days_90_plus / total) * 100}%` }}
                              className="bg-rose-500 h-full"
                            />
                          )}
                        </div>
                        <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-1 font-mono">
                          <span>0d</span>
                          {cust.days_90_plus > 0 && (
                            <span className="text-rose-600 font-bold">90d+: {formatCurrency(cust.days_90_plus)}</span>
                          )}
                        </div>
                      </div>

                      {/* Actions: Expand Bills + WhatsApp Button */}
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => toggleExpand(cust.party_ledger_id)}
                          className="flex-1 py-2 px-3 rounded-xl border border-border bg-background hover:bg-muted text-xs font-bold text-foreground flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                        >
                          <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                          <span>{isExpanded ? 'Hide Bills' : `View Bills (${cust.bills.length})`}</span>
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleOpenReminder(cust.party_ledger_id, 'auto')}
                          className="py-2 px-3.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs transition-colors cursor-pointer shrink-0 active:scale-95"
                        >
                          <MessageCircle className="w-3.5 h-3.5" />
                          <span>WhatsApp</span>
                        </button>
                      </div>

                      {/* Mobile Bill Details Dropdown */}
                      {isExpanded && (
                        <div className="pt-2 border-t border-border space-y-2 animate-in fade-in">
                          <h5 className="text-[11px] font-extrabold uppercase text-muted-foreground">Itemized Bills</h5>
                          {cust.bills.map((bill) => (
                            <div key={bill.bill_id} className="p-2.5 bg-muted/40 rounded-xl border border-border/60 space-y-1 text-xs">
                              <div className="flex justify-between items-center">
                                <span className="font-mono font-bold text-foreground">{bill.bill_reference}</span>
                                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                                  {formatCurrency(bill.outstanding_amount)}
                                </span>
                              </div>
                              <div className="flex justify-between items-center text-[10px] text-muted-foreground">
                                <span>Date: {formatDate(bill.bill_date)}</span>
                                <span className={cn("font-bold font-mono", bill.days_overdue > 0 ? "text-rose-600" : "text-emerald-600")}>
                                  {bill.days_overdue > 0 ? `${bill.days_overdue}d Overdue` : 'Current'}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* DESKTOP TABLE VIEW (Rendered on screens >= 768px) */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse min-w-[950px]">
                  <thead>
                    <tr className="border-b border-border/80 bg-muted/40 text-muted-foreground font-extrabold text-[11px] uppercase tracking-wider">
                      <th className="py-3 px-4 w-10"></th>
                      <th className="py-3 px-4 w-72">Customer / Party Name</th>
                      <th className="py-3 px-4 w-36">Dunning State</th>
                      <th className="py-3 px-4 w-52">Aging Breakdown</th>
                      <th className="py-3 px-4 w-28 text-center">Open Bills</th>
                      <th className="py-3 px-4 w-36 text-right">Total Outstanding</th>
                      <th className="py-3 px-5 text-right w-44">Quick Reminder</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredCustomers.map((cust) => {
                      const isExpanded = expandedPartyIds.has(cust.party_ledger_id)
                      const total = cust.total_outstanding || 1

                      return (
                        <tr key={cust.party_ledger_id} className="group hover:bg-muted/30 transition-colors">
                          <td className="py-3.5 px-4 text-center">
                            <button
                              onClick={() => toggleExpand(cust.party_ledger_id)}
                              className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                              title="Expand bill breakdown"
                            >
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </button>
                          </td>

                          <td className="py-3.5 px-4">
                            <div className="font-extrabold text-xs text-foreground flex items-center gap-2">
                              <Link
                                href={`/ledgers/${cust.party_ledger_id}`}
                                className="hover:text-emerald-600 transition-colors hover:underline"
                              >
                                {cust.party_name}
                              </Link>
                            </div>
                            <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-1">
                              {cust.phone && (
                                <span className="flex items-center gap-1 font-mono">
                                  <PhoneCall className="w-3 h-3 text-muted-foreground" />
                                  {cust.phone}
                                </span>
                              )}
                              <span className="font-medium">Credit: {cust.credit_period_days} Days</span>
                            </div>
                          </td>

                          <td className="py-3.5 px-4">
                            {cust.dunning_level === 'URGENT' ? (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20">
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                                URGENT (61d+)
                              </span>
                            ) : cust.dunning_level === 'FORMAL' ? (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-amber-500/10 text-amber-600 border border-amber-500/20">
                                FORMAL (31-60d)
                              </span>
                            ) : cust.dunning_level === 'GENTLE' ? (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-blue-500/10 text-blue-600 border border-blue-500/20">
                                GENTLE (1-30d)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                CURRENT (On Time)
                              </span>
                            )}
                          </td>

                          <td className="py-3.5 px-4">
                            {/* Segmented Multi-color Aging Progress Bar */}
                            <div className="w-full bg-muted/60 h-2 rounded-full overflow-hidden flex shadow-2xs">
                              {cust.current_not_due > 0 && (
                                <div
                                  style={{ width: `${(cust.current_not_due / total) * 100}%` }}
                                  className="bg-emerald-500 h-full"
                                  title={`Current: ₹${cust.current_not_due.toLocaleString()}`}
                                />
                              )}
                              {cust.days_1_30 > 0 && (
                                <div
                                  style={{ width: `${(cust.days_1_30 / total) * 100}%` }}
                                  className="bg-blue-500 h-full"
                                  title={`1-30 Days: ₹${cust.days_1_30.toLocaleString()}`}
                                />
                              )}
                              {cust.days_31_60 > 0 && (
                                <div
                                  style={{ width: `${(cust.days_31_60 / total) * 100}%` }}
                                  className="bg-amber-500 h-full"
                                  title={`31-60 Days: ₹${cust.days_31_60.toLocaleString()}`}
                                />
                              )}
                              {cust.days_61_90 > 0 && (
                                <div
                                  style={{ width: `${(cust.days_61_90 / total) * 100}%` }}
                                  className="bg-orange-500 h-full"
                                  title={`61-90 Days: ₹${cust.days_61_90.toLocaleString()}`}
                                />
                              )}
                              {cust.days_90_plus > 0 && (
                                <div
                                  style={{ width: `${(cust.days_90_plus / total) * 100}%` }}
                                  className="bg-rose-500 h-full"
                                  title={`90+ Days: ₹${cust.days_90_plus.toLocaleString()}`}
                                />
                              )}
                            </div>
                            <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-1 font-mono">
                              <span>0d</span>
                              {cust.days_90_plus > 0 && <span className="text-rose-600 font-bold">90d+ : ₹{cust.days_90_plus.toLocaleString()}</span>}
                            </div>
                          </td>

                          <td className="py-3.5 px-4 text-center font-mono font-bold">
                            <span className="px-2 py-0.5 rounded-md bg-muted text-foreground text-xs">
                              {cust.open_bills_count}
                            </span>
                          </td>

                          <td className="py-3.5 px-4 text-right font-mono font-black text-sm text-foreground">
                            {formatCurrency(cust.total_outstanding)}
                          </td>

                          <td className="py-3.5 px-5 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleOpenReminder(cust.party_ledger_id, 'auto')}
                                className="h-8 px-3 rounded-xl text-xs font-bold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 border border-emerald-500/20 transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                                title="Generate WhatsApp Dunning Message with Direct UPI link"
                              >
                                <MessageCircle className="w-3.5 h-3.5" />
                                <span>WhatsApp</span>
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Expanded Bill Details Drawer / View */}
        {Array.from(expandedPartyIds).map((partyId) => {
          const cust = data?.customers.find((c) => c.party_ledger_id === partyId)
          if (!cust) return null

          return (
            <div
              key={partyId}
              className="bg-card border border-emerald-500/30 rounded-2xl p-4 sm:p-5 shadow-md space-y-4 animate-in fade-in zoom-in-98 duration-200"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-600 shrink-0" />
                  <h4 className="font-extrabold text-xs sm:text-sm text-foreground leading-tight">
                    Bill-by-Bill Breakdown for <span className="text-emerald-600 underline">{cust.party_name}</span> ({cust.bills.length} Invoices)
                  </h4>
                </div>
                <button
                  onClick={() => toggleExpand(partyId)}
                  className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Mobile Invoice Card View (< 768px) */}
              <div className="block md:hidden space-y-2.5">
                {cust.bills.map((bill) => (
                  <div
                    key={bill.bill_id}
                    className="p-3 bg-muted/40 rounded-xl border border-border/70 space-y-2 text-xs"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-mono font-bold text-foreground text-sm block">
                          {bill.bill_reference}
                        </span>
                        <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
                          <span>Date: {bill.bill_date ? formatDate(bill.bill_date) : '—'}</span>
                          {bill.due_date && <span className="ml-2">Due: {formatDate(bill.due_date)}</span>}
                        </div>
                      </div>
                      <div>
                        {bill.days_overdue > 0 ? (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20 font-mono whitespace-nowrap">
                            {bill.days_overdue}d Overdue
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 whitespace-nowrap">
                            Current
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-1.5 pt-1 border-t border-border/50 text-[11px]">
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Bill Amt</span>
                        <span className="font-mono font-semibold text-foreground">{formatCurrency(bill.bill_amount)}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-muted-foreground block">Settled</span>
                        <span className="font-mono text-muted-foreground">{formatCurrency(bill.settled_amount)}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-muted-foreground block">Balance Due</span>
                        <span className="font-mono font-bold text-rose-600 dark:text-rose-400">
                          {formatCurrency(bill.outstanding_amount)}
                        </span>
                      </div>
                    </div>

                    {bill.voucher_id && (
                      <div className="pt-1 flex justify-end">
                        <Link
                          href={`/vouchers/${bill.voucher_id}`}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-background border border-border hover:bg-muted text-foreground transition-all inline-flex items-center gap-1"
                        >
                          <span>View Voucher</span>
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Desktop Table View (>= 768px) */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse min-w-[700px]">
                  <thead>
                    <tr className="border-b border-border/80 bg-muted/40 text-muted-foreground font-bold text-[11px]">
                      <th className="py-2.5 px-4">Invoice / Bill Ref</th>
                      <th className="py-2.5 px-4">Bill Date</th>
                      <th className="py-2.5 px-4">Due Date</th>
                      <th className="py-2.5 px-4">Days Overdue</th>
                      <th className="py-2.5 px-4 text-right">Bill Amount</th>
                      <th className="py-2.5 px-4 text-right">Settled</th>
                      <th className="py-2.5 px-4 text-right">Balance Due</th>
                      <th className="py-2.5 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {cust.bills.map((bill) => (
                      <tr key={bill.bill_id} className="hover:bg-muted/30">
                        <td className="py-3 px-4 font-mono font-bold text-foreground">
                          {bill.bill_reference}
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground">{bill.bill_date ? formatDate(bill.bill_date) : '—'}</td>
                        <td className="py-3 px-4 font-mono text-muted-foreground">{bill.due_date ? formatDate(bill.due_date) : '—'}</td>
                        <td className="py-3 px-4">
                          {bill.days_overdue > 0 ? (
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20 font-mono">
                              {bill.days_overdue} Days Overdue
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                              Current
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-mono">{formatCurrency(bill.bill_amount)}</td>
                        <td className="py-3 px-4 text-right font-mono text-muted-foreground">{formatCurrency(bill.settled_amount)}</td>
                        <td className="py-3 px-4 text-right font-mono font-black text-rose-600 dark:text-rose-400">
                          {formatCurrency(bill.outstanding_amount)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {bill.voucher_id && (
                            <Link
                              href={`/vouchers/${bill.voucher_id}`}
                              className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-muted hover:bg-muted/80 text-foreground transition-all inline-flex items-center gap-1"
                            >
                              <span>View</span>
                              <ExternalLink className="w-3 h-3" />
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        })}
      </div>

      {/* WhatsApp Reminder Preview Modal */}
      {reminderModalOpen && previewData && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold border border-emerald-500/20">
                  <MessageCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground leading-snug">
                    WhatsApp Payment Reminder
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    For: <strong className="text-foreground">{previewData.party_name}</strong>
                  </span>
                </div>
              </div>
              <button
                onClick={() => setReminderModalOpen(false)}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Dunning Severity Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                Select Dunning Notice Tone
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'gentle', label: 'Gentle Notice' },
                  { id: 'formal', label: 'Formal Reminder' },
                  { id: 'urgent', label: 'Urgent Overdue' }
                ].map((lvl) => (
                  <button
                    key={lvl.id}
                    onClick={() => handleOpenReminder(previewData.party_ledger_id, lvl.id)}
                    className={cn(
                      "py-2 rounded-xl text-xs font-bold transition-all border cursor-pointer",
                      selectedDunningLevel === lvl.id
                        ? "bg-emerald-600 text-white border-emerald-600 shadow-xs"
                        : "bg-muted/40 text-muted-foreground border-border hover:bg-muted hover:text-foreground"
                    )}
                  >
                    {lvl.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Message Preview Box */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                  Live Message Preview
                </label>
                <span className="text-[11px] font-mono text-emerald-600 font-bold">
                  Total Due: {formatCurrency(previewData.total_due)}
                </span>
              </div>
              <div className="bg-muted/50 border border-border rounded-2xl p-4 font-mono text-xs text-foreground whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed shadow-inner">
                {previewData.message_text}
              </div>
            </div>

            {/* Direct UPI VPA Banner */}
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-emerald-600" />
                <span className="text-muted-foreground">Configured Direct UPI:</span>
                <strong className="font-mono text-emerald-600">{previewData.upi_vpa}</strong>
              </div>
              <span className="text-[10px] text-emerald-600 font-bold">0% PG Fees</span>
            </div>

            {/* Actions */}
            <div className="pt-2 flex items-center gap-3">
              <button
                onClick={handleCopyMessage}
                className="flex-1 py-3 px-4 rounded-xl border border-border bg-muted/60 hover:bg-muted text-foreground text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-95"
              >
                {isCopied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                <span>{isCopied ? 'Copied to Clipboard!' : 'Copy Text'}</span>
              </button>

              <a
                href={previewData.whatsapp_url || '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 py-3 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-xs cursor-pointer active:scale-95"
              >
                <MessageCircle className="w-4 h-4" />
                <span>Open WhatsApp</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Reminders Modal */}
      {bulkModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold border border-emerald-500/20">
                  <Send className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground leading-snug">
                    Bulk WhatsApp Dunning Dispatch
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    Generate instant WhatsApp links for all debtors in target aging bucket
                  </span>
                </div>
              </div>
              <button
                onClick={() => setBulkModalOpen(false)}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Bucket Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                Target Aging Cohort
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: 'ALL_OVERDUE', label: 'All Overdue' },
                  { id: '31-60', label: '31–60 Days' },
                  { id: '61-90', label: '61–90 Days' },
                  { id: '90_PLUS', label: '90+ Days' }
                ].map((b) => (
                  <button
                    key={b.id}
                    onClick={() => {
                      setBulkBucket(b.id)
                      handleOpenBulkModal()
                    }}
                    className={cn(
                      "py-2 px-3 rounded-xl text-xs font-bold border transition-all cursor-pointer",
                      bulkBucket === b.id
                        ? "bg-foreground text-background border-foreground shadow-xs"
                        : "bg-muted/40 border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Results List */}
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {isGeneratingBulk ? (
                <div className="flex justify-center items-center py-12">
                  <RefreshCw className="w-6 h-6 animate-spin text-emerald-500" />
                </div>
              ) : bulkResults.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground text-xs">
                  No overdue debtors in this cohort.
                </div>
              ) : (
                bulkResults.map((r, i) => (
                  <div
                    key={r.party_ledger_id || i}
                    className="p-3 bg-muted/40 border border-border/80 rounded-2xl flex items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <h5 className="font-extrabold text-foreground">{r.party_name}</h5>
                      <span className="text-[11px] text-muted-foreground font-mono">
                        Due: {formatCurrency(r.total_due)} ({r.overdue_bills_count} bills)
                      </span>
                    </div>
                    <a
                      href={r.whatsapp_url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 border border-emerald-500/20 font-bold text-xs flex items-center gap-1 cursor-pointer active:scale-95"
                    >
                      <MessageCircle className="w-3.5 h-3.5" />
                      <span>Send</span>
                    </a>
                  </div>
                ))
              )}
            </div>

            <div className="pt-2">
              <button
                onClick={() => setBulkModalOpen(false)}
                className="w-full py-2.5 rounded-xl border border-border bg-card hover:bg-muted text-foreground text-xs font-bold cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
