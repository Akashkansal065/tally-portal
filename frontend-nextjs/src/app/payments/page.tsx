'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { 
  IndianRupee, 
  Clock, 
  Check, 
  X, 
  Plus, 
  Camera, 
  Eye, 
  ChevronLeft, 
  User as UserIcon,
  Calendar
} from 'lucide-react'
import { cn } from '@/lib/utils'

type Payment = {
  id: number
  ledger_name?: string
  amount: number
  payment_mode: string
  status: 'pending' | 'success' | 'cancelled'
  comments?: string
  created_at: string
  user_name: string
  photo_url?: string
}

export default function PaymentsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [payments, setPayments] = useState<Payment[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'pending' | 'success' | 'cancelled'>('pending')
  const [selectedPhoto, setSelectedPhoto] = useState<string | null>(null)

  const fetchData = async () => {
    setLoading(true)
    try {
      const isAdmin = permissions.isAdmin
      const url = isAdmin ? `${API_BASE}/payment/all` : `${API_BASE}/payment/history`
      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setPayments(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchData()
  }, [user, token, router])

  const handleStatusChange = async (paymentId: number, nextStatus: 'success' | 'cancelled') => {
    try {
      const res = await fetch(`${API_BASE}/payment/${paymentId}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ status: nextStatus })
      })
      if (!res.ok) throw new Error('Failed to update status')
      setPayments(prev => prev.map(p => p.id === paymentId ? { ...p, status: nextStatus } : p))
    } catch (err: any) {
      alert(err.message)
    }
  }

  // Grouped payments
  const pendingPayments = useMemo(() => payments.filter(p => p.status === 'pending'), [payments])
  const successPayments = useMemo(() => payments.filter(p => p.status === 'success'), [payments])
  const cancelledPayments = useMemo(() => payments.filter(p => p.status === 'cancelled'), [payments])

  const currentList = useMemo(() => {
    if (activeTab === 'success') return successPayments
    if (activeTab === 'cancelled') return cancelledPayments
    return pendingPayments
  }, [activeTab, pendingPayments, successPayments, cancelledPayments])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Top Header */}
      <header className="shrink-0 border-b border-border bg-emerald-500 text-white h-14 flex items-center px-4 justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/')} className="p-1 hover:bg-emerald-600 rounded-lg transition-colors">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-white/20 flex items-center justify-center text-xs font-bold">S</div>
            <span className="font-bold text-sm">Sneh Distributors</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        {/* Title and CTA */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-1.5 text-foreground">
              <IndianRupee className="h-5.5 w-5.5 text-emerald-500" /> Payments Log
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Collect and validate customer outstanding payments</p>
          </div>
          <button 
            onClick={() => router.push('/payments/new')}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" /> Collect
          </button>
        </div>

        {/* Status Tab Headers */}
        <div className="grid w-full grid-cols-3 bg-muted/40 p-1 rounded-xl border border-border/80 h-10 items-center">
          <button
            onClick={() => setActiveTab('pending')}
            className={cn(
              'h-8 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5',
              activeTab === 'pending'
                ? 'bg-amber-500 text-white shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Pending
            <span className={cn('text-[9px] px-1.5 py-0.5 rounded-full font-black', activeTab === 'pending' ? 'bg-white text-amber-600' : 'bg-amber-500 text-white')}>
              {pendingPayments.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('success')}
            className={cn(
              'h-8 text-xs font-bold rounded-lg transition-all',
              activeTab === 'success'
                ? 'bg-emerald-500 text-white shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Success
          </button>
          <button
            onClick={() => setActiveTab('cancelled')}
            className={cn(
              'h-8 text-xs font-bold rounded-lg transition-all',
              activeTab === 'cancelled'
                ? 'bg-rose-500 text-white shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Cancelled
          </button>
        </div>

        {/* Payments List */}
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : currentList.length === 0 ? (
          <div className="text-center py-12 bg-card border border-border rounded-2xl border-dashed">
            <IndianRupee className="h-10 w-10 mx-auto mb-3 opacity-25 text-muted-foreground" />
            <p className="text-sm font-bold text-muted-foreground">No payments found</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">There are no records in this category</p>
          </div>
        ) : (
          <div className="space-y-3">
            {currentList.map(p => (
              <div key={p.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm hover:border-emerald-500/30 transition-all flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="font-extrabold text-sm text-foreground break-words leading-tight">
                      {p.ledger_name || 'Unknown Party'}
                    </h3>
                    <div className="flex gap-2 items-center mt-1.5 text-[10px] text-muted-foreground font-semibold">
                      <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(p.created_at)}</span>
                      {permissions.isAdmin && (
                        <span className="flex items-center gap-1 uppercase bg-muted px-1.5 py-0.5 rounded tracking-wider text-[8px]">
                          {p.user_name}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <p className="font-black text-sm text-emerald-600 dark:text-emerald-400 font-mono">
                      ₹{p.amount.toLocaleString('en-IN')}
                    </p>
                    <span className="inline-flex mt-1.5 text-[9px] font-bold px-1.5 py-0.5 rounded bg-muted/65 text-muted-foreground border border-border/80">
                      {p.payment_mode}
                    </span>
                  </div>
                </div>

                {p.comments && (
                  <p className="text-[11px] text-muted-foreground bg-muted/30 p-2 rounded-xl italic leading-relaxed">
                    <span className="font-extrabold not-italic text-[8px] uppercase tracking-wider text-muted-foreground mr-1.5">Note:</span>
                    {p.comments}
                  </p>
                )}

                {/* Proof Dialog Trigger & Admin Actions */}
                <div className="flex items-center justify-between border-t border-border/40 pt-3 mt-0.5 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <span className="font-extrabold text-[9px] uppercase tracking-wider">Receipt:</span>
                    {p.photo_url ? (
                      <button 
                        onClick={() => setSelectedPhoto(p.photo_url || null)}
                        className="text-emerald-500 hover:text-emerald-600 font-bold underline flex items-center gap-0.5 cursor-pointer"
                      >
                        <Camera className="h-3.5 w-3.5" /> View Photo
                      </button>
                    ) : (
                      <span className="text-[11px] italic">N/A</span>
                    )}
                  </div>

                  {permissions.isAdmin && p.status === 'pending' && (
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={() => handleStatusChange(p.id, 'success')}
                        className="h-8 w-8 bg-green-500/10 hover:bg-green-500 text-green-600 hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-green-500/20"
                        title="Approve Payment"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                      <button 
                        onClick={() => handleStatusChange(p.id, 'cancelled')}
                        className="h-8 w-8 bg-destructive/10 hover:bg-destructive text-destructive hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-destructive/20"
                        title="Cancel Payment"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="h-16" />
      </div>

      {/* Selected Photo Viewer Modal */}
      {selectedPhoto && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="relative max-w-lg w-full bg-card rounded-3xl overflow-hidden shadow-2xl p-2 animate-in zoom-in-95 duration-200">
            <button 
              onClick={() => setSelectedPhoto(null)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors z-10"
            >
              <X className="h-4 w-4" />
            </button>
            <img 
              src={selectedPhoto} 
              alt="Payment Receipt" 
              className="w-full h-auto max-h-[80vh] object-contain rounded-2xl"
            />
          </div>
        </div>
      )}
    </div>
  )
}
