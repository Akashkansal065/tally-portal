'use client'

/**
 * PurgeModals.tsx – Two-Person Purge Workflow & Statutory Retention Catalogue Modals.
 *
 * Implements Plan Section 3.4 & Phase 5:
 *   • Two-Person Approval Rule: requester cannot self-approve (enforced on API and UI).
 *   • Irreversible Anonymisation (GDPR/DPDP): PII wiped, accounting/tax records preserved.
 *   • Statutory Data Retention Catalogue viewer.
 */

import React, { useState, useEffect } from 'react'
import {
  ShieldAlert,
  AlertTriangle,
  X,
  Loader2,
  FileText,
  Lock,
  Info,
} from 'lucide-react'
import {
  consoleUsersApi,
  ConsoleUserItem,
  ConsoleUserDetail,
  PurgeRequestItem,
  RetentionPolicyItem,
  ConsoleApiError,
} from '@/console/api'
import { useConsoleAuth } from '../context/ConsoleAuthContext'
import { cn } from '@/lib/utils'

// ─────────────────────────────────────────────────────────────────────────────
// 1. REQUEST PURGE MODAL (Initiates Request)
// ─────────────────────────────────────────────────────────────────────────────

interface RequestPurgeModalProps {
  isOpen: boolean
  user: ConsoleUserItem | ConsoleUserDetail | null
  onClose: () => void
  onSuccess: (requestId: number) => void
}

