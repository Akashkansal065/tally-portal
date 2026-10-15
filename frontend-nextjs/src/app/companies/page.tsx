'use client'

import { useState } from 'react'
import { Building, Check, Loader2, Trash2, AlertTriangle, ShieldAlert, X, AlertCircle } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn, API_BASE } from '@/lib/utils'
import { CompanySyncStatus, companyIdentity, describeFreshness, pendingText, useCompanySyncStatus } from '@/lib/sync-status'
import { isAdminUser } from '@/lib/navigation'
import { toast } from 'sonner'

/** Every company the signed-in person can open, with how fresh its data is. Companies are added by linking
 *  them in the Desktop Sync Agent, never here. */
export default function CompaniesPage() {
  const { user, token, permissions, switchCompany } = useAuth()
  const companies = useCompanySyncStatus(token)
  const isAdmin = isAdminUser(permissions, user?.role)

  const [deleteTarget, setDeleteTarget] = useState<CompanySyncStatus | null>(null)
  const [deleteAction, setDeleteAction] = useState<'archive' | 'delete'>('archive')
  const [deleteConfirmName, setDeleteConfirmName] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const handleDeleteOrArchive = async () => {
    if (!deleteTarget || !token) return
    setIsDeleting(true)
    setDeleteError('')
    try {
      const activeToken = token || localStorage.getItem('mytally_token') || localStorage.getItem('token') || ''
      // Archiving and deleting are separate endpoints: only the delete one can remove records, and it needs the name
      const isArchive = deleteAction === 'archive'
      const res = await fetch(`${API_BASE}/companies/${deleteTarget.company_id}${isArchive ? '/archive' : ''}`, {
        method: isArchive ? 'POST' : 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${activeToken}`,
          'X-Company-ID': deleteTarget.company_id.toString(),
        },
        body: isArchive ? undefined : JSON.stringify({ confirmation_name: deleteConfirmName.trim() }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Failed to ${deleteAction} company.`)
      }
      toast.success(data.detail || `Company ${deleteAction === 'archive' ? 'archived' : 'deleted'} successfully.`)
      setDeleteTarget(null)
      if (data.replacement_company_id) {
        localStorage.setItem('active_company_id', String(data.replacement_company_id))
      }
      setTimeout(() => {
        window.location.assign('/')
      }, 500)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err)
      setDeleteError(message || `An error occurred while attempting to ${deleteAction} company.`)
    } finally {
      setIsDeleting(false)
    }
  }

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
                  <div className="flex items-center gap-2 shrink-0">
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
                    {isAdmin && (
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteTarget(c)
                          setDeleteAction('archive')
                          setDeleteConfirmName('')
                          setDeleteError('')
                        }}
                        className="min-h-10 px-3 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-600 hover:bg-rose-500/20 text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5"
                        title="Archive or delete company"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Archive / Delete</span>
                      </button>
                    )}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {/* Delete / Archive Confirmation Dialog */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center font-bold">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground leading-snug">Archive / Delete Company</h3>
                  <span className="text-[11px] text-muted-foreground font-mono">Target: {deleteTarget.name}</span>
                </div>
              </div>
              <button
                onClick={() => setDeleteTarget(null)}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              {deleteError && (
                <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}

              <div className="p-3 rounded-xl bg-rose-500/5 border border-rose-500/20 text-foreground space-y-1.5">
                <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400 font-bold text-xs">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>Tenant Security & Isolation</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Only organization Admins and Owners can manage companies. Other tenants cannot view or remove companies belonging to your account.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Select Removal Method</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setDeleteAction('archive')}
                    className={cn(
                      "p-3 rounded-xl border text-left transition-all cursor-pointer",
                      deleteAction === 'archive'
                        ? "border-emerald-600 bg-emerald-500/10 shadow-sm"
                        : "border-border hover:bg-muted/50"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-foreground">Archive</span>
                      <span className="text-[10px] font-semibold bg-emerald-500/20 text-emerald-600 px-1.5 py-0.5 rounded">Recommended</span>
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground leading-tight">
                      Hides company from switcher & stops sync. Financial records remain safely preserved.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setDeleteAction('delete')}
                    className={cn(
                      "p-3 rounded-xl border text-left transition-all cursor-pointer",
                      deleteAction === 'delete'
                        ? "border-rose-600 bg-rose-500/10 shadow-sm"
                        : "border-border hover:bg-muted/50"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-rose-600 dark:text-rose-400">Delete (Purge)</span>
                      <span className="text-[10px] font-semibold bg-rose-500/20 text-rose-600 px-1.5 py-0.5 rounded">Danger</span>
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground leading-tight">
                      Permanently wipes all vouchers, ledgers, items, and data. Cannot be undone.
                    </p>
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-muted-foreground">
                  To confirm, please type <span className="font-mono text-foreground font-extrabold select-all">{deleteTarget.name}</span>:
                </label>
                <input
                  type="text"
                  value={deleteConfirmName}
                  onChange={e => setDeleteConfirmName(e.target.value)}
                  placeholder={`Type "${deleteTarget.name}" to confirm`}
                  className="w-full px-3 py-2 rounded-xl border border-input bg-background font-medium text-xs focus:outline-none focus:ring-2 focus:ring-rose-500/40"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setDeleteTarget(null)}
                  className="px-3.5 py-1.5 rounded-xl border border-border text-xs font-semibold hover:bg-muted transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDeleteOrArchive}
                  disabled={
                    isDeleting ||
                    deleteConfirmName.trim().toLowerCase() !== deleteTarget.name.trim().toLowerCase()
                  }
                  className={cn(
                    "px-4 py-1.5 rounded-xl text-white font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed",
                    deleteAction === 'delete' ? "bg-rose-600 hover:bg-rose-700" : "bg-amber-600 hover:bg-amber-700"
                  )}
                >
                  {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  Confirm {deleteAction === 'delete' ? 'Permanent Delete' : 'Archive Company'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

