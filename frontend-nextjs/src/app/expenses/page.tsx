'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { Wallet, Plus, X, Camera, Clock, CheckCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type Expense = {
  id: number
  amount: number
  date: string
  category: string
  payment_mode: string
  narration: string
  status: string
  receipt_photo_url?: string
}

const CATEGORIES = ['Travel', 'Food', 'Petrol', 'Toll', 'Accommodation', 'Stationery', 'Other']
const MODES = ['Cash', 'Bank', 'Online']

export default function ExpensesPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [category, setCategory] = useState('Travel')
  const [mode, setMode] = useState('Cash')
  const [narration, setNarration] = useState('')
  const [refNo, setRefNo] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)

  const fetchExpenses = async () => {
    const data = await fetch(`${API_BASE}/expenses`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => [])
    setExpenses(Array.isArray(data) ? data : (data?.data ?? []))
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showExpenses && !permissions.isAdmin) { router.replace('/'); return }
    fetchExpenses().finally(() => setLoading(false))
  }, [user, token, router, permissions])

  const handlePhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader(); reader.onload = ev => setPhoto(ev.target?.result as string); reader.readAsDataURL(file)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || parseFloat(amount) <= 0) { setError('Enter a valid amount.'); return }
    setSubmitting(true); setError(''); setSuccess('')
    try {
      const res = await fetch(`${API_BASE}/expenses`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ amount: parseFloat(amount), date, category, payment_mode: mode, narration, reference_no: refNo, photo_base64: photo }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setSuccess('Expense submitted!'); setShowForm(false); setAmount(''); setNarration(''); setRefNo(''); setPhoto(null)
      await fetchExpenses()
    } catch (err: any) { setError(err.message) } finally { setSubmitting(false) }
  }

  const statusIcon = (s: string) => s === 'approved' ? <CheckCircle className="h-4 w-4 text-emerald-600" /> : s === 'rejected' ? <XCircle className="h-4 w-4 text-destructive" /> : <Clock className="h-4 w-4 text-amber-500" />
  const statusColor = (s: string) => s === 'approved' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : s === 'rejected' ? 'bg-destructive/10 text-destructive' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-3 border-b border-border flex items-center justify-between">
        <h1 className="text-xl font-extrabold flex items-center gap-2"><Wallet className="h-5 w-5 text-purple-500" /> Expenses</h1>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-1.5 px-3 py-2 bg-primary text-white rounded-xl text-xs font-bold">
          {showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />} {showForm ? 'Close' : 'New Claim'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2 space-y-3">
        {success && <div className="p-3 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 text-sm">{success}</div>}
        {error && <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-sm">{error}</div>}

        {showForm && (
          <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-4 space-y-3">
            <h2 className="font-bold text-sm">Submit Expense Claim</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase">Amount (₹)</label>
                <input type="number" min="0" step="0.01" placeholder="0.00" value={amount} onChange={e => setAmount(e.target.value)} className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase">Date</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase">Category</label>
                <select className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" value={category} onChange={e => setCategory(e.target.value)}>
                  {CATEGORIES.map(c => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase">Mode</label>
                <select className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" value={mode} onChange={e => setMode(e.target.value)}>
                  {MODES.map(m => <option key={m}>{m}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase">Narration</label>
              <input type="text" placeholder="Description..." value={narration} onChange={e => setNarration(e.target.value)} className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase">Receipt Photo</label>
              {photo ? (
                <div className="relative rounded-xl overflow-hidden border border-border mt-1"><img src={photo} alt="receipt" className="w-full h-28 object-cover" /><button type="button" onClick={() => setPhoto(null)} className="absolute top-2 right-2 bg-black/60 text-white rounded-full p-1"><X className="h-3 w-3" /></button></div>
              ) : (
                <label className="mt-1 w-full flex items-center justify-center gap-2 py-3 rounded-xl border-2 border-dashed border-border hover:border-primary/50 cursor-pointer text-xs text-muted-foreground">
                  <Camera className="h-4 w-4" />Upload receipt
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handlePhoto} />
                </label>
              )}
            </div>
            <button type="submit" disabled={submitting} className="w-full py-3 bg-primary text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50">
              {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}Submit Claim
            </button>
          </form>
        )}

        {loading ? (
          <div className="flex justify-center py-8"><div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" /></div>
        ) : expenses.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground"><Wallet className="h-10 w-10 mx-auto mb-3 opacity-30" /><p className="text-sm">No expense claims yet</p></div>
        ) : (
          <div className="space-y-2">
            {expenses.map(e => (
              <div key={e.id} className="bg-card border border-border rounded-2xl p-4 flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">{statusIcon(e.status)}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm">{e.category}</p>
                  <p className="text-xs text-muted-foreground">{e.payment_mode} • {formatDate(e.date)}</p>
                  {e.narration && <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">{e.narration}</p>}
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-sm">{formatCurrency(e.amount)}</p>
                  <span className={cn('text-[10px] font-bold px-1.5 py-0.5 rounded-full capitalize', statusColor(e.status))}>{e.status}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
