'use client'

import { useCallback, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Ban, Loader2, LogOut, RefreshCw, ShieldOff } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ConfirmBar, DeviceActionButton, DeviceIcon, DeviceList } from '@/components/DeviceList'
import {
  adminBlockDevice,
  adminRevokeAllSessions,
  adminRevokeSession,
  listBlockedDevices,
  listUserSessions,
  relativeTime,
  unblockDevice,
  type BlockedDevice,
  type DeviceSession,
} from '@/lib/device-sessions'
import { useLoader } from '@/lib/use-loader'

type Pending =
  | { kind: 'revoke'; session: DeviceSession }
  | { kind: 'block'; session: DeviceSession }
  | { kind: 'revoke-all' }
  | { kind: 'revoke-older'; sessions: DeviceSession[] }
  | { kind: 'unblock'; device: BlockedDevice }

interface DeviceSessionsModalProps {
  user: { user_id: number; username: string; email: string }
  token: string
  onClose: () => void
  /** Called after any change so the user cards can refresh their device counts */
  onChanged?: () => void
}

export function DeviceSessionsModal({ user, token, onClose, onChanged }: DeviceSessionsModalProps) {
  const [showHistory, setShowHistory] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [blockReason, setBlockReason] = useState('')
  const [busy, setBusy] = useState(false)

  const fetchDevices = useCallback(async () => {
    const [sessions, blocked] = await Promise.all([
      listUserSessions(token, user.user_id, showHistory ? 'all' : 'active'),
      listBlockedDevices(token, user.user_id),
    ])
    return { sessions, blocked }
  }, [token, user.user_id, showHistory])
  const { data, error, loading, reload } = useLoader(fetchDevices)
  const sessions = useMemo(() => data?.sessions ?? [], [data])
  const blocked = data?.blocked ?? []

  const live = useMemo(() => sessions.filter((s) => !s.revoked_at), [sessions])
  const older = useMemo(() => live.filter((s) => s.legacy && !s.last_active_at), [live])
  const inUse = useMemo(() => live.filter((s) => !(s.legacy && !s.last_active_at)), [live])
  const history = useMemo(() => sessions.filter((s) => s.revoked_at), [sessions])

  const run = async (action: () => Promise<string>) => {
    setBusy(true)
    try {
      toast.success(await action())
      setPending(null)
      setBlockReason('')
      reload()
      onChanged?.()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  const confirm = () => {
    if (!pending) return
    if (pending.kind === 'revoke') {
      const s = pending.session
      run(async () => {
        await adminRevokeSession(token, s.session_id)
        return `${s.device_name} was signed out.`
      })
    } else if (pending.kind === 'block') {
      const s = pending.session
      run(async () => {
        await adminBlockDevice(token, s.session_id, blockReason)
        return `${s.device_name} is blocked and signed out.`
      })
    } else if (pending.kind === 'revoke-all') {
      run(async () => {
        const { revoked } = await adminRevokeAllSessions(token, user.user_id)
        return revoked === 1 ? '1 device was signed out.' : `${revoked} devices were signed out.`
      })
    } else if (pending.kind === 'revoke-older') {
      const ids = pending.sessions.map((s) => s.session_id)
      run(async () => {
        for (const id of ids) await adminRevokeSession(token, id)
        return `${ids.length} older session${ids.length === 1 ? '' : 's'} signed out.`
      })
    } else if (pending.kind === 'unblock') {
      const d = pending.device
      run(async () => {
        await unblockDevice(token, d.blocked_device_id)
        return `${d.device_name ?? 'The device'} can sign in again.`
      })
    }
  }

  const rowActions = (s: DeviceSession) =>
    s.revoked_at ? null : (
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
    )

  const othersThanCurrent = live.filter((s) => !s.is_current).length

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold">Devices · {user.username}</DialogTitle>
          <DialogDescription>
            {user.email}. Signing a device out ends its session immediately; blocking also stops it signing in again.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground cursor-pointer">
            <input id="device-history" type="checkbox" checked={showHistory} onChange={(e) => setShowHistory(e.target.checked)} />
            Show signed-out devices
          </label>
          <div className="flex items-center gap-2">
            <DeviceActionButton onClick={reload} disabled={loading || busy} title="Refresh">
              <RefreshCw className={loading ? 'w-3 h-3 animate-spin' : 'w-3 h-3'} /> Refresh
            </DeviceActionButton>
            {othersThanCurrent > 0 && (
              <DeviceActionButton tone="danger" onClick={() => setPending({ kind: 'revoke-all' })} disabled={busy}>
                <LogOut className="w-3 h-3" /> Sign out all devices
              </DeviceActionButton>
            )}
          </div>
        </div>

        {pending && (
          <ConfirmBar
            busy={busy}
            onCancel={() => { setPending(null); setBlockReason('') }}
            onConfirm={confirm}
            confirmLabel={
              pending.kind === 'block' ? 'Block device'
                : pending.kind === 'unblock' ? 'Unblock'
                  : 'Sign out'
            }
            message={
              pending.kind === 'revoke' ? <>Sign out <b>{pending.session.device_name}</b>? {user.username} can sign in on it again.</>
                : pending.kind === 'block' ? <>Block <b>{pending.session.device_name}</b>? It is signed out now and can&apos;t sign in as {user.username} until you unblock it.</>
                  : pending.kind === 'revoke-all' ? <>Sign out all of {user.username}&apos;s devices{live.some((s) => s.is_current) ? ' except the one you are using' : ''}?</>
                    : pending.kind === 'revoke-older' ? <>Sign out {pending.sessions.length} older session{pending.sessions.length === 1 ? '' : 's'} from before device tracking?</>
                      : <>Unblock <b>{pending.device.device_name ?? 'this device'}</b>? It will be able to sign in as {user.username} again.</>
            }
          >
            {pending.kind === 'block' && (
              <input
                id="block-reason"
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
          <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
        ) : (
          <div className="space-y-4">
            <section className="space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                Signed in · {inUse.length} device{inUse.length === 1 ? '' : 's'}
              </h3>
              <DeviceList sessions={inUse} actions={rowActions} emptyText="Not signed in on any device." />
            </section>

            {older.length > 0 && (
              <section className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                    Older sessions · {older.length}
                  </h3>
                  <DeviceActionButton onClick={() => setPending({ kind: 'revoke-older', sessions: older })} disabled={busy}>
                    <LogOut className="w-3 h-3" /> Sign out older sessions
                  </DeviceActionButton>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Signed in before device tracking and not used since. Most are left over from earlier logouts.
                </p>
                <DeviceList sessions={older} actions={rowActions} />
              </section>
            )}

            {showHistory && history.length > 0 && (
              <section className="space-y-2">
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">Signed out</h3>
                <DeviceList sessions={history} />
              </section>
            )}

            <section className="space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                Blocked devices · {blocked.length}
              </h3>
              {blocked.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">No blocked devices.</p>
              ) : (
                <ul className="divide-y divide-border/70 rounded-xl border border-border/80 bg-card">
                  {blocked.map((d) => (
                    <li key={d.blocked_device_id} className="flex flex-wrap items-center gap-3 p-3">
                      <div className="shrink-0 w-9 h-9 rounded-xl bg-destructive/10 text-destructive flex items-center justify-center">
                        <DeviceIcon session={{ client_type: d.client_type as DeviceSession['client_type'], device_type: d.device_type as DeviceSession['device_type'] }} className="w-4.5 h-4.5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-bold">{d.device_name ?? 'Unknown device'}</p>
                        <p className="text-[11px] text-muted-foreground">
                          Blocked {relativeTime(d.created_at)}{d.blocked_by ? ` by ${d.blocked_by}` : ''}{d.reason ? ` · ${d.reason}` : ''}
                        </p>
                      </div>
                      <DeviceActionButton onClick={() => setPending({ kind: 'unblock', device: d })} disabled={busy}>
                        <ShieldOff className="w-3 h-3" /> Unblock
                      </DeviceActionButton>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
