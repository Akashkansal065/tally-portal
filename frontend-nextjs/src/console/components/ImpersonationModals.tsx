'use client'

/**
 * ImpersonationModals.tsx – Time-Boxed Operator Impersonation & Session Controller.
 *
 * Implements Plan Section 5.2 & Phase 5:
 *   • Time-boxed tenant session (15m default, up to 60m).
 *   • Strictly Read-Only by default; Write access requires 'users.impersonate_write'.
 *   • Guards: sensitive tenant actions (password, billing, user deletion) are refused.
 *   • Premature termination capability voids customer token instantly.
 */

import React, { useState, useEffect } from 'react'
import {
  UserCheck,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Lock,
  X,
  Loader2,
  LogOut,
} from 'lucide-react'
import {
  consoleUsersApi,
  consoleAuthApi,
  ConsoleUserItem,
  ConsoleUserDetail,
  ImpersonationSessionItem,
  ImpersonationStartResponse,
  ConsoleApiError,
} from '@/console/api'
import { useConsoleAuth } from '../context/ConsoleAuthContext'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

// ─────────────────────────────────────────────────────────────────────────────
// 1. START IMPERSONATION MODAL
// ─────────────────────────────────────────────────────────────────────────────

interface StartImpersonationModalProps {
  isOpen: boolean
  user: ConsoleUserItem | ConsoleUserDetail | null
  onClose: () => void
  onSuccess: (res: ImpersonationStartResponse) => void
}