export function RequestPurgeModal({ isOpen, user, onClose, onSuccess }: RequestPurgeModalProps) {
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen || !user) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!reason.trim()) {
      setError('A compliance or troubleshooting justification is required.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const res = await consoleUsersApi.createPurgeRequest(user.user_id, reason.trim())
      onSuccess(res.purge_request_id)
      onClose()
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        setError(err.detail)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('Failed to submit purge request.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150">
        <div className="flex items-start justify-between border-b border-[#e3f4ee] pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Request GDPR Anonymisation / Purge</h2>
              <p className="text-xs text-slate-500 font-mono">User: {user.username} (#{user.user_id})</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-2">
            <div className="flex items-center gap-2 font-semibold text-amber-800">
              <Lock className="w-4 h-4 text-amber-600 shrink-0" />
              Two-Person Approval Rule &amp; GDPR Compliance
            </div>
            <p className="text-[11px] leading-relaxed text-amber-800">
              • <strong>Two-Person Approval:</strong> This action creates a pending request. Under platform security rules,
              a <strong>second operator</strong> must review and approve it before execution. You cannot approve your own request.
            </p>
            <p className="text-[11px] leading-relaxed text-amber-800">
              • <strong>Irreversible Anonymisation:</strong> All personal identifiable information (email, phone, name)
              will be permanently redacted. Customer accounting vouchers, invoices, and audit links remain intact under statutory retention.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Legal or Compliance Justification <span className="text-rose-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. GDPR Right to be Forgotten request filed by customer #AC-9401 on 2026-10-13."
              className="w-full h-24 px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-500/20 transition-colors resize-none shadow-sm"
              required
            />
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
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold shadow-sm transition-all disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Submit Purge Request
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. PURGE REQUESTS QUEUE DRAWER (Two-Person Approval Workflow)
// ─────────────────────────────────────────────────────────────────────────────

interface PurgeRequestsDrawerProps {
  isOpen: boolean
  onClose: () => void
  onActionComplete: () => void
}

export function PurgeRequestsDrawer({ isOpen, onClose, onActionComplete }: PurgeRequestsDrawerProps) {
  const { operator, permissions } = useConsoleAuth()
  const canHardDelete = permissions.has('users.hard_delete') || permissions.has('all')

  const [requests, setRequests] = useState<PurgeRequestItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filterStatus, setFilterStatus] = useState<string>('pending')
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Rejection modal state
  const [rejectModalReq, setRejectModalReq] = useState<PurgeRequestItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  const fetchRequests = async (status: string) => {
    setLoading(true)
    setFeedback(null)
    try {
      const data = await consoleUsersApi.listPurgeRequests(status === 'all' ? undefined : status)
      setRequests(data)
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to fetch purge requests',
      })
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
        .listPurgeRequests(filterStatus === 'all' ? undefined : filterStatus)
        .then((data) => {
          if (active) setRequests(data)
        })
        .catch((err: unknown) => {
          if (active) {
            setFeedback({
              type: 'error',
              message: err instanceof Error ? err.message : 'Failed to fetch purge requests',
            })
          }
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }
    return () => {
      active = false
    }
  }, [isOpen, filterStatus])

  if (!isOpen) return null

  const handleApprove = async (req: PurgeRequestItem) => {
    if (!confirm(`Are you sure you want to permanently execute GDPR anonymisation for user ${req.target_username} (${req.target_email})? This action is completely IRREVERSIBLE.`)) {
      return
    }

    setActionLoadingId(req.purge_request_id)
    setFeedback(null)
    try {
      const res = await consoleUsersApi.approvePurgeRequest(req.purge_request_id)
      setFeedback({ type: 'success', message: res.message || 'User successfully anonymised.' })
      void fetchRequests(filterStatus)
      onActionComplete()
    } catch (err: unknown) {
      const msg = err instanceof ConsoleApiError ? err.detail : err instanceof Error ? err.message : 'Failed to approve request'
      setFeedback({ type: 'error', message: msg })
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleConfirmReject = async () => {
    if (!rejectModalReq || !rejectReason.trim()) return

    setActionLoadingId(rejectModalReq.purge_request_id)
    try {
      await consoleUsersApi.rejectPurgeRequest(rejectModalReq.purge_request_id, rejectReason.trim())
      setFeedback({ type: 'success', message: `Purge request #${rejectModalReq.purge_request_id} rejected.` })
      setRejectModalReq(null)
      setRejectReason('')
      void fetchRequests(filterStatus)
    } catch (err: unknown) {
      const msg = err instanceof ConsoleApiError ? err.detail : err instanceof Error ? err.message : 'Failed to reject request'
      setFeedback({ type: 'error', message: msg })
    } finally {
      setActionLoadingId(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-2xl bg-white border-l border-[#dfeee8] p-6 flex flex-col h-full overflow-y-auto animate-in slide-in-from-right duration-200 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                Two-Person Purge Requests
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                  Dual-Control
                </span>
              </h2>
              <p className="text-xs text-slate-500">Review, approve, or reject irreversible GDPR anonymisation requests.</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center justify-between gap-3 mb-4 text-xs">
          <div className="flex items-center gap-1.5 bg-white p-1 rounded-xl border border-[#dfeee8] shadow-sm">
            {['pending', 'approved', 'rejected', 'all'].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={cn(
                  'px-3 py-1.5 rounded-lg capitalize font-medium transition-all',
                  filterStatus === st
                    ? 'bg-[#00d09c] text-white font-semibold shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                )}
              >
                {st}
              </button>
            ))}
          </div>

          <button
            onClick={() => void fetchRequests(filterStatus)}
            disabled={loading}
            className="px-3 py-1.5 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#00a26d]" /> : 'Refresh'}
          </button>
        </div>

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={cn(
              'p-3 rounded-xl mb-4 text-xs flex items-center justify-between gap-2 shadow-sm',
              feedback.type === 'success'
                ? 'bg-[#ecfff7] border border-[#a7f3d0] text-[#00875a]'
                : 'bg-[#fff1f2] border border-[#fecaca] text-[#d92d20]'
            )}
          >
            <span>{feedback.message}</span>
            <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-700">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* List of Requests */}
        <div className="space-y-3.5 flex-1 overflow-y-auto pr-1">
          {loading && requests.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500 text-xs">
              <Loader2 className="w-6 h-6 animate-spin mb-2 text-[#00a26d]" />
              Loading purge queue...
            </div>
          ) : requests.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-xs bg-[#f9fffc] rounded-2xl border border-[#e3f4ee]">
              No {filterStatus} purge requests found.
            </div>
          ) : (
            requests.map((req) => {
              const isRequester = req.requested_by_admin_id === operator?.admin_id
              const isPending = req.status === 'pending'
              const canApproveAction = req.can_approve && canHardDelete && !isRequester

              return (
                <div
                  key={req.purge_request_id}
                  className="bg-[#f9fffc] border border-[#e3f4ee] rounded-2xl p-4 space-y-3 text-xs hover:border-[#cfeee0] transition-all shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-sm">{req.target_username}</span>
                        <span className="font-mono text-[11px] text-slate-500">ID #{req.target_user_id}</span>
                        <span
                          className={cn(
                            'px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider',
                            req.status === 'pending'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : req.status === 'approved'
                              ? 'bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc]'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          )}
                        >
                          {req.status}
                        </span>
                      </div>
                      <div className="font-mono text-slate-500 text-[11px] mt-0.5 select-all">
                        {req.target_email}
                      </div>
                    </div>

                    <div className="text-right text-[11px] text-slate-500">
                      Req #{req.purge_request_id}
                      <div className="text-[10px]">{new Date(req.requested_at).toLocaleDateString()}</div>
                    </div>
                  </div>

                  {/* Reason Quote */}
                  <div className="p-2.5 rounded-xl bg-white border border-[#e3f4ee] text-slate-700 text-[11px] shadow-sm">
                    <span className="text-slate-500 font-semibold block mb-0.5">Stated Justification:</span>
                    &ldquo;{req.reason}&rdquo;
                  </div>

                  {/* Metadata: Requester and Approver */}
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600 pt-1">
                    <div>
                      <span className="text-slate-500">Requested by:</span>{' '}
                      <span className="text-slate-800 font-mono">{req.requester_email || `Admin #${req.requested_by_admin_id}`}</span>
                    </div>
                    {req.approver_email && (
                      <div>
                        <span className="text-slate-500">Approved by:</span>{' '}
                        <span className="text-[#00a26d] font-mono">{req.approver_email}</span>
                      </div>
                    )}
                    {req.rejecter_email && (
                      <div>
                        <span className="text-slate-500">Rejected by:</span>{' '}
                        <span className="text-rose-600 font-mono">{req.rejecter_email}</span>
                      </div>
                    )}
                  </div>

                  {/* Two-Person Guard Notice & Action Buttons */}
                  {isPending && (
                    <div className="pt-2 border-t border-[#e3f4ee] flex items-center justify-between gap-3">
                      {isRequester ? (
                        <div className="flex items-center gap-1.5 text-amber-800 text-[11px] bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200">
                          <Lock className="w-3.5 h-3.5 text-amber-600" />
                          <span>Awaiting 2nd Operator (Self-approval forbidden)</span>
                        </div>
                      ) : (
                        <div className="text-[11px] text-slate-500">
                          2nd operator review available.
                        </div>
                      )}

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setRejectModalReq(req)
                            setRejectReason('')
                          }}
                          disabled={actionLoadingId === req.purge_request_id}
                          className="px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 font-semibold text-xs border border-rose-200 transition-all disabled:opacity-50"
                        >
                          Reject
                        </button>

                        <button
                          onClick={() => void handleApprove(req)}
                          disabled={!canApproveAction || actionLoadingId === req.purge_request_id}
                          title={
                            isRequester
                              ? 'Under the Two-Person Rule, you cannot approve your own request.'
                              : !canHardDelete
                              ? "Requires 'users.hard_delete' permission."
                              : 'Approve & Execute Irreversible Anonymisation'
                          }
                          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          {actionLoadingId === req.purge_request_id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <ShieldAlert className="w-3.5 h-3.5" />
                          )}
                          Approve &amp; Purge
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Rejection Modal Subdialog */}
        {rejectModalReq && (
          <div className="fixed inset-0 z-60 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-white border border-[#dfeee8] rounded-2xl p-5 shadow-2xl animate-in zoom-in-95">
              <h3 className="text-sm font-bold text-slate-900 mb-2">Reject Purge Request #{rejectModalReq.purge_request_id}</h3>
              <p className="text-xs text-slate-500 mb-3">Please specify the reason for rejecting this purge request.</p>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Account has pending reconciliation or dispute."
                className="w-full h-20 px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-500/20 transition-colors resize-none mb-4 shadow-sm"
              />
              <div className="flex items-center justify-end gap-2 text-xs">
                <button
                  onClick={() => setRejectModalReq(null)}
                  className="px-3 py-1.5 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void handleConfirmReject()}
                  disabled={!rejectReason.trim()}
                  className="px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold disabled:opacity-50 shadow-sm"
                >
                  Confirm Rejection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. STATUTORY DATA RETENTION POLICY CATALOGUE MODAL
// ─────────────────────────────────────────────────────────────────────────────

interface RetentionPoliciesModalProps {
  isOpen: boolean
  onClose: () => void
}

export function RetentionPoliciesModal({ isOpen, onClose }: RetentionPoliciesModalProps) {
  const [policies, setPolicies] = useState<RetentionPolicyItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (isOpen) {
      queueMicrotask(() => {
        if (active) {
          setLoading(true)
          setError(null)
        }
      })
      consoleUsersApi
        .getRetentionPolicies()
        .then((data) => {
          if (active) setPolicies(data)
        })
        .catch((err: unknown) => {
          if (active) setError(err instanceof Error ? err.message : 'Failed to fetch retention policies.')
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }
    return () => {
      active = false
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-4xl bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] text-[#00a26d]">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                Statutory Data Retention Schedules
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                  Compliance
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Official regulatory retention periods, legal basis, and automated expiration actions.
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs mb-4">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-500 text-xs">
              <Loader2 className="w-6 h-6 animate-spin mb-2 text-[#00a26d]" />
              Loading retention schedule...
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[#e3f4ee]">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-[#f9fffc] border-b border-[#e3f4ee] text-slate-600 font-semibold">
                    <th className="py-3 px-3.5">Category</th>
                    <th className="py-3 px-3.5">Retention Period</th>
                    <th className="py-3 px-3.5">Legal Basis</th>
                    <th className="py-3 px-3.5">Action on Expiry</th>
                    <th className="py-3 px-3.5">Scope &amp; Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef7f3]">
                  {policies.map((p) => (
                    <tr key={p.policy_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-3.5 font-bold text-slate-900">
                        {p.title}
                        <div className="font-mono text-[10px] text-slate-500">{p.data_category}</div>
                      </td>
                      <td className="py-3 px-3.5 font-mono text-[#00a26d] font-semibold whitespace-nowrap">
                        {p.retention_period_days} days
                        <span className="block text-[10px] text-slate-500 font-normal">
                          (~{Math.round(p.retention_period_days / 365 * 10) / 10} yrs)
                        </span>
                      </td>
                      <td className="py-3 px-3.5 text-amber-800 font-medium text-[11px] whitespace-nowrap">
                        {p.legal_basis}
                      </td>
                      <td className="py-3 px-3.5 whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-700 border border-slate-200">
                          {p.action_on_expiry}
                        </span>
                      </td>
                      <td className="py-3 px-3.5 text-slate-600 text-[11px]">
                        {p.description || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-[#e3f4ee] mt-4 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <Info className="w-4 h-4 text-slate-400" />
            <span>Nightly cleanup worker purges soft-deleted users past their 30-day window automatically.</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 font-semibold shadow-sm"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
