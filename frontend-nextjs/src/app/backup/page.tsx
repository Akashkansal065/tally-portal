'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, CheckCircle2, Clock, Database, Download, Loader2, RotateCcw, XCircle } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { API_BASE, authHeaders, cn, formatToIST } from '@/lib/utils'

/* Backups of the company being worked in. Each company's sync agent backs it up every hour from the Tally on its
   PC, keeps a copy there and uploads one here (backend/app/routers/backups.py). Kept: every backup from today and
   the last one of each of the previous seven days. */

type Backup = {
  backup_id: number
  backup_key: string
  kind: 'hourly' | 'manual' | 'pre_restore'
  status: 'requested' | 'uploading' | 'stored' | 'failed'
  taken_at: string | null
  created_at: string | null
  size_bytes: number | null
  record_counts: Record<string, number>
  error: string | null
}
type Restore = {
  restore_id: number
  backup_id: number | null
  status: 'requested' | 'running' | 'completed' | 'failed' | 'cancelled'
  summary: Record<string, { sent: number; created: number; altered: number; errors: number }>
  error: string | null
  created_at: string | null
  finished_at: string | null
}
type Listing = {
  company: { company_id: number; name: string }
  restore_enabled: boolean
  keep_days: number
  backups: Backup[]
  restores: Restore[]
}

