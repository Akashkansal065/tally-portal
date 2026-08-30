'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, toTitleCase } from '@/lib/utils'
import { ArrowLeft, Loader2, Download, ShieldCheck, FileSpreadsheet, AlertCircle, Edit3, Trash2, QrCode, ExternalLink, Copy, CheckCircle2, Zap, X } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import VoucherDetailsClient from './voucher-details-client'
import VoucherFormModal from '@/components/VoucherFormModal'
import { generateVoucherPdf } from '@/lib/pdf-generator'

type VoucherEntry = {
  ledger_name: string
  ledger_id?: number
  amount: number
  debit_amount?: number
  credit_amount?: number
  entry_type: 'Debit' | 'Credit'
  cost_center_id?: number | null
  bank_allocations?: any[]
}

type VoucherDetail = {
  voucher_id: number
  date: string
  voucher_type: string
  voucher_type_id?: number
  voucher_number: string
  reference_number: string | null
  narration: string | null
  party_name: string
  party_ledger_id?: number
  amount: number
  total_amount: number
  status?: string
  original_voucher_id?: number | null
  entries: VoucherEntry[]
  accounts: any[]
  inventory: any[]
  inventory_entries?: any[]
  is_inventory_voucher: boolean
  party_ledger: any
  sync_status?: string
  tally_error_message?: string | null
  can_rollback?: boolean
  sync_id?: number | null
  einvoice_metadata?: {
    irn: string
    ack_no: string
    ack_date: string
    eway_bill_no: string | null
    eway_bill_date: string | null
  } | null
}

