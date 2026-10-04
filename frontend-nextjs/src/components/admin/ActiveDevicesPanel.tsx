'use client'

import { useCallback, useEffect, useState } from 'react'
import { useLoader } from '@/lib/use-loader'
import { toast } from 'sonner'
import { Ban, Loader2, LogOut, RefreshCw, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ConfirmBar, DeviceActionButton, DeviceList } from '@/components/DeviceList'
import {
  adminBlockDevice,
  adminRevokeSession,
  listCompanySessions,
  type CompanySessionSummary,
  type DeviceSession,
} from '@/lib/device-sessions'

type Pending = { kind: 'revoke' | 'block'; session: DeviceSession }

const SUMMARY_ITEMS: { key: keyof CompanySessionSummary; label: string; deviceType?: string; clientType?: string; activeNow?: boolean }[] = [
  { key: 'total', label: 'Signed in' },
  { key: 'active_now', label: 'Active now', activeNow: true },
  { key: 'mobile', label: 'Mobile', deviceType: 'mobile' },
  { key: 'tablet', label: 'Tablet', deviceType: 'tablet' },
  { key: 'desktop', label: 'Desktop', deviceType: 'desktop' },
  { key: 'sync_agent', label: 'Sync Agents', clientType: 'sync-agent' },
]

/** Every signed-in device in the admin's company, with counts, search and filters. */
export function ActiveDevicesPanel({ token }: { token: string }) {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [deviceType, setDeviceType] = useState('')
  const [clientType, setClientType] = useState('')
  const [activeNow, setActiveNow] = useState(false)
  const [includeOlder, setIncludeOlder] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [blockReason, setBlockReason] = useState('')
  const [busy, setBusy] = useState(false)

  // Search as the admin types, without a request per keystroke
  useEffect(() => {
    const id = setTimeout(() => setQuery(search), 300)
    return () => clearTimeout(id)
  }, [search])

  const fetchDevices = useCallback(
    () => listCompanySessions(token, { q: query, deviceType, clientType, activeNow, includeOlder }),
    [token, query, deviceType, clientType, activeNow, includeOlder],
  )
  const { data, error, loading, reload } = useLoader(fetchDevices)
  const summary: CompanySessionSummary | null = data?.summary ?? null
  const sessions: DeviceSession[] = data?.sessions ?? []

  const applySummaryFilter = (item: (typeof SUMMARY_ITEMS)[number]) => {
    setDeviceType(item.deviceType ?? '')
    setClientType(item.clientType ?? '')
    setActiveNow(Boolean(item.activeNow))
  }

  const isSummaryActive = (item: (typeof SUMMARY_ITEMS)[number]) =>
    (item.deviceType ?? '') === deviceType && (item.clientType ?? '') === clientType && Boolean(item.activeNow) === activeNow

  const confirm = async () => {
    if (!pending) return
    const { kind, session } = pending
    setBusy(true)
    try {
      if (kind === 'revoke') {
        await adminRevokeSession(token, session.session_id)
        toast.success(`${session.device_name} (${session.username}) was signed out.`)
      } else {
        await adminBlockDevice(token, session.session_id, blockReason)
        toast.success(`${session.device_name} is blocked for ${session.username}.`)
      }
      setPending(null)
      setBlockReason('')
      reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {SUMMARY_ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => applySummaryFilter(item)}
            className={cn(
              'text-left rounded-xl border px-3 py-2.5 transition-colors cursor-pointer',
              isSummaryActive(item) ? 'border-emerald-500/50 bg-emerald-500/10' : 'border-border/80 bg-card hover:bg-muted/60',
            )}
          >
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-muted-foreground">{item.label}</p>
            <p className="text-xl font-black tabular-nums text-foreground">{summary ? summary[item.key] : '–'}</p>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            id="device-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search user, device or IP"
            className="w-full h-9 pl-8 pr-3 text-xs rounded-xl border border-border bg-card"
          />
        </div>
        <select id="device-type-filter" value={deviceType} onChange={(e) => setDeviceType(e.target.value)} className="h-9 px-2 text-xs rounded-xl border border-border bg-card">
          <option value="">All device types</option>
          <option value="mobile">Mobile</option>
          <option value="tablet">Tablet</option>
          <option value="desktop">Desktop</option>
        </select>
        <select id="client-type-filter" value={clientType} onChange={(e) => setClientType(e.target.value)} className="h-9 px-2 text-xs rounded-xl border border-border bg-card">
          <option value="">All apps</option>
          <option value="web">Web</option>
          <option value="android">Android app</option>
          <option value="ios">iOS app</option>
          <option value="sync-agent">Sync Agent</option>
          <option value="api">API</option>
        </select>
        <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground cursor-pointer">
          <input id="active-now-filter" type="checkbox" checked={activeNow} onChange={(e) => setActiveNow(e.target.checked)} /> Active now
        </label>
        <label className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground cursor-pointer">
          <input id="include-older-filter" type="checkbox" checked={includeOlder} onChange={(e) => setIncludeOlder(e.target.checked)} />
          Older sessions{summary ? ` (${summary.older_sessions})` : ''}
        </label>
        <DeviceActionButton onClick={reload} disabled={loading || busy} title="Refresh">
          <RefreshCw className={loading ? 'w-3 h-3 animate-spin' : 'w-3 h-3'} /> Refresh
        </DeviceActionButton>
      </div>

      {pending && (
        <ConfirmBar
          busy={busy}
          onCancel={() => { setPending(null); setBlockReason('') }}
          onConfirm={confirm}
          confirmLabel={pending.kind === 'block' ? 'Block device' : 'Sign out'}
          message={
            pending.kind === 'revoke'
              ? <>Sign out <b>{pending.session.device_name}</b> for {pending.session.username}?</>
              : <>Block <b>{pending.session.device_name}</b> for {pending.session.username}? It is signed out now and can&apos;t sign in as them until unblocked.</>
          }
        >
          {pending.kind === 'block' && (
            <input
              id="panel-block-reason"
              value={blockReason}
              onChange={(e) => setBlockReason(e.target.value)}
              maxLength={255}
              placeholder="Reason (optional, visible to admins only)"
              className="w-full h-8 px-2.5 text-xs rounded-lg border border-border bg-background"
            />
          )}
        </ConfirmBar>
      )}

      {error && <p className="text-xs font-semibold text-destructive">{error}</p>}

      {loading && !data ? (
        <div className="flex justify-center py-10"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
      ) : (
        <DeviceList
          sessions={sessions}
          showUser
          emptyText={query || deviceType || clientType || activeNow ? 'No devices match these filters.' : 'No one is signed in.'}
          actions={(s) => (
            <>
              <DeviceActionButton onClick={() => setPending({ kind: 'revoke', session: s })} disabled={busy}>
                <LogOut className="w-3 h-3" /> Sign out
              </DeviceActionButton>
              {s.device_id && !s.is_current && !s.is_blocked && (
                <DeviceActionButton tone="danger" onClick={() => setPending({ kind: 'block', session: s })} disabled={busy}>
                  <Ban className="w-3 h-3" /> Block
                </DeviceActionButton>
              )}
            </>
          )}
        />
      )}
    </div>
  )
}
