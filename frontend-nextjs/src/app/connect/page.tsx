'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle2, Loader2, MonitorCog } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'

const field = 'h-12 w-full rounded-xl border border-border bg-background px-3 text-center font-mono text-lg uppercase tracking-[0.25em] focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'
const mainButton = 'inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer'

const STEPS = [
  'On the PC that runs TallyPrime, install and open MyTally Bridge.',
  'Open your company in TallyPrime, then choose "Connect with a code from the app" in MyTally Bridge.',
  'Enter the code it shows here.',
]

/**
 * Connect Tally: where someone who signed up in the app links the PC that runs TallyPrime. The PC shows a
 * code, it is entered here, and after confirming which PC it is, that PC is signed in to this business.
 * Until a business has a PC connected, the people who can connect one are kept on this page (RouteGuard);
 * an admin adding another PC later opens it by choice and can go back.
 */
export default function ConnectTallyPage() {
  const router = useRouter()
  const { token, user, logout } = useAuth()
  const [code, setCode] = useState('')
  const [found, setFound] = useState<{ device_name: string; account_name: string } | null>(null)
  const [connected, setConnected] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // The PC collects its sign-in a few seconds after the code is approved; only then does the app open
  const [collected, setCollected] = useState(false)
  // Someone adding another PC to a business that already has one is not waiting for anything
  const signedIn = collected || !user?.needs_tally_setup

  useEffect(() => {
    if (!connected || signedIn) return
    let gone = false
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token), cache: 'no-store' })
        if (!gone && res.ok && (await res.json()).needs_tally_setup === false) setCollected(true)
      } catch { /* offline for a moment: the next look will tell */ }
    }
    check()
    const timer = setInterval(check, 2000)
    return () => { gone = true; clearInterval(timer) }
  }, [connected, signedIn, token])

  const call = async (path: string) => {
    const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers: authHeaders(token), body: JSON.stringify({ code: code.trim() }) })
    const body = await res.json().catch(() => null)
    if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'That did not work. Try again.')
    return body
  }

  const run = async (work: () => Promise<void>) => {
    setError('')
    setBusy(true)
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const lookUp = () => run(async () => setFound(await call('/agent/pair/lookup')))
  const approve = () => run(async () => setConnected((await call('/agent/pair/approve')).device_name))

  return (
    <main className="mx-auto flex min-h-[80vh] w-full max-w-md flex-col justify-center px-4 py-10 font-sans">
      <h1 className="flex items-center gap-2 text-xl font-extrabold"><MonitorCog className="h-5 w-5" /> Connect Tally</h1>

      {connected ? (
        <div className="mt-4 space-y-4 text-sm">
          <p className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <span><span className="font-semibold">{connected}</span> is connected. MyTally Bridge links the company open in TallyPrime and starts syncing; the first sync of a large company can take a while.</span></p>
          {/* A full load, so the app starts in the Tally company that has just taken the place of the empty one */}
          <button type="button" onClick={() => window.location.assign('/')} disabled={!signedIn} className={mainButton}>
            {!signedIn && <Loader2 className="h-4 w-4 animate-spin" />}{signedIn ? 'Go to my business' : 'Waiting for the PC...'}
          </button>
          {!signedIn && <p className="text-xs text-muted-foreground">Keep MyTally Bridge open on the PC. This takes a few seconds.</p>}
        </div>
      ) : found ? (
        <div className="mt-4 space-y-4 text-sm">
          <p>Connect <span className="font-semibold">{found.device_name}</span> to <span className="font-semibold">{found.account_name}</span>?</p>
          <p className="text-muted-foreground">Only continue if this is your PC and the code is on its screen right now. That PC will be able to sync this business&apos;s Tally data.</p>
          {error && <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p>}
          <button type="button" onClick={approve} disabled={busy} className={mainButton}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Connect this PC</button>
          <button type="button" onClick={() => { setFound(null); setError('') }} disabled={busy} className="w-full text-center text-sm font-semibold underline cursor-pointer">Not my PC</button>
        </div>
      ) : (
        <form className="mt-4 space-y-4 text-sm" onSubmit={e => { e.preventDefault(); lookUp() }}>
          <p className="text-muted-foreground">Your business data comes from TallyPrime. Connect the PC it runs on once, and it stays in step from then on.</p>
          <ol className="space-y-2">
            {STEPS.map((text, i) => (
              <li key={text} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-bold">{i + 1}</span>
                <span>{text}</span>
              </li>
            ))}
          </ol>
          <label className="block"><span className="mb-1 block font-semibold">Code shown on the PC</span>
            <input value={code} onChange={e => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, '').slice(0, 9))}
              placeholder="ABCD-2345" autoComplete="off" autoCapitalize="characters" spellCheck={false} className={field} /></label>
          {error && <p role="alert" className="text-rose-700 dark:text-rose-400">{error}</p>}
          <button type="submit" disabled={busy || code.replace(/-/g, '').length < 8} className={mainButton}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Continue
          </button>
          {/* Someone held here has no other way out than connecting a PC or leaving the account */}
          {user?.needs_tally_setup ? (
            <button type="button" onClick={() => { logout(); router.replace('/login') }} className="w-full text-center text-sm font-semibold text-muted-foreground underline cursor-pointer">Sign in with a different account</button>
          ) : (
            <button type="button" onClick={() => router.replace('/')} className="w-full text-center text-sm font-semibold text-muted-foreground underline cursor-pointer">Back to the app</button>
          )}
        </form>
      )}
    </main>
  )
}
