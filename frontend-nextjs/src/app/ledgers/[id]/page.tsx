'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { usePeriod } from '@/context/PeriodContext'
import { API_BASE, authHeaders, toTitleCase } from '@/lib/utils'
import { ArrowLeft, Loader2, Phone, Mail, MapPin, CreditCard } from 'lucide-react'
import LedgerDetailsClient from './ledger-details-client'

type LedgerInfo = {
  ledger_id: number
  name: string
  alias_name?: string | null
  parent: string
  gstn: string | null
  gst_registration_type?: string | null
  pan_number?: string | null
  address: string | null
  state: string | null
  pincode?: string | null
  country?: string | null
  phone?: string | null
  mobile: string | null
  email?: string | null
  contact_person?: string | null
  opening_balance?: number
  opening_balance_type?: string
  credit_limit?: number | null
  credit_period_days?: number | null
  total_opening_dr?: number
  total_opening_cr?: number
  total_opening_diff?: number
  total_opening_diff_type?: string
}

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

export default function LedgerDetailsPage() {
  const { user, token } = useAuth()
  const { startDate, endDate } = usePeriod()
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string

  const [ledgerInfo, setLedgerInfo] = useState<LedgerInfo | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!id) return

    setLoading(true)
    let url = `${API_BASE}/ledgers/${id}/statement`
    const q: string[] = []
    if (startDate) q.push(`from_date=${startDate}`)
    if (endDate) q.push(`to_date=${endDate}`)
    if (q.length > 0) url += `?${q.join('&')}`

    fetch(url, { headers: authHeaders(token) })
      .then(r => {
        if (!r.ok) throw new Error('Not found')
        return r.json()
      })
      .then(data => {
        if (data.success) {
          setLedgerInfo(data.ledgerInfo)
          setTransactions(data.transactions)
        } else {
          setError(data.error || 'Failed to load details')
        }
      })
      .catch(() => setError('Ledger details not found'))
      .finally(() => setLoading(false))
  }, [user, token, router, id, startDate, endDate])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full py-20">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
      </div>
    )
  }

  if (error || !ledgerInfo) {
    return (
      <div className="p-6">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="p-10 text-center text-muted-foreground">
          {error || 'Ledger details not found.'}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto my-1 sm:my-4 px-1 sm:px-4 pb-20 md:pb-6 font-sans text-base">
      <div className="flex justify-between items-center mb-3 sm:mb-4 px-2 sm:px-0">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Ledgers
        </button>
      </div>

      {/* Header Info Banner matching tally-web layout */}
      <div className="p-4 sm:p-5 border border-border rounded-2xl bg-card text-card-foreground shadow-sm mb-4 space-y-3 font-sans relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-border/80 pb-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400 break-words leading-snug uppercase tracking-tight">
              {toTitleCase(ledgerInfo.name)}
            </h1>
            {ledgerInfo.alias_name && (
              <p className="text-xs text-muted-foreground font-medium italic mt-0.5">
                (alias: {ledgerInfo.alias_name})
              </p>
            )}
            <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mt-1">
              {ledgerInfo.parent} {ledgerInfo.gst_registration_type ? `• ${ledgerInfo.gst_registration_type}` : ''}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 sm:gap-6 shrink-0 text-left sm:text-right">
            <div>
              <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                GSTIN / UIN
              </p>
              <p className="font-mono font-bold text-sm sm:text-base text-foreground mt-0.5">
                {ledgerInfo.gstn || 'Unregistered'}
              </p>
            </div>

            {/* Total Opening Balance (Tally Style) */}
            {typeof ledgerInfo.total_opening_dr === 'number' && (
              <div className="border border-border rounded-xl p-2 bg-muted/40 text-right min-w-[150px]">
                <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider block border-b border-border/60 pb-0.5 mb-1">
                  Total Opening Balance
                </span>
                <p className="text-xs font-mono font-bold text-foreground">
                  ₹{ledgerInfo.total_opening_dr.toLocaleString('en-IN', { minimumFractionDigits: 2 })} Dr
                </p>
                <p className="text-xs font-mono font-bold text-foreground">
                  ₹{ledgerInfo.total_opening_cr?.toLocaleString('en-IN', { minimumFractionDigits: 2 })} Cr
                </p>
                {typeof ledgerInfo.total_opening_diff === 'number' && ledgerInfo.total_opening_diff > 0 && (
                  <div className="pt-0.5 border-t border-border/60 mt-1">
                    <span className="text-[9px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider block">Difference</span>
                    <p className="text-xs font-mono font-extrabold text-amber-600 dark:text-amber-400">
                      ₹{ledgerInfo.total_opening_diff.toLocaleString('en-IN', { minimumFractionDigits: 2 })} {ledgerInfo.total_opening_diff_type}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Extended User / Customer Details Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-muted-foreground pt-1">
          {/* Column 1: Mobile & Phone */}
          <div className="space-y-1">
            {(ledgerInfo.mobile || ledgerInfo.phone) && (
              <p className="flex items-center gap-1.5 font-medium text-foreground">
                <Phone className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                <span>{ledgerInfo.mobile || ledgerInfo.phone}</span>
              </p>
            )}
            {ledgerInfo.email && (
              <p className="flex items-center gap-1.5 font-medium">
                <Mail className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                <span>{ledgerInfo.email}</span>
              </p>
            )}
            {!ledgerInfo.mobile && !ledgerInfo.phone && !ledgerInfo.email && (
              <p className="italic text-muted-foreground/60">No contact info recorded</p>
            )}
          </div>

          {/* Column 2: Address & State */}
          <div className="space-y-1">
            {(ledgerInfo.address || ledgerInfo.state) ? (
              <p className="flex items-start gap-1.5 font-medium">
                <MapPin className="w-3.5 h-3.5 text-rose-500 shrink-0 mt-0.5" />
                <span>
                  {[ledgerInfo.address, ledgerInfo.state, ledgerInfo.pincode].filter(Boolean).join(', ')}
                </span>
              </p>
            ) : (
              <p className="italic text-muted-foreground/60">No address recorded</p>
            )}
          </div>

          {/* Column 3: PAN & Balances */}
          <div className="space-y-1 sm:text-right">
            {ledgerInfo.pan_number && (
              <p className="font-bold text-foreground">
                <span className="text-[10px] text-muted-foreground uppercase mr-1">PAN:</span>
                <span className="font-mono">{ledgerInfo.pan_number}</span>
              </p>
            )}
            {typeof ledgerInfo.opening_balance === 'number' && (
              <p className="font-semibold">
                <span className="text-[10px] text-muted-foreground uppercase mr-1">Opening Bal:</span>
                <span className="font-bold text-foreground">
                  ₹{Math.abs(ledgerInfo.opening_balance).toLocaleString('en-IN', { minimumFractionDigits: 2 })} {ledgerInfo.opening_balance_type || 'Dr'}
                </span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Interactive table list container */}
      <LedgerDetailsClient ledgerInfo={ledgerInfo} transactions={transactions} />
    </div>
  )
}
