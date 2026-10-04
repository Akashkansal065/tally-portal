'use client'

import { useCallback, useMemo, useState } from 'react'
import { useLoader } from '@/lib/use-loader'
import { toast } from 'sonner'
import { Loader2, LogOut, MonitorSmartphone, RefreshCw } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { ConfirmBar, DeviceActionButton, DeviceList } from '@/components/DeviceList'
import { listMySessions, revokeMyOtherSessions, revokeMySession, type DeviceSession } from '@/lib/device-sessions'

type Pending = { kind: 'revoke'; session: DeviceSession } | { kind: 'others' }

/** Every user's own signed-in devices, with sign-out for a lost or shared phone. */
export default function MyDevicesPage() {
  const { token, logout } = useAuth()
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)

  const fetchSessions = useCallback(
    (): Promise<DeviceSession[]> => (token ? listMySessions(token) : Promise.resolve([])),
    [token],
  )
  const { data, error, loading, reload } = useLoader(fetchSessions)
  const sessions = useMemo(() => data ?? [], [data])

  const current = useMemo(() => sessions.filter((s) => s.is_current), [sessions])
  const others = useMemo(() => sessions.filter((s) => !s.is_current), [sessions])

  const confirm = async () => {
    if (!pending) return
    setBusy(true)
    try {
      if (pending.kind === 'others') {
        const { revoked } = await revokeMyOtherSessions(token)
        toast.success(revoked === 1 ? '1 other device was signed out.' : `${revoked} other devices were signed out.`)
      } else {
        await revokeMySession(token, pending.session.session_id)
        toast.success(`${pending.session.device_name} was signed out.`)
      }
      setPending(null)
      reload()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-full bg-muted/20 pb-10">
      <div className="bg-card border-b border-border/80 px-4 lg:px-8 py-6">
        <div className="max-w-3xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center border border-emerald-500/20">
              <MonitorSmartphone className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tight text-foreground">My devices</h1>
              <p className="text-xs text-muted-foreground">Where you&apos;re signed in. Sign out any device you don&apos;t recognise or no longer use.</p>
            </div>
          </div>
          <DeviceActionButton onClick={reload} disabled={loading || busy} title="Refresh">
            <RefreshCw className={loading ? 'w-3 h-3 animate-spin' : 'w-3 h-3'} /> Refresh
          </DeviceActionButton>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 lg:px-0 py-6 space-y-5">
        {error && <p className="text-xs font-semibold text-destructive">{error}</p>}

        {pending && (
          <ConfirmBar
            busy={busy}
            onCancel={() => setPending(null)}
            onConfirm={confirm}
            confirmLabel="Sign out"
            message={
              pending.kind === 'others'
                ? <>Sign out all {others.length} other device{others.length === 1 ? '' : 's'}? You stay signed in here.</>
                : <>Sign out <b>{pending.session.device_name}</b>?</>
            }
          />
        )}

        {loading && !data ? (
          <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
        ) : (
          <>
            <section className="space-y-2">
              <h2 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">This device</h2>
              <DeviceList
                sessions={current}
                emptyText="This device's session wasn't found. Try signing in again."
                actions={() => (
                  <DeviceActionButton onClick={logout}>
                    <LogOut className="w-3 h-3" /> Sign out
                  </DeviceActionButton>
                )}
              />
            </section>

            <section className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                  Other devices · {others.length}
                </h2>
                {others.length > 0 && (
                  <DeviceActionButton tone="danger" onClick={() => setPending({ kind: 'others' })} disabled={busy}>
                    <LogOut className="w-3 h-3" /> Sign out all other devices
                  </DeviceActionButton>
                )}
              </div>
              <DeviceList
                sessions={others}
                emptyText="You're not signed in anywhere else."
                actions={(s) => (
                  <DeviceActionButton onClick={() => setPending({ kind: 'revoke', session: s })} disabled={busy}>
                    <LogOut className="w-3 h-3" /> Sign out
                  </DeviceActionButton>
                )}
              />
            </section>

            <p className="text-[11px] text-muted-foreground">
              Lost a phone? Sign it out here, then ask your administrator to block it so it can&apos;t sign in again.
            </p>
          </>
        )}
      </div>
    </div>
  )
}
