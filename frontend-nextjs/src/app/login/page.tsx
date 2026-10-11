'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, afterLoginPath } from '@/lib/utils'
import { getDeviceHeaders } from '@/lib/device'
import { Eye, EyeOff, LogIn } from 'lucide-react'
import { PhoneSignIn } from '@/components/auth/PhoneSignIn'
import { phoneSignInOffered } from '@/lib/phone-auth'

export default function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Mobile number sign-in is shown first where it is switched on; email and password is always there
  const [phoneOffered, setPhoneOffered] = useState(false)
  const [way, setWay] = useState<'phone' | 'email'>('email')

  useEffect(() => {
    if (!isLoading && user) router.replace(afterLoginPath())
  }, [user, isLoading, router])

  useEffect(() => {
    let gone = false
    phoneSignInOffered().then(offered => {
      if (gone || !offered) return
      setPhoneOffered(true)
      setWay('phone')
    })
    return () => { gone = true }
  }, [])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const qToken = params.get('token')
      const qEmail = params.get('email')
      if (qToken && qEmail) {
        login(qToken, qEmail).then(() => {
          router.replace('/admin')
        })
      }
    }
  }, [login, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(await getDeviceHeaders()) },
        body: JSON.stringify({ email, password }),
        cache: 'no-store',
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Invalid email or password.')
      }
      const { access_token } = await res.json()
      await login(access_token, email)
      router.replace(afterLoginPath())
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Action failed. Please check input.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-background via-muted/30 to-background">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-2xl mb-4">
            <span className="text-3xl font-black text-primary">S</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">Sneh Distributors</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Mobile ERP — Sign in to continue
          </p>
        </div>

        {way === 'phone' ? (
          <div className="bg-card border border-border rounded-3xl p-6 shadow-xl shadow-black/5">
            <PhoneSignIn />
            <p className="mt-4 text-center text-xs text-muted-foreground">
              <button type="button" onClick={() => setWay('email')} className="font-semibold underline cursor-pointer">Sign in with email and password</button>
              {' · '}Joining a business? <a href="/accept-invite" className="font-semibold underline">Accept your invitation</a>.
            </p>
          </div>
        ) : (
        <div className="bg-card border border-border rounded-3xl p-6 shadow-xl shadow-black/5">
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-destructive/10 text-destructive text-sm flex items-start gap-2">
              <span>⚠️</span>
              <span className="break-words">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 pr-11 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl transition-all active:scale-[0.98] disabled:opacity-50 text-sm uppercase tracking-wider shadow-lg shadow-primary/20"
            >
              {submitting ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <LogIn className="h-4 w-4" />
              )}
              {submitting ? 'Processing...' : 'Sign In'}
            </button>
          </form>
          {/* A new account starts with a mobile number, where that is switched on; people join one by invitation */}
          <p className="mt-4 text-center text-xs text-muted-foreground">
            {phoneOffered && (
              <>
                <button type="button" onClick={() => setWay('phone')} className="font-semibold underline cursor-pointer">Sign in or sign up with your mobile number</button>
                {' · '}
              </>
            )}
            Joining a business? <a href="/accept-invite" className="font-semibold underline">Accept your invitation</a>.
          </p>
        </div>
        )}
      </div>
    </div>
  )
}
