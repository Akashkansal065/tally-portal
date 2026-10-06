'use client'

import { useEffect, useState } from 'react'
import { BellRing, CalendarClock, Check, History, Loader2, Mail, MessageCircle, Pencil, Send } from 'lucide-react'
import { toast } from 'sonner'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { cn } from '@/lib/utils'
import {
  STATUS_LABEL,
  WEEKDAYS,
  describeSchedule,
  getChannels,
  getLog,
  getPreview,
  getSchedules,
  getSummary,
  saveContact,
  saveSchedules,
  sendNow,
  stopSchedule,
  type Channel,
  type ChannelsInfo,
  type Frequency,
  type LogStatus,
  type ReminderLogEntry,
  type ReminderPreview,
  type ReminderSchedule,
  type ReminderSummary,
} from '@/lib/reminders'

const rupees = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`
const TIMES = Array.from({ length: 23 }, (_, i) => `${String(9 + Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`)
const FREQUENCIES: { id: Frequency; label: string }[] = [
  { id: 'once', label: 'Once' },
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'monthly', label: 'Monthly' },
]
const CHANNEL_ICON = { email: Mail, whatsapp: MessageCircle }
const STATUS_TONE: Record<LogStatus, string> = {
  sent: 'bg-sky-500/15 text-sky-800 dark:text-sky-300',
  delivered: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300',
  read: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300',
  failed: 'bg-rose-500/15 text-rose-700 dark:text-rose-300',
  skipped: 'bg-muted text-muted-foreground',
  dry_run: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
}
const BUCKETS = [
  { id: 'overdue', label: 'Anyone overdue' },
  { id: '1-30 Days', label: '1–30 days' },
  { id: '31-60 Days', label: '31–60 days' },
  { id: '61-90 Days', label: '61–90 days' },
  { id: '90+ Days', label: '90+ days' },
]

const when = (iso: string) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })

interface ScheduleForm {
  channels: Channel[]
  frequency: Frequency
  send_time: string
  weekday: number
  month_day: number
  only_when_overdue: boolean
}

const DEFAULT_FORM: ScheduleForm = { channels: [], frequency: 'weekly', send_time: '10:00', weekday: 0, month_day: 1, only_when_overdue: true }

/** Frequency, time and "only while overdue" fields shared by the customer and bulk sheets. */
function ScheduleFields({ form, onChange }: { form: ScheduleForm; onChange: (f: ScheduleForm) => void }) {
  const field = 'h-10 rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'
  return (
    <div className="space-y-3">
      <div className="inline-flex flex-wrap rounded-xl bg-muted p-1" role="radiogroup" aria-label="How often">
        {FREQUENCIES.map(f => (
          <button
            key={f.id}
            type="button"
            role="radio"
            aria-checked={form.frequency === f.id}
            onClick={() => onChange({ ...form, frequency: f.id })}
            className={cn('min-h-10 rounded-lg px-3.5 text-sm font-semibold cursor-pointer',
              form.frequency === f.id ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {form.frequency === 'weekly' && (
          <select aria-label="Weekday" value={form.weekday} onChange={e => onChange({ ...form, weekday: Number(e.target.value) })} className={field}>
            {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
        )}
        {form.frequency === 'monthly' && (
          <label className="flex items-center gap-2">
            Day
            <select aria-label="Day of the month" value={form.month_day} onChange={e => onChange({ ...form, month_day: Number(e.target.value) })} className={field}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2">
          at
          <select aria-label="Time" value={form.send_time} onChange={e => onChange({ ...form, send_time: e.target.value })} className={field}>
            {TIMES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.only_when_overdue}
          onChange={e => onChange({ ...form, only_when_overdue: e.target.checked })}
          className="mt-0.5 h-4 w-4 accent-primary"
        />
        <span>Only while something is overdue <span className="text-muted-foreground">(stops by itself once fully paid either way)</span></span>
      </label>
    </div>
  )
}

function ChannelPicker({ channels, selected, onChange, contact }: {
  channels: { channel: Channel; label: string; ready: boolean; reason: string }[]
  selected: Channel[]
  onChange: (c: Channel[]) => void
  contact?: ReminderPreview['contact']
}) {
  return (
    <div className="space-y-2">
      {channels.map(c => {
        const Icon = CHANNEL_ICON[c.channel]
        const missing = contact && !(c.channel === 'email' ? contact.email : contact.whatsapp)
        const checked = selected.includes(c.channel)
        return (
          <label key={c.channel} className={cn('flex items-start gap-3 rounded-xl border border-border p-3', !c.ready && 'opacity-70')}>
            <input
              type="checkbox"
              disabled={!c.ready}
              checked={checked && c.ready}
              onChange={e => onChange(e.target.checked ? [...selected, c.channel] : selected.filter(x => x !== c.channel))}
              className="mt-0.5 h-4 w-4 accent-primary"
            />
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-sm font-semibold"><Icon className="h-4 w-4" aria-hidden="true" /> {c.label}</span>
              {!c.ready ? (
                <span className="block text-xs text-muted-foreground">{c.reason}</span>
              ) : missing ? (
                <span className="block text-xs text-amber-800 dark:text-amber-300">
                  No {c.channel === 'email' ? 'email address' : 'mobile number'} yet: add one above, or this channel is skipped.
                </span>
              ) : null}
            </span>
          </label>
        )
      })}
    </div>
  )
}

function ContactRow({ label, value, source, placeholder, type, onSave }: {
  label: string
  value: string | null
  source: string | null
  placeholder: string
  type: 'email' | 'tel'
  onSave: (value: string) => Promise<void>
}) {
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const shown = type === 'tel' && value ? `+${value.slice(0, 2)} ${value.slice(2)}` : value
  if (draft === null) {
    return (
      <div className="flex items-center justify-between gap-2 py-1.5">
        <div className="min-w-0 text-sm">
          <span className="text-muted-foreground">{label}: </span>
          {shown ? <span className="font-medium break-all">{shown}</span> : <span className="text-muted-foreground">none</span>}
          {source && <span className="ml-1 text-xs text-muted-foreground">({source === 'tally' ? 'from Tally' : 'MyTally'})</span>}
        </div>
        <button type="button" onClick={() => setDraft(value ?? '')}
          className="inline-flex min-h-10 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-primary hover:bg-muted cursor-pointer">
          <Pencil className="h-3.5 w-3.5" /> {value ? 'Change' : 'Add'}
        </button>
      </div>
    )
  }
  const save = async () => {
    setSaving(true)
    try {
      await onSave(draft.trim())
      setDraft(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="flex gap-2 py-1.5">
      <input
        type={type}
        inputMode={type === 'tel' ? 'tel' : 'email'}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        placeholder={placeholder}
        aria-label={label}
        autoFocus
        className="h-10 min-w-0 flex-1 rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
      <button type="button" onClick={save} disabled={saving} aria-label={`Save ${label}`}
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-60 cursor-pointer">
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
      </button>
      <button type="button" onClick={() => setDraft(null)} className="min-h-10 rounded-xl px-2 text-sm text-muted-foreground hover:bg-muted cursor-pointer">
        Cancel
      </button>
    </div>
  )
}

function LogList({ entries, showCustomer }: { entries: ReminderLogEntry[]; showCustomer?: boolean }) {
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">No reminders yet.</p>
  return (
    <ul className="divide-y divide-border">
      {entries.map(e => {
        const Icon = CHANNEL_ICON[e.channel]
        return (
          <li key={e.id} className="flex items-start gap-2 py-2 text-sm">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-label={e.channel} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2">
                {showCustomer && <span className="font-semibold">{e.customer}</span>}
                <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', STATUS_TONE[e.status])}>{STATUS_LABEL[e.status]}</span>
                <span className="text-xs text-muted-foreground">{when(e.created_at)}</span>
              </div>
              {e.detail && <p className="text-xs text-muted-foreground">{e.detail}</p>}
              {e.outstanding !== null && e.status !== 'skipped' && (
                <p className="text-xs text-muted-foreground">{rupees(e.outstanding)} outstanding{e.overdue ? `, ${rupees(e.overdue)} overdue` : ''}</p>
              )}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function DryRunNote({ on }: { on?: boolean }) {
  if (!on) return null
  return (
    <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
      <strong>Dry run is on</strong> (REMINDERS_DRY_RUN on the server): reminders are logged but not actually sent.
    </p>
  )
}

/* ── one customer ─────────────────────────────────────────────────────────── */

interface SheetData {
  ledgerId: number
  preview: ReminderPreview
  channels: ChannelsInfo
  schedule: ReminderSchedule | null
  log: ReminderLogEntry[]
}

/** Payment reminders for one customer: where they go, send now, a schedule, preview and history. */
export function ReminderSheet({ target, token, onClose, onChanged }: {
  target: { ledgerId: number; name: string } | null
  token: string
  onClose: () => void
  onChanged?: () => void
}) {
  return (
    <BottomSheet
      open={target !== null}
      onOpenChange={open => { if (!open) onClose() }}
      title={`Payment reminders · ${target?.name ?? ''}`}
      description="Email and WhatsApp reminders with the amount due and your UPI ID. Nothing goes out before 9 am or after 8 pm."
    >
      {target && <ReminderSheetBody key={target.ledgerId} ledgerId={target.ledgerId} token={token} onChanged={onChanged} />}
    </BottomSheet>
  )
}

function ReminderSheetBody({ ledgerId, token, onChanged }: { ledgerId: number; token: string; onChanged?: () => void }) {
  const [data, setData] = useState<SheetData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const [form, setForm] = useState<ScheduleForm | null>(null)
  const [busy, setBusy] = useState<'send' | 'save' | 'stop' | null>(null)

  useEffect(() => {
    let current = true
    Promise.all([getPreview(token, ledgerId), getChannels(token), getSchedules(token, ledgerId), getLog(token, ledgerId, 20)])
      .then(([preview, channels, schedules, log]) => {
        if (current) setData({ ledgerId, preview, channels, schedule: schedules[0] ?? null, log })
      })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load reminders') })
    return () => { current = false }
  }, [token, ledgerId, reload])

  if (error) return <p className="py-8 text-center text-sm text-muted-foreground">{error}</p>
  if (!data) {
    return <div className="flex justify-center py-10" role="status"><Loader2 className="h-5 w-5 animate-spin text-primary" /><span className="sr-only">Loading</span></div>
  }

  const { preview, channels, schedule, log } = data
  const ready = channels.channels.filter(c => c.ready).map(c => c.channel)
  const fromSchedule: ScheduleForm | null = schedule && {
    channels: schedule.channels, frequency: schedule.frequency, send_time: schedule.send_time,
    weekday: schedule.weekday ?? 0, month_day: schedule.month_day ?? 1, only_when_overdue: schedule.only_when_overdue,
  }
  const current = form ?? fromSchedule ?? { ...DEFAULT_FORM, channels: ready }
  const chosen = current.channels.filter(c => ready.includes(c))
  const refresh = () => { setReload(k => k + 1); onChanged?.() }

  const run = async (kind: 'send' | 'save' | 'stop', action: () => Promise<string>) => {
    setBusy(kind)
    try {
      toast.success(await action())
      setForm(null)
      refresh()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  const doSend = () => run('send', async () => {
    const logs = await sendNow(token, ledgerId, chosen)
    const done = logs.filter(l => ['sent', 'delivered', 'read', 'dry_run'].includes(l.status))
    if (done.length === 0) throw new Error(logs.map(l => l.detail).filter(Boolean).join(' ') || 'Nothing was sent.')
    return logs.every(l => l.status === 'dry_run') ? 'Dry run: logged, not sent' : `Reminder sent by ${done.map(l => l.channel === 'email' ? 'email' : 'WhatsApp').join(' and ')}`
  })
  const doSave = () => run('save', async () => {
    await saveSchedules(token, { ledger_ids: [ledgerId], ...current, channels: chosen })
    return 'Automatic reminders saved'
  })
  const doStop = () => run('stop', async () => {
    if (schedule) await stopSchedule(token, schedule.id)
    return 'Automatic reminders stopped'
  })
  const onContact = async (value: { email?: string; whatsapp?: string }) => {
    await saveContact(token, ledgerId, value)
    toast.success('Saved to the customer’s MyTally profile')
    setReload(k => k + 1)
  }

  return (
    <div className="space-y-5">
      <DryRunNote on={channels.dry_run} />
      <p className="text-sm">
        <span className="font-bold">{rupees(preview.outstanding)}</span> outstanding
        {preview.overdue > 0 && <> · <span className="font-semibold text-rose-700 dark:text-rose-400">{rupees(preview.overdue)} overdue</span></>}
      </p>

      <section>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">Send to</h3>
        <ContactRow label="Email" type="email" placeholder="name@example.com" value={preview.contact.email} source={preview.contact.email_source}
          onSave={v => onContact({ email: v })} />
        <ContactRow label="WhatsApp" type="tel" placeholder="10-digit mobile" value={preview.contact.whatsapp} source={preview.contact.whatsapp_source}
          onSave={v => onContact({ whatsapp: v })} />
        {!preview.upi && <p className="text-xs text-amber-800 dark:text-amber-300">No company UPI ID set: WhatsApp reminders need one.</p>}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Channels</h3>
        <ChannelPicker channels={channels.channels} selected={chosen} contact={preview.contact} onChange={c => setForm({ ...current, channels: c })} />
      </section>

      <button type="button" onClick={doSend} disabled={busy !== null || chosen.length === 0}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-50 cursor-pointer">
        {busy === 'send' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send reminder now
      </button>

      <section className="space-y-3 rounded-2xl border border-border p-4">
        <h3 className="flex items-center gap-1.5 text-sm font-bold"><CalendarClock className="h-4 w-4" /> Automatic reminders</h3>
        {schedule && (
          <p className="text-sm">
            <span className="font-semibold">On:</span> {describeSchedule(schedule)} by {schedule.channels.map(c => c === 'email' ? 'email' : 'WhatsApp').join(' and ')}
            {schedule.next_run_at && <span className="text-muted-foreground"> · next {when(schedule.next_run_at)}</span>}
          </p>
        )}
        <ScheduleFields form={current} onChange={setForm} />
        <div className="flex gap-2">
          {schedule && (
            <button type="button" onClick={doStop} disabled={busy !== null}
              className="min-h-11 flex-1 rounded-xl border border-border text-sm font-bold hover:bg-muted disabled:opacity-50 cursor-pointer">
              {busy === 'stop' ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : 'Stop'}
            </button>
          )}
          <button type="button" onClick={doSave} disabled={busy !== null || chosen.length === 0}
            className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
            {busy === 'save' && <Loader2 className="h-4 w-4 animate-spin" />}
            {schedule ? 'Update schedule' : 'Start automatic reminders'}
          </button>
        </div>
        {chosen.length === 0 && <p className="text-xs text-muted-foreground">Turn on a channel above to send or schedule.</p>}
      </section>

      {(preview.email || preview.whatsapp) && (
        <details className="rounded-2xl border border-border p-4">
          <summary className="cursor-pointer text-sm font-bold">Preview the message</summary>
          {preview.email && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-muted-foreground">Email · {preview.email.subject}</p>
              <pre className="mt-1 whitespace-pre-wrap rounded-xl bg-muted p-3 font-sans text-sm">{preview.email.text}</pre>
            </div>
          )}
          {preview.whatsapp && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-muted-foreground">
                WhatsApp{preview.whatsapp.template ? ` · template “${preview.whatsapp.template}”` : ''} (Meta sends the approved wording)
              </p>
              <p className="mt-1 rounded-xl bg-muted p-3 text-sm">{preview.whatsapp.text}</p>
            </div>
          )}
        </details>
      )}

      <section>
        <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">History</h3>
        <LogList entries={log} />
      </section>
    </div>
  )
}

/* ── everyone in a bucket ─────────────────────────────────────────────────── */

function BulkScheduleSheet({ open, token, onClose, onSaved }: { open: boolean; token: string; onClose: () => void; onSaved: () => void }) {
  return (
    <BottomSheet
      open={open}
      onOpenChange={o => { if (!o) onClose() }}
      title="Automatic reminders for a group"
      description="Sets the same schedule for every customer in the group. A customer's existing schedule is replaced; each one stops by itself once they've paid."
    >
      {open && <BulkScheduleBody token={token} onSaved={() => { onSaved(); onClose() }} />}
    </BottomSheet>
  )
}

function BulkScheduleBody({ token, onSaved }: { token: string; onSaved: () => void }) {
  const [channels, setChannels] = useState<ChannelsInfo | null>(null)
  const [bucket, setBucket] = useState('overdue')
  const [form, setForm] = useState<ScheduleForm | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let current = true
    getChannels(token).then(c => { if (current) setChannels(c) }).catch(() => toast.error('Could not load channels'))
    return () => { current = false }
  }, [token])

  if (!channels) return <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
  const ready = channels.channels.filter(c => c.ready).map(c => c.channel)
  const current = form ?? { ...DEFAULT_FORM, channels: ready }
  const chosen = current.channels.filter(c => ready.includes(c))

  const save = async () => {
    setSaving(true)
    try {
      const saved = await saveSchedules(token, { bucket, ...current, channels: chosen })
      toast.success(saved.length ? `Automatic reminders set for ${saved.length} customer${saved.length === 1 ? '' : 's'}` : 'Nobody in that group owes money')
      onSaved()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-5">
      <DryRunNote on={channels.dry_run} />
      <section>
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Who</h3>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Customers">
          {BUCKETS.map(b => (
            <button key={b.id} type="button" role="radio" aria-checked={bucket === b.id} onClick={() => setBucket(b.id)}
              className={cn('min-h-10 rounded-full border px-3.5 text-sm font-semibold cursor-pointer',
                bucket === b.id ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted')}>
              {b.label}
            </button>
          ))}
        </div>
      </section>
      <section>
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">Channels</h3>
        <ChannelPicker channels={channels.channels} selected={chosen} onChange={c => setForm({ ...current, channels: c })} />
        <p className="mt-2 text-xs text-muted-foreground">Customers without an email or mobile number are skipped on that channel.</p>
      </section>
      <section>
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">When</h3>
        <ScheduleFields form={current} onChange={setForm} />
      </section>
      <button type="button" onClick={save} disabled={saving || chosen.length === 0}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
        {saving && <Loader2 className="h-4 w-4 animate-spin" />} Start automatic reminders
      </button>
      {chosen.length === 0 && <p className="text-xs text-muted-foreground">Turn on Email or WhatsApp in Admin → Integrations first.</p>}
    </div>
  )
}

/* ── summary strip on Outstanding ─────────────────────────────────────────── */

/** "Automatic reminders: 4 on · 3 sent today · 1 failed", with the group schedule and the full history. */
export function AutoRemindersStrip({ token, reloadKey, onChanged }: { token: string; reloadKey: number; onChanged: () => void }) {
  const [summary, setSummary] = useState<ReminderSummary | null>(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [history, setHistory] = useState<ReminderLogEntry[] | null>(null)

  useEffect(() => {
    let current = true
    getSummary(token).then(s => { if (current) setSummary(s) }).catch(() => {})
    return () => { current = false }
  }, [token, reloadKey])

  useEffect(() => {
    if (!historyOpen) return
    let current = true
    getLog(token, undefined, 100).then(l => { if (current) setHistory(l) }).catch(() => { if (current) setHistory([]) })
    return () => { current = false }
  }, [historyOpen, token, reloadKey])

  return (
    <section aria-label="Automatic reminders" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600"><BellRing className="h-5 w-5" /></div>
        <div>
          <h2 className="text-sm font-bold">Automatic reminders</h2>
          <p className="text-sm text-muted-foreground">
            {summary
              ? <>{summary.active_schedules} customer{summary.active_schedules === 1 ? '' : 's'} on · {summary.sent_today} sent today
                {summary.dry_run_today > 0 && <> · {summary.dry_run_today} dry run</>}
                {summary.failed_today > 0 && <> · <span className="font-semibold text-rose-700 dark:text-rose-400">{summary.failed_today} failed</span></>}</>
              : 'Loading…'}
          </p>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="button" onClick={() => setHistoryOpen(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer">
          <History className="h-4 w-4" /> History
        </button>
        <button type="button" onClick={() => setBulkOpen(true)}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-primary px-3 text-sm font-semibold text-primary-foreground cursor-pointer">
          <CalendarClock className="h-4 w-4" /> Schedule a group
        </button>
      </div>
      <BulkScheduleSheet open={bulkOpen} token={token} onClose={() => setBulkOpen(false)} onSaved={onChanged} />
      <BottomSheet open={historyOpen} onOpenChange={setHistoryOpen} title="Reminder history" description="The last 100 reminders, newest first.">
        {history === null ? <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div> : <LogList entries={history} showCustomer />}
      </BottomSheet>
    </section>
  )
}
