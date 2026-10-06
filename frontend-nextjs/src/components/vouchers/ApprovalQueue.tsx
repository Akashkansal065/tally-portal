'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Check, ClipboardCheck, Loader2, Undo2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { approve, getRequests, reject, type ApprovalItem } from '@/lib/approvals'

const rupees = (n: number) => `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : '')

/**
 * Vouchers page: vouchers waiting for this person's approval, and their own vouchers that are waiting or were sent
 * back. Renders nothing when there's nothing to show.
 */
export function ApprovalQueue({ token, focus }: { token: string; focus?: boolean }) {
  const [toMe, setToMe] = useState<ApprovalItem[]>([])
  const [mine, setMine] = useState<ApprovalItem[]>([])
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<number | null>(null)
  const [note, setNote] = useState('')

  useEffect(() => {
    let current = true
    Promise.all([getRequests(token, 'to_me'), getRequests(token, 'mine', 'all')])
      .then(([a, b]) => { if (current) { setToMe(a); setMine(b.filter(i => i.status !== 'Approved')) } })
      .catch(() => {})
    return () => { current = false }
  }, [token, reload])

  if (toMe.length === 0 && mine.length === 0) return null

  const act = async (item: ApprovalItem, kind: 'approve' | 'reject') => {
    setBusy(item.request_id)
    try {
      const r = kind === 'approve' ? await approve(token, item.request_id) : await reject(token, item.request_id, note)
      toast.success(r.detail)
      setRejecting(null)
      setNote('')
      setReload(k => k + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section id="approvals" aria-labelledby="approvals-title"
      className={cn('space-y-3 rounded-2xl border bg-card p-4 shadow-sm', focus ? 'border-primary ring-2 ring-primary/20' : 'border-border')}>
      <h2 id="approvals-title" className="flex items-center gap-1.5 text-sm font-bold"><ClipboardCheck className="h-4 w-4" /> Approvals</h2>
      {toMe.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">Waiting for you ({toMe.length})</p>
          <ul className="divide-y divide-border">
            {toMe.map(item => (
              <li key={item.request_id} className="space-y-2 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/vouchers/${item.voucher_id}`} className="min-w-0 hover:underline">
                    <p className="text-sm font-semibold">{item.voucher_type} {item.voucher_number}{item.party ? ` · ${item.party}` : ''}</p>
                    <p className="text-xs text-muted-foreground">By {item.requested_by} · {day(item.requested_at)}</p>
                  </Link>
                  <span className="shrink-0 text-sm font-bold tabular-nums">{rupees(item.amount)}</span>
                </div>
                {rejecting === item.request_id ? (
                  <div className="flex gap-2">
                    <input autoFocus value={note} onChange={e => setNote(e.target.value)} placeholder="What needs changing?" aria-label="Reason for sending it back"
                      className="h-10 min-w-0 flex-1 rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30" />
                    <button type="button" disabled={busy !== null || !note.trim()} onClick={() => act(item, 'reject')}
                      className="min-h-10 rounded-xl bg-rose-600 px-3 text-sm font-semibold text-white disabled:opacity-50 cursor-pointer">
                      {busy === item.request_id ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Send back'}
                    </button>
                    <button type="button" onClick={() => { setRejecting(null); setNote('') }} className="min-h-10 rounded-xl px-2 text-sm text-muted-foreground hover:bg-muted cursor-pointer">Cancel</button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button type="button" disabled={busy !== null} onClick={() => act(item, 'approve')}
                      className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-emerald-600 px-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50 cursor-pointer">
                      {busy === item.request_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Approve
                    </button>
                    <button type="button" disabled={busy !== null} onClick={() => setRejecting(item.request_id)}
                      className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted disabled:opacity-50 cursor-pointer">
                      <Undo2 className="h-4 w-4" /> Send back
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {mine.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">Your vouchers</p>
          <ul className="divide-y divide-border">
            {mine.map(item => (
              <li key={item.request_id} className="py-2">
                <Link href={`/vouchers/${item.voucher_id}`} className="flex items-start justify-between gap-2 hover:underline">
                  <span className="min-w-0 text-sm">
                    <span className="font-semibold">{item.voucher_type} {item.voucher_number}</span>
                    {item.status === 'Rejected'
                      ? <span className="block text-xs text-rose-700 dark:text-rose-300">Sent back by {item.acted_by}: {item.note}</span>
                      : <span className="block text-xs text-muted-foreground">Waiting for approval</span>}
                  </span>
                  <span className="shrink-0 text-sm font-bold tabular-nums">{rupees(item.amount)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
