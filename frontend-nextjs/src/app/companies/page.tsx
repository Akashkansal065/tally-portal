'use client'

import { Building, Check, Loader2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { companyIdentity, describeFreshness, pendingText, useCompanySyncStatus } from '@/lib/sync-status'

/** Every company the signed-in person can open, with how fresh its data is. Companies are added by linking
 *  them in the Desktop Sync Agent, never here. */
export default function CompaniesPage() {
  const { user, token, switchCompany } = useAuth()
  const companies = useCompanySyncStatus(token)

  return (
    <main className="mx-auto w-full max-w-3xl space-y-4 px-4 py-5 font-sans">
      <header>
        <h1 className="text-lg font-extrabold">Companies</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Each company keeps its own books, kept in step with Tally by the Desktop Sync Agent. To add a company, open it in
          TallyPrime on the PC running the agent and link it from the agent&apos;s Companies window.
        </p>
      </header>

      {companies === null ? (
        <Loader2 className="h-6 w-6 animate-spin text-primary" aria-label="Loading companies" />
      ) : companies.length === 0 ? (
        <p className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground">You do not have a company yet.</p>
      ) : (
        <ul className="space-y-3" role="list">
          {companies.map(c => {
            const fresh = describeFreshness(c)
            const current = c.company_id === user?.company_id
            const identity = companyIdentity(c, companies)
            const pending = pendingText(c)
            return (
              <li key={c.company_id} className={cn('rounded-2xl border bg-card p-4 shadow-sm', current ? 'border-primary/50' : 'border-border')}>
                <div className="flex items-start gap-3">
                  <Building className={cn('mt-0.5 h-5 w-5 shrink-0', current ? 'text-primary' : 'text-muted-foreground')} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-base font-bold">{c.name}</h2>
                    {identity && <p className="truncate text-xs text-muted-foreground">{identity}</p>}
                    <p className="mt-2 flex items-start gap-2 text-sm">
                      <span className={cn('mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full', fresh.dot)} aria-hidden="true" />
                      <span>{fresh.text}</span>
                    </p>
                    {pending && <p className="mt-1 text-sm text-muted-foreground">{pending}</p>}
                    {c.freshness === 'attention' && c.last_error && (
                      <p className="mt-1 text-sm text-rose-700 dark:text-rose-400">{c.last_error}</p>
                    )}
                    {c.synced_from && <p className="mt-1 text-xs text-muted-foreground">Synced from {c.synced_from}</p>}
                  </div>
                  {current ? (
                    <span className="inline-flex min-h-10 shrink-0 items-center gap-1 text-sm font-semibold text-primary">
                      <Check className="h-4 w-4" aria-hidden="true" /> Open now
                    </span>
                  ) : (
                    <button type="button" onClick={() => switchCompany(c.company_id)}
                      className="min-h-10 shrink-0 rounded-xl border border-border px-4 text-sm font-bold hover:bg-muted cursor-pointer">
                      Open
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </main>
  )
}
