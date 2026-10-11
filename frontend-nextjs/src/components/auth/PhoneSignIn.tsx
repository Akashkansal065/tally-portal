'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, afterLoginPath } from '@/lib/utils'
import { getDeviceHeaders } from '@/lib/device'
import { forgetOtp } from '@/lib/phone-auth'
import { PhoneOtp, otpField as field, otpLabel as label, otpMainButton as mainButton } from '@/components/auth/PhoneOtp'

type Step = 'otp' | 'join' | 'details'

/** POST to a mobile number sign-in endpoint; the server's own words are what a failure says. */
export async function phonePost(path: string, body: object) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await getDeviceHeaders()) },
    body: JSON.stringify(body),
    cache: 'no-store',
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Sign-in failed. Try again.')
  return data
}

/**
 * Sign in or sign up with a mobile number. Once the number is confirmed: someone who has an account is signed
 * in; a number an admin invited joins that business after giving a name; any other number gives the few
 * details a new business needs. A new business has no Tally PC, so the app then holds it at Connect Tally.
 */
export function PhoneSignIn() {
  const { login } = useAuth()
  const router = useRouter()
  const [step, setStep] = useState<Step>('otp')
  const [phone, setPhone] = useState('')
  const [idToken, setIdToken] = useState('')
  const [invitedTo, setInvitedTo] = useState('')
  const [details, setDetails] = useState({ full_name: '', business_name: '', pincode: '', email: '', accept_terms: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const enter = async (signed: { access_token: string; phone: string }) => {
    await forgetOtp()
    const next = afterLoginPath()
    await login(signed.access_token, signed.phone)
    // A business with no Tally PC yet is taken to Connect Tally from wherever this goes (RouteGuard)
    router.replace(next)
  }

  const confirmed = async (token: string, number: string) => {
    const answer = await phonePost('/auth/phone/login', { id_token: token })
    if (answer.registered) return enter(answer)
    setIdToken(token)
    setPhone(number)
    setInvitedTo(answer.invite?.account_name || '')
    setStep(answer.invite ? 'join' : 'details')
  }

  const run = async (work: () => Promise<void>) => {
    setError('')
    setBusy(true)
    try {
      await work()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const join = () => run(async () => enter(await phonePost('/auth/phone/join', { id_token: idToken, full_name: details.full_name.trim() })))

  const register = () => run(async () => enter(await phonePost('/auth/phone/register', {
    id_token: idToken,
    full_name: details.full_name.trim(),
    business_name: details.business_name.trim(),
    pincode: details.pincode.trim() || null,
    email: details.email.trim() || null,
    accept_terms: details.accept_terms,
  })))

  const startOver = () => {
    forgetOtp()
    setIdToken('')
    setError('')
    setStep('otp')
  }

  if (step === 'otp') {
    return <PhoneOtp onConfirmed={confirmed} hint="We send a 6-digit code by SMS to confirm it. New here? This also creates your account." />
  }

  const nameField = (
    <div>
      <label htmlFor="reg-name" className={label}>Your name</label>
      <input id="reg-name" value={details.full_name} onChange={e => setDetails({ ...details, full_name: e.target.value })}
        autoComplete="name" maxLength={50} required autoFocus className={field} />
    </div>
  )
  const differentNumber = (
    <button type="button" onClick={startOver} className="font-semibold underline cursor-pointer">Use a different number</button>
  )

  return (
    <div>
      {error && (
        <div role="alert" className="mb-4 p-3 rounded-xl bg-destructive/10 text-destructive text-sm break-words">{error}</div>
      )}

      {step === 'join' && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); join() }}>
          <p className="text-sm text-muted-foreground"><span className="font-semibold text-foreground">{phone}</span> is confirmed.
            You have been invited to join <span className="font-semibold text-foreground">{invitedTo}</span>.</p>
          {nameField}
          <button type="submit" disabled={busy || !details.full_name.trim()} className={mainButton}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}{busy ? 'Joining...' : `Join ${invitedTo}`}
          </button>
          <p className="flex justify-between text-xs text-muted-foreground">
            {differentNumber}
            <button type="button" onClick={() => { setError(''); setStep('details') }} className="font-semibold underline cursor-pointer">Start my own business instead</button>
          </p>
        </form>
      )}

      {step === 'details' && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); register() }}>
          <p className="text-sm text-muted-foreground"><span className="font-semibold text-foreground">{phone}</span> is confirmed. A few details to create your account.</p>
          {nameField}
          <div>
            <label htmlFor="reg-business" className={label}>Business name</label>
            <input id="reg-business" value={details.business_name} onChange={e => setDetails({ ...details, business_name: e.target.value })}
              autoComplete="organization" maxLength={150} required className={field} />
          </div>
          <div>
            <label htmlFor="reg-pincode" className={label}>Pin code</label>
            <input id="reg-pincode" value={details.pincode} onChange={e => setDetails({ ...details, pincode: e.target.value.replace(/\D/g, '').slice(0, 6) })}
              inputMode="numeric" autoComplete="postal-code" className={field} />
          </div>
          <div>
            <label htmlFor="reg-email" className={label}>Email address (optional)</label>
            <input id="reg-email" type="email" value={details.email} onChange={e => setDetails({ ...details, email: e.target.value })}
              autoComplete="email" maxLength={120} className={field} />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={details.accept_terms} onChange={e => setDetails({ ...details, accept_terms: e.target.checked })} className="mt-0.5 h-4 w-4" />
            <span>I accept the terms of service and the privacy policy</span>
          </label>
          <button type="submit" disabled={busy || !details.full_name.trim() || !details.business_name.trim() || !details.accept_terms} className={mainButton}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}{busy ? 'Creating...' : 'Create account'}
          </button>
          <p className="text-center text-xs text-muted-foreground">{differentNumber}</p>
        </form>
      )}
    </div>
  )
}
