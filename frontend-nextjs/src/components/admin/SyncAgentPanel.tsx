'use client'

import { useEffect, useState } from 'react'
import { Copy, Loader2, MonitorCog, Trash2, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { API_BASE, authHeaders } from '@/lib/utils'

const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

type Device = { device_id: number; name: string | null; signed_in: boolean; last_seen_at: string | null; companies: { company_id: number; name: string }[] }
type AdminAccess = { user_id: number; username: string; email: string; allowed: boolean }
type Invite = { invite_id: number; email: string; role_id: number; company_ids: number[]; expires_at: string; status: 'open' | 'accepted' | 'closed' }
type Company = { company_id: number; name: string }

async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(token) })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`)
  return body as T
}

/** Admin → Sync agent & team: the PCs signed in to the sync agent, who may use it, and invitations to join. */
export function SyncAgentPanel({ token, companies }: { token: string | null; companies: Company[] }) {
  const [devices, setDevices] = useState<Device[] | null>(null)
  const [admins, setAdmins] = useState<AdminAccess[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [roles, setRoles] = useState<{ role_id: number; name: string }[]>([])
  const [reload, setReload] = useState(0)
  const [email, setEmail] = useState('')
  const [roleId, setRoleId] = useState('')
  const [companyIds, setCompanyIds] = useState<number[]>([])
  const [saving, setSaving] = useState(false)
  const [newInvite, setNewInvite] = useState<{ email: string; token: string; emailed: boolean } | null>(null)

  useEffect(() => {
    if (!token) return
    let current = true
    Promise.all([
      call<Device[]>(token, '/admin/agent-devices'),
      call<AdminAccess[]>(token, '/admin/sync-agent-access'),
      call<Invite[]>(token, '/admin/invites'),
      call<{ role_id: number; name: string }[]>(token, '/admin/roles'),
    ]).then(([d, a, i, r]) => {
      if (!current) return
      setDevices(d)
      setAdmins(a)
      setInvites(i)
      setRoles(Array.isArray(r) ? r : [])
    }).catch(e => {
      if (current) setDevices([])
      toast.error(e instanceof Error ? e.message : 'Could not load the sync agent settings')
    })
    return () => { current = false }
  }, [token, reload])

  if (!token) return null
  const run = async (work: () => Promise<unknown>, done: string) => {
    try {
      await work()
      toast.success(done)
      setReload(k => k + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'That did not work')
    }
  }
  const signOut = (device: Device) => {
    if (!window.confirm(`Sign ${device.name || 'this PC'} out of the sync agent? Its companies stop syncing until a PC links them again.`)) return
    run(() => call(token, `/admin/agent-devices/${device.device_id}/revoke`, { method: 'POST' }), 'PC signed out')
  }
  const invite = async () => {
    setSaving(true)
    try {
      const created = await call<{ invite_token: string; email: string; email_sent: boolean }>(token, '/admin/invites', {
        method: 'POST', body: JSON.stringify({ email, role_id: Number(roleId), company_ids: companyIds }),
      })
      setNewInvite({ email: created.email, token: created.invite_token, emailed: created.email_sent })
      setEmail('')
      setReload(k => k + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not send the invitation')
    } finally {
      setSaving(false)
    }
  }
  const toggleCompany = (id: number) => setCompanyIds(ids => (ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id]))
  const inviteLink = newInvite ? `${window.location.origin}/accept-invite?token=${newInvite.token}` : ''
  const openInvites = invites.filter(i => i.status === 'open')

  return (
    <div className="space-y-4 font-sans">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <h2 className="flex items-center gap-1.5 text-sm font-extrabold uppercase tracking-wider"><MonitorCog className="h-4 w-4" /> Sync agent PCs</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Each PC running the Desktop Sync Agent signs in here once. A company is synced from one PC at a time.
        </p>
        {devices === null ? <Loader2 className="mt-3 h-5 w-5 animate-spin text-primary" /> : devices.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">No PC has signed in to the sync agent yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {devices.map(d => (
              <li key={d.device_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0">
                  <span className="font-semibold">{d.name || 'Unnamed PC'}</span>
                  <span className="text-muted-foreground"> · {d.signed_in ? 'signed in' : 'signed out'}</span>
                  <span className="block text-xs text-muted-foreground">
                    {d.companies.length ? `Syncs ${d.companies.map(c => c.name).join(', ')}` : 'No company linked'}
                    {d.last_seen_at ? ` · last seen ${new Date(`${d.last_seen_at}Z`).toLocaleString('en-IN')}` : ''}
                  </span>
                </span>
                {d.signed_in && (
                  <button type="button" onClick={() => signOut(d)}
                    className="min-h-10 shrink-0 rounded-xl border border-border px-3 text-xs font-bold text-rose-700 hover:bg-rose-500/10 dark:text-rose-400 cursor-pointer">
                    Sign out
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h3 className="text-sm font-bold">Who may use the sync agent</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Only admins ticked here can sign a PC in, link companies and sign PCs out. Changing this needs the permission yourself, and at least one admin must keep it.
        </p>
        <ul className="mt-3 divide-y divide-border">
          {admins.map(a => (
            <li key={a.user_id} className="py-2">
              <label className="flex min-h-10 cursor-pointer items-center gap-3 text-sm">
                <input type="checkbox" className="h-4 w-4" checked={a.allowed}
                  onChange={e => run(() => call(token, `/admin/users/${a.user_id}/sync-agent`, { method: 'PUT', body: JSON.stringify({ allowed: e.target.checked }) }),
                    e.target.checked ? `${a.username} can use the sync agent` : `${a.username} can no longer use the sync agent`)} />
                <span><span className="font-semibold">{a.username}</span> <span className="text-muted-foreground">{a.email}</span></span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h3 className="flex items-center gap-1.5 text-sm font-bold"><UserPlus className="h-4 w-4" /> Invite someone</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          People join your business by invitation. They choose their own password; the invitation works once and expires in 7 days.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-sm"><span className="mb-1 block font-semibold">Email</span>
            <input type="email" autoComplete="off" value={email} onChange={e => setEmail(e.target.value)} className={field} /></label>
          <label className="text-sm"><span className="mb-1 block font-semibold">Role</span>
            <select value={roleId} onChange={e => setRoleId(e.target.value)} className={field}>
              <option value="">Choose a role</option>
              {roles.map(r => <option key={r.role_id} value={r.role_id}>{r.name}</option>)}
            </select></label>
        </div>
        <fieldset className="mt-3 text-sm">
          <legend className="mb-1 font-semibold">Companies they can open</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-1">
            {companies.map(c => (
              <label key={c.company_id} className="flex min-h-10 cursor-pointer items-center gap-2">
                <input type="checkbox" className="h-4 w-4" checked={companyIds.includes(c.company_id)} onChange={() => toggleCompany(c.company_id)} />
                {c.name}
              </label>
            ))}
          </div>
        </fieldset>
        <button type="button" onClick={invite} disabled={saving || !email || !roleId || companyIds.length === 0}
          className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Send invitation
        </button>

        {newInvite && (
          <div className="mt-3 rounded-xl border border-border bg-background p-3 text-sm">
            <p>
              {newInvite.emailed
                ? `Invitation emailed to ${newInvite.email}. You can also pass this link on yourself.`
                : `The email to ${newInvite.email} could not be sent. Pass this link on yourself.`} It is shown only now.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg bg-muted px-2 py-1 text-xs">{inviteLink}</code>
              <button type="button" aria-label="Copy the invitation link"
                onClick={() => navigator.clipboard.writeText(inviteLink).then(() => toast.success('Link copied'))}
                className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-xl border border-border hover:bg-muted cursor-pointer">
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {openInvites.length > 0 && (
          <ul className="mt-4 divide-y divide-border">
            {openInvites.map(i => (
              <li key={i.invite_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>
                  <span className="font-semibold">{i.email}</span>
                  <span className="text-muted-foreground"> · waiting · expires {new Date(`${i.expires_at}Z`).toLocaleDateString('en-IN')}</span>
                </span>
                <button type="button" aria-label={`Cancel the invitation for ${i.email}`}
                  onClick={() => run(() => call(token, `/admin/invites/${i.invite_id}`, { method: 'DELETE' }), 'Invitation cancelled')}
                  className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-xl text-rose-700 hover:bg-rose-500/10 dark:text-rose-400 cursor-pointer">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
