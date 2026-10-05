'use client'

import { useState } from 'react'
import { Loader2, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import { updateReportSettings } from '@/lib/report-insights'

/*
 * Credit days decide when a bill counts as overdue: invoice date + credit days. Tally doesn't hold them for
 * this business, so each customer's value is kept in MyTally, with a default (30) for everyone else.
 */

const PRESETS = [0, 7, 15, 30, 45, 60, 90]

const SOURCE_LABEL: Record<string, string> = {
  customer: 'set for this customer',
  tally: 'from Tally',
  default: 'default',
}

export function CreditDaysLabel({ days, source, isAdmin, onEdit, className, prefix = 'Credit' }: {
  days: number
  source?: string
  isAdmin: boolean
  onEdit: () => void
  className?: string
  /** "Credit" for a customer, "Default credit" for the default */
  prefix?: string
}) {
  const text = `${prefix} ${days}d${source && source !== 'customer' ? ` (${SOURCE_LABEL[source] ?? source})` : ''}`
  if (!isAdmin) return <span className={className}>{text}</span>
  return (
    <button
      type="button"
      onClick={onEdit}
      className={cn('inline-flex min-h-8 items-center gap-1 rounded-md hover:text-foreground hover:underline cursor-pointer', className)}
      title="Change credit days"
    >
      {text}
      <Pencil className="h-3 w-3" aria-hidden="true" />
    </button>
  )
}

/** One sheet for both a customer's credit days and the default. */
export function CreditDaysSheet({ target, defaultDays, token, onClose, onSaved }: {
  /** null: closed. ledgerId null: editing the default */
  target: { ledgerId: number | null; name: string; days: number; source?: string } | null
  defaultDays: number
  token: string
  onClose: () => void
  onSaved: () => void
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const value = draft ?? String(target?.days ?? '')
  const n = Number(value)
  const valid = value !== '' && Number.isInteger(n) && n >= 0 && n <= 365
  const isDefault = target?.ledgerId === null

  const save = async (days: number | null) => {
    if (!target) return
    setSaving(true)
    try {
      if (isDefault) {
        await updateReportSettings(token, { default_credit_days: days ?? 30 })
      } else {
        const res = await fetch(`${API_BASE}/payment/credit-days/${target.ledgerId}`, {
          method: 'PUT',
          headers: authHeaders(token),
          body: JSON.stringify({ credit_days: days }),
        })
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Could not save credit days')
      }
      toast.success('Credit days saved')
      setDraft(null)
      onSaved()
      onClose()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save credit days')
    } finally {
      setSaving(false)
    }
  }

  return (
    <BottomSheet
      open={target !== null}
      onOpenChange={open => { if (!open) { setDraft(null); onClose() } }}
      title={isDefault ? 'Default credit days' : `Credit days · ${target?.name ?? ''}`}
      description={isDefault
        ? 'Used for every customer without their own credit days. A bill is overdue once its date + credit days has passed.'
        : `A bill is overdue once its date + these days has passed. Without a value here, the default (${defaultDays} days) applies.`}
      footer={
        <div className="flex gap-2">
          {!isDefault && target?.source === 'customer' && (
            <button
              type="button"
              disabled={saving}
              onClick={() => save(null)}
              className="min-h-12 flex-1 rounded-xl border border-border text-sm font-bold hover:bg-muted disabled:opacity-60 cursor-pointer"
            >
              Use default ({defaultDays})
            </button>
          )}
          <button
            type="button"
            disabled={!valid || saving}
            onClick={() => save(n)}
            className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </button>
        </div>
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map(p => (
          <button
            key={p}
            type="button"
            aria-pressed={n === p && value !== ''}
            onClick={() => setDraft(String(p))}
            className={cn(
              'min-h-10 min-w-12 rounded-full border px-3 text-sm font-semibold cursor-pointer',
              n === p && value !== '' ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted',
            )}
          >
            {p}
          </button>
        ))}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={365}
            value={value}
            onChange={e => setDraft(e.target.value)}
            aria-label="Credit days"
            className="h-10 w-20 rounded-xl border border-border bg-background px-3 tabular-nums focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          days
        </label>
      </div>
      {!valid && value !== '' && <p className="mt-2 text-sm text-destructive">Enter whole days from 0 to 365.</p>}
    </BottomSheet>
  )
}
