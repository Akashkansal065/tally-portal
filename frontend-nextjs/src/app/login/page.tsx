'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE } from '@/lib/utils'
import { Eye, EyeOff, LogIn } from 'lucide-react'

export default function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const router = useRouter()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Registration states
  const [companyName, setCompanyName] = useState('')
  const [booksBeginDate, setBooksBeginDate] = useState('2026-04-01')
  const [registerUsername, setRegisterUsername] = useState('')

  useEffect(() => {
    if (!isLoading && user) router.replace('/')
  }, [user, isLoading, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (isRegister) {
        // Register Company & Admin User
        const res = await fetch(`${API_BASE}/auth/register-company`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: companyName,
            books_begin_date: booksBeginDate,
            username: registerUsername,
            email,
            password
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Registration failed.')
        }
        
        // Log in immediately after registration
        const loginRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!loginRes.ok) {
          throw new Error('Company registered, but login failed. Please sign in.')
        }
        const { access_token } = await loginRes.json()
        await login(access_token, email)
        router.replace('/')
      } else {
        // Normal Sign In
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Invalid email or password.')
        }
        const { access_token } = await res.json()
        await login(access_token, email)
        router.replace('/')
      }
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
            {isRegister ? 'Create a new Company & Admin profile' : 'Mobile ERP — Sign in to continue'}
          </p>
        </div>

        <div className="bg-card border border-border rounded-3xl p-6 shadow-xl shadow-black/5">
          {error && (
            <div className="mb-4 p-3 rounded-xl bg-destructive/10 text-destructive text-sm flex items-start gap-2">
              <span>⚠️</span>
              <span className="break-all">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={e => setCompanyName(e.target.value)}
                    required
                    placeholder="e.g. Sneh Distributors Pvt Ltd"
                    className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Books Beginning Date
                  </label>
                  <input
                    type="date"
                    value={booksBeginDate}
                    onChange={e => setBooksBeginDate(e.target.value)}
                    required
                    className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Admin Name
                  </label>
                  <input
                    type="text"
                    value={registerUsername}
                    onChange={e => setRegisterUsername(e.target.value)}
                    required
                    placeholder="e.g. Akash Kansal"
                    className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  />
                </div>
              </>
            )}

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
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
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
              {submitting ? 'Processing...' : isRegister ? 'Register & Log In' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-border flex justify-between items-center text-xs">
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister)
                setError('')
              }}
              className="text-primary font-bold hover:underline"
            >
              {isRegister ? 'Already have a company? Sign In' : 'Register New Company'}
            </button>
          </div>

          {!isRegister && (
            <p className="text-center text-[10px] text-muted-foreground mt-4">
              Demo: <span className="font-mono text-primary">admin_test@test.com</span> / <span className="font-mono text-primary">securepassword123</span>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
