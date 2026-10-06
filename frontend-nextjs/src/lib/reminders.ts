import { API_BASE, authHeaders } from '@/lib/utils'

/* Automatic payment reminders by email (Gmail) and WhatsApp (Meta), each behind its Admin → Integrations switch.
   See docs/livekeeping-parity-plan.md, Phase 2. */

export type Channel = 'email' | 'whatsapp'
export type Frequency = 'once' | 'daily' | 'weekly' | 'monthly'
export type LogStatus = 'sent' | 'delivered' | 'read' | 'failed' | 'skipped' | 'dry_run'

export interface ChannelsInfo {
  channels: { channel: Channel; label: string; ready: boolean; reason: string }[]
  emails_sent_today: number
  email_daily_limit: number
  dry_run: boolean
  sending_hours: string
}

export interface ReminderSummary {
  active_schedules: number
  sent_today: number
  dry_run_today: number
  failed_today: number
  skipped_today: number
}

export interface ReminderPreview {
  ledger_id: number
  customer: string
  outstanding: number
  overdue: number
  contact: { email: string | null; email_source: string | null; whatsapp: string | null; whatsapp_source: string | null }
  upi: string | null
  channels: Record<Channel, { ready: boolean; reason: string }>
  email: { subject: string; text: string } | null
  whatsapp: { template: string | null; text: string } | null
}

export interface ReminderSchedule {
  id: number
  ledger_id: number
  customer: string | null
  channels: Channel[]
  frequency: Frequency
  send_time: string
  weekday: number | null
  month_day: number | null
  only_when_overdue: boolean
  active: boolean
  stop_reason: string | null
  next_run_at: string | null
  last_run_at: string | null
}

export interface ReminderLogEntry {
  id: number
  ledger_id: number
  customer: string | null
  channel: Channel
  recipient: string | null
  status: LogStatus
  detail: string | null
  outstanding: number | null
  overdue: number | null
  created_at: string
}

export interface ScheduleInput {
  ledger_ids?: number[]
  bucket?: string
  channels: Channel[]
  frequency: Frequency
  send_time: string
  weekday?: number | null
  month_day?: number | null
  only_when_overdue: boolean
}

async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/reminders${path}`, { ...init, headers: authHeaders(token) })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getChannels = (token: string) => call<ChannelsInfo>(token, '/channels')
export const getSummary = (token: string) => call<ReminderSummary>(token, '/summary')
export const getPreview = (token: string, ledgerId: number) => call<ReminderPreview>(token, `/preview/${ledgerId}`)
export const getSchedules = (token: string, ledgerId?: number) =>
  call<ReminderSchedule[]>(token, `/schedules${ledgerId ? `?ledger_id=${ledgerId}` : ''}`)
export const getLog = (token: string, ledgerId?: number, limit = 50) =>
  call<ReminderLogEntry[]>(token, `/log?limit=${limit}${ledgerId ? `&ledger_id=${ledgerId}` : ''}`)
export const sendNow = (token: string, ledgerId: number, channels: Channel[]) =>
  call<ReminderLogEntry[]>(token, '/send-now', { method: 'POST', body: JSON.stringify({ ledger_id: ledgerId, channels }) })
export const saveSchedules = (token: string, input: ScheduleInput) =>
  call<ReminderSchedule[]>(token, '/schedules', { method: 'POST', body: JSON.stringify(input) })
export const stopSchedule = (token: string, id: number) =>
  call<{ detail: string }>(token, `/schedules/${id}`, { method: 'DELETE' })
export const saveContact = (token: string, ledgerId: number, contact: { email?: string; whatsapp?: string }) =>
  call<ReminderPreview['contact']>(token, `/contact/${ledgerId}`, { method: 'PUT', body: JSON.stringify(contact) })

/** Email a PDF made in the browser (invoice, statement) through Gmail; logged in the customer's reminder history. */
export async function emailDocument(token: string, input: {
  ledgerId: number; to: string; subject: string; message: string; reference: string; pdf: Blob; filename: string
}): Promise<ReminderLogEntry> {
  const form = new FormData()
  form.append('ledger_id', String(input.ledgerId))
  form.append('to', input.to)
  form.append('subject', input.subject)
  form.append('message', input.message)
  form.append('reference', input.reference)
  form.append('file', input.pdf, input.filename)
  // No Content-Type header: the browser sets the multipart boundary
  const res = await fetch(`${API_BASE}/reminders/email-document`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { detail = (await res.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  return res.json()
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

/** "Daily at 10:00", "Every Friday at 11:30", "On the 5th of each month at 10:00", "Once at 10:00" */
export function describeSchedule(s: Pick<ReminderSchedule, 'frequency' | 'send_time' | 'weekday' | 'month_day'>): string {
  if (s.frequency === 'daily') return `Daily at ${s.send_time}`
  if (s.frequency === 'weekly') return `Every ${WEEKDAYS[s.weekday ?? 0]} at ${s.send_time}`
  if (s.frequency === 'monthly') return `On day ${s.month_day} of each month at ${s.send_time}`
  return `Once at ${s.send_time}`
}

export const STATUS_LABEL: Record<LogStatus, string> = {
  sent: 'Sent',
  delivered: 'Delivered',
  read: 'Read',
  failed: 'Failed',
  skipped: 'Not sent',
  dry_run: 'Dry run',
}
