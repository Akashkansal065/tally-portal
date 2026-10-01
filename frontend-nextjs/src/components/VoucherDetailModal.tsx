'use client'

import React, { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import {
  X,
  ExternalLink,
  Receipt,
  FileText,
  Landmark,
  Calendar,
  Building2,
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Check,
  Tag,
  ArrowDownLeft,
  ArrowUpRight
} from 'lucide-react'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase, cn } from '@/lib/utils'

export interface BankTxContext {
  transaction_id: number
  transaction_date: string
  transaction_type: 'DEBIT' | 'CREDIT'
  amount: number
  description: string
  reference_no?: string
  cheque_no?: string
  match_notes?: string
}

interface Props {
  isOpen: boolean
  voucherId: number | null
  token: string | null
  onClose: () => void
  bankTx?: BankTxContext | null
  onApproveMatch?: (transactionId: number, voucherId: number) => Promise<void> | void
  isApproving?: boolean
}

export default function VoucherDetailModal({
  isOpen,
  voucherId,
  token,
  onClose,
  bankTx,
  onApproveMatch,
  isApproving = false
}: Props) {
  const [voucher, setVoucher] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchVoucherDetail = useCallback(async (id: number) => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}`, {
        headers: authHeaders(token),
        cache: 'no-store'
      })
      if (!res.ok) {
        throw new Error(`Failed to load voucher details (Status: ${res.status})`)
      }
      const data = await res.json()
      setVoucher(data)
    } catch (err: any) {
      console.error('[VoucherDetailModal] Error loading voucher:', err)
      setError(err.message || 'Unable to retrieve voucher information.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (isOpen && voucherId) {
      fetchVoucherDetail(voucherId)
    } else {
      setVoucher(null)
      setError(null)
    }
  }, [isOpen, voucherId, fetchVoucherDetail])

  // Handle Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const isReceipt = (voucher?.voucher_type || '').toLowerCase().includes('receipt')
  const isPayment = (voucher?.voucher_type || '').toLowerCase().includes('payment')

  const rawEntries = voucher?.entries || voucher?.accounts || []
  const totalDebit = rawEntries.reduce(
    (sum: number, e: any) => sum + (Number(e.debit_amount || 0) || (e.entry_type === 'Debit' ? Math.abs(Number(e.amount || 0)) : 0)),
    0
  )
  const totalCredit = rawEntries.reduce(
    (sum: number, e: any) => sum + (Number(e.credit_amount || 0) || (e.entry_type === 'Credit' ? Math.abs(Number(e.amount || 0)) : 0)),
    0
  )
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-t-[28px] sm:rounded-3xl max-w-3xl w-full shadow-2xl overflow-hidden animate-in slide-in-from-bottom-6 sm:zoom-in-95 duration-200 flex flex-col max-h-[94vh] sm:max-h-[88vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mobile Pull Handle Indicator */}
        <div className="w-12 h-1.5 bg-muted-foreground/25 rounded-full mx-auto mt-2.5 mb-0.5 sm:hidden shrink-0" />

        {/* Modal Header */}
        <div className="px-4 py-3 sm:px-6 sm:py-4 border-b border-border/80 flex items-center justify-between gap-3 bg-muted/30 shrink-0">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <div className={cn(
              "w-9 h-9 sm:w-10 sm:h-10 rounded-xl sm:rounded-2xl flex items-center justify-center shrink-0 border shadow-2xs",
              isReceipt
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                : isPayment
                ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                : "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20"
            )}>
              {isReceipt ? (
                <Receipt className="h-4.5 w-4.5 sm:h-5 sm:w-5" />
              ) : isPayment ? (
                <CreditCard className="h-4.5 w-4.5 sm:h-5 sm:w-5" />
              ) : (
                <FileText className="h-4.5 w-4.5 sm:h-5 sm:w-5" />
              )}
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                <span className={cn(
                  "text-[10px] sm:text-[11px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border",
                  isReceipt
                    ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30"
                    : isPayment
                    ? "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30"
                    : "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30"
                )}>
                  {voucher?.voucher_type || 'Voucher'} #{voucher?.voucher_number || voucherId}
                </span>

                {voucher?.date && (
                  <span className="text-[11px] sm:text-xs font-semibold text-muted-foreground flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {formatDate(voucher.date)}
                  </span>
                )}

                {voucher?.is_cancelled && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-600 border border-rose-500/20">
                    CANCELLED
                  </span>
                )}
                {voucher?.bank_reconciliation && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 flex items-center gap-1">
                    <Landmark className="h-3 w-3" /> Cleared
                  </span>
                )}
              </div>
              <h2 className="text-sm sm:text-base md:text-lg font-black text-foreground truncate mt-0.5">
                {voucher?.party_name ? toTitleCase(voucher.party_name) : (loading ? 'Loading Voucher...' : 'Voucher Details')}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {voucherId && (
              <Link
                href={`/vouchers/${voucherId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border hover:bg-muted text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
                title="Open in standalone page"
              >
                <span>Full View</span>
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
            <button
              onClick={onClose}
              className="p-1.5 sm:p-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
              title="Close (Esc)"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-3.5 sm:p-6 overflow-y-auto space-y-3.5 sm:space-y-5 flex-1">
          {loading && (
            <div className="py-14 sm:py-16 flex flex-col items-center justify-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-xs font-medium text-muted-foreground">Fetching complete voucher records...</p>
            </div>
          )}

          {error && !loading && (
            <div className="p-4 rounded-2xl bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-start gap-3">
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Error loading voucher</p>
                <p className="text-xs mt-1 text-destructive/80">{error}</p>
                <button
                  onClick={() => voucherId && fetchVoucherDetail(voucherId)}
                  className="mt-3 px-3 py-1 bg-destructive text-white rounded-lg text-xs font-bold cursor-pointer"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {voucher && !loading && (
            <>
              {/* Bank Reconciliation Candidate Match Comparison Banner */}
              {bankTx && (
                <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border border-amber-500/30 rounded-2xl p-3 sm:p-4 space-y-2.5 sm:space-y-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4 text-amber-500 shrink-0" />
                      <span className="text-[11px] sm:text-xs font-black text-amber-800 dark:text-amber-300 uppercase tracking-wider">
                        Reconciliation Candidate Match
                      </span>
                    </div>
                    {bankTx.match_notes && (
                      <span className="text-[10px] sm:text-[11px] font-bold text-amber-700 dark:text-amber-300 bg-amber-500/20 px-2.5 py-0.5 rounded-full border border-amber-500/30">
                        {bankTx.match_notes}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 sm:gap-3 text-xs">
                    {/* Bank Side */}
                    <div className="bg-card/90 border border-border/80 rounded-xl p-2.5 sm:p-3 space-y-1.5 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                          <Landmark className="h-3 w-3 text-blue-500" /> Bank Statement
                        </span>
                        <span className="font-mono text-[11px] font-bold text-foreground">
                          {formatDate(bankTx.transaction_date)}
                        </span>
                      </div>
                      <div className="flex items-baseline justify-between">
                        <span className={cn(
                          "text-[10px] sm:text-xs font-black uppercase px-1.5 py-0.5 rounded",
                          bankTx.transaction_type === 'CREDIT' ? "bg-emerald-500/15 text-emerald-600" : "bg-rose-500/15 text-rose-600"
                        )}>
                          {bankTx.transaction_type}
                        </span>
                        <span className="text-sm sm:text-base font-black text-foreground font-mono">
                          {formatCurrency(bankTx.amount)}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground break-words break-all line-clamp-2" title={bankTx.description}>
                        {bankTx.description}
                      </p>
                      {bankTx.reference_no && (
                        <p className="text-[10px] text-muted-foreground font-mono">
                          Ref/UTR: <span className="text-foreground font-semibold">{bankTx.reference_no}</span>
                        </p>
                      )}
                    </div>

                    {/* Book Side */}
                    <div className="bg-card/90 border border-border/80 rounded-xl p-2.5 sm:p-3 space-y-1.5 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                          <Receipt className="h-3 w-3 text-purple-500" /> Book Voucher
                        </span>
                        <span className="font-mono text-[11px] font-bold text-foreground">
                          {formatDate(voucher.date)}
                        </span>
                      </div>
                      <div className="flex items-baseline justify-between">
                        <span className="text-[10px] sm:text-xs font-black uppercase px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-600">
                          {voucher.voucher_type} #{voucher.voucher_number}
                        </span>
                        <span className="text-sm sm:text-base font-black text-foreground font-mono">
                          {formatCurrency(voucher.total_amount || voucher.amount)}
                        </span>
                      </div>
                      <p className="text-[11px] font-semibold text-foreground truncate">
                        {toTitleCase(voucher.party_name)}
                      </p>
                      {voucher.narration ? (
                        <p className="text-[10px] text-muted-foreground break-words line-clamp-1">
                          {voucher.narration}
                        </p>
                      ) : (
                        <p className="text-[10px] text-muted-foreground italic">No narration recorded</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Key Overview Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
                <div className="bg-muted/40 border border-border/60 rounded-2xl p-2.5 sm:p-3.5 space-y-0.5 sm:space-y-1">
                  <span className="text-[10px] sm:text-[11px] font-semibold text-muted-foreground block">Voucher Amount</span>
                  <span className="text-base sm:text-xl font-black text-foreground font-mono tabular-nums block">
                    {formatCurrency(voucher.total_amount || voucher.amount)}
                  </span>
                  <span className="text-[9px] sm:text-[10px] text-muted-foreground font-medium block">
                    {isReceipt ? 'Total Received' : isPayment ? 'Total Paid' : 'Total Value'}
                  </span>
                </div>

                <div className="bg-muted/40 border border-border/60 rounded-2xl p-2.5 sm:p-3.5 space-y-0.5 sm:space-y-1">
                  <span className="text-[10px] sm:text-[11px] font-semibold text-muted-foreground block">Voucher Date</span>
                  <span className="text-xs sm:text-base font-bold text-foreground block">
                    {formatDate(voucher.date)}
                  </span>
                  <span className="text-[9px] sm:text-[10px] text-muted-foreground font-mono block">
                    No. {voucher.voucher_number}
                  </span>
                </div>

                <div className="bg-muted/40 border border-border/60 rounded-2xl p-2.5 sm:p-3.5 space-y-0.5 sm:space-y-1 col-span-2 sm:col-span-2">
                  <span className="text-[10px] sm:text-[11px] font-semibold text-muted-foreground block">Party / Account</span>
                  <div className="flex items-center gap-1.5">
                    {voucher.party_ledger_id ? (
                      <Link
                        href={`/ledgers/${voucher.party_ledger_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs sm:text-sm font-extrabold text-foreground hover:text-primary hover:underline truncate inline-flex items-center gap-1"
                        title="Open party ledger"
                      >
                        <span className="truncate">{toTitleCase(voucher.party_name)}</span>
                        <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
                      </Link>
                    ) : (
                      <span className="text-xs sm:text-sm font-extrabold text-foreground truncate">
                        {toTitleCase(voucher.party_name)}
                      </span>
                    )}
                  </div>
                  {voucher.party_ledger?.gstn ? (
                    <span className="text-[9px] sm:text-[10px] font-mono text-muted-foreground block truncate">
                      GSTIN: <span className="text-foreground font-semibold">{voucher.party_ledger.gstn}</span>
                    </span>
                  ) : (
                    <span className="text-[9px] sm:text-[10px] text-muted-foreground block">
                      Status: <span className="text-emerald-600 font-semibold">{voucher.status || 'Active'}</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Reference & Narration Card (If present) */}
              {(voucher.narration || voucher.reference_number) && (
                <div className="p-2.5 sm:p-3.5 rounded-2xl bg-muted/20 border border-border/60 space-y-1 text-xs">
                  {voucher.reference_number && (
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground font-semibold text-[11px]">Ref / Chq No:</span>
                      <span className="font-mono font-bold text-foreground bg-muted px-2 py-0.5 rounded border border-border text-[11px]">
                        {voucher.reference_number}
                      </span>
                    </div>
                  )}
                  {voucher.narration && (
                    <div>
                      <span className="text-muted-foreground font-semibold block mb-0.5 text-[11px]">Narration:</span>
                      <p className="text-foreground leading-relaxed italic bg-card/60 p-2 rounded-xl border border-border/40 text-[11px]">
                        &quot;{voucher.narration}&quot;
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Double-Entry Accounting Allocations */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-[11px] sm:text-xs font-black uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5 text-primary" />
                    Double-Entry Accounting Allocations
                  </h3>
                  <span className="text-[10px] sm:text-[11px] text-muted-foreground font-medium">
                    {rawEntries.length} ledgers
                  </span>
                </div>

                {/* MOBILE VIEW (< 640px): Card breakdown with full horizontal readability */}
                <div className="sm:hidden space-y-2">
                  {rawEntries.map((entry: any, idx: number) => {
                    const isDebit = entry.entry_type === 'Debit' || (Number(entry.debit_amount || 0) > 0)
                    const debitAmt = entry.debit_amount !== undefined
                      ? Number(entry.debit_amount)
                      : (isDebit ? Math.abs(Number(entry.amount || 0)) : 0)
                    const creditAmt = entry.credit_amount !== undefined
                      ? Number(entry.credit_amount)
                      : (!isDebit ? Math.abs(Number(entry.amount || 0)) : 0)
                    const displayAmt = isDebit ? debitAmt : creditAmt

                    return (
                      <div
                        key={entry.entry_id || idx}
                        className="p-3 rounded-2xl border border-border/80 bg-muted/20 flex items-center justify-between gap-3 shadow-2xs"
                      >
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex items-center gap-1.5">
                            <span className={cn(
                              "text-[9px] font-black px-1.5 py-0.5 rounded border inline-flex items-center gap-0.5 shrink-0",
                              isDebit
                                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                                : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                            )}>
                              {isDebit ? <ArrowDownLeft className="h-2.5 w-2.5" /> : <ArrowUpRight className="h-2.5 w-2.5" />}
                              {isDebit ? 'DR' : 'CR'}
                            </span>
                            {entry.ledger_id ? (
                              <Link
                                href={`/ledgers/${entry.ledger_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs font-bold text-foreground hover:text-primary hover:underline truncate inline-flex items-center gap-1"
                              >
                                <span className="truncate">{entry.ledger_name || entry.ledger || 'General Ledger'}</span>
                                <ExternalLink className="h-2.5 w-2.5 opacity-50 shrink-0" />
                              </Link>
                            ) : (
                              <span className="text-xs font-bold text-foreground truncate">
                                {entry.ledger_name || entry.ledger || 'General Ledger'}
                              </span>
                            )}
                          </div>

                          {entry.bank_allocations && entry.bank_allocations.length > 0 && (
                            <div className="text-[10px] text-muted-foreground font-mono space-y-0.5">
                              {entry.bank_allocations.map((ba: any, bi: number) => (
                                <div key={bi} className="bg-muted/70 px-1.5 py-0.2 rounded inline-block truncate max-w-full">
                                  Instr: {ba.instrument_number || '—'} {ba.bank_name ? `• ${ba.bank_name}` : ''}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="text-right shrink-0">
                          <span className={cn(
                            "text-sm font-black font-mono block tabular-nums",
                            isDebit ? "text-blue-600 dark:text-blue-400" : "text-emerald-600 dark:text-emerald-400"
                          )}>
                            {formatCurrency(displayAmt)}
                          </span>
                          <span className="text-[9px] uppercase font-bold text-muted-foreground">
                            {isDebit ? 'Debit' : 'Credit'}
                          </span>
                        </div>
                      </div>
                    )
                  })}

                  {/* Mobile Total Balancing Summary Footer */}
                  <div className="p-3 rounded-2xl bg-muted/40 border border-border/80 flex items-center justify-between text-xs">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground">
                      Total Balance
                    </span>
                    <div className="flex items-center gap-2.5 font-mono font-black text-xs">
                      <span className="text-blue-600 dark:text-blue-400">Dr {formatCurrency(totalDebit)}</span>
                      <span className="text-emerald-600 dark:text-emerald-400">Cr {formatCurrency(totalCredit)}</span>
                      {isBalanced && (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0 ml-0.5" />
                      )}
                    </div>
                  </div>
                </div>

                {/* TABLET / DESKTOP VIEW (>= 640px): Standard 4-column balanced table */}
                <div className="hidden sm:block border border-border/80 rounded-2xl overflow-x-auto shadow-2xs">
                  <table className="w-full text-xs text-left min-w-[500px]">
                    <thead className="bg-muted/60 border-b border-border/80 text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                      <tr>
                        <th className="px-3.5 py-2.5 w-16">Type</th>
                        <th className="px-3.5 py-2.5">Ledger Name</th>
                        <th className="px-3.5 py-2.5 text-right w-32">Debit (Dr)</th>
                        <th className="px-3.5 py-2.5 text-right w-32">Credit (Cr)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50 bg-card">
                      {rawEntries.map((entry: any, idx: number) => {
                        const isDebit = entry.entry_type === 'Debit' || (Number(entry.debit_amount || 0) > 0)
                        const debitAmt = entry.debit_amount !== undefined
                          ? Number(entry.debit_amount)
                          : (isDebit ? Math.abs(Number(entry.amount || 0)) : 0)
                        const creditAmt = entry.credit_amount !== undefined
                          ? Number(entry.credit_amount)
                          : (!isDebit ? Math.abs(Number(entry.amount || 0)) : 0)

                        return (
                          <tr key={entry.entry_id || idx} className="hover:bg-muted/30 transition-colors">
                            <td className="px-3.5 py-2.5 whitespace-nowrap">
                              <span className={cn(
                                "text-[10px] font-extrabold px-2 py-0.5 rounded border inline-flex items-center gap-1",
                                isDebit
                                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
                                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                              )}>
                                {isDebit ? <ArrowDownLeft className="h-2.5 w-2.5" /> : <ArrowUpRight className="h-2.5 w-2.5" />}
                                {isDebit ? 'DR' : 'CR'}
                              </span>
                            </td>
                            <td className="px-3.5 py-2.5 font-semibold text-foreground">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {entry.ledger_id ? (
                                  <Link
                                    href={`/ledgers/${entry.ledger_id}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:text-primary hover:underline transition-colors inline-flex items-center gap-1"
                                  >
                                    <span>{entry.ledger_name || entry.ledger || 'General Ledger'}</span>
                                    <ExternalLink className="h-2.5 w-2.5 opacity-50" />
                                  </Link>
                                ) : (
                                  <span>{entry.ledger_name || entry.ledger || 'General Ledger'}</span>
                                )}
                              </div>
                              {entry.bank_allocations && entry.bank_allocations.length > 0 && (
                                <div className="mt-1 text-[10px] text-muted-foreground space-y-0.5">
                                  {entry.bank_allocations.map((ba: any, bi: number) => (
                                    <div key={bi} className="font-mono bg-muted/60 px-2 py-0.5 rounded inline-block">
                                      Instr: {ba.instrument_number || '—'} • Date: {ba.instrument_date || '—'} {ba.bank_name ? `• ${ba.bank_name}` : ''}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-bold text-foreground tabular-nums whitespace-nowrap">
                              {debitAmt > 0 ? formatCurrency(debitAmt) : '—'}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-bold text-foreground tabular-nums whitespace-nowrap">
                              {creditAmt > 0 ? formatCurrency(creditAmt) : '—'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                    <tfoot className="bg-muted/40 border-t border-border/80 font-mono font-black text-foreground">
                      <tr>
                        <td colSpan={2} className="px-3.5 py-2.5 text-right uppercase text-[10px] tracking-wider text-muted-foreground">
                          Total Balancing
                        </td>
                        <td className="px-3.5 py-2.5 text-right text-xs text-blue-600 dark:text-blue-400 tabular-nums">
                          {formatCurrency(totalDebit)}
                        </td>
                        <td className="px-3.5 py-2.5 text-right text-xs text-emerald-600 dark:text-emerald-400 tabular-nums">
                          {formatCurrency(totalCredit)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              {/* Inventory details if voucher has stock entries */}
              {voucher.inventory && voucher.inventory.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-[11px] sm:text-xs font-black uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5 text-primary" />
                    Inventory Line Items ({voucher.inventory.length})
                  </h3>

                  {/* Mobile inventory card view */}
                  <div className="sm:hidden space-y-2">
                    {voucher.inventory.map((item: any, idx: number) => (
                      <div key={idx} className="p-3 rounded-2xl border border-border/80 bg-muted/20 flex items-center justify-between gap-3 shadow-2xs">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-foreground truncate">{item.stock_item_name || item.item}</p>
                          <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                            {item.quantity} {item.uom || ''} @ ₹{Number(item.rate || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </p>
                        </div>
                        <div className="text-right shrink-0 font-mono font-black text-xs text-foreground">
                          {formatCurrency(item.amount)}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Desktop inventory table */}
                  <div className="hidden sm:block border border-border/80 rounded-2xl overflow-x-auto shadow-2xs">
                    <table className="w-full text-xs text-left min-w-[450px]">
                      <thead className="bg-muted/60 border-b border-border/80 text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                        <tr>
                          <th className="px-3.5 py-2.5">Item Name</th>
                          <th className="px-3.5 py-2.5 text-right">Qty</th>
                          <th className="px-3.5 py-2.5 text-right">Rate</th>
                          <th className="px-3.5 py-2.5 text-right">Amount</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50 bg-card">
                        {voucher.inventory.map((item: any, idx: number) => (
                          <tr key={idx} className="hover:bg-muted/30 transition-colors">
                            <td className="px-3.5 py-2.5 font-semibold text-foreground">
                              {item.stock_item_name || item.item}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono text-muted-foreground">
                              {item.quantity} {item.uom || ''}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono text-muted-foreground">
                              ₹{Number(item.rate || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-3.5 py-2.5 text-right font-mono font-bold text-foreground">
                              {formatCurrency(item.amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Sticky Footer Actions */}
        <div className="px-4 py-3 sm:px-6 sm:py-4 border-t border-border/80 bg-muted/20 flex items-center justify-between gap-2.5 sm:gap-3 shrink-0 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 sm:px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-bold text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            Close
          </button>

          <div className="flex items-center gap-2">
            {voucherId && (
              <Link
                href={`/vouchers/${voucherId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="sm:hidden px-3 py-2 rounded-xl border border-border text-xs font-semibold text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
              >
                <span>Full Page</span>
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}

            {/* Direct Approve Match Action when matching a candidate in Bank Recon */}
            {bankTx && onApproveMatch && (
              <button
                type="button"
                onClick={async () => {
                  if (voucherId) {
                    await onApproveMatch(bankTx.transaction_id, voucherId)
                    onClose()
                  }
                }}
                disabled={isApproving}
                className="px-4 sm:px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
              >
                {isApproving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4 stroke-[3]" />
                )}
                <span>Approve Match</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
