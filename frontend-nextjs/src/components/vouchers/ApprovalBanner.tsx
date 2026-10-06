'use client'

import { useEffect, useState } from 'react'
import { Clock, Loader2, Undo2 } from 'lucide-react'
import { toast } from 'sonner'
import { approve, getVoucherApproval, reject, resubmit, type ApprovalItem } from '@/lib/approvals'

/** Voucher page: "Waiting for approval" / "Sent back", with approve, send back or send again. */
export function ApprovalBanner({ token, voucherId, onChanged }: { token: string; voucherId: number; onChanged?: () => void }) {
  const [item, setItem] = useState<ApprovalItem | null>(null)
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    let current = true
    getVoucherApproval(token, voucherId).then(r => { if (current) setItem(r) }).catch(() => {})
    return () => { current = false }
  }, [token, voucherId, reload])

  if (!item || item.status === 'Approved') return null
  const run = async (action: () => Promise<{ detail: string }>) => {
    setBusy(true)
    try {
      toast.success((await action()).detail)
      setNote('')
      setReload(k => k + 1)
      onChanged?.()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }
  const pending = item.status === 'Pending'

  return (
    <div role="status" className={pending
      ? 'mb-4 space-y-2 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-950 dark:text-amber-100'
      : 'mb-4 space-y-2 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-950 dark:text-rose-100'}>
      <p className="flex items-center gap-1.5 font-semibold">
        {pending ? <Clock className="h-4 w-4" /> : <Undo2 className="h-4 w-4" />}
        {pending ? `Waiting for approval${item.approver_role ? ` (${item.approver_role})` : ''}. It goes to Tally once approved.`
          : `Sent back by ${item.acted_by}: ${item.note}`}
      </p>
      {pending && item.can_decide && (
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={busy} onClick={() => run(() => approve(token, item.request_id))}
            className="min-h-10 rounded-xl bg-emerald-600 px-4 text-sm font-semibold text-white disabled:opacity-50 cursor-pointer">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Approve'}
          </button>
          <input value={note} onChange={e => setNote(e.target.value)} placeholder="What needs changing?" aria-label="Reason for sending it back"
            className="h-10 min-w-0 flex-1 rounded-xl border border-border bg-background px-3 text-sm text-foreground" />
          <button type="button" disabled={busy || !note.trim()} onClick={() => run(() => reject(token, item.request_id, note))}
            className="min-h-10 rounded-xl border border-border bg-background px-3 text-sm font-semibold text-foreground disabled:opacity-50 cursor-pointer">
            Send back
          </button>
        </div>
      )}
      {!pending && item.can_resubmit && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs">Fix it with Alter / Edit, then:</span>
          <button type="button" disabled={busy} onClick={() => run(() => resubmit(token, voucherId))}
            className="min-h-10 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50 cursor-pointer">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Send again'}
          </button>
        </div>
      )}
    </div>
  )
}