export function StartImpersonationModal({ isOpen, user, onClose, onSuccess }: StartImpersonationModalProps) {
  const { permissions, operator } = useConsoleAuth()
  const canWriteImpersonate = (operator?.max_rank ?? 0) >= 1000 || permissions.has('users.impersonate_write') || permissions.has('all')

  const [reason, setReason] = useState('')
  const [minutes, setMinutes] = useState(15)
  const [writeAccess, setWriteAccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step-up authentication states
  const [stepUpRequired, setStepUpRequired] = useState(false)
  const [stepUpPassword, setStepUpPassword] = useState('')
  const [stepUpError, setStepUpError] = useState<string | null>(null)
  const [submittingStepUp, setSubmittingStepUp] = useState(false)

  if (!isOpen || !user) return null

  const launchTenantPortal = (res: ImpersonationStartResponse) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('mytally_token', res.token)
      const newWin = window.open('/', '_blank')
      if (!newWin || newWin.closed || typeof newWin.closed === 'undefined') {
        toast.success(
          `Impersonation active for ${user.email} (${res.write_access ? 'Read-Write' : 'Read-Only'}).`,
          {
            action: {
              label: 'Open Customer Portal ↗',
              onClick: () => window.open('/', '_blank'),
            },
            duration: 10000,
          }
        )
      } else {
        toast.success(
          `Impersonation active for ${user.email}. Customer portal opened in a new tab.`,
          {
            action: {
              label: 'Open Again ↗',
              onClick: () => window.open('/', '_blank'),
            },
            duration: 6000,
          }
        )
      }
    }
    onSuccess(res)
    onClose()
  }

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedReason = reason.trim()
    if (!trimmedReason || trimmedReason.length < 5) {
      setError('A troubleshooting justification of at least 5 characters is mandatory for audit logging.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const res = await consoleUsersApi.impersonate(user.user_id, {
        reason: trimmedReason,
        minutes,
        write_access: writeAccess,
      })

      launchTenantPortal(res)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        const detailStr = typeof err.detail === 'string' ? err.detail : String(err.detail || '')
        if (err.isStepUpRequired || detailStr.toLowerCase().includes('step-up')) {
          setStepUpRequired(true)
          setStepUpError(null)
          return
        }
        setError(detailStr || 'Failed to initiate impersonation session.')
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to initiate impersonation session.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleStepUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!stepUpPassword) return

    setSubmittingStepUp(true)
    setStepUpError(null)
    try {
      await consoleAuthApi.stepUp(stepUpPassword)
      setStepUpRequired(false)
      setStepUpPassword('')

      // Now retry impersonation immediately
      setLoading(true)
      const res = await consoleUsersApi.impersonate(user.user_id, {
        reason: reason.trim(),
        minutes,
        write_access: writeAccess,
      })

      launchTenantPortal(res)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        const detailStr = typeof err.detail === 'string' ? err.detail : String(err.detail || '')
        setStepUpError(detailStr || 'Step-up verification failed.')
      } else if (err instanceof Error) {
        setStepUpError(err.message)
      } else {
        setStepUpError('Step-up verification failed.')
      }
    } finally {
      setSubmittingStepUp(false)
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between border-b border-[#e3f4ee] pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-600">
              <UserCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Impersonate Customer User</h2>
              <p className="text-xs text-slate-500 font-mono">
                {user.username} (#{user.user_id}) • {user.email}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        {stepUpRequired ? (
          <form onSubmit={handleStepUpSubmit} className="space-y-4 text-xs">
            {stepUpError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{stepUpError}</span>
              </div>
            )}

            <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-2">
              <div className="flex items-center gap-2 font-semibold text-amber-800">
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                Step-Up Verification Required
              </div>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                Operator impersonation is a sensitive, time-boxed operation. Please re-authenticate with your operator password to authorize this session.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Operator Password <span className="text-rose-500">*</span>
              </label>
              <input
                type="password"
                value={stepUpPassword}
                onChange={(e) => setStepUpPassword(e.target.value)}
                placeholder="Enter operator password to confirm"
                className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-500/20 transition-colors shadow-sm"
                autoFocus
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#e3f4ee]">
              <button
                type="button"
                onClick={() => {
                  setStepUpRequired(false)
                  setStepUpPassword('')
                }}
                className="px-4 py-2 text-slate-700 hover:text-slate-900 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors shadow-sm"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={submittingStepUp || !stepUpPassword}
                className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-semibold shadow-sm flex items-center gap-2 transition-all disabled:opacity-50"
              >
                {submittingStepUp ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-3.5 h-3.5" />
                    <span>Authorize &amp; Launch</span>
                  </>
                )}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleStart} className="space-y-4 text-xs">
            {error && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

          {/* Security Notice */}
          <div className="p-3.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee] text-slate-700 space-y-2">
            <div className="flex items-center gap-2 font-semibold text-amber-700">
              <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0" />
              Safety &amp; Isolation Safeguards
            </div>
            <ul className="list-disc pl-4 space-y-1 text-[11px] text-slate-600">
              <li>Time-boxed marked token valid strictly for the selected duration.</li>
              <li>Every action will be logged under both your operator identity and the user.</li>
              <li>
                <strong>Sensitive operations strictly blocked:</strong> Password changes, billing upgrades, and user deletions cannot be executed during impersonation.
              </li>
            </ul>
          </div>

          {/* Reason */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-slate-700">
                Troubleshooting Reason / Ticket ID <span className="text-rose-500">*</span>
              </label>
              <span className="text-[10px] text-slate-400">Min. 5 characters</span>
            </div>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Investigating GST invoice mismatch for customer ticket #T-8821"
              minLength={5}
              maxLength={500}
              className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 transition-colors shadow-sm"
              required
            />
          </div>

          {/* Duration Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              Session Duration
            </label>
            <div className="grid grid-cols-4 gap-2">
              {[5, 15, 30, 60].map((dur) => (
                <button
                  key={dur}
                  type="button"
                  onClick={() => setMinutes(dur)}
                  className={cn(
                    'py-2 px-3 rounded-xl border text-xs font-semibold transition-all shadow-sm',
                    minutes === dur
                      ? 'bg-[#00d09c] border-[#00d09c] text-white shadow-sm'
                      : 'bg-white border-[#dfeee8] text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  )}
                >
                  {dur} mins
                </button>
              ))}
            </div>
          </div>

          {/* Access Mode Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                Access Mode
              </span>
              <span className="text-[10px] text-slate-500 font-medium">
                {writeAccess ? (
                  <span className="text-rose-600 font-bold">● Read-Write Selected</span>
                ) : (
                  <span className="text-emerald-700 font-medium">● Read-Only Selected</span>
                )}
              </span>
            </label>

            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setWriteAccess(false)}
                className={cn(
                  'p-3 rounded-xl border text-left transition-all shadow-sm flex flex-col justify-between cursor-pointer',
                  !writeAccess
                    ? 'bg-[#00d09c]/10 border-[#00d09c] text-slate-900 ring-2 ring-[#00d09c]/30'
                    : 'bg-white border-[#dfeee8] text-slate-600 hover:bg-slate-50'
                )}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-bold text-xs flex items-center gap-1.5 text-emerald-800">
                    <ShieldCheck className="w-4 h-4 text-[#00a26d]" />
                    Strictly Read-Only
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
                    Default
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 leading-snug">
                  Recommended: Mutating requests (POST/PUT/DELETE) are blocked.
                </p>
              </button>

              <button
                type="button"
                disabled={!canWriteImpersonate}
                onClick={() => setWriteAccess(true)}
                className={cn(
                  'p-3 rounded-xl border text-left transition-all shadow-sm flex flex-col justify-between cursor-pointer',
                  writeAccess
                    ? 'bg-rose-50 border-rose-400 text-slate-900 ring-2 ring-rose-400/40'
                    : 'bg-white border-[#dfeee8] text-slate-600 hover:bg-slate-50',
                  !canWriteImpersonate && 'opacity-50 cursor-not-allowed'
                )}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <span className="font-bold text-xs flex items-center gap-1.5 text-rose-700">
                    <ShieldAlert className="w-4 h-4 text-rose-500" />
                    Read-Write Mode
                  </span>
                  {writeAccess && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-200 text-rose-900 font-bold">
                      Active
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 leading-snug">
                  Permits modifying live customer records and data.
                </p>
              </button>
            </div>

            {!canWriteImpersonate && (
              <p className="text-[10px] text-slate-500 italic mt-1.5">
                * Read-write impersonation requires the &apos;users.impersonate_write&apos; security badge.
              </p>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#e3f4ee]">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 rounded-xl text-slate-700 hover:text-slate-900 bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors font-medium shadow-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !reason.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold shadow-sm transition-all disabled:opacity-50"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Launch Impersonation
            </button>
          </div>
        </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. ACTIVE IMPERSONATIONS DRAWER (Monitor & Terminate)
// ─────────────────────────────────────────────────────────────────────────────

interface ActiveImpersonationsDrawerProps {
  isOpen: boolean
  onClose: () => void
}

export function ActiveImpersonationsDrawer({ isOpen, onClose }: ActiveImpersonationsDrawerProps) {
  const [sessions, setSessions] = useState<ImpersonationSessionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [terminatingId, setTerminatingId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  const fetchActive = async () => {
    setLoading(true)
    try {
      const data = await consoleUsersApi.listActiveImpersonations()
      setSessions(data)
    } catch {
      // Ignored
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    if (isOpen) {
      queueMicrotask(() => {
        if (active) setLoading(true)
      })
      consoleUsersApi
        .listActiveImpersonations()
        .then((data) => {
          if (active) setSessions(data)
        })
        .catch(() => {})
        .finally(() => {
          if (active) setLoading(false)
        })
    }
    return () => {
      active = false
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleTerminate = async (sessionId: number) => {
    setTerminatingId(sessionId)
    setFeedback(null)
    try {
      await consoleUsersApi.terminateImpersonation(sessionId)
      setFeedback(`Impersonation session #${sessionId} successfully terminated.`)
      void fetchActive()
    } catch (err: unknown) {
      setFeedback(err instanceof Error ? err.message : 'Failed to terminate session')
    } finally {
      setTerminatingId(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-xl bg-white border-l border-[#dfeee8] p-6 flex flex-col h-full overflow-y-auto animate-in slide-in-from-right duration-200 shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                Active Operator Impersonations
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                  {sessions.length} Live
                </span>
              </h2>
              <p className="text-xs text-slate-500">Currently active sessions acting on behalf of customer accounts.</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        {feedback && (
          <div className="p-3 rounded-xl bg-[#ecfff7] border border-[#a7f3d0] text-[#00875a] text-xs mb-4 flex items-center justify-between shadow-sm">
            <span>{feedback}</span>
            <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-700">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs">
          {loading && sessions.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500">
              <Loader2 className="w-6 h-6 animate-spin mb-2 text-[#00a26d]" />
              Loading active sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div className="py-12 text-center text-slate-400 bg-[#f9fffc] rounded-2xl border border-[#e3f4ee]">
              No active operator impersonation sessions right now.
            </div>
          ) : (
            sessions.map((sess) => (
              <div
                key={sess.impersonation_id}
                className="bg-[#f9fffc] border border-[#e3f4ee] rounded-2xl p-4 space-y-2.5 shadow-sm hover:border-[#cfeee0] transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900">Target User #{sess.target_user_id}</span>
                      <span className="font-mono text-[10px] text-slate-500">Acc #{sess.target_account_id}</span>
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider',
                          sess.is_write
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        )}
                      >
                        {sess.is_write ? 'Read-Write' : 'Read-Only'}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Operator: <span className="text-slate-800 font-mono font-medium">{sess.admin_email}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => void handleTerminate(sess.impersonation_id)}
                    disabled={terminatingId === sess.impersonation_id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs shadow-sm transition-all disabled:opacity-50"
                  >
                    {terminatingId === sess.impersonation_id ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <LogOut className="w-3.5 h-3.5" />
                    )}
                    Terminate
                  </button>
                </div>

                <div className="p-2.5 rounded-xl bg-white border border-[#e3f4ee] text-[11px] text-slate-700 shadow-sm">
                  <span className="text-slate-500 font-medium">Reason:</span> &ldquo;{sess.reason}&rdquo;
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                  <span>Started: {new Date(sess.started_at).toLocaleTimeString()}</span>
                  <span>Expires: {new Date(sess.expires_at).toLocaleTimeString()}</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="pt-4 border-t border-[#e3f4ee] mt-4 flex items-center justify-between text-xs text-slate-500">
          <button
            onClick={() => void fetchActive()}
            disabled={loading}
            className="px-3 py-1.5 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 font-semibold shadow-sm transition-colors"
          >
            Refresh
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
