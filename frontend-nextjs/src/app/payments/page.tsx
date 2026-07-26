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
  cheque_date?: string
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
    if (!permissions.showPayments) { router.replace('/'); return }
    fetchData()
  }, [user, token, router, permissions])

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

  const formatPaymentDate = (isoStr?: string) => {
    if (!isoStr) return '--'
    const d = new Date(isoStr)
    const day = d.getDate()
    const month = d.toLocaleString('en-US', { month: 'short' })
    const hours = String(d.getHours()).padStart(2, '0')
    const mins = String(d.getMinutes()).padStart(2, '0')
    return `${day} ${month}, ${hours}:${mins}`
  }

  const formatChequeDate = (dateStr?: string) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const day = d.getDate()
    const month = d.toLocaleString('en-US', { month: 'short' })
    const year = d.getFullYear()
    return `${day} ${month} ${year}`
  }

  // Filter states (Date defaults to current date)
  const [paymentDate, setPaymentDate] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [paymentSalesperson, setPaymentSalesperson] = useState('')
  const [salespersons, setSalespersons] = useState<{ user_id: number; username: string; email: string }[]>([])

  useEffect(() => {
    if (!token || !permissions.isAdmin) return
    fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        if (Array.isArray(data)) setSalespersons(data)
      })
      .catch(() => {})
  }, [token, permissions])

  const filteredList = useMemo(() => {
    return currentList.filter(p => {
      const matchesDate = !paymentDate || (p.created_at && p.created_at.startsWith(paymentDate))
      const matchesUser = !paymentSalesperson || (p.user_name && p.user_name.toLowerCase() === paymentSalesperson.toLowerCase())
      return matchesDate && matchesUser
    })
  }, [currentList, paymentDate, paymentSalesperson])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Main Content Container */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-6xl mx-auto w-full space-y-4">
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
            className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" /> Collect
          </button>
        </div>

        {/* Filter Control Bar matching Visit View */}
        <div className="bg-card border border-border rounded-2xl p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            {/* Date Filter (Default to current date) */}
            <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
              <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
              <input
                type="date"
                value={paymentDate}
                onChange={e => setPaymentDate(e.target.value)}
                className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer"
              />
              {paymentDate && (
                <button
                  onClick={() => setPaymentDate('')}
                  className="text-[10px] text-muted-foreground hover:text-foreground font-bold px-1"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Salesperson Filter */}
            {permissions.isAdmin && salespersons.length > 0 && (
              <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
                <UserIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                <select
                  value={paymentSalesperson}
                  onChange={e => setPaymentSalesperson(e.target.value)}
                  className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer pr-2"
                >
                  <option value="">All Salespersons</option>
                  {salespersons.map(u => (
                    <option key={u.user_id} value={u.username || u.email}>
                      {u.username || u.email}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Payment Count Indicator */}
          <div className="text-xs text-muted-foreground font-medium self-end sm:self-auto shrink-0">
            {filteredList.length} {filteredList.length === 1 ? 'payment found' : 'payments found'}
          </div>
        </div>

        {/* Status Tab Headers */}
        <div className="grid w-full grid-cols-3 bg-muted/40 p-1 rounded-xl border border-border/80 h-10 items-center max-w-xs">
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
        ) : filteredList.length === 0 ? (
          <div className="text-center py-12 bg-card border border-border rounded-2xl border-dashed">
            <IndianRupee className="h-10 w-10 mx-auto mb-3 opacity-25 text-muted-foreground" />
            <p className="text-sm font-bold text-muted-foreground">No payments found</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">There are no records matching the selected date and filters</p>
          </div>
        ) : (
          <>
            {/* Desktop Table View (Visible on medium & desktop screens) */}
            <div className="hidden md:block bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-muted/50 border-b border-border text-xs font-bold text-foreground">
                      <th className="py-3.5 px-5">Date</th>
                      <th className="py-3.5 px-5">Salesperson</th>
                      <th className="py-3.5 px-5">Shop</th>
                      <th className="py-3.5 px-5">Amount</th>
                      <th className="py-3.5 px-5">Mode</th>
                      <th className="py-3.5 px-5">Proof</th>
                      <th className="py-3.5 px-5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border text-xs font-medium">
                    {filteredList.map(p => (
                      <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                        {/* Date */}
                        <td className="py-4 px-5 font-bold text-foreground whitespace-nowrap">
                          {formatPaymentDate(p.created_at)}
                        </td>

                        {/* Salesperson */}
                        <td className="py-4 px-5 whitespace-nowrap">
                          <span className="inline-block border border-border/80 bg-muted/30 px-3 py-1 rounded-full text-xs font-semibold text-foreground">
                            {p.user_name || 'Salesperson'}
                          </span>
                        </td>

                        {/* Shop */}
                        <td className="py-4 px-5 font-extrabold text-foreground min-w-[200px]">
                          {p.ledger_name || 'Unknown Party'}
                        </td>

                        {/* Amount */}
                        <td className="py-4 px-5 whitespace-nowrap font-extrabold text-base text-emerald-600 dark:text-emerald-400 font-mono">
                          ₹{p.amount.toLocaleString('en-IN')}
                        </td>

                        {/* Mode */}
                        <td className="py-4 px-5 whitespace-nowrap">
                          <span className="inline-block bg-muted/80 text-foreground px-3 py-1 rounded-full text-xs font-semibold">
                            {p.payment_mode}
                          </span>
                          {p.cheque_date && (
                            <p className="text-[10px] text-muted-foreground mt-1 font-medium">
                              Cheque Date: {formatChequeDate(p.cheque_date)}
                            </p>
                          )}
                        </td>

                        {/* Proof */}
                        <td className="py-4 px-5 whitespace-nowrap">
                          {p.photo_url ? (
                            <button
                              onClick={() => setSelectedPhoto(p.photo_url || null)}
                              className="text-sky-500 hover:text-sky-600 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer transition-colors"
                            >
                              <Eye className="h-4 w-4" /> View Proof
                            </button>
                          ) : (
                            <span className="text-muted-foreground text-xs italic">No Proof</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-4 px-5 text-right whitespace-nowrap">
                          {permissions.isAdmin && p.status === 'pending' ? (
                            <div className="inline-flex items-center gap-1.5">
                              <button
                                onClick={() => handleStatusChange(p.id, 'success')}
                                className="border border-border bg-card hover:bg-emerald-500 hover:text-white hover:border-emerald-500 rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all shadow-2xs cursor-pointer"
                              >
                                Review
                              </button>
                              <button
                                onClick={() => handleStatusChange(p.id, 'cancelled')}
                                className="border border-rose-500/20 text-rose-600 hover:bg-rose-500 hover:text-white rounded-xl px-2.5 py-1.5 text-xs font-bold transition-all cursor-pointer"
                                title="Reject Payment"
                              >
                                <X className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          ) : (
                            <span className={cn(
                              'inline-block px-3 py-1 rounded-full text-[11px] font-bold border',
                              p.status === 'success' ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 border-rose-500/20'
                            )}>
                              {p.status === 'success' ? 'Approved' : 'Cancelled'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Mobile Card View (Visible on mobile screens) */}
            <div className="block md:hidden space-y-3">
              {filteredList.map(p => (
                <div key={p.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3">
                  {/* Top Header Row */}
                  <div className="flex items-start justify-between gap-3 border-b border-border/50 pb-2.5">
                    <div className="min-w-0">
                      <h3 className="font-extrabold text-sm text-foreground break-words leading-tight">
                        {p.ledger_name || 'Unknown Party'}
                      </h3>
                      <p className="text-[10px] text-muted-foreground font-semibold mt-1 flex items-center gap-1">
                        <Calendar className="h-3 w-3 text-muted-foreground shrink-0" />
                        {formatPaymentDate(p.created_at)}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <p className="font-black text-base text-emerald-600 dark:text-emerald-400 font-mono">
                        ₹{p.amount.toLocaleString('en-IN')}
                      </p>
                      <span className="inline-block mt-1 bg-muted/80 text-foreground px-2.5 py-0.5 rounded-full text-[10px] font-bold">
                        {p.payment_mode}
                      </span>
                    </div>
                  </div>

                  {/* Middle Details Row */}
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-wide">By:</span>
                      <span className="border border-border/80 bg-muted/30 px-2.5 py-0.5 rounded-full text-[11px] font-semibold text-foreground">
                        {p.user_name || 'Salesperson'}
                      </span>
                    </div>

                    {p.cheque_date && (
                      <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-lg">
                        Cheque: {formatChequeDate(p.cheque_date)}
                      </span>
                    )}
                  </div>

                  {p.comments && (
                    <p className="text-[11px] text-muted-foreground bg-muted/30 p-2.5 rounded-xl italic leading-relaxed">
                      "{p.comments}"
                    </p>
                  )}

                  {/* Bottom Action / Proof Row */}
                  <div className="flex items-center justify-between border-t border-border/40 pt-2.5 text-xs">
                    {p.photo_url ? (
                      <button
                        onClick={() => setSelectedPhoto(p.photo_url || null)}
                        className="text-sky-500 hover:text-sky-600 font-bold flex items-center gap-1.5 cursor-pointer text-xs"
                      >
                        <Eye className="h-3.5 w-3.5" /> View Proof
                      </button>
                    ) : (
                      <span className="text-muted-foreground text-[11px] italic">No Proof</span>
                    )}

                    {permissions.isAdmin && p.status === 'pending' ? (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleStatusChange(p.id, 'success')}
                          className="border border-border bg-card hover:bg-emerald-500 hover:text-white rounded-xl px-3 py-1 text-xs font-bold transition-all cursor-pointer shadow-2xs"
                        >
                          Review
                        </button>
                        <button
                          onClick={() => handleStatusChange(p.id, 'cancelled')}
                          className="border border-rose-500/20 text-rose-600 hover:bg-rose-500 hover:text-white rounded-xl px-2 py-1 text-xs font-bold transition-all cursor-pointer"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : (
                      <span className={cn(
                        'inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold border',
                        p.status === 'success' ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 border-rose-500/20'
                      )}>
                        {p.status === 'success' ? 'Approved' : 'Cancelled'}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="h-16" />
      </div>

      {/* Selected Photo Viewer Modal */}
      {selectedPhoto && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="relative max-w-lg w-full bg-card rounded-3xl overflow-hidden shadow-2xl p-2 animate-in zoom-in-95 duration-200 border border-border">
            <button 
              onClick={() => setSelectedPhoto(null)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors z-10 cursor-pointer"
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
