'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE } from '@/lib/utils'
import { Eye, EyeOff, LogIn } from 'lucide-react'

export default function LoginPage() {
  const { user, isLoading, login } = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Auto-bootstrap checking states
  const [needBootstrap, setNeedBootstrap] = useState(false)
  const [companyName, setCompanyName] = useState('')
  const [mailingName, setMailingName] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
  const [companyState, setCompanyState] = useState('')
  const [country, setCountry] = useState('India')
  const [pincode, setPincode] = useState('')
  const [telephone, setTelephone] = useState('')
  const [mobile, setMobile] = useState('')
  const [website, setWebsite] = useState('')
  const [financialYearStart, setFinancialYearStart] = useState('2026-04-01')
  const [booksBeginDate, setBooksBeginDate] = useState('2026-04-01')
  const [baseCurrency, setBaseCurrency] = useState('INR')
  const [registerUsername, setRegisterUsername] = useState('')

  useEffect(() => {
    if (!isLoading && user) router.replace('/')
  }, [user, isLoading, router])

  useEffect(() => {
    const checkBootstrap = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/bootstrap-status`)
        if (res.ok) {
          const data = await res.json()
          setNeedBootstrap(data.need_bootstrap)
        }
      } catch (e) {
        console.error('Error fetching bootstrap status:', e)
      }
    }
    checkBootstrap()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      if (needBootstrap) {
        // Register Company & Admin User with full Tally Prime profile fields
        const res = await fetch(`${API_BASE}/auth/register-company`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_name: companyName,
            mailing_name: mailingName,
            address_line1: addressLine1,
            address_line2: addressLine2,
            state: companyState,
            country: country,
            pincode: pincode,
            telephone: telephone,
            mobile: mobile,
            website: website,
            financial_year_start: financialYearStart,
            books_begin_date: booksBeginDate,
            base_currency: baseCurrency,
            username: registerUsername,
            email,
            password
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Setup failed.')
        }
        
        // Log in immediately after registration
        const loginRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        if (!loginRes.ok) {
          throw new Error('Bootstrap success, but login failed. Please sign in.')
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
            {needBootstrap ? 'First-time Setup — Configure Admin Account' : 'Mobile ERP — Sign in to continue'}
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
            {needBootstrap && (
              <>
                <div className="border border-border/80 bg-muted/20 p-4 rounded-2xl space-y-3.5">
                  <div className="text-xs font-bold text-primary uppercase tracking-wider border-b border-border pb-1.5 flex items-center gap-1.5">
                    <span>🏢</span> Company Profile (Tally Details)
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                      Company Name *
                    </label>
                    <input
                      type="text"
                      value={companyName}
                      onChange={e => setCompanyName(e.target.value)}
                      required
                      placeholder="e.g. Sneh Distributors Pvt Ltd"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                      Mailing Name
                    </label>
                    <input
                      type="text"
                      value={mailingName}
                      onChange={e => setMailingName(e.target.value)}
                      placeholder="e.g. Sneh Distributors Pvt Ltd"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                        Address Line 1
                      </label>
                      <input
                        type="text"
                        value={addressLine1}
                        onChange={e => setAddressLine1(e.target.value)}
                        placeholder="Street / Area"
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                        Address Line 2
                      </label>
                      <input
                        type="text"
                        value={addressLine2}
                        onChange={e => setAddressLine2(e.target.value)}
                        placeholder="Landmark / City"
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                        State
                      </label>
                      <input
                        type="text"
                        value={companyState}
                        onChange={e => setCompanyState(e.target.value)}
                        placeholder="State"
                        className="w-full px-2.5 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                        Country
                      </label>
                      <input
                        type="text"
                        value={country}
                        onChange={e => setCountry(e.target.value)}
                        placeholder="India"
                        className="w-full px-2.5 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                        Pincode
                      </label>
                      <input
                        type="text"
                        value={pincode}
                        onChange={e => setPincode(e.target.value)}
                        placeholder="Pincode"
                        className="w-full px-2.5 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                        Telephone
                      </label>
                      <input
                        type="text"
                        value={telephone}
                        onChange={e => setTelephone(e.target.value)}
                        placeholder="Landline"
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                        Mobile
                      </label>
                      <input
                        type="text"
                        value={mobile}
                        onChange={e => setMobile(e.target.value)}
                        placeholder="Mobile No."
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                      Website
                    </label>
                    <input
                      type="text"
                      value={website}
                      onChange={e => setWebsite(e.target.value)}
                      placeholder="www.example.com"
                      className="w-full px-3.5 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                        Financial Year Start *
                      </label>
                      <input
                        type="date"
                        value={financialYearStart}
                        onChange={e => setFinancialYearStart(e.target.value)}
                        required
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-semibold text-muted-foreground uppercase mb-1">
                        Books Beginning From *
                      </label>
                      <input
                        type="date"
                        value={booksBeginDate}
                        onChange={e => setBooksBeginDate(e.target.value)}
                        required
                        className="w-full px-3 py-2 rounded-xl border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                    Admin Username *
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
                  autoComplete={needBootstrap ? 'new-password' : 'current-password'}
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
              {submitting ? 'Processing...' : needBootstrap ? 'Register & Log In' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
