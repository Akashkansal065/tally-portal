'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import {
  Wallet,
  Plus,
  X,
  Camera,
  Clock,
  Check,
  XCircle,
  ChevronLeft,
  ListTodo,
  BarChart3,
  Calendar,
  CheckCircle2
} from 'lucide-react'
import { cn } from '@/lib/utils'

type Expense = {
  id: number
  amount: number
  date: string
  category: string
  payment_mode: string
  narration: string
  status: 'pending' | 'approved' | 'rejected'
  receipt_photo_url?: string
  salesperson?: string
  user_id?: number
}

const CATEGORIES = ['Travel', 'Food', 'Petrol', 'Toll', 'Accommodation', 'Stationery', 'Other']
const MODES = ['Cash', 'Bank', 'Online']

export default function ExpensesPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'claims' | 'analytics'>('claims')
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Form states
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [category, setCategory] = useState('Travel')
  const [mode, setMode] = useState('Cash')
  const [narration, setNarration] = useState('')
  const [refNo, setRefNo] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)

  // Zoomed image modal state
  const [selectedReceipt, setSelectedReceipt] = useState<string | null>(null)

  // Admin approval/rejection remarks
  const [rejectingExpenseId, setRejectingExpenseId] = useState<number | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const fetchExpenses = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/expenses`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setExpenses(Array.isArray(data) ? data : (data?.data ?? []))
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showExpenses && !permissions.isAdmin) { router.replace('/'); return }
    fetchExpenses()
  }, [user, token, router, permissions])

  const handlePhotoCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setProcessingPhoto(true)
    setError('')
    try {
      const result = await stampPhoto(file)
      setPhoto(result.photoBase64)
    } catch (err: any) {
      setError(err.message || 'Failed to capture stamped location metadata.')
    } finally {
      setProcessingPhoto(false)
    }
  }

  const handleSubmitClaim = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || parseFloat(amount) <= 0) { setError('Enter a valid amount.'); return }
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const res = await fetch(`${API_BASE}/expenses`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          amount: parseFloat(amount),
          date,
          category,
          payment_mode: mode,
          narration,
          reference_no: refNo,
          photo_base64: photo
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setSuccess('Expense claim submitted successfully!')
      setShowForm(false)
      setAmount('')
      setNarration('')
      setRefNo('')
      setPhoto(null)
      await fetchExpenses()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleApproveStatus = async (expenseId: number, status: 'approved' | 'rejected', reason?: string) => {
    try {
      const res = await fetch(`${API_BASE}/expenses/${expenseId}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ status, cancel_reason: reason || null })
      })
      if (!res.ok) throw new Error('Failed to update status')
      setExpenses(prev => prev.map(e => e.id === expenseId ? { ...e, status } : e))
      setRejectingExpenseId(null)
      setRejectReason('')
    } catch (err: any) {
      alert(err.message)
    }
  }

  // Client side analytics calculations
  const analytics = useMemo(() => {
    let totalSpend = 0
    const catTotals: Record<string, number> = {}
    const statusCounts: Record<string, { count: number; total: number }> = {
      approved: { count: 0, total: 0 },
      pending: { count: 0, total: 0 },
      rejected: { count: 0, total: 0 }
    }

    expenses.forEach(e => {
      const amt = Number(e.amount)
      totalSpend += amt

      catTotals[e.category] = (catTotals[e.category] || 0) + amt

      const st = e.status || 'pending'
      if (!statusCounts[st]) {
        statusCounts[st] = { count: 0, total: 0 }
      }
      statusCounts[st].count++
      statusCounts[st].total += amt
    })

    const categoryBreakdown = Object.keys(catTotals).map(cat => ({
      category: cat,
      total: catTotals[cat],
      percentage: totalSpend > 0 ? Math.round((catTotals[cat] / totalSpend) * 100) : 0
    })).sort((a, b) => b.total - a.total)

    return {
      totalSpend,
      categoryBreakdown,
      statusCounts
    }
  }, [expenses])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Main Container */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        {/* Title and CTA */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-1.5 text-foreground">
              <Wallet className="h-5.5 w-5.5 text-purple-500" /> Expense Claims
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Submit and review business reimbursement requests</p>
          </div>
          <button
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 cursor-pointer"
          >
            {showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />} {showForm ? 'Close' : 'New Claim'}
          </button>
        </div>

        {/* Tab Selection */}
        {!showForm && (
          <div className="grid w-full grid-cols-2 bg-muted/40 p-1 rounded-xl border border-border/80 h-10 items-center">
            <button
              onClick={() => setActiveTab('claims')}
              className={cn(
                'h-8 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5',
                activeTab === 'claims'
                  ? 'bg-emerald-500 text-white shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <ListTodo className="h-3.5 w-3.5" /> Claims Log
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={cn(
                'h-8 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5',
                activeTab === 'analytics'
                  ? 'bg-emerald-500 text-white shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <BarChart3 className="h-3.5 w-3.5" /> Analytics
            </button>
          </div>
        )}

        {success && <div className="p-3.5 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold">{success}</div>}
        {error && <div className="p-3.5 rounded-2xl bg-destructive/10 text-destructive text-xs font-bold">{error}</div>}

        {/* Create Form */}
        {showForm && (
          <form onSubmit={handleSubmitClaim} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
            <h2 className="font-extrabold text-sm text-foreground">Log Expense Claim</h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Amount (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={amount}
                  required
                  onChange={e => setAmount(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Date</label>
                <input
                  type="date"
                  value={date}
                  required
                  onChange={e => setDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Payment Mode</label>
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  {MODES.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Narration Description</label>
              <textarea
                placeholder="What was this expense spent on?"
                value={narration}
                onChange={e => setNarration(e.target.value)}
                rows={2}
                className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
              />
            </div>

            {/* Receipt Photo Stamping */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Receipt Photo Proof</label>
              {photo ? (
                <div className="relative rounded-xl overflow-hidden border border-border mt-1 shadow-sm">
                  <img src={photo} alt="receipt preview" className="w-full h-32 object-cover" />
                  <button
                    type="button"
                    onClick={() => setPhoto(null)}
                    className="absolute top-2.5 right-2.5 bg-black/75 hover:bg-black text-white rounded-full p-2 text-xs transition-colors cursor-pointer"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <label className="mt-1.5 w-full flex flex-col items-center justify-center gap-1.5 py-6 rounded-2xl border-2 border-dashed border-border hover:border-emerald-500/50 cursor-pointer text-xs text-muted-foreground transition-all">
                  {processingPhoto ? (
                    <>
                      <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                      <span className="font-bold">Encoding camera metadata...</span>
                    </>
                  ) : (
                    <>
                      <Camera className="h-5 w-5 opacity-70 text-muted-foreground" />
                      <span className="font-bold">Capture Stamped Receipt</span>
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="hidden"
                        onChange={handlePhotoCapture}
                      />
                    </>
                  )}
                </label>
              )}
            </div>

            <button
              type="submit"
              disabled={submitting || processingPhoto}
              className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50 transition-all shadow-md cursor-pointer"
            >
              {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              Submit Reimbursement Claim
            </button>
          </form>
        )}

        {/* Claims Log view */}
        {!showForm && activeTab === 'claims' && (
          <div className="space-y-3">
            {loading ? (
              <div className="flex justify-center py-10">
                <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : expenses.length === 0 ? (
              <div className="text-center py-12 bg-card border border-border rounded-2xl border-dashed">
                <Wallet className="h-10 w-10 mx-auto mb-3 opacity-25 text-muted-foreground" />
                <p className="text-sm font-bold text-muted-foreground">No claims log found</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Submit your first expense claim above</p>
              </div>
            ) : (
              expenses.map(e => (
                <div key={e.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm hover:border-emerald-500/30 transition-all flex flex-col gap-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-extrabold text-sm text-foreground">{e.category}</h3>
                      <div className="flex gap-2 items-center mt-1 text-[10px] text-muted-foreground font-semibold">
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(e.date)}</span>
                        {permissions.isAdmin && e.salesperson && (
                          <span className="flex items-center gap-1 uppercase bg-muted px-1.5 py-0.5 rounded tracking-wider text-[8px]">
                            {e.salesperson}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-black text-sm text-emerald-600 dark:text-emerald-400 font-mono">
                        ₹{Number(e.amount).toLocaleString('en-IN')}
                      </p>
                      <span className={cn(
                        'inline-flex mt-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full capitalize border',
                        e.status === 'approved' && 'bg-green-500/10 text-green-600 border-green-500/20',
                        e.status === 'rejected' && 'bg-red-500/10 text-red-600 border-red-500/20',
                        e.status === 'pending' && 'bg-amber-500/10 text-amber-600 border-amber-500/20'
                      )}>
                        {e.status}
                      </span>
                    </div>
                  </div>

                  {e.narration && (
                    <p className="text-[11px] text-muted-foreground bg-muted/20 p-2.5 rounded-xl border border-border/40 leading-relaxed font-medium">
                      {e.narration}
                    </p>
                  )}

                  <div className="flex items-center justify-between border-t border-border/40 pt-3 mt-1.5 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <span className="font-extrabold text-[9px] uppercase tracking-wider">Proof:</span>
                      {e.receipt_photo_url ? (
                        <button
                          onClick={() => setSelectedReceipt(e.receipt_photo_url || null)}
                          className="text-emerald-500 hover:text-emerald-600 font-bold underline flex items-center gap-0.5 cursor-pointer"
                        >
                          <Camera className="h-3.5 w-3.5" /> View Receipt
                        </button>
                      ) : (
                        <span className="text-[11px] italic">N/A</span>
                      )}
                    </div>

                    {permissions.isAdmin && e.status === 'pending' && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleApproveStatus(e.id, 'approved')}
                          className="h-8 w-8 bg-green-500/10 hover:bg-green-500 text-green-600 hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-green-500/20"
                          title="Approve Claim"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setRejectingExpenseId(e.id)}
                          className="h-8 w-8 bg-destructive/10 hover:bg-destructive text-destructive hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-destructive/20"
                          title="Reject Claim"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Analytics dashboard view */}
        {!showForm && activeTab === 'analytics' && (
          <div className="space-y-4">
            {/* Spend summary card */}
            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm flex flex-col justify-center items-center text-center">
              <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Claims Spending</span>
              <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1 font-mono">
                ₹{analytics.totalSpend.toLocaleString('en-IN')}
              </span>
              <p className="text-[10px] text-muted-foreground mt-1">Aggregated across all registered claims in cache</p>
            </div>

            {/* Status breakdown grid */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-card border border-border rounded-xl p-3 shadow-sm flex flex-col items-center">
                <span className="text-[9px] font-bold text-green-600 uppercase tracking-wide">Approved</span>
                <span className="text-sm font-black mt-1 font-mono">₹{analytics.statusCounts.approved.total.toLocaleString('en-IN')}</span>
                <span className="text-[9px] text-muted-foreground mt-0.5">{analytics.statusCounts.approved.count} claims</span>
              </div>
              <div className="bg-card border border-border rounded-xl p-3 shadow-sm flex flex-col items-center">
                <span className="text-[9px] font-bold text-amber-500 uppercase tracking-wide">Pending</span>
                <span className="text-sm font-black mt-1 font-mono">₹{analytics.statusCounts.pending.total.toLocaleString('en-IN')}</span>
                <span className="text-[9px] text-muted-foreground mt-0.5">{analytics.statusCounts.pending.count} claims</span>
              </div>
              <div className="bg-card border border-border rounded-xl p-3 shadow-sm flex flex-col items-center">
                <span className="text-[9px] font-bold text-rose-500 uppercase tracking-wide">Rejected</span>
                <span className="text-sm font-black mt-1 font-mono">₹{analytics.statusCounts.rejected.total.toLocaleString('en-IN')}</span>
                <span className="text-[9px] text-muted-foreground mt-0.5">{analytics.statusCounts.rejected.count} claims</span>
              </div>
            </div>

            {/* Category breakdown bar charts */}
            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-4">
              <h3 className="font-extrabold text-sm text-foreground">Spend by Category</h3>
              {analytics.categoryBreakdown.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">No spending data to compute breakdown.</p>
              ) : (
                <div className="space-y-3">
                  {analytics.categoryBreakdown.map(cat => (
                    <div key={cat.category} className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-foreground">{cat.category}</span>
                        <span className="text-muted-foreground font-mono">{formatCurrency(cat.total)} ({cat.percentage}%)</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2 overflow-hidden border border-border/40">
                        <div
                          className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${cat.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="h-16" />
      </div>

      {/* Zoomed Receipt Modal */}
      {selectedReceipt && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="relative max-w-lg w-full bg-card rounded-3xl overflow-hidden shadow-2xl p-2 animate-in zoom-in-95 duration-200">
            <button
              onClick={() => setSelectedReceipt(null)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors z-10 cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
            <img
              src={selectedReceipt}
              alt="Expense Receipt Proof"
              className="w-full h-auto max-h-[80vh] object-contain rounded-2xl"
            />
          </div>
        </div>
      )}

      {/* Reject Reason input dialog */}
      {rejectingExpenseId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-sm rounded-3xl shadow-xl overflow-hidden p-6 space-y-4 animate-in zoom-in-95 duration-200 border border-border/80">
            <h3 className="font-extrabold text-sm text-foreground">Reject Claim Reason</h3>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Cancellation Reason</label>
              <input
                type="text"
                placeholder="Reason details..."
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-muted/40 text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setRejectingExpenseId(null); setRejectReason('') }}
                className="flex-1 py-2.5 border border-border hover:bg-muted text-muted-foreground font-bold rounded-xl text-xs transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => handleApproveStatus(rejectingExpenseId, 'rejected', rejectReason)}
                disabled={!rejectReason.trim()}
                className="flex-1 py-2.5 bg-destructive hover:bg-destructive/95 text-white font-bold rounded-xl text-xs transition-all shadow-md disabled:opacity-50 cursor-pointer"
              >
                Reject Claim
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
