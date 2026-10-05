'use client'

import { useState } from 'react'
import {
  AlertTriangle,
  Bell,
  Check,
  ClipboardCheck,
  Clock,
  Loader2,
  MapPin,
  MapPinOff,
  ShieldAlert,
  ShoppingCart,
  Wallet,
  X,
  type LucideIcon,
} from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { cn } from '@/lib/utils'
import {
  announceNotificationsChanged,
  decide,
  formatTimeAgo,
  needsDecision,
  type AppNotification,
} from '@/lib/notifications'

const CATEGORY_LOOK: Record<string, { icon: LucideIcon; tone: string }> = {
  approvals: { icon: ClipboardCheck, tone: 'bg-amber-500/15 text-amber-700 dark:text-amber-400' },
  attendance: { icon: Clock, tone: 'bg-purple-500/15 text-purple-700 dark:text-purple-400' },
  orders: { icon: ShoppingCart, tone: 'bg-sky-500/15 text-sky-700 dark:text-sky-400' },
  expenses: { icon: Wallet, tone: 'bg-amber-500/15 text-amber-700 dark:text-amber-400' },
  visits: { icon: MapPin, tone: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400' },
  alerts: { icon: MapPinOff, tone: 'bg-rose-500/15 text-rose-700 dark:text-rose-400' },
  security: { icon: ShieldAlert, tone: 'bg-rose-500/15 text-rose-700 dark:text-rose-400' },
}

function lookOf(n: AppNotification) {
  if (n.title.toLowerCase().includes('discrepancy')) {
    return { icon: AlertTriangle, tone: 'bg-rose-500/15 text-rose-700 dark:text-rose-400' }
  }
  return CATEGORY_LOOK[n.category] ?? { icon: Bell, tone: 'bg-muted text-muted-foreground' }
}

interface NotificationListProps {
  items: AppNotification[]
  onOpen: (n: AppNotification) => void
  onMarkRead: (n: AppNotification) => void
  onDelete: (n: AppNotification) => void
  /** Called after an approval was decided here, with the new state */
  onDecided: (n: AppNotification, decision: 'approved' | 'rejected') => void
  /** Tighter spacing for the bell dropdown */
  compact?: boolean
}

/**
 * Notification rows. Each row is a button that opens the notification; read/dismiss and, for approvals,
 * Approve/Reject sit beside it so they never trigger the row.
 */
export function NotificationList({ items, onOpen, onMarkRead, onDelete, onDecided, compact }: NotificationListProps) {
  const { token, user } = useAuth()
  const [busyId, setBusyId] = useState<number | null>(null)
  const [rejecting, setRejecting] = useState<AppNotification | null>(null)
  const [reason, setReason] = useState('')

  const companyName = (id: number) => user?.allowedCompanies?.find(c => c.company_id === id)?.name

  const runDecision = async (n: AppNotification, decision: 'approve' | 'reject', why?: string) => {
    if (!token) return
    setBusyId(n.id)
    try {
      await decide(token, n, decision, why)
      const outcome = decision === 'approve' ? 'approved' : 'rejected'
      toast.success(decision === 'approve' ? 'Approved' : 'Rejected')
      onDecided(n, outcome)
      announceNotificationsChanged()
      setRejecting(null)
      setReason('')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save the decision')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <>
      <ul className="divide-y divide-border/60">
        {items.map(n => {
          const { icon: Icon, tone } = lookOf(n)
          const otherCompany = user && n.company_id !== user.company_id ? companyName(n.company_id) : null
          const busy = busyId === n.id
          return (
            <li key={n.id} className={cn('group relative', !n.is_read && 'bg-primary/5')}>
              <div className="flex items-start">
                <button
                  type="button"
                  onClick={() => onOpen(n)}
                  className={cn(
                    'flex min-w-0 flex-1 items-start gap-3 text-left transition-colors hover:bg-muted/60 cursor-pointer',
                    compact ? 'p-3' : 'p-3.5 sm:p-4',
                  )}
                >
                  <span className={cn('mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', tone)}>
                    <Icon className="h-4.5 w-4.5" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className={cn('text-sm leading-snug', n.is_read ? 'font-medium text-foreground/85' : 'font-bold text-foreground')}>
                        {n.title}
                      </span>
                      <span className="mt-0.5 shrink-0 whitespace-nowrap text-xs text-muted-foreground">
                        {formatTimeAgo(n.created_at)}
                      </span>
                    </span>
                    <span className="mt-0.5 block text-xs leading-snug text-muted-foreground line-clamp-2 break-words">
                      {n.message}
                    </span>
                    {(otherCompany || n.decision === 'approved' || n.decision === 'rejected') && (
                      <span className="mt-1.5 flex flex-wrap gap-1.5">
                        {otherCompany && (
                          <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
                            {otherCompany}
                          </span>
                        )}
                        {n.decision === 'approved' && (
                          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                            Approved
                          </span>
                        )}
                        {n.decision === 'rejected' && (
                          <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-400">
                            Rejected
                          </span>
                        )}
                      </span>
                    )}
                    {!n.is_read && <span className="sr-only">Unread</span>}
                  </span>
                </button>
                <div className={cn('flex shrink-0 flex-col items-center', compact ? 'py-2 pr-1.5' : 'py-2.5 pr-2')}>
                  {!n.is_read && (
                    <button
                      type="button"
                      onClick={() => onMarkRead(n)}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-full text-emerald-600 hover:bg-emerald-500/15 dark:text-emerald-400 cursor-pointer"
                      aria-label={`Mark "${n.title}" as read`}
                      title="Mark as read"
                    >
                      <Check className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => onDelete(n)}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground hover:bg-rose-500/15 hover:text-rose-600 cursor-pointer"
                    aria-label={`Dismiss "${n.title}"`}
                    title="Dismiss"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {needsDecision(n) && (
                <div className={cn('flex gap-2 pb-3', compact ? 'pl-15 pr-3' : 'pl-15 pr-4 sm:pl-16')}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => runDecision(n, 'approve')}
                    className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-xl bg-emerald-600 px-3 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-60 cursor-pointer"
                  >
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => { setRejecting(n); setReason('') }}
                    className="inline-flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-xl border border-border px-3 text-sm font-bold text-rose-600 hover:bg-rose-500/10 disabled:opacity-60 dark:text-rose-400 cursor-pointer"
                  >
                    <X className="h-4 w-4" />
                    Reject
                  </button>
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <BottomSheet
        open={rejecting !== null}
        onOpenChange={open => { if (!open) setRejecting(null) }}
        title="Reject request"
        description={rejecting?.message}
        footer={
          <button
            type="button"
            disabled={busyId !== null}
            onClick={() => rejecting && runDecision(rejecting, 'reject', reason.trim())}
            className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-rose-600 text-sm font-bold text-white hover:bg-rose-700 disabled:opacity-60 cursor-pointer"
          >
            {busyId !== null && <Loader2 className="h-4 w-4 animate-spin" />}
            Reject
          </button>
        }
      >
        <label className="block">
          <span className="mb-1.5 block text-sm font-semibold text-foreground">Reason (optional)</span>
          <textarea
            value={reason}
            onChange={e => setReason(e.target.value)}
            rows={3}
            placeholder="Shown to the employee"
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </label>
      </BottomSheet>
    </>
  )
}
