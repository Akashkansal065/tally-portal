'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, toTitleCase } from '@/lib/utils'
import { ArrowLeft, Loader2, Download } from 'lucide-react'
import { cn } from '@/lib/utils'
import VoucherDetailsClient from './voucher-details-client'
import { generateVoucherPdf } from '@/lib/pdf-generator'

type VoucherEntry = {
  ledger_name: string
  amount: number
  entry_type: 'Debit' | 'Credit'
}

type VoucherDetail = {
  voucher_id: number
  date: string
  voucher_type: string
  voucher_number: string
  reference_number: string | null
  narration: string | null
  party_name: string
  amount: number
  total_amount: number
  entries: VoucherEntry[]
  accounts: any[]
  inventory: any[]
  is_inventory_voucher: boolean
  party_ledger: any
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

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!id) return

    fetch(`${API_BASE}/vouchers/${id}`, { headers: authHeaders(token) })
      .then(r => {
        if (!r.ok) throw new Error('Not found')
        return r.json()
      })
      .then(data => setVoucher(data))
      .catch(() => setError('Voucher not found'))
      .finally(() => setLoading(false))
  }, [user, token, router, id])

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
        accounts: voucher.accounts,
        inventory: voucher.inventory,
        partyLedger: voucher.party_ledger,
        shouldDownload: true
      })
    } catch (err) {
      console.error('Failed to generate PDF:', err)
    } finally {
      setDownloading(false)
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

  return (
    <div className="max-w-5xl mx-auto my-1 sm:my-4 px-1 sm:px-4 pb-20 md:pb-6">
      {/* Download PDF button at top right */}
      <div className="flex justify-between items-center mb-3 sm:mb-4 px-2 sm:px-0 no-print">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Vouchers
        </button>
        <button
          onClick={handleDownloadPdf}
          disabled={downloading}
          className="bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-300 text-white font-extrabold text-xs shadow-md rounded-xl h-11 px-6 border-none cursor-pointer flex items-center justify-center gap-1.5 transition-colors"
        >
          {downloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Download PDF
        </button>
      </div>

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
            <span className="font-bold underline decoration-dotted underline-offset-4">
              {toTitleCase(voucher.party_name)}
            </span>
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
          accounts={voucher.accounts}
          inventory={voucher.inventory}
          isInventoryVoucher={voucher.is_inventory_voucher}
        />

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
                ₹{Math.abs(voucher.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Spacer to prevent content hiding behind MobileBottomNav */}
      <div className="h-20 lg:hidden" />
    </div>
  )
}
