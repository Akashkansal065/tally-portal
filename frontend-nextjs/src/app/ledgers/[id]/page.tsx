'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, toTitleCase } from '@/lib/utils'
import { ArrowLeft, Loader2 } from 'lucide-react'
import LedgerDetailsClient from './ledger-details-client'

type LedgerInfo = {
  ledger_id: number
  name: string
  parent: string
  gstn: string | null
  address: string | null
  state: string | null
  mobile: string | null
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

    fetch(`${API_BASE}/ledgers/${id}/statement`, { headers: authHeaders(token) })
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
  }, [user, token, router, id])

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
    <div className="max-w-5xl mx-auto my-1 sm:my-4 px-1 sm:px-4 pb-20 md:pb-6 font-mono text-base">
      <div className="flex justify-between items-center mb-3 sm:mb-4 px-2 sm:px-0">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Customers
        </button>
      </div>

      {/* Header Info Banner matching tally-web layout */}
      <div className="p-4 sm:p-5 border border-foreground sm:border-2 bg-card text-card-foreground shadow-sm dark:shadow-none mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-emerald-600 dark:text-emerald-400 break-words leading-snug uppercase tracking-tight">
            {toTitleCase(ledgerInfo.name)}
          </h1>
          <p className="text-xs sm:text-sm font-bold text-muted-foreground uppercase tracking-wider mt-0.5">
            {ledgerInfo.parent}
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
            GSTIN / UIN
          </p>
          <p className="font-mono font-bold text-sm sm:text-base text-foreground mt-0.5">
            {ledgerInfo.gstn || 'Unregistered'}
          </p>
        </div>
      </div>

      {/* Interactive table list container */}
      <LedgerDetailsClient ledgerInfo={ledgerInfo} transactions={transactions} />
    </div>
  )
}
