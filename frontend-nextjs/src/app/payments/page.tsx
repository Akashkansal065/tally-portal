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
  Calendar,
  MessageSquare,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2
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
  review_comment?: string
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

  // Review modal states
  const [reviewTarget, setReviewTarget] = useState<{ payment: Payment; action: 'success' | 'cancelled' } | null>(null)
  const [reviewComment, setReviewComment] = useState('')
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [reviewError, setReviewError] = useState('')

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

  const openReviewModal = (payment: Payment, action: 'success' | 'cancelled') => {
    setReviewTarget({ payment, action })
    setReviewComment('')
    setReviewError('')
  }

  const closeReviewModal = () => {
    if (reviewSubmitting) return
    setReviewTarget(null)
    setReviewComment('')
    setReviewError('')
  }

  const handleConfirmReview = async () => {
    if (!reviewTarget) return
    const trimmed = reviewComment.trim()
    if (!trimmed) {
      setReviewError('A review comment is required.')
      return
    }

    setReviewSubmitting(true)
    setReviewError('')
    try {
      const res = await fetch(`${API_BASE}/payment/${reviewTarget.payment.id}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ 
          status: reviewTarget.action,
          review_comment: trimmed
        })
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to update status')
      }
      setPayments(prev => prev.map(p => 
        p.id === reviewTarget.payment.id 
          ? { ...p, status: reviewTarget.action, review_comment: trimmed } 
          : p
      ))
      setReviewTarget(null)
      setReviewComment('')
    } catch (err: any) {
      setReviewError(err.message || 'Something went wrong')
    } finally {
      setReviewSubmitting(false)
    }
  }

  // Grouped payments (sorted by date desc)
  const sortedPayments = useMemo(() => {
    return [...payments].sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0
      return dateB - dateA
    })
  }, [payments])

  const pendingPayments = useMemo(() => sortedPayments.filter(p => p.status === 'pending'), [sortedPayments])
  const successPayments = useMemo(() => sortedPayments.filter(p => p.status === 'success'), [sortedPayments])
  const cancelledPayments = useMemo(() => sortedPayments.filter(p => p.status === 'cancelled'), [sortedPayments])

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

  // Filter states (No date filter by default)
  const [paymentDate, setPaymentDate] = useState('')
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
    return currentList
      .filter(p => {
        const matchesDate = !paymentDate || (p.created_at && p.created_at.startsWith(paymentDate))
        const matchesUser = !paymentSalesperson || (p.user_name && p.user_name.toLowerCase() === paymentSalesperson.toLowerCase())
        return matchesDate && matchesUser
      })
      .sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0
        return dateB - dateA
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
                        <td className="py-4 px-5 min-w-[220px]">
                          <div className="font-extrabold text-foreground">
                            {p.ledger_name || 'Unknown Party'}
                          </div>
                          {p.comments && (
                            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1 italic">
                              Note: "{p.comments}"
                            </p>
                          )}
                          {p.review_comment && (
                            <div className="mt-1.5 inline-flex items-start gap-1.5 text-[11px] bg-muted/60 border border-border/80 px-2.5 py-1 rounded-lg text-foreground max-w-sm">
                              <MessageSquare className="h-3 w-3 mt-0.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                              <span className="break-words">
                                <strong className="text-[10px] uppercase font-bold text-muted-foreground mr-1">Review:</strong>
                                {p.review_comment}
                              </span>
                            </div>
                          )}
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
                                onClick={() => openReviewModal(p, 'success')}
                                className="border border-emerald-500/30 bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-600 dark:hover:text-white rounded-xl px-3 py-1.5 text-xs font-bold transition-all shadow-xs cursor-pointer flex items-center gap-1"
                                title="Approve Payment"
                              >
                                <Check className="h-3.5 w-3.5" /> Approve
                              </button>
                              <button
                                onClick={() => openReviewModal(p, 'cancelled')}
                                className="border border-rose-500/20 text-rose-600 hover:bg-rose-500 hover:text-white dark:border-rose-500/30 dark:hover:bg-rose-600 rounded-xl px-2.5 py-1.5 text-xs font-bold transition-all cursor-pointer"
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

                  {p.review_comment && (
                    <div className="text-[11px] bg-muted/50 border border-border/80 text-foreground p-2.5 rounded-xl leading-relaxed flex items-start gap-2">
                      <MessageSquare className="h-3.5 w-3.5 mt-0.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <span className="font-bold text-[10px] uppercase tracking-wider text-muted-foreground block mb-0.5">Review Comment</span>
                        <p className="text-foreground font-medium break-words">{p.review_comment}</p>
                      </div>
                    </div>
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
                          onClick={() => openReviewModal(p, 'success')}
                          className="border border-emerald-500/30 bg-emerald-50 text-emerald-700 hover:bg-emerald-600 hover:text-white rounded-xl px-3 py-1 text-xs font-bold transition-all cursor-pointer shadow-xs flex items-center gap-1"
                        >
                          <Check className="h-3 w-3" /> Approve
                        </button>
                        <button
                          onClick={() => openReviewModal(p, 'cancelled')}
                          className="border border-rose-500/20 text-rose-600 hover:bg-rose-500 hover:text-white rounded-xl px-2 py-1 text-xs font-bold transition-all cursor-pointer"
                          title="Reject Payment"
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

      {/* Review Comment Modal (Mandatory for Approval and Rejection) */}
      {reviewTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={cn(
                  'w-10 h-10 rounded-2xl flex items-center justify-center shrink-0',
                  reviewTarget.action === 'success' 
                    ? 'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400' 
                    : 'bg-rose-500/10 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400'
                )}>
                  {reviewTarget.action === 'success' ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    <XCircle className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground">
                    {reviewTarget.action === 'success' ? 'Approve Payment' : 'Reject Payment'}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {reviewTarget.action === 'success' 
                      ? 'Confirm collection verification with a comment' 
                      : 'State the rejection reason for this payment'}
                  </p>
                </div>
              </div>
              <button
                onClick={closeReviewModal}
                disabled={reviewSubmitting}
                className="text-muted-foreground hover:text-foreground p-1 rounded-lg transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Payment Summary Box */}
            <div className="bg-muted/40 border border-border/80 rounded-2xl p-3.5 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground font-medium">Party:</span>
                <span className="font-bold text-foreground truncate max-w-[200px]">
                  {reviewTarget.payment.ledger_name || 'Unknown Party'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground font-medium">Amount:</span>
                <span className="font-black text-sm text-emerald-600 dark:text-emerald-400 font-mono">
                  ₹{reviewTarget.payment.amount.toLocaleString('en-IN')}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground font-medium">Mode:</span>
                <span className="font-semibold text-foreground">
                  {reviewTarget.payment.payment_mode}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground font-medium">Collected By:</span>
                <span className="font-semibold text-foreground">
                  {reviewTarget.payment.user_name || 'Salesperson'}
                </span>
              </div>
              {reviewTarget.payment.comments && (
                <div className="pt-2 border-t border-border/60 text-[11px] text-muted-foreground italic">
                  Note: "{reviewTarget.payment.comments}"
                </div>
              )}
            </div>

            {/* Review Comment Input */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-foreground">
                Review Comment <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={3}
                value={reviewComment}
                onChange={(e) => {
                  setReviewComment(e.target.value)
                  if (reviewError) setReviewError('')
                }}
                placeholder={
                  reviewTarget.action === 'success'
                    ? 'e.g. Verified in bank statement / Cheque deposited in HDFC'
                    : 'e.g. Cheque bounced / Amount mismatch with bank entry'
                }
                className="w-full bg-background border border-border rounded-xl p-3 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none"
                autoFocus
              />
              <div className="flex items-center justify-between text-[11px]">
                {reviewError ? (
                  <span className="text-rose-500 font-semibold flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" /> {reviewError}
                  </span>
                ) : (
                  <span className="text-muted-foreground">Mandatory for approval & rejection</span>
                )}
                <span className="text-muted-foreground/80 font-mono">
                  {reviewComment.trim().length} chars
                </span>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={closeReviewModal}
                disabled={reviewSubmitting}
                className="px-4 py-2 border border-border hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReview}
                disabled={reviewSubmitting || reviewComment.trim().length === 0}
                className={cn(
                  'px-5 py-2 rounded-xl text-xs font-bold text-white transition-all shadow-md cursor-pointer flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed',
                  reviewTarget.action === 'success'
                    ? 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/20'
                    : 'bg-rose-600 hover:bg-rose-700 shadow-rose-500/20'
                )}
              >
                {reviewSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {reviewTarget.action === 'success' ? 'Confirm Approval' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

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