const KIND_LABEL: Record<Backup['kind'], string> = { hourly: 'Hourly', manual: 'Backed up now', pre_restore: 'Before a restore' }
const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(token) })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`)
  return body as T
}

function size(bytes: number | null) {
  if (!bytes) return ''
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function when(iso: string | null) {
  return iso ? formatToIST(iso, { includeDate: true }) : '--'
}

export default function BackupPage() {
  const { token } = useAuth()
  const [data, setData] = useState<Listing | null>(null)
  const [problem, setProblem] = useState('')
  const [asking, setAsking] = useState(false)
  const [restoring, setRestoring] = useState<Backup | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    try {
      setData(await call<Listing>(token, '/backups'))
      setProblem('')
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'Could not load the backups')
    }
  }, [token])

  useEffect(() => { load() }, [load])

  // While the agent has work to do for this company, look again every 15 seconds
  const busy = !!data && (data.backups.some(b => b.status === 'requested' || b.status === 'uploading')
    || data.restores.some(r => r.status === 'requested' || r.status === 'running'))
  useEffect(() => {
    if (!busy) return
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [busy, load])

  const backUpNow = async () => {
    if (!token) return
    setAsking(true)
    try {
      await call(token, '/backups', { method: 'POST' })
      toast.success('Asked the sync agent for a backup. It usually arrives within a few minutes.')
      await load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not ask for a backup')
    } finally {
      setAsking(false)
    }
  }

  const download = async (backup: Backup) => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/backups/${backup.backup_id}/download`, { headers: authHeaders(token) })
      if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail || 'Could not download the backup')
      const name = /filename="?([^"]+)"?/.exec(res.headers.get('content-disposition') || '')?.[1] || `${backup.backup_key}.zip`
      const url = URL.createObjectURL(await res.blob())
      const link = Object.assign(document.createElement('a'), { href: url, download: name })
      link.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not download the backup')
    }
  }

  const cancelRestore = async (restore: Restore) => {
    if (!token) return
    try {
      await call(token, `/backups/restores/${restore.restore_id}/cancel`, { method: 'POST' })
      await load()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not cancel the restore')
    }
  }

  if (problem) {
    return <div className="mx-auto max-w-3xl p-6 text-sm text-muted-foreground">{problem}</div>
  }
  if (!data) {
    return <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
  }

  const openRestore = data.restores.find(r => r.status === 'requested' || r.status === 'running')
  const finished = data.restores.filter(r => r !== openRestore)

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 pb-24 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Database className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-bold">Backups</h1>
            <p className="text-sm text-muted-foreground">{data.company.name}</p>
          </div>
        </div>
        <button onClick={backUpNow} disabled={asking}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-60">
          {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />} Back up now
        </button>
      </header>

      <p className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">
        The sync agent on the PC where this company&apos;s Tally runs backs it up every hour, while the company is open in
        Tally. Each backup is kept on that PC and here: every backup from today, then the last one of each of the
        previous {data.keep_days} days.
      </p>

      {openRestore && (
        <section className="flex flex-col gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            <RotateCcw className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              {openRestore.status === 'requested'
                ? 'A restore is waiting for the sync agent. It starts the next time the agent checks in, with the company open in Tally.'
                : `A restore is being written into Tally (started ${when(openRestore.created_at)}). Leave Tally and the agent running until it finishes.`}
            </span>
          </div>
          <button onClick={() => cancelRestore(openRestore)} className="h-9 shrink-0 rounded-xl border border-border bg-background px-3 text-sm font-medium">
            {openRestore.status === 'requested' ? 'Cancel restore' : 'Close a stuck restore'}
          </button>
        </section>
      )}

      {!data.restore_enabled && (
        <p className="flex items-start gap-2 rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          Restoring is not switched on yet. Backups are made and can be downloaded; restoring one into Tally is switched
          on once it has been checked on a test company.
        </p>
      )}

      <section className="overflow-hidden rounded-2xl border border-border bg-card">
        {data.backups.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            No backups yet. The first one is made within an hour of the sync agent running with this company open in Tally.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data.backups.map(b => (
              <li key={b.backup_id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                    {when(b.taken_at || b.created_at)}
                    <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{KIND_LABEL[b.kind]}</span>
                  </div>
                  <BackupState backup={b} />
                </div>
                {b.status === 'stored' && (
                  <div className="flex shrink-0 gap-2">
                    <button onClick={() => download(b)} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-medium">
                      <Download className="h-4 w-4" /> Download
                    </button>
                    {data.restore_enabled && (
                      <button onClick={() => setRestoring(b)} disabled={!!openRestore}
                        className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-medium disabled:opacity-50">
                        <RotateCcw className="h-4 w-4" /> Restore
                      </button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {finished.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold">Recent restores</h2>
          <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card text-sm">
            {finished.map(r => (
              <li key={r.restore_id} className="space-y-1 p-4">
                <div className="flex items-center gap-2 font-medium">
                  {r.status === 'completed' ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-muted-foreground" />}
                  {r.status === 'completed' ? 'Restored' : r.status === 'cancelled' ? 'Cancelled' : 'Restore failed'} · {when(r.finished_at || r.created_at)}
                </div>
                {Object.keys(r.summary).length > 0 && (
                  <p className="text-muted-foreground">
                    {Object.values(r.summary).reduce((n, line) => n + line.created + line.altered, 0)} records written
                    {Object.values(r.summary).some(line => line.errors) && `, ${Object.values(r.summary).reduce((n, line) => n + line.errors, 0)} refused by Tally`}
                  </p>
                )}
                {r.error && <p className="text-muted-foreground">{r.error}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {restoring && token && (
        <RestoreDialog token={token} backup={restoring} companyName={data.company.name}
          onClose={() => setRestoring(null)} onAsked={() => { setRestoring(null); load() }} />
      )}
    </div>
  )
}

function BackupState({ backup }: { backup: Backup }) {
  const counts = backup.record_counts || {}
  if (backup.status === 'stored') {
    return (
      <p className="text-xs text-muted-foreground">
        {(counts.ledgers ?? 0).toLocaleString('en-IN')} ledgers · {(counts.vouchers ?? 0).toLocaleString('en-IN')} vouchers · {size(backup.size_bytes)}
      </p>
    )
  }
  if (backup.status === 'failed') {
    return <p className="text-xs text-rose-600 dark:text-rose-400">Not made: {backup.error || 'the sync agent could not back up the company.'}</p>
  }
  return (
    <p className={cn('flex items-center gap-1 text-xs text-muted-foreground')}>
      <Clock className="h-3 w-3" />
      {backup.status === 'requested' ? 'Waiting for the sync agent…' : 'Uploading from the Tally PC…'}
    </p>
  )
}

function RestoreDialog({ token, backup, companyName, onClose, onAsked }: {
  token: string; backup: Backup; companyName: string; onClose: () => void; onAsked: () => void
}) {
  const [typed, setTyped] = useState('')
  const [sending, setSending] = useState(false)
  const matches = typed.trim().toLowerCase() === companyName.trim().toLowerCase()

  const ask = async () => {
    setSending(true)
    try {
      await call(token, `/backups/${backup.backup_id}/restore`, { method: 'POST', body: JSON.stringify({ confirm_company_name: typed }) })
      toast.success('Restore asked for. The sync agent backs up the company as it is now, then restores this backup.')
      onAsked()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not ask for the restore')
    } finally {
      setSending(false)
    }
  }

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Restore the backup of {when(backup.taken_at)}?</DialogTitle>
          <DialogDescription>
            Every master and voucher in this backup is written back into {companyName} in Tally, as it was then.
            Records added since the backup are not removed. Before writing anything, the sync agent backs up the
            company as it is now, so this can be undone by restoring that backup.
          </DialogDescription>
        </DialogHeader>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">Type the company&apos;s name to confirm</span>
          <input value={typed} onChange={e => setTyped(e.target.value)} placeholder={companyName} className={field} autoFocus />
        </label>
        <DialogFooter>
          <button onClick={onClose} className="h-10 rounded-xl border border-border px-4 text-sm font-medium">Keep things as they are</button>
          <button onClick={ask} disabled={!matches || sending}
            className="inline-flex h-10 items-center gap-2 rounded-xl bg-rose-600 px-4 text-sm font-semibold text-white disabled:opacity-50">
            {sending && <Loader2 className="h-4 w-4 animate-spin" />} Restore into Tally
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
