'use client'

import { useEffect, useState } from 'react'
import { CalendarClock, Loader2, Play } from 'lucide-react'
import { toast } from 'sonner'
import { API_BASE, authHeaders, cn } from '@/lib/utils'

interface Schedule {
  enabled: boolean
  time: string
  keep: number
  email_to: string
  last_run_day: string | null
  last_result: { at: string; ok: boolean; message: string } | null
  running: number
}

const field = 'h-10 rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

async function call(token: string, path: string, init?: RequestInit): Promise<Schedule> {
  const res = await fetch(`${API_BASE}/backup-schedule${path}`, { ...init, headers: authHeaders(token) })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Could not load the schedule')
  return res.json()
}

/** Backup page: back up every day at a set time, keep the last N, and optionally email the file. */
export function BackupScheduleCard({ token }: { token: string }) {
  const [data, setData] = useState<Schedule | null>(null)
  const [draft, setDraft] = useState<Partial<Schedule>>({})
  const [busy, setBusy] = useState<'save' | 'run' | null>(null)

  useEffect(() => {
    let current = true
    call(token, '').then(d => { if (current) setData(d) }).catch(() => {})
    return () => { current = false }
  }, [token])

  if (!data) return null
  const v = { ...data, ...draft }
  const run = async (kind: 'save' | 'run') => {
    setBusy(kind)
    try {
      const next = kind === 'save'
        ? await call(token, '', { method: 'PUT', body: JSON.stringify({ enabled: v.enabled, time: v.time, keep: v.keep, email_to: v.email_to }) })
        : await call(token, '/run-now', { method: 'POST' })
      setData(next)
      setDraft({})
      toast.success(kind === 'save' ? 'Backup schedule saved' : next.last_result?.message || 'Backup started')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card p-5 shadow-sm" aria-labelledby="backup-schedule">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 id="backup-schedule" className="flex items-center gap-1.5 text-sm font-bold"><CalendarClock className="h-4 w-4" /> Daily backup</h2>
          <p className="text-sm text-muted-foreground">Backs up each company that&apos;s open in Tally. It needs the server to reach the Tally PC.</p>
        </div>
        <label className="inline-flex items-center gap-2 text-sm font-semibold">
          <input type="checkbox" checked={v.enabled} onChange={e => setDraft(d => ({ ...d, enabled: e.target.checked }))} className="h-4 w-4 accent-primary" />
          On
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm"><span className="mb-1 block font-semibold">Time (IST)</span>
          <input type="time" value={v.time} onChange={e => setDraft(d => ({ ...d, time: e.target.value }))} className={cn(field, 'w-full')} /></label>
        <label className="text-sm"><span className="mb-1 block font-semibold">Keep the last</span>
          <select value={v.keep} onChange={e => setDraft(d => ({ ...d, keep: Number(e.target.value) }))} className={cn(field, 'w-full')}>
            {[3, 7, 14, 30].map(n => <option key={n} value={n}>{n} backups</option>)}
          </select></label>
        <label className="text-sm"><span className="mb-1 block font-semibold">Email a copy to (optional)</span>
          <input type="email" value={v.email_to} placeholder="owner@example.com" onChange={e => setDraft(d => ({ ...d, email_to: e.target.value }))} className={cn(field, 'w-full')} />
          <span className="text-xs text-muted-foreground">Needs Email (Gmail) on in Admin → Integrations; files over 20 MB are only mentioned.</span></label>
      </div>
      {data.last_result && (
        <p className={cn('text-sm', data.last_result.ok ? 'text-muted-foreground' : 'text-rose-700 dark:text-rose-300')}>
          Last run {new Date(data.last_result.at).toLocaleString('en-IN')}: {data.last_result.message}{data.running ? ` · ${data.running} still running` : ''}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => run('save')} disabled={busy !== null || Object.keys(draft).length === 0}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
          {busy === 'save' && <Loader2 className="h-4 w-4 animate-spin" />} Save
        </button>
        <button type="button" onClick={() => run('run')} disabled={busy !== null}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border px-4 text-sm font-semibold hover:bg-muted disabled:opacity-50 cursor-pointer">
          {busy === 'run' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Back up now
        </button>
      </div>
    </section>
  )
}
