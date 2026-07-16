'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { IndianRupee, Clock, CheckCircle, XCircle, Plus, X, Camera } from 'lucide-react'
import { cn } from '@/lib/utils'

type Payment = {
  id: number
  ledger_name?: string
  amount: number
  payment_mode: string
  status: string
  comments?: string
  created_at: string
}

type Ledger = { ledger_id: number; name: string }

const MODES = ['Cash', 'Cheque', 'Online']

export default function PaymentsPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  const [payments, setPayments] = useState<Payment[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [ledgerId, setLedgerId] = useState('')
  const [amount, setAmount] = useState('')
  const [mode, setMode] = useState('Cash')
  const [comments, setComments] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)

  const fetchData = async () => {
    const [ps, ls] = await Promise.all([
      fetch(`${API_BASE}/payment/history`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
    ])
    setPayments(Array.isArray(ps) ? ps : (ps?.data ?? []))
    setLedgers(Array.isArray(ls) ? ls.slice(0, 200) : [])
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchData().finally(() => setLoading(false))
  }, [user, token, router])

  const handlePhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return
    const reader = new FileReader(); reader.onload = ev => setPhoto(ev.target?.result as string); reader.readAsDataURL(file)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ledgerId || !amount || parseFloat(amount) <= 0) { setError('Select a party and enter a valid amount.'); return }
    setSubmitting(true); setError(''); setSuccess('')
    try {
      const res = await fetch(`${API_BASE}/payment/collect`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ ledger_id: parseInt(ledgerId), amount: parseFloat(amount), payment_mode: mode, comments, photo_base64: photo }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setSuccess('Payment recorded!'); setShowForm(false); setLedgerId(''); setAmount(''); setMode('Cash'); setComments(''); setPhoto(null)
      await fetchData()
    } catch (err: any) { setError(err.message) } finally { setSubmitting(false) }
  }

  const statusIcon = (s: string) => {
    if (s === 'success') return <CheckCircle className="h-4 w-4 text-emerald-600" />
    if (s === 'cancelled') return <XCircle className="h-4 w-4 text-destructive" />
    return <Clock className="h-4 w-4 text-amber-500" />
  }

  const statusColor = (s: string) => s === 'success' ? 'text-emerald-600' : s === 'cancelled' ? 'text-destructive' : 'text-amber-500'

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-3 border-b border-border flex items-center justify-between">
        <h1 className="text-xl font-extrabold flex items-center gap-2"><IndianRupee className="h-5 w-5 text-teal-500" /> Payments</h1>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-1.5 px-3 py-2 bg-primary text-white rounded-xl text-xs font-bold">
          {showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {showForm ? 'Close' : 'New'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2 space-y-4">
        {success && <div className="p-3 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-sm">{success}</div>}
        {error && <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-sm">{error}</div>}

        {showForm && (
          <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-4 space-y-3">
            <h2 className="font-bold text-sm">Record Payment</h2>
            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Party / Ledger</label>
              <select className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" value={ledgerId} onChange={e => setLedgerId(e.target.value)}>
                <option value="">— Select Party —</option>
                {ledgers.map(l => <option key={l.ledger_id} value={l.ledger_id}>{l.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Amount (₹)</label>
                <input type="number" min="0" step="0.01" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0.00" className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Mode</label>
                <select className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" value={mode} onChange={e => setMode(e.target.value)}>
                  {MODES.map(m => <option key={m}>{m}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Comments</label>
              <input type="text" value={comments} onChange={e => setComments(e.target.value)} placeholder="Optional notes..." className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Proof Photo (Optional)</label>
              {photo ? (
                <div className="relative rounded-xl overflow-hidden border border-border mt-1"><img src={photo} alt="proof" className="w-full h-28 object-cover" /><button type="button" onClick={() => setPhoto(null)} className="absolute top-2 right-2 bg-black/60 text-white rounded-full p-1 text-xs"><X className="h-3 w-3" /></button></div>
              ) : (
                <label className="mt-1 w-full flex items-center justify-center gap-2 py-3 rounded-xl border-2 border-dashed border-border hover:border-primary/50 cursor-pointer text-xs text-muted-foreground">
                  <Camera className="h-4 w-4" />Capture receipt
                  <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handlePhoto} />
                </label>
              )}
            </div>
            <button type="submit" disabled={submitting} className="w-full py-3 bg-primary text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50">
              {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              Record Payment
            </button>
          </form>
        )}

        {loading ? (
          <div className="flex justify-center py-8"><div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" /></div>
        ) : payments.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground"><IndianRupee className="h-10 w-10 mx-auto mb-3 opacity-30" /><p className="text-sm">No payments recorded yet</p></div>
        ) : (
          <div className="space-y-2">
            {payments.map(p => (
              <div key={p.id} className="bg-card border border-border rounded-2xl p-4 flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center">{statusIcon(p.status)}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm">{p.ledger_name || 'Unknown Party'}</p>
                  <p className="text-xs text-muted-foreground">{p.payment_mode} • {formatDate(p.created_at)}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-sm">{formatCurrency(p.amount)}</p>
                  <p className={cn('text-[10px] font-bold capitalize', statusColor(p.status))}>{p.status}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
