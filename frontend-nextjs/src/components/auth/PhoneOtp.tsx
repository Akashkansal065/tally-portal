'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Loader2 } from 'lucide-react'
import { confirmOtp, forgetOtp, sendOtp } from '@/lib/phone-auth'

export const otpBox = 'px-4 py-3 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm'
export const otpField = `w-full ${otpBox}`
export const otpLabel = 'block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5'
export const otpMainButton = 'w-full flex items-center justify-center gap-2 py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl transition-all active:scale-[0.98] disabled:opacity-50 text-sm uppercase tracking-wider shadow-lg shadow-primary/20 cursor-pointer'
const RESEND_AFTER_SECONDS = 30

/**
 * Confirm a mobile number: the number, then the code sent to it. `onConfirmed` gets Firebase's proof (an ID
 * token) for the server to check; what it throws is shown under the code. With `lockedPhone` the number is
 * fixed (an invitation named it) and only the code is asked for.
 */
export function PhoneOtp({ lockedPhone, hint, onConfirmed }: {
  lockedPhone?: string
  hint?: string
  onConfirmed: (idToken: string, phone: string) => Promise<void>
}) {
  const [step, setStep] = useState<'number' | 'code'>('number')
  const [countryCode, setCountryCode] = useState('+91')
  const [number, setNumber] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [resendIn, setResendIn] = useState(0)
  const anchor = useRef<HTMLDivElement>(null)

  const digits = number.replace(/\D/g, '')
  const phone = lockedPhone || `${countryCode.trim()}${digits}`
  const validPhone = /^\+[1-9]\d{7,14}$/.test(phone) && (Boolean(lockedPhone) || countryCode.trim() !== '+91' || digits.length === 10)

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn(s => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  // Leaving the page gives up a code that was waiting
  useEffect(() => () => { forgetOtp() }, [])

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

  const send = () => run(async () => {
    if (!validPhone) throw new Error('Enter your 10-digit mobile number.')
    if (!anchor.current) return
    await sendOtp(phone, anchor.current)
    setCode('')
    setResendIn(RESEND_AFTER_SECONDS)
    setStep('code')
  })

  const verify = () => run(async () => onConfirmed(await confirmOtp(code), phone))

  const startOver = () => {
    forgetOtp()
    setCode('')
    setError('')
    setStep('number')
  }

  const spinner = <Loader2 className="h-4 w-4 animate-spin" />

  return (
    <div>
      {error && (
        <div role="alert" className="mb-4 p-3 rounded-xl bg-destructive/10 text-destructive text-sm break-words">{error}</div>
      )}

      {step === 'number' && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); send() }}>
          <div>
            <label htmlFor="phone-number" className={otpLabel}>Mobile number</label>
            {lockedPhone ? (
              <input id="phone-number" value={lockedPhone} readOnly className={`${otpField} opacity-80`} />
            ) : (
              <div className="flex gap-2">
                <input aria-label="Country code" value={countryCode} onChange={e => setCountryCode(e.target.value.replace(/[^\d+]/g, '').slice(0, 5))}
                  inputMode="tel" autoComplete="tel-country-code" className={`${otpBox} w-20 shrink-0 px-2 text-center`} />
                <input id="phone-number" value={number} onChange={e => setNumber(e.target.value.replace(/[^\d ]/g, '').slice(0, 15))}
                  type="tel" inputMode="numeric" autoComplete="tel-national" placeholder="98765 43210" required autoFocus className={`${otpBox} min-w-0 flex-1`} />
              </div>
            )}
            <p className="mt-1.5 text-xs text-muted-foreground">{hint || 'We send a 6-digit code by SMS to confirm it.'}</p>
          </div>
          <button type="submit" disabled={busy || !validPhone && Boolean(lockedPhone) || !lockedPhone && !number.trim()} className={otpMainButton}>
            {busy ? spinner : <ArrowRight className="h-4 w-4" />}{busy ? 'Sending...' : 'Send code'}
          </button>
        </form>
      )}

      {step === 'code' && (
        <form className="space-y-4" onSubmit={e => { e.preventDefault(); verify() }}>
          <div>
            <label htmlFor="phone-code" className={otpLabel}>Code sent to {phone}</label>
            <input id="phone-code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              inputMode="numeric" autoComplete="one-time-code" placeholder="6-digit code" required autoFocus
              className={`${otpField} text-center text-lg tracking-[0.4em]`} />
          </div>
          <button type="submit" disabled={busy || code.length < 6} className={otpMainButton}>
            {busy ? spinner : <ArrowRight className="h-4 w-4" />}{busy ? 'Checking...' : 'Continue'}
          </button>
          <div className="flex justify-between text-xs text-muted-foreground">
            {lockedPhone ? <span /> : <button type="button" onClick={startOver} className="font-semibold underline cursor-pointer">Change number</button>}
            <button type="button" onClick={send} disabled={busy || resendIn > 0} className="font-semibold underline disabled:no-underline disabled:opacity-60 cursor-pointer">
              {resendIn > 0 ? `Send again in ${resendIn}s` : 'Send the code again'}
            </button>
          </div>
        </form>
      )}

      {/* The invisible security check Firebase needs before it sends an SMS attaches here */}
      <div ref={anchor} />
    </div>
  )
}
