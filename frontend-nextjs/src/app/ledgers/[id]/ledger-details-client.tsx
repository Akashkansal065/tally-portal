'use client'

import { useState, useMemo, useEffect } from 'react'
import Link from 'next/link'
import { usePeriod } from '@/context/PeriodContext'
import { useAuth } from '@/context/AuthContext'
import { cn, toTitleCase } from '@/lib/utils'
import { toast } from 'sonner'
import {
  Download,
  FileText,
  MessageCircle,
  Copy,
  Check,
  X,
  Phone,
  Filter,
  ChevronDown
} from 'lucide-react'
import {
  exportLedgerToCsv,
  exportLedgerToPdf,
  generateWhatsAppStatementMessage,
  openWhatsAppWithStatement
} from '@/lib/ledger-export'

type Transaction = {
  id: number
  date: string
  voucherType: string
  voucherNumber: string
  referenceNumber: string | null
  narration: string | null
  partyName: string
  amount: string
}

type Props = {
  ledgerInfo: any
  transactions: Transaction[]
  customerPhone?: string
  customerName?: string
}

export default function LedgerDetailsClient({
  ledgerInfo,
  transactions,
  customerPhone,
  customerName
}: Props) {
  const { user } = useAuth()
  const { startDate: globalStart, endDate: globalEnd } = usePeriod()

  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState(globalStart || '2025-04-01')
  const [endDate, setEndDate] = useState(globalEnd || '2026-03-31')

  // Sync date inputs with global selected period across pages
  useEffect(() => {
    if (globalStart) setStartDate(globalStart)
    if (globalEnd) setEndDate(globalEnd)
  }, [globalStart, globalEnd])

  const [filterVoucherType, setFilterVoucherType] = useState('all')
  const [filterFlow, setFilterFlow] = useState('all') // all | debit | credit
  const [sortBy, setSortBy] = useState('date-desc') // date-desc | date-asc | amount-desc | amount-asc

  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

  // Export dropdown states
  const [showPdfMenu, setShowPdfMenu] = useState(false)
  const [showCsvMenu, setShowCsvMenu] = useState(false)

  // WhatsApp Modal State
  const [showWhatsAppModal, setShowWhatsAppModal] = useState(false)
  const [whatsAppPhone, setWhatsAppPhone] = useState(
    customerPhone || ledgerInfo?.mobile || ledgerInfo?.phone || ''
  )
  const [whatsAppFilter, setWhatsAppFilter] = useState<'current' | 'all' | 'sales' | 'purchase' | 'receipt'>('current')
  const [copiedMessage, setCopiedMessage] = useState(false)

  useEffect(() => {
    const phone = customerPhone || ledgerInfo?.mobile || ledgerInfo?.phone || ''
    if (phone) setWhatsAppPhone(phone)
  }, [customerPhone, ledgerInfo])

  // Company details for export
  const company = useMemo(() => {
    if (user?.company) return user.company
    if (user?.company_name) return { name: user.company_name }
    return { name: 'Sneh Distributors' }
  }, [user])

  // Count transactions for quick filters
  const voucherCounts = useMemo(() => {
    const counts = { all: 0, sales: 0, purchase: 0, receipt: 0, payment: 0, other: 0 }
    if (!transactions) return counts
    counts.all = transactions.length
    transactions.forEach(t => {
      const vt = (t.voucherType || '').toLowerCase()
      if (vt.includes('sale')) counts.sales++
      else if (vt.includes('purchase')) counts.purchase++
      else if (vt.includes('receipt')) counts.receipt++
      else if (vt.includes('payment')) counts.payment++
      else counts.other++
    })
    return counts
  }, [transactions])

  // Dynamically build unique voucher types for dropdown filter
  const uniqueVoucherTypes = useMemo(() => {
    if (!transactions) return []
    const types = new Set<string>()
    transactions.forEach(t => {
      if (t.voucherType) {
        types.add(t.voucherType)
      }
    })
    return Array.from(types).sort()
  }, [transactions])

  // Filter and sort transactions list
  const processedTransactions = useMemo(() => {
    if (!transactions) return []
    let result = [...transactions]

    // 1. Text Search Filter
    if (searchQuery.trim()) {
      const lower = searchQuery.toLowerCase()
      result = result.filter(t => {
        return (
          t.narration?.toLowerCase().includes(lower) ||
          t.voucherType?.toLowerCase().includes(lower) ||
          t.voucherNumber?.toLowerCase().includes(lower) ||
          (t.referenceNumber && t.referenceNumber.toLowerCase().includes(lower))
        )
      })
    }

    // 2. Date Range Filter
    if (startDate) {
      const start = new Date(startDate)
      start.setHours(0, 0, 0, 0)
      result = result.filter(t => {
        if (!t.date) return false
        return new Date(t.date).getTime() >= start.getTime()
      })
    }
    if (endDate) {
      const end = new Date(endDate)
      end.setHours(23, 59, 59, 999)
      result = result.filter(t => {
        if (!t.date) return false
        return new Date(t.date).getTime() <= end.getTime()
      })
    }

    // 3. Voucher Type Filter
    if (filterVoucherType !== 'all') {
      const target = filterVoucherType.toLowerCase()
      result = result.filter(t => {
        const vt = (t.voucherType || '').toLowerCase()
        if (vt === target) return true
        if (target === 'sales' && vt.includes('sale')) return true
        if (target === 'purchase' && vt.includes('purchase')) return true
        if (target === 'receipt' && vt.includes('receipt')) return true
        if (target === 'payment' && vt.includes('payment')) return true
        return false
      })
    }

    // 4. Flow (Debit / Credit) Filter
    if (filterFlow !== 'all') {
      result = result.filter(t => {
        const amt = parseFloat(t.amount || '0')
        return filterFlow === 'debit' ? amt < 0 : amt > 0
      })
    }

    // 5. Apply Sorting
    result.sort((a, b) => {
      const [key, direction] = sortBy.split('-')
      const mult = direction === 'asc' ? 1 : -1

      if (key === 'date') {
        const timeA = a.date ? new Date(a.date).getTime() : 0
        const timeB = b.date ? new Date(b.date).getTime() : 0
        return (timeA - timeB) * mult
      }

      if (key === 'amount') {
        const valA = parseFloat(a.amount || '0')
        const valB = parseFloat(b.amount || '0')
        return (Math.abs(valA) - Math.abs(valB)) * mult
      }

      return 0
    })

    return result
  }, [transactions, searchQuery, startDate, endDate, filterVoucherType, filterFlow, sortBy])

  // Filtered transactions amount totals
  const filteredTotals = useMemo(() => {
    let deb = 0
    let cred = 0
    processedTransactions.forEach(t => {
      const amt = parseFloat(t.amount || '0')
      if (amt < 0) deb += Math.abs(amt)
      else cred += amt
    })
    return { debit: deb, credit: cred, count: processedTransactions.length }
  }, [processedTransactions])

  // Helper to get transaction subset for explicit filter option
  const getTransactionsForFilter = (fType: string) => {
    if (fType === 'current') return processedTransactions
    if (fType === 'all') return transactions || []
    const target = fType.toLowerCase()
    return (transactions || []).filter(t => {
      const vt = (t.voucherType || '').toLowerCase()
      if (vt === target) return true
      if (target === 'sales' && vt.includes('sale')) return true
      if (target === 'purchase' && vt.includes('purchase')) return true
      if (target === 'receipt' && vt.includes('receipt')) return true
      if (target === 'payment' && vt.includes('payment')) return true
      return false
    })
  }

  // Mobile pagination subset
  const paginatedTransactions = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize
    return processedTransactions.slice(startIndex, startIndex + pageSize)
  }, [processedTransactions, currentPage])

  const totalPages = Math.ceil(processedTransactions.length / pageSize)

  const formatNumber = (val: string | number) => {
    const parsed = typeof val === 'string' ? parseFloat(val) : val
    return isNaN(parsed) ? '' : parsed.toLocaleString('en-IN', { minimumFractionDigits: 2 })
  }

  // Period Opening & Closing Balances calculation based on selected date range
  const periodSummary = useMemo(() => {
    // 1. Base opening balance in Tally is as of FY start (2026-04-01)
    const baseOpBal = ledgerInfo?.opening_balance || 0
    const isDr = ledgerInfo?.opening_balance_type === 'Dr'
    const fyOpNet = isDr ? -baseOpBal : baseOpBal // negative = Dr, positive = Cr

    // Check if transactions array contains pre-FY vouchers (before 2026-04-01) that were rolled into fyOpNet
    const fyAnchor = '2026-04-01'
    let preFyNet = 0
    if (transactions) {
      transactions.forEach(t => {
        if (!t.date) return
        const d = t.date.split('T')[0]
        if (d < fyAnchor) {
          preFyNet += parseFloat(t.amount || '0') // negative = Dr, positive = Cr
        }
      })
    }
    // True base balance before all recorded transactions in the database
    const trueBaseBeforeAll = fyOpNet - preFyNet

    const startStr = startDate || ''
    const endStr = endDate || ''

    // Calculate prior transactions before the selected startDate
    let priorNet = 0
    let totalPeriodDebit = 0
    let totalPeriodCredit = 0

    if (transactions) {
      transactions.forEach(t => {
        if (!t.date) return
        const d = t.date.split('T')[0]
        const amt = parseFloat(t.amount || '0') // negative = Dr, positive = Cr

        if (startStr && d < startStr) {
          priorNet += amt
        } else if (!endStr || d <= endStr) {
          if (amt < 0) {
            totalPeriodDebit += Math.abs(amt)
          } else {
            totalPeriodCredit += Math.abs(amt)
          }
        }
      })
    }

    const periodOpNet = trueBaseBeforeAll + priorNet
    const periodClosingNet = periodOpNet + (totalPeriodCredit - totalPeriodDebit)

    return {
      opBal: Math.abs(periodOpNet),
      opType: Math.abs(periodOpNet) < 0.005 ? 'Dr' : (periodOpNet < 0 ? 'Dr' : 'Cr'),
      totalDebit: totalPeriodDebit,
      totalCredit: totalPeriodCredit,
      clBal: Math.abs(periodClosingNet),
      clType: Math.abs(periodClosingNet) < 0.005 ? 'Dr' : (periodClosingNet < 0 ? 'Dr' : 'Cr')
    }
  }, [ledgerInfo, transactions, startDate, endDate])

  // PDF Export Action
  const handleDownloadPdf = (targetFilter: string = filterVoucherType) => {
    try {
      setShowPdfMenu(false)
      const txns = targetFilter === filterVoucherType ? processedTransactions : getTransactionsForFilter(targetFilter)
      exportLedgerToPdf({
        ledgerInfo,
        transactions: txns,
        periodSummary,
        startDate,
        endDate,
        filterType: targetFilter,
        company,
        customerName: customerName || ledgerInfo?.name
      })
      toast.success(`Downloaded statement as PDF (${txns.length} vouchers)`)
    } catch (err: any) {
      console.error('PDF export failed', err)
      toast.error('Failed to generate PDF statement')
    }
  }

  // CSV Export Action
  const handleDownloadCsv = (targetFilter: string = filterVoucherType) => {
    try {
      setShowCsvMenu(false)
      const txns = targetFilter === filterVoucherType ? processedTransactions : getTransactionsForFilter(targetFilter)
      exportLedgerToCsv({
        ledgerInfo,
        transactions: txns,
        periodSummary,
        startDate,
        endDate,
        filterType: targetFilter,
        company,
        customerName: customerName || ledgerInfo?.name
      })
      toast.success(`Downloaded statement as CSV (${txns.length} vouchers)`)
    } catch (err: any) {
      console.error('CSV export failed', err)
      toast.error('Failed to generate CSV statement')
    }
  }

  // Live WhatsApp message generation
  const currentWhatsAppMessage = useMemo(() => {
    const txns = getTransactionsForFilter(whatsAppFilter)
    const effectiveFilter = whatsAppFilter === 'current' ? filterVoucherType : whatsAppFilter
    return generateWhatsAppStatementMessage({
      ledgerInfo,
      transactions: txns,
      periodSummary,
      startDate,
      endDate,
      filterType: effectiveFilter,
      company,
      customerName: customerName || ledgerInfo?.name
    })
  }, [whatsAppFilter, filterVoucherType, processedTransactions, transactions, ledgerInfo, periodSummary, startDate, endDate, company, customerName])

  // Send WhatsApp Action
  const handleSendWhatsApp = () => {
    openWhatsAppWithStatement(whatsAppPhone, currentWhatsAppMessage)
    setShowWhatsAppModal(false)
    toast.success('Opening WhatsApp...')
  }

  // Copy WhatsApp Message Action
  const handleCopyWhatsAppMessage = async () => {
    try {
      await navigator.clipboard.writeText(currentWhatsAppMessage)
      setCopiedMessage(true)
      toast.success('Statement message copied to clipboard!')
      setTimeout(() => setCopiedMessage(false), 2000)
    } catch {
      toast.error('Failed to copy to clipboard')
    }
  }

  return (
    <div className="space-y-4 max-w-5xl mx-auto">
      {/* Period Balance Breakdown Strip */}
      <div className="bg-card border border-border rounded-2xl p-3.5 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-sans shadow-sm">
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Op. Balance ({startDate ? startDate.split('-').reverse().join('/') : 'Start'})
          </span>
          <span className="font-mono font-extrabold text-foreground text-sm">
            ₹{periodSummary.opBal.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {periodSummary.opType}
          </span>
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Total Period Debit</span>
          <span className="font-mono font-extrabold text-rose-600 dark:text-rose-400 text-sm">
            ₹{periodSummary.totalDebit.toLocaleString('en-IN', { minimumFractionDigits: 2 })} Dr
          </span>
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Total Period Credit</span>
          <span className="font-mono font-extrabold text-emerald-600 dark:text-emerald-400 text-sm">
            ₹{periodSummary.totalCredit.toLocaleString('en-IN', { minimumFractionDigits: 2 })} Cr
          </span>
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
            Closing Balance ({endDate ? endDate.split('-').reverse().join('/') : 'End'})
          </span>
          <span className="font-mono font-black text-foreground text-sm">
            ₹{periodSummary.clBal.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {periodSummary.clType}
          </span>
        </div>
      </div>

      {/* ─── QUICK FILTER PILLS & ACTION BUTTONS STRIP ─── */}
      <div className="bg-card border border-border rounded-2xl p-3 shadow-sm space-y-3 no-print">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          {/* Quick Filter Pills (All / Sales / Purchase / Receipt / Payment) */}
          <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mr-1 hidden md:inline-flex items-center gap-1">
              <Filter className="w-3 h-3" /> Filter:
            </span>

            {/* All */}
            <button
              type="button"
              onClick={() => {
                setFilterVoucherType('all')
                setCurrentPage(1)
              }}
              className={cn(
                'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer flex items-center gap-1.5',
                filterVoucherType === 'all'
                  ? 'bg-foreground text-background shadow-sm'
                  : 'bg-muted/70 hover:bg-muted text-muted-foreground hover:text-foreground'
              )}
            >
              <span>All</span>
              <span className={cn(
                'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                filterVoucherType === 'all' ? 'bg-background/20 text-background' : 'bg-background text-muted-foreground'
              )}>
                {voucherCounts.all}
              </span>
            </button>

            {/* Sales */}
            <button
              type="button"
              onClick={() => {
                setFilterVoucherType('sales')
                setCurrentPage(1)
              }}
              className={cn(
                'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer flex items-center gap-1.5',
                filterVoucherType.toLowerCase() === 'sales'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-blue-50 dark:bg-blue-950/30 hover:bg-blue-100 text-blue-600 dark:text-blue-400 border border-blue-200/50 dark:border-blue-900/40'
              )}
            >
              <span>Sales</span>
              <span className={cn(
                'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                filterVoucherType.toLowerCase() === 'sales' ? 'bg-white/20 text-white' : 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
              )}>
                {voucherCounts.sales}
              </span>
            </button>

            {/* Receipt */}
            <button
              type="button"
              onClick={() => {
                setFilterVoucherType('receipt')
                setCurrentPage(1)
              }}
              className={cn(
                'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer flex items-center gap-1.5',
                filterVoucherType.toLowerCase() === 'receipt'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-emerald-50 dark:bg-emerald-950/30 hover:bg-emerald-100 text-emerald-600 dark:text-emerald-400 border border-emerald-200/50 dark:border-emerald-900/40'
              )}
            >
              <span>Receipt</span>
              <span className={cn(
                'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                filterVoucherType.toLowerCase() === 'receipt' ? 'bg-white/20 text-white' : 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300'
              )}>
                {voucherCounts.receipt}
              </span>
            </button>

            {/* Purchase */}
            <button
              type="button"
              onClick={() => {
                setFilterVoucherType('purchase')
                setCurrentPage(1)
              }}
              className={cn(
                'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer flex items-center gap-1.5',
                filterVoucherType.toLowerCase() === 'purchase'
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'bg-amber-50 dark:bg-amber-950/30 hover:bg-amber-100 text-amber-600 dark:text-amber-400 border border-amber-200/50 dark:border-amber-900/40'
              )}
            >
              <span>Purchase</span>
              <span className={cn(
                'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                filterVoucherType.toLowerCase() === 'purchase' ? 'bg-white/20 text-white' : 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300'
              )}>
                {voucherCounts.purchase}
              </span>
            </button>

            {/* Payment (if any) */}
            {voucherCounts.payment > 0 && (
              <button
                type="button"
                onClick={() => {
                  setFilterVoucherType('payment')
                  setCurrentPage(1)
                }}
                className={cn(
                  'px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer flex items-center gap-1.5',
                  filterVoucherType.toLowerCase() === 'payment'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'bg-purple-50 dark:bg-purple-950/30 hover:bg-purple-100 text-purple-600 dark:text-purple-400 border border-purple-200/50 dark:border-purple-900/40'
                )}
              >
                <span>Payment</span>
                <span className={cn(
                  'text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold',
                  filterVoucherType.toLowerCase() === 'payment' ? 'bg-white/20 text-white' : 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300'
                )}>
                  {voucherCounts.payment}
                </span>
              </button>
            )}
          </div>

          {/* Action Buttons: WhatsApp, PDF, CSV */}
          <div className="flex items-center gap-2 shrink-0">
            {/* WhatsApp Share Button */}
            <button
              type="button"
              onClick={() => setShowWhatsAppModal(true)}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#25D366] hover:bg-[#20ba59] text-white font-bold text-xs shadow-sm transition-all cursor-pointer active:scale-95"
              title="Share statement on WhatsApp"
            >
              <MessageCircle className="w-4 h-4 fill-white" />
              <span>WhatsApp</span>
            </button>

            {/* PDF Download Button & Options */}
            <div className="relative flex-1 sm:flex-none">
              <div className="inline-flex rounded-xl shadow-sm overflow-hidden w-full">
                <button
                  type="button"
                  onClick={() => handleDownloadPdf(filterVoucherType)}
                  className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs transition-colors cursor-pointer active:scale-95"
                  title={`Download PDF (${filterVoucherType === 'all' ? 'All' : toTitleCase(filterVoucherType)})`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>PDF</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowPdfMenu(!showPdfMenu)
                    setShowCsvMenu(false)
                  }}
                  className="px-1.5 bg-rose-700 hover:bg-rose-800 text-white transition-colors cursor-pointer border-l border-rose-800"
                  title="PDF export options"
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
              </div>

              {/* PDF Dropdown Menu */}
              {showPdfMenu && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-card border border-border rounded-xl shadow-lg z-30 py-1 text-xs font-sans">
                  <div className="px-3 py-1.5 font-bold text-[10px] text-muted-foreground uppercase tracking-wider border-b border-border/60">
                    Download PDF as:
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf(filterVoucherType)}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between cursor-pointer"
                  >
                    <span>Current Filter ({filterVoucherType})</span>
                    <span className="text-[10px] font-mono text-muted-foreground">{processedTransactions.length}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf('all')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between cursor-pointer"
                  >
                    <span>All Transactions</span>
                    <span className="text-[10px] font-mono text-muted-foreground">{voucherCounts.all}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf('sales')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-blue-600 dark:text-blue-400 cursor-pointer"
                  >
                    <span>Sales Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.sales}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf('receipt')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-emerald-600 dark:text-emerald-400 cursor-pointer"
                  >
                    <span>Receipt Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.receipt}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadPdf('purchase')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-amber-600 dark:text-amber-400 cursor-pointer"
                  >
                    <span>Purchase Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.purchase}</span>
                  </button>
                </div>
              )}
            </div>

            {/* CSV Download Button & Options */}
            <div className="relative flex-1 sm:flex-none">
              <div className="inline-flex rounded-xl shadow-sm overflow-hidden w-full">
                <button
                  type="button"
                  onClick={() => handleDownloadCsv(filterVoucherType)}
                  className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600 text-white font-bold text-xs transition-colors cursor-pointer active:scale-95"
                  title={`Download CSV (${filterVoucherType === 'all' ? 'All' : toTitleCase(filterVoucherType)})`}
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>CSV</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCsvMenu(!showCsvMenu)
                    setShowPdfMenu(false)
                  }}
                  className="px-1.5 bg-slate-900 hover:bg-black dark:bg-slate-800 dark:hover:bg-slate-900 text-white transition-colors cursor-pointer border-l border-slate-700"
                  title="CSV export options"
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
              </div>

              {/* CSV Dropdown Menu */}
              {showCsvMenu && (
                <div className="absolute right-0 top-full mt-1 w-48 bg-card border border-border rounded-xl shadow-lg z-30 py-1 text-xs font-sans">
                  <div className="px-3 py-1.5 font-bold text-[10px] text-muted-foreground uppercase tracking-wider border-b border-border/60">
                    Download CSV as:
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDownloadCsv(filterVoucherType)}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between cursor-pointer"
                  >
                    <span>Current Filter ({filterVoucherType})</span>
                    <span className="text-[10px] font-mono text-muted-foreground">{processedTransactions.length}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadCsv('all')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between cursor-pointer"
                  >
                    <span>All Transactions</span>
                    <span className="text-[10px] font-mono text-muted-foreground">{voucherCounts.all}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadCsv('sales')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-blue-600 dark:text-blue-400 cursor-pointer"
                  >
                    <span>Sales Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.sales}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadCsv('receipt')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-emerald-600 dark:text-emerald-400 cursor-pointer"
                  >
                    <span>Receipt Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.receipt}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadCsv('purchase')}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium flex items-center justify-between text-amber-600 dark:text-amber-400 cursor-pointer"
                  >
                    <span>Purchase Vouchers</span>
                    <span className="text-[10px] font-mono">{voucherCounts.purchase}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Filtered Result Context Bar (when a filter other than 'all' or active search is applied) */}
        {filterVoucherType !== 'all' && (
          <div className="flex items-center justify-between bg-muted/30 px-3 py-2 rounded-xl text-xs border border-border/50">
            <div className="flex items-center gap-2">
              <span className="font-bold uppercase tracking-wider text-[10px] text-muted-foreground">Showing:</span>
              <span className="font-bold text-foreground">
                {processedTransactions.length} {toTitleCase(filterVoucherType)} Vouchers
              </span>
            </div>
            <div className="font-mono text-xs font-bold text-foreground">
              {filteredTotals.debit > 0 && (
                <span className="text-rose-600 dark:text-rose-400 mr-2">
                  Total Dr: ₹{formatNumber(filteredTotals.debit)}
                </span>
              )}
              {filteredTotals.credit > 0 && (
                <span className="text-emerald-600 dark:text-emerald-400">
                  Total Cr: ₹{formatNumber(filteredTotals.credit)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Search & Advanced Filters Bar */}
      <div className="bg-muted/40 p-3 flex flex-wrap gap-x-4 gap-y-3 items-center border rounded-xl shadow-sm text-xs bg-card no-print">
        {/* Search Input */}
        <div className="flex-1 min-w-[200px] max-w-xs">
          <input
            type="text"
            placeholder="Search narration, ref, vch number..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setCurrentPage(1)
            }}
            className="w-full px-3 py-1.5 text-xs border border-border rounded-xl bg-background shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-shadow"
          />
        </div>

        {/* Date Inputs */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value)
              setCurrentPage(1)
            }}
            className="px-2.5 py-1 border border-border rounded-xl bg-background text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          />
          <span className="text-muted-foreground text-[10px] uppercase font-bold">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value)
              setCurrentPage(1)
            }}
            className="px-2.5 py-1 border border-border rounded-xl bg-background text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          />
        </div>

        {/* Voucher Type Dropdown Filter */}
        {uniqueVoucherTypes.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Type:</span>
            <select
              value={filterVoucherType}
              onChange={(e) => {
                setFilterVoucherType(e.target.value)
                setCurrentPage(1)
              }}
              className="bg-background border border-border rounded-xl px-2.5 py-1 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
            >
              <option value="all">All Vouchers ({transactions.length})</option>
              <option value="sales">Sales ({voucherCounts.sales})</option>
              <option value="receipt">Receipt ({voucherCounts.receipt})</option>
              <option value="purchase">Purchase ({voucherCounts.purchase})</option>
              {voucherCounts.payment > 0 && <option value="payment">Payment ({voucherCounts.payment})</option>}
              {uniqueVoucherTypes
                .filter(v => !['sales', 'receipt', 'purchase', 'payment'].includes(v.toLowerCase()))
                .map((v, idx) => (
                  <option key={idx} value={v}>{v}</option>
                ))}
            </select>
          </div>
        )}

        {/* Flow Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Flow:</span>
          <select
            value={filterFlow}
            onChange={(e) => {
              setFilterFlow(e.target.value)
              setCurrentPage(1)
            }}
            className="bg-background border border-border rounded-xl px-2.5 py-1 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="all">All Flows</option>
            <option value="debit">Debit Only (Dr)</option>
            <option value="credit">Credit Only (Cr)</option>
          </select>
        </div>

        {/* Sort Filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Sort By:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-background border border-border rounded-xl px-2.5 py-1 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer text-emerald-600 font-bold"
          >
            <option value="date-desc">Date (New-Old)</option>
            <option value="date-asc">Date (Old-New)</option>
            <option value="amount-desc">Amount (High-Low)</option>
            <option value="amount-asc">Amount (Low-High)</option>
          </select>
        </div>

        {/* Clear Filters Button */}
        {(searchQuery !== '' || startDate !== globalStart || endDate !== globalEnd || filterVoucherType !== 'all' || filterFlow !== 'all' || sortBy !== 'date-desc') && (
          <button
            type="button"
            onClick={() => {
              setSearchQuery('')
              setStartDate(globalStart || '2025-04-01')
              setEndDate(globalEnd || '2026-03-31')
              setFilterVoucherType('all')
              setFilterFlow('all')
              setSortBy('date-desc')
              setCurrentPage(1)
            }}
            className="text-[10px] text-rose-600 dark:text-rose-400 font-bold hover:underline ml-auto cursor-pointer"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Mobile Card List View (hidden on Desktop) */}
      <div className="block lg:hidden space-y-3">
        {paginatedTransactions.length > 0 ? paginatedTransactions.map((txn, index) => {
          const amt = parseFloat(txn.amount || '0')
          const isDebit = amt < 0
          const isCredit = amt > 0

          return (
            <div key={index} className="p-4 bg-card border border-border rounded-2xl shadow-sm flex flex-col gap-2.5 hover:border-emerald-500/30 transition-colors">
              {/* Header: Date, Voucher Type, Ref */}
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground font-semibold tabular-nums">
                  {txn.date
                    ? new Date(txn.date).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })
                    : 'N/A'}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className={cn(
                    "font-extrabold uppercase tracking-tight text-[9px] px-2 py-0.5 rounded",
                    txn.voucherType?.toLowerCase().includes('sale') ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' :
                    txn.voucherType?.toLowerCase().includes('receipt') ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
                    txn.voucherType?.toLowerCase().includes('purchase') ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
                    'bg-slate-500/10 text-slate-600 dark:text-slate-400'
                  )}>
                    {txn.voucherType}
                  </span>
                  <span className="text-muted-foreground font-medium text-[10px]">
                    #{txn.voucherNumber}
                  </span>
                </div>
                <div>
                  <Link
                    href={`/vouchers/${txn.id}`}
                    className="text-blue-600 dark:text-blue-400 hover:underline font-bold text-xs font-sans"
                  >
                    {txn.referenceNumber || `Vch: ${txn.voucherNumber}`}
                  </Link>
                </div>
              </div>

              {/* Amount Display */}
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">Amount:</span>
                <div className={cn(
                  'text-xs font-black font-mono px-2.5 py-1 rounded border',
                  isDebit
                    ? 'bg-rose-50 dark:bg-rose-950/20 text-rose-800 dark:text-rose-400 border-rose-200/50'
                    : isCredit
                      ? 'bg-emerald-50 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400 border-emerald-200/50'
                      : 'bg-muted text-muted-foreground border-border'
                )}>
                  ₹{formatNumber(Math.abs(amt))}
                  {isDebit ? ' Dr' : isCredit ? ' Cr' : ''}
                </div>
              </div>

              {/* Narration */}
              {txn.narration && (
                <div className="mt-1 pt-1.5 border-t border-border/40 text-[10px] text-muted-foreground leading-relaxed italic">
                  <span className="font-semibold uppercase tracking-wider text-[8px] opacity-75 not-italic">Narration:</span>{' '}
                  {txn.narration}
                </div>
              )}
            </div>
          )
        }) : (
          <div className="p-8 text-center text-muted-foreground italic border rounded-2xl bg-card/30">
            No transactions found with current filters
          </div>
        )}

        {/* Mobile Pagination */}
        {processedTransactions.length > pageSize && (
          <div className="flex items-center justify-between gap-4 pt-2">
            <button
              type="button"
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className="px-3 py-1.5 border rounded-xl text-xs font-semibold bg-card disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
            >
              Previous
            </button>
            <div className="text-xs text-muted-foreground font-semibold">
              Page {currentPage} of {totalPages || 1}
            </div>
            <button
              type="button"
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage === totalPages || totalPages === 0}
              className="px-3 py-1.5 border rounded-xl text-xs font-semibold bg-card disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Desktop Table View (hidden on Mobile) */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full border-t border-foreground text-sm font-mono">
          <thead>
            <tr className="border-b border-foreground text-left bg-muted/50">
              <th className="py-2.5 px-2">Date</th>
              <th className="py-2.5 px-2">Voucher Details</th>
              <th className="py-2.5 px-2">Ref / Invoice</th>
              <th className="py-2.5 px-2">Narration</th>
              <th className="py-2.5 text-right px-2">Debit (Dr)</th>
              <th className="py-2.5 text-right px-2">Credit (Cr)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {processedTransactions.map((txn, idx) => {
              const amt = parseFloat(txn.amount || '0')
              const isDebit = amt < 0
              const isCredit = amt > 0

              return (
                <tr key={idx} className="hover:bg-muted/30 transition-colors align-top">
                  <td className="py-2.5 px-2 font-mono tabular-nums">
                    {txn.date
                      ? new Date(txn.date).toLocaleDateString('en-IN', {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                      })
                      : 'N/A'}
                  </td>
                  <td className="py-2.5 px-2">
                    <span className={cn(
                      "not-italic font-bold uppercase text-xs",
                      txn.voucherType?.toLowerCase().includes('sale') ? 'text-blue-600 dark:text-blue-400' :
                      txn.voucherType?.toLowerCase().includes('receipt') ? 'text-emerald-600 dark:text-emerald-400' :
                      txn.voucherType?.toLowerCase().includes('purchase') ? 'text-amber-600 dark:text-amber-400' :
                      'text-muted-foreground'
                    )}>
                      {txn.voucherType}
                    </span>
                    <div className="text-[10px] text-muted-foreground font-medium mt-0.5">
                      #{txn.voucherNumber}
                    </div>
                  </td>
                  <td className="py-2.5 px-2">
                    <Link
                      href={`/vouchers/${txn.id}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline font-bold text-xs font-sans"
                    >
                      {txn.referenceNumber || `Vch: ${txn.voucherNumber}`}
                    </Link>
                  </td>
                  <td className="py-2.5 px-2 text-muted-foreground italic text-xs leading-relaxed max-w-xs break-words">
                    {txn.narration || '-'}
                  </td>
                  <td className="py-2.5 text-right px-2 font-mono font-bold text-rose-600 dark:text-rose-455 tabular-nums">
                    {isDebit ? formatNumber(Math.abs(amt)) : ''}
                  </td>
                  <td className="py-2.5 text-right px-2 font-mono font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                    {isCredit ? formatNumber(Math.abs(amt)) : ''}
                  </td>
                </tr>
              )
            })}
            {processedTransactions.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-muted-foreground italic">
                  No transactions found with current filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ─── WHATSAPP STATEMENT SHARING MODAL ─── */}
      {showWhatsAppModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-5 sm:p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-2xl bg-[#25D366]/15 flex items-center justify-center text-[#25D366]">
                  <MessageCircle className="w-5 h-5 fill-[#25D366]" />
                </div>
                <div>
                  <h3 className="font-extrabold text-foreground text-base">Share Statement on WhatsApp</h3>
                  <p className="text-xs text-muted-foreground">
                    Send detailed account statement directly to the customer
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowWhatsAppModal(false)}
                className="p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="space-y-4 overflow-y-auto pr-1 flex-1">
              {/* Recipient Phone Number */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-emerald-600" />
                  Recipient WhatsApp Number:
                </label>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-2 bg-muted/60 border border-border rounded-xl text-xs font-mono font-bold text-muted-foreground">
                    +91
                  </span>
                  <input
                    type="tel"
                    value={whatsAppPhone}
                    onChange={(e) => setWhatsAppPhone(e.target.value)}
                    placeholder="Enter 10-digit mobile number"
                    className="flex-1 px-3 py-2 bg-background border border-border rounded-xl text-xs font-mono font-medium focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-sm"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground italic">
                  Leave empty to let WhatsApp pick any contact or chat from your list.
                </p>
              </div>

              {/* Filter Selection for WhatsApp Statement */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Select Filter to Include:
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => setWhatsAppFilter('current')}
                    className={cn(
                      'p-2 rounded-xl border text-center font-bold transition-all cursor-pointer',
                      whatsAppFilter === 'current'
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
                        : 'border-border bg-background hover:bg-muted text-muted-foreground'
                    )}
                  >
                    <span className="block truncate">Current View</span>
                    <span className="text-[10px] opacity-75 font-mono">({processedTransactions.length})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setWhatsAppFilter('all')}
                    className={cn(
                      'p-2 rounded-xl border text-center font-bold transition-all cursor-pointer',
                      whatsAppFilter === 'all'
                        ? 'border-foreground bg-foreground text-background'
                        : 'border-border bg-background hover:bg-muted text-muted-foreground'
                    )}
                  >
                    <span className="block truncate">All Vouchers</span>
                    <span className="text-[10px] opacity-75 font-mono">({voucherCounts.all})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setWhatsAppFilter('sales')}
                    className={cn(
                      'p-2 rounded-xl border text-center font-bold transition-all cursor-pointer',
                      whatsAppFilter === 'sales'
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'
                        : 'border-border bg-background hover:bg-muted text-muted-foreground'
                    )}
                  >
                    <span className="block truncate">Sales Only</span>
                    <span className="text-[10px] opacity-75 font-mono">({voucherCounts.sales})</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setWhatsAppFilter('receipt')}
                    className={cn(
                      'p-2 rounded-xl border text-center font-bold transition-all cursor-pointer',
                      whatsAppFilter === 'receipt'
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
                        : 'border-border bg-background hover:bg-muted text-muted-foreground'
                    )}
                  >
                    <span className="block truncate">Receipts Only</span>
                    <span className="text-[10px] opacity-75 font-mono">({voucherCounts.receipt})</span>
                  </button>
                </div>
              </div>

              {/* Message Live Preview */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Message Preview:
                  </label>
                  <button
                    type="button"
                    onClick={handleCopyWhatsAppMessage}
                    className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold hover:underline cursor-pointer"
                  >
                    {copiedMessage ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedMessage ? 'Copied!' : 'Copy Text'}</span>
                  </button>
                </div>
                <div className="p-3 bg-muted/40 border border-border rounded-2xl font-mono text-[11px] text-foreground leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto shadow-inner">
                  {currentWhatsAppMessage}
                </div>
              </div>
            </div>

            {/* Modal Footer Actions */}
            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border shrink-0">
              <button
                type="button"
                onClick={() => setShowWhatsAppModal(false)}
                className="px-4 py-2 rounded-xl border border-border text-muted-foreground hover:text-foreground font-semibold text-xs transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSendWhatsApp}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#25D366] hover:bg-[#20ba59] text-white font-bold text-xs shadow-md transition-all cursor-pointer active:scale-95"
              >
                <MessageCircle className="w-4 h-4 fill-white" />
                <span>Open in WhatsApp</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
