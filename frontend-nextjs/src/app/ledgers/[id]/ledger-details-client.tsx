'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { cn, toTitleCase } from '@/lib/utils'

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
}

export default function LedgerDetailsClient({ ledgerInfo, transactions }: Props) {
  const defaultDates = useMemo(() => {
    const today = new Date()
    const currentMonth = today.getMonth() // 0-indexed: 3 = April
    const currentYear = today.getFullYear()
    const fyStartYear = currentMonth >= 3 ? currentYear : currentYear - 1
    return {
      start: `${fyStartYear}-04-01`,
      end: `${fyStartYear + 1}-03-31`
    }
  }, [])

  const [searchQuery, setSearchQuery] = useState('')
  const [startDate, setStartDate] = useState(defaultDates.start)
  const [endDate, setEndDate] = useState(defaultDates.end)
  const [filterVoucherType, setFilterVoucherType] = useState('all')
  const [filterFlow, setFilterFlow] = useState('all') // all | debit | credit
  const [sortBy, setSortBy] = useState('date-desc') // date-desc | date-asc | amount-desc | amount-asc
  
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 10

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
      result = result.filter(t => t.voucherType?.toLowerCase() === filterVoucherType.toLowerCase())
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

  return (
    <div className="space-y-4 max-w-5xl mx-auto">
      {/* Search & Filters Bar */}
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

        {/* Voucher Type Filter */}
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
              <option value="all">All Vouchers</option>
              {uniqueVoucherTypes.map((v, idx) => (
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
        {(searchQuery !== '' || startDate !== defaultDates.start || endDate !== defaultDates.end || filterVoucherType !== 'all' || filterFlow !== 'all' || sortBy !== 'date-desc') && (
          <button
            onClick={() => {
              setSearchQuery('')
              setStartDate(defaultDates.start)
              setEndDate(defaultDates.end)
              setFilterVoucherType('all')
              setFilterFlow('all')
              setSortBy('date-desc')
              setCurrentPage(1)
            }}
            className="text-[10px] text-rose-600 dark:text-rose-400 font-bold hover:underline ml-auto"
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
                  <span className="font-extrabold text-emerald-600 dark:text-emerald-400 uppercase tracking-tight text-[9px] bg-emerald-500/10 px-2 py-0.5 rounded">
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
          <div className="p-8 text-center text-muted-foreground italic border rounded-2xl bg-card/30">No transactions found with current filters</div>
        )}

        {/* Mobile Pagination */}
        {processedTransactions.length > pageSize && (
          <div className="flex items-center justify-between gap-4 pt-2">
            <button
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
                    <span className="text-emerald-600 dark:text-emerald-400 not-italic font-bold uppercase text-xs">
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
    </div>
  )
}
