'use client'

/**
 * app/(console)/console/audit/page.tsx – Platform Tamper-Evident Audit Trail & Forensic Console.
 *
 * Implements Plan Section 3.5 & 4:
 *   • SHA-256 cryptographic hash-chain live verification badge
 *   • Keyset cursor-paginated audit trail with multi-dimensional filtering
 *   • Side-by-side JSON state diff modal for mutation investigations
 *   • Forensic cryptographic details (row_hash, prev_hash, request_id, IP, UA)
 *   • Audited export modal with Step-Up MFA challenge support
 */

import React, { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowDownToLine,
  CheckCircle2,
  ChevronRight,
  Clock,
  Copy,
  Eye,
  FileSpreadsheet,
  Fingerprint,
  Hash,
  Key,
  Layers,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react'
import {
  AuditExportPayload,
  AuditIntegrityResponse,
  AuditLogDetail,
  AuditLogItem,
  ConsoleApiError,
  consoleAuditApi,
  consoleAuthApi,
} from '@/console/api'

// Pre-defined operator action categories for filtering
const ACTION_PRESETS = [
  { value: '', label: 'All Action Types' },
  { value: 'users.create', label: 'users.create (New Customer User)' },
  { value: 'users.update', label: 'users.update (User Metadata Edit)' },
  { value: 'users.suspend', label: 'users.suspend (Account Suspension)' },
  { value: 'users.reinstate', label: 'users.reinstate (Account Reinstated)' },
  { value: 'users.reset_password', label: 'users.reset_password (Password Reset)' },
  { value: 'users.revoke_sessions', label: 'users.revoke_sessions (Session Revocation)' },
  { value: 'users.soft_deleted', label: 'users.soft_deleted (Soft Deletion)' },
  { value: 'users.restored', label: 'users.restored (Account Restored)' },
  { value: 'roles.create', label: 'roles.create (New Role)' },
  { value: 'roles.update', label: 'roles.update (Role Metadata)' },
  { value: 'roles.delete', label: 'roles.delete (Role Removed)' },
  { value: 'roles.permissions_updated', label: 'roles.permissions_updated (Privilege Modification)' },
  { value: 'admins.create', label: 'admins.create (New Operator)' },
  { value: 'admins.update', label: 'admins.update (Operator Edit)' },
  { value: 'admins.roles_assigned', label: 'admins.roles_assigned (Role Assignment)' },
  { value: 'admins.passkeys_reset', label: 'admins.passkeys_reset (Passkeys Cleared)' },
  { value: 'admins.sessions_revoked', label: 'admins.sessions_revoked (Operator Sessions Revoked)' },
  { value: 'audit.exported', label: 'audit.exported (Audit Log Export)' },
  { value: 'auth.login_success', label: 'auth.login_success (Operator Sign-In)' },
  { value: 'auth.login_failed', label: 'auth.login_failed (Failed Sign-In)' },
]

export default function PlatformAuditConsolePage() {
  // ── Audit Logs State ──
  const [logs, setLogs] = useState<AuditLogItem[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [hasMore, setHasMore] = useState<boolean>(false)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [cursorHistory, setCursorHistory] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // ── Filters ──
  const [actionFilter, setActionFilter] = useState<string>('')
  const [outcomeFilter, setOutcomeFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [fromDate, setFromDate] = useState<string>('')
  const [toDate, setToDate] = useState<string>('')

  // ── Integrity Status State ──
  const [integrity, setIntegrity] = useState<AuditIntegrityResponse | null>(null)
  const [isVerifyingChain, setIsVerifyingChain] = useState<boolean>(false)

  // ── Detail / Diff Modal State ──
  const [selectedAuditId, setSelectedAuditId] = useState<number | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<AuditLogDetail | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false)

  // ── Export Modal State ──
  const [showExportModal, setShowExportModal] = useState<boolean>(false)
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv')
  const [isExporting, setIsExporting] = useState<boolean>(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // ── Step-Up MFA Challenge State ──
  const [stepUpRequired, setStepUpRequired] = useState<boolean>(false)
  const [stepUpPassword, setStepUpPassword] = useState<string>('')
  const [isSubmittingStepUp, setIsSubmittingStepUp] = useState<boolean>(false)

  // ── Toast notification ──
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 4000)
  }

  // ── Load Chain Integrity ──
  const loadIntegrity = useCallback(async () => {
    setIsVerifyingChain(true)
    try {
      const rep = await consoleAuditApi.getIntegrity()
      setIntegrity(rep)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError && err.status === 401) return
      console.warn('Integrity verification failed:', err)
    } finally {
      setIsVerifyingChain(false)
    }
  }, [])

  // ── Load Audit Logs ──
  const loadLogs = useCallback(async (cursorToLoad?: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await consoleAuditApi.list({
        cursor: cursorToLoad,
        limit: 25,
        action_type: actionFilter || undefined,
        outcome: outcomeFilter || undefined,
        search: searchQuery.trim() || undefined,
        from: fromDate ? new Date(fromDate).toISOString() : undefined,
        to: toDate ? new Date(toDate).toISOString() : undefined,
      })
      setLogs(res.items)
      setTotalCount(res.total_count)
      setHasMore(res.has_more)
      setNextCursor(res.next_cursor)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load audit logs'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [actionFilter, outcomeFilter, searchQuery, fromDate, toDate])

  // Mount effect
  useEffect(() => {
    const timer = setTimeout(() => {
      void loadLogs()
      void loadIntegrity()
    }, 0)
    return () => clearTimeout(timer)
  }, [loadLogs, loadIntegrity])

  // Handle pagination forward
  const handleNextPage = () => {
    if (!nextCursor) return
    setCursorHistory((prev) => [...prev, nextCursor])
    void loadLogs(nextCursor)
  }

  // Handle reset to first page
  const handleResetPagination = () => {
    setCursorHistory([])
    void loadLogs(undefined)
  }

  // Load single audit log detail
  const handleOpenDetail = async (auditId: number) => {
    setSelectedAuditId(auditId)
    setIsLoadingDetail(true)
    try {
      const detail = await consoleAuditApi.get(auditId)
      setSelectedDetail(detail)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load log detail'
      showToast(msg)
      setSelectedAuditId(null)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  // Handle Export Submit
  const handleRunExport = async () => {
    setIsExporting(true)
    setExportError(null)
    try {
      const payload: AuditExportPayload = {
        format: exportFormat,
        action_type: actionFilter || undefined,
        outcome: outcomeFilter || undefined,
        from: fromDate ? new Date(fromDate).toISOString() : undefined,
        to: toDate ? new Date(toDate).toISOString() : undefined,
        limit: 2000,
      }
      const res = await consoleAuditApi.export(payload)

      if (exportFormat === 'csv' && res.blob) {
        const url = window.URL.createObjectURL(res.blob)
        const a = document.createElement('a')
        a.href = url
        a.download = res.filename || `platform-audit-${Date.now()}.csv`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
        showToast('CSV export downloaded successfully.')
      } else if (res.data) {
        const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(res.data, null, 2))
        const a = document.createElement('a')
        a.href = dataStr
        a.download = `platform-audit-${Date.now()}.json`
        document.body.appendChild(a)
        a.click()
        a.remove()
        showToast('JSON export downloaded successfully.')
      }
      setShowExportModal(false)
      setStepUpRequired(false)
      // Refresh audit logs to show audit.exported entry
      void loadLogs()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'stepUpRequired' in err) {
        setStepUpRequired(true)
      } else {
        const msg = err instanceof Error ? err.message : 'Export failed'
        setExportError(msg)
      }
    } finally {
      setIsExporting(false)
    }
  }

  // Handle Step-Up MFA Submission
  const handleStepUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!stepUpPassword) return
    setIsSubmittingStepUp(true)
    setExportError(null)
    try {
      await consoleAuthApi.stepUp(stepUpPassword)
      setStepUpRequired(false)
      setStepUpPassword('')
      showToast('Step-up authentication verified. Running export...')
      // Retry export
      void handleRunExport()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Step-up verification failed'
      setExportError(msg)
    } finally {
      setIsSubmittingStepUp(false)
    }
  }

  // Copy to clipboard helper
  const copyText = (txt: string, label: string) => {
    void navigator.clipboard.writeText(txt)
    showToast(`Copied ${label} to clipboard.`)
  }

  // Color helper for action tags
  const getActionBadgeColor = (action: string) => {
    if (action.startsWith('users.')) return 'bg-sky-50 text-sky-700 border-sky-200'
    if (action.startsWith('roles.')) return 'bg-purple-50 text-purple-700 border-purple-200'
    if (action.startsWith('admins.')) return 'bg-indigo-50 text-indigo-700 border-indigo-200'
    if (action.startsWith('auth.login_failed')) return 'bg-rose-50 text-rose-700 border-rose-200'
    if (action.startsWith('auth.')) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
    if (action.startsWith('audit.')) return 'bg-amber-50 text-amber-700 border-amber-200'
    return 'bg-slate-100 text-slate-700 border-slate-200'
  }

  return (
    <div className="space-y-6">
      {/* ── Toast Notification ── */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl bg-white border border-[#dfeee8] text-slate-900 shadow-2xl shadow-slate-900/10 text-sm animate-in fade-in slide-in-from-bottom-2">
          <CheckCircle2 className="w-4 h-4 text-[#00d09c] shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* ── Header ── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
              Tamper-Evident Audit Trail
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] font-semibold tracking-wider uppercase">
                Phase 4 Complete
              </span>
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Cryptographic SHA-256 hash-chained immutable ledger of all operator mutations and system security events.
          </p>
        </div>

        {/* Top Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => void loadIntegrity()}
            disabled={isVerifyingChain}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 hover:text-slate-900 transition-colors shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isVerifyingChain ? 'animate-spin text-[#00d09c]' : 'text-slate-400'}`} />
            {isVerifyingChain ? 'Verifying Chain...' : 'Verify Chain'}
          </button>

          <button
            onClick={() => {
              setShowExportModal(true)
              setStepUpRequired(false)
              setExportError(null)
            }}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white shadow-sm transition-colors"
          >
            <ArrowDownToLine className="w-3.5 h-3.5" />
            Export Audit Trail
          </button>
        </div>
      </div>

      {/* ── Cryptographic Hash-Chain Integrity Banner Card ── */}
      <div className="p-4 rounded-2xl border border-[#dfeee8] bg-white shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
              integrity?.chain_intact
                ? 'bg-[#ebfff7] border border-[#b8f5dc] text-[#00a26d]'
                : integrity?.broken_at_id
                ? 'bg-rose-50 border border-rose-200 text-rose-600'
                : 'bg-slate-100 border border-slate-200 text-slate-500'
            }`}>
              {integrity?.chain_intact ? (
                <ShieldCheck className="w-6 h-6" />
              ) : integrity?.broken_at_id ? (
                <ShieldAlert className="w-6 h-6" />
              ) : (
                <Layers className="w-6 h-6" />
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-900">
                  {integrity?.chain_intact
                    ? 'Cryptographic Chain Verified & Intact'
                    : integrity?.broken_at_id
                    ? 'CRITICAL ALERT: Chain Tampering Detected!'
                    : 'Cryptographic Status Loading...'}
                </span>
                {integrity?.chain_intact && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono font-medium">
                    SHA-256 Validated
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {integrity?.chain_intact ? (
                  <>
                    All {integrity.total_verified.toLocaleString()} sequential records strictly match canonical row hashes and link continuity.
                  </>
                ) : integrity?.broken_at_id ? (
                  <span className="text-rose-600 font-medium">
                    Discrepancy at Record #{integrity.broken_at_id}: {integrity.error_detail}
                  </span>
                ) : (
                  'Verifying blockchain-style forward hash chaining...'
                )}
              </p>
            </div>
          </div>

          {integrity?.last_verified_at && (
            <div className="text-right sm:border-l sm:border-[#eef7f3] sm:pl-4">
              <div className="text-[11px] font-mono text-slate-400">Last Verified</div>
              <div className="text-xs text-slate-700 font-mono mt-0.5">
                {new Date(integrity.last_verified_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Filters & Search Toolbar ── */}
      <div className="p-4 rounded-2xl border border-[#dfeee8] bg-white shadow-[0_10px_24px_rgba(15,23,42,0.03)] space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search email, action, reason, IP..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm transition-colors"
            />
          </div>

          {/* Action Filter */}
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-800 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm transition-colors"
          >
            {ACTION_PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>

          {/* Outcome Filter */}
          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-800 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm transition-colors"
          >
            <option value="">All Outcomes</option>
            <option value="success">Success</option>
            <option value="denied">Denied / Forbidden</option>
            <option value="failed">Failed / Error</option>
          </select>

          {/* Date range */}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-1/2 px-2.5 py-1.5 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-800 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              title="From Date"
            />
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-1/2 px-2.5 py-1.5 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-800 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              title="To Date"
            />
          </div>
        </div>

        {/* Clear Filters indicator */}
        {(actionFilter || outcomeFilter || searchQuery || fromDate || toDate) && (
          <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-[#eef7f3]">
            <span>Filtered results active</span>
            <button
              onClick={() => {
                setActionFilter('')
                setOutcomeFilter('')
                setSearchQuery('')
                setFromDate('')
                setToDate('')
              }}
              className="text-[#00a26d] hover:underline font-medium transition-colors"
            >
              Reset all filters
            </button>
          </div>
        )}
      </div>

      {/* ── Audit Logs Table ── */}
      <div className="rounded-2xl border border-[#dfeee8] bg-white overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#e3f4ee] bg-[#f9fffc] text-slate-600 uppercase tracking-wider font-semibold text-[10px]">
                <th className="py-3.5 px-4"># ID & Time</th>
                <th className="py-3.5 px-4">Operator</th>
                <th className="py-3.5 px-4">Action</th>
                <th className="py-3.5 px-4">Outcome</th>
                <th className="py-3.5 px-4">Reason / Target</th>
                <th className="py-3.5 px-4">Cryptographic Hash</th>
                <th className="py-3.5 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eef7f3] text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    <div className="w-6 h-6 border-2 border-[#00d09c] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                    Loading tamper-evident ledger...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-rose-600">
                    <AlertTriangle className="w-6 h-6 mx-auto mb-2 text-rose-500" />
                    {error}
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    No audit records found matching your filters.
                  </td>
                </tr>
              ) : (
                logs.map((row) => (
                  <tr
                    key={row.audit_id}
                    className="hover:bg-slate-50/70 transition-colors group cursor-pointer"
                    onClick={() => void handleOpenDetail(row.audit_id)}
                  >
                    {/* ID & Time */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="font-mono text-slate-900 font-semibold">#{row.audit_id}</div>
                      <div className="text-[10px] text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock className="w-3 h-3 text-slate-400" />
                        {new Date(row.occurred_at).toLocaleString([], {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </div>
                    </td>

                    {/* Operator */}
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900 max-w-[180px] truncate" title={row.admin_email}>
                        {row.admin_email}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500">
                        {row.ip_address || '127.0.0.1'}
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${getActionBadgeColor(row.action_type)}`}>
                        {row.action_type}
                      </span>
                    </td>

                    {/* Outcome */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {row.outcome === 'success' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Success
                        </span>
                      ) : row.outcome === 'denied' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          <AlertTriangle className="w-3 h-3 text-amber-500" /> Denied
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                          <AlertTriangle className="w-3 h-3 text-rose-500" /> Failed
                        </span>
                      )}
                    </td>

                    {/* Reason / Target */}
                    <td className="py-3.5 px-4 max-w-[220px]">
                      <div className="text-slate-700 truncate" title={row.reason || ''}>
                        {row.reason || '—'}
                      </div>
                      {row.target_type && (
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          {row.target_type}: {row.target_id || row.target_user_id || '—'}
                        </div>
                      )}
                    </td>

                    {/* Hash */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-600">
                        <Hash className="w-3 h-3 text-[#00d09c] shrink-0" />
                        <span className="text-slate-800 font-semibold truncate w-24" title={row.row_hash}>
                          {row.row_hash.slice(0, 10)}...{row.row_hash.slice(-6)}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 truncate w-24">
                        prev: {row.prev_hash ? `${row.prev_hash.slice(0, 8)}...` : 'genesis'}
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          void handleOpenDetail(row.audit_id)
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-[#dfeee8] transition-colors shadow-sm"
                      >
                        <Eye className="w-3 h-3 text-[#00d09c]" />
                        {row.has_diff ? 'View Diff' : 'Detail'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* ── Keyset Pagination Footer ── */}
        <div className="p-3 border-t border-[#eef7f3] bg-[#f9fffc] flex items-center justify-between text-xs text-slate-600">
          <div>
            Total verified records: <span className="font-semibold text-slate-900">{totalCount.toLocaleString()}</span>
          </div>

          <div className="flex items-center gap-2">
            {cursorHistory.length > 0 && (
              <button
                onClick={handleResetPagination}
                className="px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 shadow-sm transition-colors font-medium text-xs"
              >
                Back to First Page
              </button>
            )}

            <button
              onClick={handleNextPage}
              disabled={!hasMore || isLoading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium text-xs"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Forensic Detail & JSON Diff Modal ── */}
      {selectedAuditId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-white border border-[#dfeee8] shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-[#eef7f3] flex items-center justify-between bg-white">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] flex items-center justify-center text-[#00a26d]">
                  <Fingerprint className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    Audit Record #{selectedAuditId}
                    {selectedDetail && (
                      <span className={`text-[10px] px-2 py-0.5 rounded font-mono border ${getActionBadgeColor(selectedDetail.action_type)}`}>
                        {selectedDetail.action_type}
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Cryptographic forensic payload and state mutation diff.
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedAuditId(null)
                  setSelectedDetail(null)
                }}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 flex-1">
              {isLoadingDetail ? (
                <div className="py-16 text-center text-slate-500">
                  <div className="w-8 h-8 border-2 border-[#00d09c] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  Loading cryptographic signature & state diff...
                </div>
              ) : selectedDetail ? (
                <>
                  {/* Overview Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-3 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Occurred At</div>
                      <div className="text-xs font-semibold text-slate-900 mt-1">
                        {new Date(selectedDetail.occurred_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Operator Email</div>
                      <div className="text-xs font-semibold text-slate-900 mt-1 truncate" title={selectedDetail.admin_email}>
                        {selectedDetail.admin_email}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">IP Address</div>
                      <div className="text-xs font-mono font-semibold text-slate-900 mt-1">
                        {selectedDetail.ip_address || '—'}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                      <div className="text-[10px] text-slate-500 uppercase font-mono">Outcome</div>
                      <div className="text-xs font-semibold mt-1">
                        {selectedDetail.outcome === 'success' ? (
                          <span className="text-emerald-600 font-semibold">Success</span>
                        ) : (
                          <span className="text-rose-600 font-semibold">{selectedDetail.outcome}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Cryptographic Block */}
                  <div className="p-4 rounded-xl bg-[#f9fffc] border border-[#e3f4ee] space-y-2.5">
                    <div className="text-xs font-bold text-slate-900 flex items-center gap-2">
                      <Hash className="w-3.5 h-3.5 text-[#00d09c]" />
                      Cryptographic Blockchain Chaining
                    </div>

                    <div className="space-y-1.5 font-mono text-[11px]">
                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-[#dfeee8]">
                        <span className="text-slate-500">Row Hash (SHA-256):</span>
                        <div className="flex items-center gap-2 text-slate-800">
                          <span className="font-semibold">{selectedDetail.row_hash}</span>
                          <button
                            onClick={() => copyText(selectedDetail.row_hash, 'Row Hash')}
                            className="p-1 hover:text-[#00a26d] transition-colors"
                            title="Copy Hash"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-[#dfeee8]">
                        <span className="text-slate-500">Previous Hash (Link):</span>
                        <div className="flex items-center gap-2 text-slate-800">
                          <span className="font-semibold">{selectedDetail.prev_hash || 'Genesis Block (None)'}</span>
                          {selectedDetail.prev_hash && (
                            <button
                              onClick={() => copyText(selectedDetail.prev_hash!, 'Previous Hash')}
                              className="p-1 hover:text-[#00a26d] transition-colors"
                              title="Copy Prev Hash"
                            >
                              <Copy className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-[#dfeee8]">
                        <span className="text-slate-500">Request ID:</span>
                        <div className="flex items-center gap-2 text-slate-800">
                          <span className="font-semibold">{selectedDetail.request_id}</span>
                          <button
                            onClick={() => copyText(selectedDetail.request_id, 'Request ID')}
                            className="p-1 hover:text-[#00a26d] transition-colors"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Visual JSON State Diff */}
                  <div className="space-y-2">
                    <div className="text-xs font-bold text-slate-900 flex items-center justify-between">
                      <span>State Mutation Diff</span>
                      {selectedDetail.old_values || selectedDetail.new_values ? (
                        <span className="text-[10px] font-normal text-[#00a26d]">Redacted denylist applied</span>
                      ) : null}
                    </div>

                    {selectedDetail.old_values || selectedDetail.new_values ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Old Values */}
                        <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-3">
                          <div className="text-xs font-semibold text-rose-700 mb-2 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-rose-500" />
                            Previous State (Before Mutation)
                          </div>
                          <pre className="text-[11px] font-mono text-slate-800 p-2.5 rounded-lg bg-white border border-rose-200 overflow-x-auto max-h-60 shadow-sm">
                            {selectedDetail.old_values
                              ? JSON.stringify(selectedDetail.old_values, null, 2)
                              : 'None (Initial state / Creation)'}
                          </pre>
                        </div>

                        {/* New Values */}
                        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3">
                          <div className="text-xs font-semibold text-emerald-700 mb-2 flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            New State (After Mutation)
                          </div>
                          <pre className="text-[11px] font-mono text-slate-800 p-2.5 rounded-lg bg-white border border-emerald-200 overflow-x-auto max-h-60 shadow-sm">
                            {selectedDetail.new_values
                              ? JSON.stringify(selectedDetail.new_values, null, 2)
                              : 'None (Deletion / Teardown)'}
                          </pre>
                        </div>
                      </div>
                    ) : (
                      <div className="p-8 text-center text-slate-500 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                        No state property diff recorded for this security action.
                      </div>
                    )}
                  </div>
                </>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 border-t border-[#eef7f3] bg-white flex items-center justify-end">
              <button
                onClick={() => {
                  setSelectedAuditId(null)
                  setSelectedDetail(null)
                }}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Export Modal with Step-Up MFA Challenge ── */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-md rounded-2xl bg-white border border-[#dfeee8] shadow-2xl overflow-hidden">
            {/* Export Modal Header */}
            <div className="px-6 py-4 border-b border-[#eef7f3] flex items-center justify-between bg-white">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] flex items-center justify-center text-[#00a26d]">
                  <ArrowDownToLine className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Export Audit Trail</h3>
                  <p className="text-xs text-slate-500">Cryptographically audited ledger export.</p>
                </div>
              </div>
              <button
                onClick={() => setShowExportModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Export Modal Body */}
            <div className="p-6 space-y-4">
              {exportError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                  <span>{exportError}</span>
                </div>
              )}

              {stepUpRequired ? (
                /* ── Step-Up Challenge Form ── */
                <form onSubmit={handleStepUpSubmit} className="space-y-4">
                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1">
                    <div className="font-semibold flex items-center gap-1.5">
                      <Key className="w-4 h-4 text-amber-600" />
                      Step-Up Authentication Required
                    </div>
                    <p className="text-amber-700">
                      Audit export is a sensitive privilege requiring re-authentication within the past 5 minutes.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                      Confirm Operator Password
                    </label>
                    <input
                      type="password"
                      required
                      placeholder="Enter your operator password"
                      value={stepUpPassword}
                      onChange={(e) => setStepUpPassword(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-[#dfeee8] text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                      autoFocus
                    />
                  </div>

                  <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setStepUpRequired(false)}
                      className="px-3.5 py-2 text-xs font-semibold rounded-xl bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 transition-colors shadow-sm"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmittingStepUp || !stepUpPassword}
                      className="px-4 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white disabled:opacity-50 shadow-sm transition-colors"
                    >
                      {isSubmittingStepUp ? 'Verifying...' : 'Verify & Continue Export'}
                    </button>
                  </div>
                </form>
              ) : (
                /* ── Regular Export Settings ── */
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-2">
                      Export Format
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        type="button"
                        onClick={() => setExportFormat('csv')}
                        className={`p-3 rounded-xl border text-left flex items-start gap-2.5 transition-colors shadow-sm ${
                          exportFormat === 'csv'
                            ? 'bg-[#ebfff7] border-[#00d09c] text-slate-900'
                            : 'bg-white border-[#dfeee8] text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        <FileSpreadsheet className="w-4 h-4 text-[#00a26d] mt-0.5 shrink-0" />
                        <div>
                          <div className="text-xs font-semibold text-slate-900">CSV Document</div>
                          <div className="text-[10px] text-slate-500">Spreadsheet ready</div>
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setExportFormat('json')}
                        className={`p-3 rounded-xl border text-left flex items-start gap-2.5 transition-colors shadow-sm ${
                          exportFormat === 'json'
                            ? 'bg-[#ebfff7] border-[#00d09c] text-slate-900'
                            : 'bg-white border-[#dfeee8] text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        <Hash className="w-4 h-4 text-[#00a26d] mt-0.5 shrink-0" />
                        <div>
                          <div className="text-xs font-semibold text-slate-900">JSON Payload</div>
                          <div className="text-[10px] text-slate-500">For SIEM ingestion</div>
                        </div>
                      </button>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-[#f9fffc] border border-[#e3f4ee] text-xs text-slate-600 space-y-1">
                    <div className="font-semibold text-slate-800">Auditing Notice:</div>
                    <p>
                      Triggering this export creates an immutable <span className="font-mono text-emerald-700">audit.exported</span> entry recording your operator identity, IP, and timestamp.
                    </p>
                  </div>

                  <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setShowExportModal(false)}
                      className="px-3.5 py-2 text-xs font-semibold rounded-xl bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 shadow-sm transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleRunExport()}
                      disabled={isExporting}
                      className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white disabled:opacity-50 shadow-sm transition-colors"
                    >
                      <ArrowDownToLine className="w-3.5 h-3.5" />
                      {isExporting ? 'Generating Export...' : `Download ${exportFormat.toUpperCase()}`}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
