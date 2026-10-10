'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, UserCheck } from 'lucide-react'
import { API_BASE } from '@/lib/utils'
import { LinkParams } from '@/components/LinkParams'
import { useAuth } from '@/context/AuthContext'

const field = 'h-11 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

/** Join a business from an invitation: confirm what it is for, choose a name and password, then sign in. */
export default function AcceptInvitePage() {
  const router = useRouter()
  const { user, logout } = useAuth()
  const [token, setToken] = useState('')
  const [invite, setInvite] = useState<{ email: string; account_name: string } | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const lookUp = async (value: string) => {
    const code = value.trim()
    if (!code) return
    setBusy(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/auth/invites/${encodeURIComponent(code)}`)
      const body = await res.json().catch(() => null)
      if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'This invitation could not be checked.')
      setInvite(body)
    } catch (e) {
      setInvite(null)
      setError(e instanceof Error ? e.message : 'This invitation could not be checked.')
    } finally {
      setBusy(false)
    }
  }

  // The emailed link carries the invitation
  const fromLink = (params: URLSearchParams) => {
    const code = params.get('token') || ''
    if (code) {
      setToken(code)
      lookUp(code)
    }
  }

  const accept = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/auth/invites/accept`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim(), username: username.trim(), password }),
      })
      const body = await res.json().catch(() => null)
      if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'The invitation could not be accepted.')
      setDone(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The invitation could not be accepted.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="mx-auto flex min-h-[80vh] w-full max-w-md flex-col justify-center px-4 py-10 font-sans">
      <LinkParams onChange={fromLink} />
      <h1 className="flex items-center gap-2 text-xl font-extrabold"><UserCheck className="h-5 w-5" /> Accept your invitation</h1>

      {done ? (
        <div className="mt-4 space-y-4 text-sm">
          <p>Your account is ready. Sign in with <span className="font-semibold">{invite?.email}</span> and the password you chose.</p>
          <button type="button" onClick={() => { if (user) logout(); router.replace('/login') }}
            className="min-h-11 w-full rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground cursor-pointer">Go to sign in</button>
        </div>
      ) : !invite ? (
        <form className="mt-4 space-y-3 text-sm" onSubmit={e => { e.preventDefault(); lookUp(token) }}>
          <p className="text-muted-foreground">Open the link from your invitation email, or paste the invitation code here.</p>
          <label className="block"><span className="mb-1 block font-semibold">Invitation code</span>
            <input value={token} onChange={e => setToken(e.target.value)} autoComplete="off" className={field} /></label>
          {error && <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p>}
          <button type="submit" disabled={busy || !token.trim()}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Continue
          </button>
        </form>
      ) : (
        <form className="mt-4 space-y-3 text-sm" onSubmit={accept}>
          <p>You are joining <span className="font-semibold">{invite.account_name}</span> as <span className="font-semibold">{invite.email}</span>.</p>
          {user && user.email !== invite.email && (
            <p className="text-muted-foreground">This device is signed in as {user.email}. Going on to sign in as {invite.email} signs that person out here.</p>
          )}
          <label className="block"><span className="mb-1 block font-semibold">Your name</span>
            <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="name" maxLength={50} required className={field} /></label>
          <label className="block"><span className="mb-1 block font-semibold">Choose a password</span>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required className={field} />
            <span className="text-xs text-muted-foreground">8 characters or more</span></label>
          {error && <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p>}
          <button type="submit" disabled={busy || !username.trim() || password.length < 8}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create my account
          </button>
        </form>
      )}
    </main>
  )
}