export default function VoucherDetailPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string

  const [voucher, setVoucher] = useState<VoucherDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [generatingEinvoice, setGeneratingEinvoice] = useState(false)

  // Rollback & Retry Sync States
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [isRetrying, setIsRetrying] = useState(false)
  const [isRollbackModalOpen, setIsRollbackModalOpen] = useState(false)

  // Tally Prime 7.0 Paylink & UPI States
  const [paylink, setPaylink] = useState<any>(null)
  const [generatingPaylink, setGeneratingPaylink] = useState(false)
  const [showPaylinkCard, setShowPaylinkCard] = useState(true)
  const [isQrModalOpen, setIsQrModalOpen] = useState(false)

  // Alter (Edit) & Delete States
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [ledgers, setLedgers] = useState<any[]>([])
  const [voucherTypes, setVoucherTypes] = useState<any[]>([])

  const fetchPaylink = useCallback(async () => {
    if (!id || !token) return
    try {
      const res = await fetch(`${API_BASE}/payments/${id}/paylink`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setPaylink(data)
      }
    } catch (err) {
      console.error(err)
    }
  }, [id, token])

  useEffect(() => {
    fetchPaylink()
  }, [fetchPaylink])

  const fetchVoucher = useCallback(() => {
    if (!id || !token) return
    setLoading(true)
    fetch(`${API_BASE}/vouchers/${id}`, { headers: authHeaders(token) })
      .then(r => {
        if (!r.ok) throw new Error('Not found')
        return r.json()
      })
      .then(data => setVoucher(data))
      .catch(() => setError('Voucher not found'))
      .finally(() => setLoading(false))
  }, [id, token])

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchVoucher()

    // Fetch ledgers & voucher types for edit modal
    if (token) {
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(d => setLedgers(Array.isArray(d) ? d : []))
        .catch(console.error)
      fetch(`${API_BASE}/vouchers/types`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(d => setVoucherTypes(Array.isArray(d) ? d : []))
        .catch(console.error)
    }
  }, [user, fetchVoucher, token, router])

  const handleAlterVoucher = async (payload: any, voucherId?: number | null) => {
    if (!token || !id) return
    setIsSaving(true)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}`, {
        method: 'PUT',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to update voucher')
      }
      toast.success('Voucher updated successfully and synced to Tally!')
      setIsEditModalOpen(false)
      fetchVoucher()
    } catch (err: any) {
      toast.error(err.message || 'Failed to alter voucher')
    } finally {
      setIsSaving(false)
    }
  }

  const handleRollback = async () => {
    if (!token || !id) return
    setIsRollingBack(true)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}/rollback`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to rollback voucher')
      }
      toast.success('Voucher and inventory rolled back to original pre-edit state!')
      setIsRollbackModalOpen(false)
      fetchVoucher()
    } catch (err: any) {
      toast.error(err.message || 'Rollback failed')
    } finally {
      setIsRollingBack(false)
    }
  }

  const handleRetrySync = async () => {
    if (!token || !id) return
    setIsRetrying(true)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}/retry-sync`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      const data = await res.json()
      if (data.tally_synced) {
        toast.success('Voucher successfully synced to Tally Prime!')
      } else {
        toast.error(`Tally sync failed: ${data.tally_message || 'Unknown error'}`)
      }
      fetchVoucher()
    } catch (err: any) {
      toast.error(err.message || 'Retry sync failed')
    } finally {
      setIsRetrying(false)
    }
  }

  const handleCancelVoucher = async () => {
    if (!token || !id) return
    setIsDeleting(true)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}/cancel`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to cancel voucher')
      }
      toast.success('Voucher marked as Cancelled (<ISCANCELLED>Yes</ISCANCELLED>) and synced to Tally!')
      setIsDeleteDialogOpen(false)
      fetchVoucher()
    } catch (err: any) {
      toast.error(err.message || 'Failed to cancel voucher')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleDeleteVoucher = async () => {
    if (!token || !id) return
    setIsDeleting(true)
    try {
      const res = await fetch(`${API_BASE}/vouchers/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to delete voucher')
      }
      toast.success('Voucher deleted successfully and synced to Tally!')
      setIsDeleteDialogOpen(false)
      router.push('/vouchers')
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete voucher')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleGeneratePaylink = async (openModal = false) => {
    if (!voucher || !id || !token) return
    setGeneratingPaylink(true)
    try {
      const res = await fetch(`${API_BASE}/payments/generate-link`, {
        method: 'POST',
        headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voucher_id: voucher.voucher_id,
          amount: finalTotal
        })
      })
      if (res.ok) {
        const data = await res.json()
        setPaylink(data)
        setShowPaylinkCard(true)
        if (openModal) {
          setIsQrModalOpen(true)
        }
        toast.success('Dynamic UPI Paylink generated successfully!')
      } else {
        const err = await res.json()
        toast.error(err.detail || 'Failed to generate paylink')
      }
    } catch (err: any) {
      toast.error(err.message || 'Error creating paylink')
    } finally {
      setGeneratingPaylink(false)
    }
  }

  const handleDownloadPdf = async () => {
    if (!voucher || !id) return
    setDownloading(true)
    try {
      await generateVoucherPdf({
        voucherGuid: id,
        header: {
          voucherType: voucher.voucher_type,
          voucherNumber: voucher.voucher_number,
          date: voucher.date,
          referenceNumber: voucher.reference_number,
          partyName: voucher.party_name
        },
        accounts: voucher.entries || voucher.accounts || [],
        inventory: voucher.inventory || [],
        partyLedger: voucher.party_ledger,
        shouldDownload: true
      })
    } catch (err) {
      console.error('Failed to generate PDF:', err)
    } finally {
      setDownloading(false)
    }
  }

  const handleGenerateEinvoice = async () => {
    if (!voucher || !id || !token) return
    setGeneratingEinvoice(true)
    try {
      const res = await fetch(`${API_BASE}/gst/einvoice/${voucher.voucher_id}/generate`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        alert('E-Invoice (IRN & Acknowledgement) generated successfully!')
        // Refresh details
        fetchVoucher()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to generate e-invoice.')
      }
    } catch (e: any) {
      alert(e.message || 'Error occurred during generation.')
    } finally {
      setGeneratingEinvoice(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full py-20">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
      </div>
    )
  }

  if (error || !voucher) {
    return (
      <div className="p-6">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="p-10 text-center text-muted-foreground">
          {error || 'Voucher not found.'}
        </div>
      </div>
    )
  }

  const formattedDate = voucher.date
    ? new Date(voucher.date).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      })
    : 'N/A'

  const isSalesVoucher = voucher.voucher_type.toLowerCase().includes('sales')
  const partyGstin = voucher.party_ledger?.gstn

  const finalTotal = (() => {
    if (!voucher) return 0
    // 1. Try finding Party Ledger amount (the net invoice/bill amount)
    if (voucher.accounts && voucher.accounts.length > 0 && voucher.party_name) {
      const partyAcc = voucher.accounts.find(
        (a: any) => (a.ledger_name || a.ledger || '').trim().toLowerCase() === (voucher.party_name || '').trim().toLowerCase()
      )
      if (partyAcc) {
        const pAmt = Math.abs(parseFloat(partyAcc.amount ?? partyAcc.debit_amount ?? partyAcc.credit_amount ?? '0'))
        if (pAmt > 0) return pAmt
      }
    }
    // 2. Direct total_amount from DB / API
    if (voucher.total_amount && Math.abs(Number(voucher.total_amount)) > 0) {
      return Math.abs(Number(voucher.total_amount))
    }
    if (voucher.amount && Math.abs(Number(voucher.amount)) > 0) {
      return Math.abs(Number(voucher.amount))
    }
    // 3. Fallback: Sum inventory items + non-party non-sales/purchase account ledger splits
    let total = 0
    const partyNameLower = (voucher.party_name || '').trim().toLowerCase()
    const hasItems = voucher.inventory && voucher.inventory.length > 0
    if (hasItems) {
      total += voucher.inventory.reduce((sum: number, i: any) => sum + Math.abs(parseFloat(i.amount || '0')), 0)
    }
    if (voucher.accounts && voucher.accounts.length > 0) {
      voucher.accounts.forEach((acc: any) => {
        const lName = (acc.ledger_name || acc.ledger || '').trim().toLowerCase()
        if (!lName || lName === partyNameLower) return
        if (hasItems && (
          ['sales', 'sales a/c', 'sales account', 'sales ac', 'purchase', 'purchase a/c', 'purchase account', 'purchase ac'].includes(lName) ||
          lName.startsWith('sales ') || lName.startsWith('purchase ')
        )) {
          return
        }
        total += parseFloat(acc.amount || '0')
      })
    }
    return total > 0 ? Math.abs(total) : Math.abs(voucher.amount || 0)
  })()

  return (
    <div className="max-w-5xl mx-auto my-1 sm:my-4 px-1 sm:px-4 pb-20 md:pb-6">
      {/* Top Action Bar */}
      <div className="flex flex-wrap justify-between items-center gap-3 mb-3 sm:mb-4 px-2 sm:px-0 no-print">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Vouchers
        </button>

        <div className="flex items-center gap-2">
          {/* UPI Paylink Button (for Sales / Invoice Vouchers) */}
          <button
            type="button"
            onClick={() => {
              if (!paylink) {
                handleGeneratePaylink(true)
              } else {
                setIsQrModalOpen(true)
              }
            }}
            disabled={generatingPaylink}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-sm rounded-xl h-10 px-4 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            {generatingPaylink ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
            {paylink ? (paylink.status === 'COMPLETED' ? '✅ Paid via UPI' : '⚡ View Paylink & QR') : '⚡ Generate Paylink'}
          </button>

          {/* Alter / Edit Voucher Button */}
          <button
            type="button"
            onClick={() => setIsEditModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm rounded-xl h-10 px-4 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            <Edit3 className="h-3.5 w-3.5" />
            Alter / Edit
          </button>

          {/* Delete Voucher Button */}
          <button
            type="button"
            onClick={() => setIsDeleteDialogOpen(true)}
            className="bg-rose-50 hover:bg-rose-100 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-800 font-bold text-xs shadow-xs rounded-xl h-10 px-3.5 flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </button>

          {/* Download PDF button */}
          <button
            onClick={handleDownloadPdf}
            disabled={downloading}
            className="bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-300 text-white font-extrabold text-xs shadow-md rounded-xl h-10 px-5 border-none cursor-pointer flex items-center justify-center gap-1.5 transition-colors"
          >
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download PDF
          </button>
        </div>
      </div>

      {/* Tally Prime Sync Failure Alert Banner */}
      {voucher?.sync_status === 'FAILED' && (
        <div className="mb-4 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 dark:border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm animate-in fade-in duration-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-black uppercase tracking-wider text-amber-800 dark:text-amber-300">
                  Tally Prime Sync Failed
                </h4>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-extrabold bg-amber-500/20 text-amber-700 dark:text-amber-300">
                  Out of Sync
                </span>
              </div>
              <p className="text-xs text-amber-700 dark:text-amber-400 mt-1 font-medium">
                {voucher.tally_error_message || 'This voucher was altered in MyTally but could not be synced to Tally Prime.'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
            <button
              onClick={handleRetrySync}
              disabled={isRetrying}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer"
            >
              {isRetrying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
              Retry Sync
            </button>
            {voucher.can_rollback && (
              <button
                onClick={() => setIsRollbackModalOpen(true)}
                disabled={isRollingBack}
                className="px-3 py-1.5 bg-white dark:bg-slate-900 border border-amber-500 text-amber-800 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-950/50 rounded-xl text-xs font-bold shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
              >
                Rollback Changes
              </button>
            )}
          </div>
        </div>
      )}

      {/* Dynamic Paylink & UPI QR Code Banner */}
      {(showPaylinkCard || paylink) && paylink && (
        <div className="mb-4 p-4 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/60 flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in duration-200">
          <div className="flex items-center gap-4">
            <div 
              onClick={() => setIsQrModalOpen(true)}
              className="p-2 bg-white rounded-xl border border-indigo-200 shadow-sm flex flex-col items-center cursor-pointer hover:scale-105 transition-transform"
              title="Click to view full-size QR code"
            >
              {paylink?.upi_uri ? (
                <QRCodeSVG value={paylink.upi_uri} size={64} level="M" />
              ) : (
                <QrCode className="w-16 h-16 text-indigo-600" />
              )}
              <span className="text-[8px] font-black uppercase text-indigo-700 tracking-wider mt-1">Click to Scan</span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-black uppercase tracking-wider text-indigo-700 dark:text-indigo-300">
                  Tally 7.0 Connected Paylink
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                  paylink?.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-600' : 'bg-amber-500/20 text-amber-600'
                }`}>
                  {paylink?.status || 'PENDING'}
                </span>
              </div>
              <p className="text-sm font-bold text-slate-800 dark:text-slate-200">
                Amount Payable: ₹{parseFloat(String(paylink?.amount || finalTotal)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-muted-foreground font-mono truncate max-w-sm">
                UPI VPA: <span className="font-bold text-indigo-600 dark:text-indigo-400">{paylink?.upi_vpa || (paylink?.upi_uri ? new URLSearchParams(paylink.upi_uri.split('?')[1]).get('pa') : '') || 'Configured UPI VPA'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto justify-end">
            <button
              type="button"
              onClick={() => setIsQrModalOpen(true)}
              className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5 cursor-pointer"
            >
              <QrCode className="w-3.5 h-3.5" /> Show QR Code
            </button>

            <button
              type="button"
              onClick={() => {
                if (paylink?.payment_url) {
                  navigator.clipboard.writeText(paylink.payment_url)
                  toast.success('Payment link copied to clipboard!')
                }
              }}
              className="px-3 py-2 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-bold rounded-xl border border-border flex items-center gap-1.5 cursor-pointer"
            >
              <Copy className="w-3.5 h-3.5" /> Copy Link
            </button>
          </div>
        </div>
      )}

      {/* Interactive Full-Screen/Popup QR Modal */}
      {isQrModalOpen && paylink && (
        <div 
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setIsQrModalOpen(false)}
        >
          <div 
            className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-600 flex items-center justify-center font-bold">
                  <Zap className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground leading-snug">Instant UPI Payment QR</h3>
                  <span className="text-[11px] text-muted-foreground font-mono">Invoice #{voucher?.voucher_number} • Tally Prime 7.0 e-Banking</span>
                </div>
              </div>
              <button
                onClick={() => setIsQrModalOpen(false)}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* QR Code Container with High-Contrast White Surface */}
            <div className="flex flex-col items-center justify-center p-5 bg-white rounded-2xl border-2 border-indigo-100 shadow-inner">
              <QRCodeSVG
                value={paylink.upi_uri || ''}
                size={200}
                level="H"
                includeMargin={true}
              />
              <div className="mt-3 flex items-center gap-1.5 text-center">
                <span className="px-3 py-1 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Scan with GPay, PhonePe, Paytm, BHIM or CRED
                </span>
              </div>
            </div>

            {/* Payment Details Card */}
            <div className="p-3.5 rounded-xl bg-muted/40 border border-border space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground font-medium">Payee VPA:</span>
                <div className="flex items-center gap-1.5 font-bold font-mono">
                  <span>{paylink?.upi_vpa || (paylink?.upi_uri ? new URLSearchParams(paylink.upi_uri.split('?')[1]).get('pa') : '') || 'Configured UPI VPA'}</span>
                  <button
                    onClick={() => {
                      const vpaStr = paylink?.upi_vpa || (paylink?.upi_uri ? new URLSearchParams(paylink.upi_uri.split('?')[1]).get('pa') : '') || ''
                      if (vpaStr) {
                        navigator.clipboard.writeText(vpaStr)
                        toast.success("UPI ID copied!")
                      }
                    }}
                    className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground cursor-pointer"
                    title="Copy UPI ID"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-muted-foreground font-medium">Amount Payable:</span>
                <span className="text-base font-black text-emerald-600 dark:text-emerald-400 font-mono">
                  ₹{parseFloat(String(paylink.amount || finalTotal)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-muted-foreground font-medium">Settlement Status:</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${
                  paylink.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-600' : 'bg-amber-500/20 text-amber-600'
                }`}>
                  {paylink.status}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-1">
              <button
                type="button"
                onClick={() => {
                  if (paylink.payment_url) {
                    navigator.clipboard.writeText(paylink.payment_url)
                    toast.success('Payment link copied to clipboard!')
                  }
                }}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <Copy className="w-3.5 h-3.5" /> Copy Payment Link
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main voucher document panel */}
      <div className="p-2 sm:p-5 font-mono text-base border border-foreground sm:border-2 bg-card text-card-foreground shadow-sm dark:shadow-none">
        {/* Header Section */}
        <div className="flex justify-between border-b border-foreground pb-2 mb-4 text-base sm:text-lg">
          <div>
            <h1 className="text-2xl font-extrabold uppercase tracking-tight">{voucher.voucher_type}</h1>
            <p className="text-muted-foreground text-sm">
              No. <span className="font-bold text-foreground">{voucher.voucher_number}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="font-extrabold text-sm sm:text-base">
              {formattedDate}
            </p>
          </div>
        </div>

        {/* Party Details */}
        <div className="mb-4 space-y-1 text-sm sm:text-base">
          <p>
            <span className="text-muted-foreground">Party:</span>{' '}
            {voucher.party_ledger_id ? (
              <Link
                href={`/ledgers/${voucher.party_ledger_id}`}
                className="font-bold underline decoration-dotted underline-offset-4 hover:text-primary transition-colors inline-flex items-center gap-1"
                title={`Open ${voucher.party_name} ledger statement`}
              >
                {toTitleCase(voucher.party_name)}
              </Link>
            ) : (
              <Link
                href={`/ledgers?search=${encodeURIComponent(voucher.party_name)}`}
                className="font-bold underline decoration-dotted underline-offset-4 hover:text-primary transition-colors inline-flex items-center gap-1"
                title={`Search ${voucher.party_name} in ledgers`}
              >
                {toTitleCase(voucher.party_name)}
              </Link>
            )}
            {partyGstin && (
              <span className="ml-2 px-2 py-0.5 bg-blue-500/10 text-blue-600 rounded text-xs font-bold font-sans">
                GSTIN: {partyGstin}
              </span>
            )}
          </p>
          {voucher.reference_number && (
            <p>
              <span className="text-muted-foreground">Ref:</span>{' '}
              <span className="font-medium">{voucher.reference_number}</span>
            </p>
          )}
        </div>

        {/* Interactive Voucher details listing */}
        <VoucherDetailsClient
          header={{ partyName: voucher.party_name }}
          accounts={voucher.entries || voucher.accounts || []}
          inventory={voucher.inventory || []}
          isInventoryVoucher={voucher.is_inventory_voucher}
        />

        {/* E-Invoicing Section */}
        {isSalesVoucher && (
          <div className="mt-6 border border-border rounded-xl p-4 bg-muted/20 font-sans no-print">
            {voucher.einvoice_metadata ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-emerald-600" />
                  <h3 className="text-sm font-extrabold text-emerald-600">GST E-Invoice Registered (IRN generated)</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="bg-background border border-border p-2.5 rounded-lg col-span-1 sm:col-span-2">
                    <span className="text-[10px] text-muted-foreground block font-sans font-semibold mb-0.5">Invoice Reference Number (IRN)</span>
                    <span className="break-all font-semibold select-all">{voucher.einvoice_metadata.irn}</span>
                  </div>
                  <div className="bg-background border border-border p-2.5 rounded-lg">
                    <span className="text-[10px] text-muted-foreground block font-sans font-semibold mb-0.5">Acknowledgement No.</span>
                    <span className="font-semibold">{voucher.einvoice_metadata.ack_no}</span>
                  </div>
                  <div className="bg-background border border-border p-2.5 rounded-lg">
                    <span className="text-[10px] text-muted-foreground block font-sans font-semibold mb-0.5">Acknowledgement Date</span>
                    <span className="font-semibold">
                      {new Date(voucher.einvoice_metadata.ack_date).toLocaleString('en-IN')}
                    </span>
                  </div>
                  {voucher.einvoice_metadata.eway_bill_no && (
                    <div className="bg-background border border-border p-2.5 rounded-lg col-span-1 sm:col-span-2 flex justify-between items-center">
                      <div>
                        <span className="text-[10px] text-muted-foreground block font-sans font-semibold mb-0.5">E-Way Bill Number</span>
                        <span className="font-semibold">{voucher.einvoice_metadata.eway_bill_no}</span>
                      </div>
                      {voucher.einvoice_metadata.eway_bill_date && (
                        <div className="text-right">
                          <span className="text-[10px] text-muted-foreground block font-sans font-semibold mb-0.5">E-Way Bill Date</span>
                          <span className="font-semibold">
                            {new Date(voucher.einvoice_metadata.eway_bill_date).toLocaleDateString('en-IN')}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : partyGstin ? (
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <FileSpreadsheet className="h-4.5 w-4.5 text-blue-600" />
                    <h3 className="text-sm font-extrabold text-foreground">GST E-Invoicing Available</h3>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed max-w-lg">
                    This is a B2B sales invoice with a registered recipient GSTIN. Click the button to upload to the Invoice Registration Portal (IRP) and generate an IRN and QR Code.
                  </p>
                </div>
                <button
                  onClick={handleGenerateEinvoice}
                  disabled={generatingEinvoice}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-extrabold text-xs shadow-md rounded-xl h-11 px-5 flex items-center justify-center gap-1.5 transition-colors whitespace-nowrap cursor-pointer"
                >
                  {generatingEinvoice ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="h-4 w-4" />
                  )}
                  Generate E-Invoice
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-muted-foreground shrink-0" />
                <div>
                  <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">E-Invoicing Not Required</h3>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                    E-invoicing is only applicable for B2B transactions. Recipient party is unregistered (no GSTIN).
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer Section */}
        <div className="mt-8 border-t border-foreground pt-4 flex flex-col md:flex-row justify-between gap-4">
          <div className="max-w-md">
            <p className="text-xs font-bold uppercase text-muted-foreground mb-1">Narration:</p>
            <p className="italic text-foreground/80 text-sm sm:text-base leading-relaxed border-l-2 border-muted pl-3">
              {voucher.narration || "No narration provided."}
            </p>
          </div>
          <div className="text-right">
            <div className="inline-block border-t-2 border-b-4 border-foreground py-2 px-6 bg-muted/30">
              <span className="text-sm uppercase mr-4 text-muted-foreground font-bold">Total</span>
              <span className="text-2xl font-black tabular-nums text-emerald-600">
                ₹{finalTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Spacer to prevent content hiding behind MobileBottomNav */}
      <div className="h-20 lg:hidden" />

      {/* Alter / Edit Voucher Modal */}
      {isEditModalOpen && (
        <VoucherFormModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          onSave={handleAlterVoucher}
          isSaving={isSaving}
          ledgers={ledgers}
          voucherTypes={voucherTypes}
          editVoucher={voucher}
        />
      )}

      {/* Cancel vs Delete Confirmation Modal */}
      {isDeleteDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-lg shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-5">
            <div className="flex items-center gap-3 text-rose-600 dark:text-rose-400">
              <div className="p-3 bg-rose-100 dark:bg-rose-950/60 rounded-xl">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Manage Voucher #{voucher.voucher_number}</h3>
                <p className="text-xs text-slate-500">Real-time sync to TallyPrime</p>
              </div>
            </div>

            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              How would you like to handle <strong className="text-slate-900 dark:text-white">{voucher.voucher_type} #{voucher.voucher_number}</strong>?
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="border border-amber-500/20 bg-amber-500/5 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-bold text-xs">
                    <AlertCircle className="w-4 h-4" /> Cancel Voucher
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    Zeroes out financial balances, reverses inventory, and marks as Cancelled in Tally while preserving the sequence number.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleCancelVoucher}
                  disabled={isDeleting}
                  className="w-full mt-2 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow flex items-center justify-center gap-1.5 cursor-pointer transition-all"
                >
                  {isDeleting && <Loader2 className="w-3 h-3 animate-spin" />}
                  Mark Cancelled
                </button>
              </div>

              <div className="border border-rose-500/20 bg-rose-500/5 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-bold text-xs">
                    <Trash2 className="w-4 h-4" /> Hard Delete
                  </div>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                    Permanently removes the voucher record from MyTally and pushes a direct Delete action to Tally.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleDeleteVoucher}
                  disabled={isDeleting}
                  className="w-full mt-2 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow flex items-center justify-center gap-1.5 cursor-pointer transition-all"
                >
                  {isDeleting && <Loader2 className="w-3 h-3 animate-spin" />}
                  Hard Delete
                </button>
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => setIsDeleteDialogOpen(false)}
                disabled={isDeleting}
                className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rollback Confirmation Modal */}
      {isRollbackModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-md shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center gap-3 text-amber-600 dark:text-amber-400">
              <div className="p-3 bg-amber-100 dark:bg-amber-950/60 rounded-xl">
                <AlertCircle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">Rollback Voucher Alter?</h3>
                <p className="text-xs text-slate-500">Restore to pre-edit state</p>
              </div>
            </div>

            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              This will discard the failed alter changes and restore <strong className="text-slate-900 dark:text-white">#{voucher.voucher_number}</strong> back to its original header, ledger splits, and inventory stock balances before this edit.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsRollbackModalOpen(false)}
                disabled={isRollingBack}
                className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRollback}
                disabled={isRollingBack}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl shadow flex items-center gap-1.5 cursor-pointer transition-all"
              >
                {isRollingBack && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Confirm Rollback
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
