'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, UserCheck } from 'lucide-react'
import { API_BASE } from '@/lib/utils'
import { LinkParams } from '@/components/LinkParams'
import { useAuth } from '@/context/AuthContext'
import { PhoneOtp } from '@/components/auth/PhoneOtp'
import { phonePost } from '@/components/auth/PhoneSignIn'
import { forgetOtp, phoneSignInOffered } from '@/lib/phone-auth'

const field = 'h-11 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

/**
 * Join a business from an invitation: confirm what it is for, give a name, then either choose a password or,
 * where mobile number sign-in is on, confirm a mobile number with an OTP and sign in with that from then on.
 * An invitation that names a mobile number can only be accepted by confirming that number.
 */
export default function AcceptInvitePage() {
  const router = useRouter()
  const { user, logout, login } = useAuth()
  const [token, setToken] = useState('')
  const [invite, setInvite] = useState<{ email: string; account_name: string; phone?: string | null } | null>(null)
  const [phoneOffered, setPhoneOffered] = useState(false)
  const [chosen, setChosen] = useState<'phone' | 'password' | null>(null)

  useEffect(() => {
    let gone = false
    phoneSignInOffered().then(offered => { if (!gone) setPhoneOffered(offered) })
    return () => { gone = true }
  }, [])

  // A named number must be confirmed; otherwise the person picks, and the mobile number is offered first
  const mustConfirmPhone = Boolean(invite?.phone) && phoneOffered
  const way = mustConfirmPhone ? 'phone' : chosen ?? (phoneOffered ? 'phone' : 'password')

  const joinWithPhone = async (idToken: string) => {
    if (!username.trim()) throw new Error('Enter your name above first.')
    const signed = await phonePost('/auth/phone/join', { id_token: idToken, full_name: username.trim(), token: token.trim() })
    await forgetOtp()
    await login(signed.access_token, signed.phone)
    router.replace('/')
  }
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
        <div className="mt-4 space-y-3 text-sm">
          <p>You are joining <span className="font-semibold">{invite.account_name}</span>{invite.email && <> as <span className="font-semibold">{invite.email}</span></>}.</p>
          {user && (
            <p className="text-muted-foreground">This device is signed in as {user.email || user.username}. Joining signs that person out here.</p>
          )}
          <label className="block"><span className="mb-1 block font-semibold">Your name</span>
            <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="name" maxLength={50} required className={field} /></label>

          {way === 'phone' ? (
            <div className="space-y-3 pt-1">
              <p className="font-semibold">Confirm your mobile number</p>
              <PhoneOtp lockedPhone={invite.phone || undefined} onConfirmed={joinWithPhone}
                hint={invite.phone ? 'Your admin invited this number. We send it a 6-digit code by SMS.' : 'We send a 6-digit code by SMS. You sign in with this number from now on.'} />
              {!mustConfirmPhone && invite.email && (
                <button type="button" onClick={() => setChosen('password')} className="w-full text-center font-semibold underline cursor-pointer">Use a password instead</button>
              )}
            </div>
          ) : (
            <form className="space-y-3" onSubmit={accept}>
              <label className="block"><span className="mb-1 block font-semibold">Choose a password</span>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required className={field} />
                <span className="text-xs text-muted-foreground">8 characters or more</span></label>
              {error && <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p>}
              <button type="submit" disabled={busy || !username.trim() || password.length < 8}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
                {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create my account
              </button>
              {phoneOffered && (
                <button type="button" onClick={() => setChosen('phone')} className="w-full text-center font-semibold underline cursor-pointer">Confirm a mobile number instead</button>
              )}
            </form>
          )}
        </div>
      )}
    </main>
  )
}
