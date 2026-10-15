'use client'

/**
 * app/(console)/console/users/page.tsx – Customer User Directory & Lifecycle Console.
 *
 * Implements Plan Phase 2 (Section 2.2 & 4.1):
 *   • Opaque cursor pagination on indexed keys (created_at, username, last_login)
 *   • Anchored debounce search across usernames, emails, and phone numbers
 *   • Privacy & PII compliance: clear indicator of masking vs audit-logged unmasked view
 *   • Full user lifecycle actions: Suspend, Reinstate, Unlock, Reset Password, Revoke Sessions, Soft Delete, Restore
 *   • Optimistic concurrency (If-Match: W/"<version>") with conflict resolution dialog
 *   • Last-admin protection guard handling
 */

import React, { useEffect, useState, useCallback } from 'react'
import {
  Users,
  Search,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  Lock,
  Unlock,
  KeyRound,
  Trash2,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  Copy,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  UserX,
  Eye,
  EyeOff,
  LogOut,
  Building,
  Briefcase,
  X,
  Loader2,
  Hash,
  FileText,
  ShieldAlert,
} from 'lucide-react'
import { useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import {
  consoleUsersApi,
  ConsoleApiError,
  ConsoleUserItem,
  ConsoleUserDetail,
  UserMetaLookups,
  CreateUserPayload,
  UpdateUserPayload,
  PasswordResetResult,
  ImpersonationStartResponse,
} from '@/console/api'
import {
  RequestPurgeModal,
  PurgeRequestsDrawer,
  RetentionPoliciesModal,
} from '@/console/components/PurgeModals'
import {
  StartImpersonationModal,
  ActiveImpersonationsDrawer,
} from '@/console/components/ImpersonationModals'
import { cn } from '@/lib/utils'

function getApiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ConsoleApiError) {
    return err.detail || fallback
  }
  if (err instanceof Error) {
    return err.message || fallback
  }
  if (typeof err === 'object' && err !== null && 'detail' in err) {
    return String((err as { detail: unknown }).detail)
  }
  return fallback
}

export default function CustomerUsersPage() {
  const { permissions } = useConsoleAuth()

  // Capabilities
  const canRead = permissions.has('users.read') || permissions.has('all')
  const canWrite = permissions.has('users.write') || permissions.has('all')
  const canReadPii = permissions.has('users.read_pii') || permissions.has('all')

  // Data states
  const [users, setUsers] = useState<ConsoleUserItem[]>([])
  const [lookups, setLookups] = useState<UserMetaLookups | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null)

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'suspended' | 'locked' | 'deleted'>('all')
  const [accountIdFilter, setAccountIdFilter] = useState<number | null>(null)
  const [roleIdFilter, setRoleIdFilter] = useState<number | null>(null)
  const [sortField, setSortField] = useState<'created_at' | 'last_login' | 'username'>('created_at')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')

  // Cursor Pagination states
  const [currentCursor, setCurrentCursor] = useState<string | undefined>(undefined)
  const [cursorHistory, setCursorHistory] = useState<(string | undefined)[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [approxCount, setApproxCount] = useState<number | null>(null)

  // Modals & Action Drawer states
  const [detailUser, setDetailUser] = useState<ConsoleUserDetail | null>(null)
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false)

  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [userToEdit, setUserToEdit] = useState<ConsoleUserDetail | null>(null)

  const [suspendModalOpen, setSuspendModalOpen] = useState(false)
  const [userToSuspend, setUserToSuspend] = useState<ConsoleUserItem | null>(null)
  const [suspendReason, setSuspendReason] = useState('')

  const [reinstateModalOpen, setReinstateModalOpen] = useState(false)
  const [userToReinstate, setUserToReinstate] = useState<ConsoleUserItem | null>(null)
  const [reinstateReason, setReinstateReason] = useState('')

  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [userToDelete, setUserToDelete] = useState<ConsoleUserItem | null>(null)

  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [userToResetPassword, setUserToResetPassword] = useState<ConsoleUserItem | null>(null)
  const [passwordResetMode, setPasswordResetMode] = useState<'temporary' | 'link'>('temporary')
  const [passwordResetResult, setPasswordResetResult] = useState<PasswordResetResult | null>(null)

  const [conflictModalOpen, setConflictModalOpen] = useState(false)
  const [conflictError, setConflictError] = useState('')

  // Phase 5 Capabilities & States
  const canHardDelete = permissions.has('users.hard_delete') || permissions.has('all')
  const canImpersonate = permissions.has('users.impersonate') || permissions.has('all')

  const [purgeRequestModalOpen, setPurgeRequestModalOpen] = useState(false)
  const [userToPurge, setUserToPurge] = useState<ConsoleUserItem | ConsoleUserDetail | null>(null)
  const [purgeDrawerOpen, setPurgeDrawerOpen] = useState(false)
  const [pendingPurgesCount, setPendingPurgesCount] = useState<number>(0)

  const [impersonateModalOpen, setImpersonateModalOpen] = useState(false)
  const [userToImpersonate, setUserToImpersonate] = useState<ConsoleUserItem | ConsoleUserDetail | null>(null)
  const [activeImpersonationsOpen, setActiveImpersonationsOpen] = useState(false)

  const [retentionModalOpen, setRetentionModalOpen] = useState(false)

  // Create form state
  const [createFormData, setCreateFormData] = useState<CreateUserPayload>({
    account_id: 1,
    company_id: 1,
    role_id: 1,
    email: '',
    username: '',
    phone: '',
    designation: '',
    employee_code: '',
    generate_temp_password: true,
    verified_by_us: true,
    reason: 'Created via Platform Operator Console',
  })
  const [createdTempPassword, setCreatedTempPassword] = useState<string | null>(null)

  // Edit form state
  const [editFormData, setEditFormData] = useState<UpdateUserPayload>({
    username: '',
    phone: '',
    designation: '',
    employee_code: '',
    role_id: undefined,
    reason: '',
  })

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim())
      setCurrentCursor(undefined)
      setCursorHistory([])
    }, 350)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Load Lookups on mount
  useEffect(() => {
    if (!canRead) return
    let active = true
    consoleUsersApi
      .getLookups()
      .then((data) => {
        if (!active) return
        setLookups(data)
        if (data.accounts.length > 0) {
          setCreateFormData((prev) => ({
            ...prev,
            account_id: prev.account_id || data.accounts[0].account_id,
            company_id: prev.company_id || data.companies[0]?.company_id || 1,
            role_id: prev.role_id || data.roles[0]?.role_id || 1,
          }))
        }
      })
      .catch((err) => {
        if (err instanceof ConsoleApiError && err.status === 401) return
        console.warn('Failed to load lookups', err)
      })
    return () => {
      active = false
    }
  }, [canRead])

  // Quick message auto-dismiss
  const showSuccess = (msg: string) => {
    setFeedbackSuccess(msg)
    setTimeout(() => setFeedbackSuccess(null), 5000)
  }

  const showError = (msg: string) => {
    setFeedbackError(msg)
    setTimeout(() => setFeedbackError(null), 8000)
  }

  const refreshPurgesCount = useCallback(async () => {
    if (!canRead) return
    try {
      const list = await consoleUsersApi.listPurgeRequests('pending')
      setPendingPurgesCount(list.length)
    } catch {
      // Ignored
    }
  }, [canRead])

  useEffect(() => {
    queueMicrotask(() => {
      void refreshPurgesCount()
    })
  }, [refreshPurgesCount])

  // Fetch users function
  const fetchUsers = useCallback(
    async (cursorToUse?: string) => {
      if (!canRead) return
      setLoading(true)
      setFeedbackError(null)

      try {
        const res = await consoleUsersApi.list({
          cursor: cursorToUse,
          limit: 30,
          sort: sortField,
          order: sortOrder,
          q: debouncedSearch || undefined,
          account_id: accountIdFilter !== null ? accountIdFilter : undefined,
          role_id: roleIdFilter !== null ? roleIdFilter : undefined,
          status: statusFilter === 'all' || statusFilter === 'deleted' ? undefined : statusFilter,
          include_deleted: statusFilter === 'deleted' || statusFilter === 'all',
          include_approx_count: true,
        })

        let items = res.items
        if (statusFilter === 'deleted') {
          items = items.filter((u) => u.deleted_at !== null || u.status === 'deleted')
        } else if (statusFilter !== 'all') {
          items = items.filter((u) => u.status === statusFilter && !u.deleted_at)
        }

        setUsers(items)
        setNextCursor(res.next_cursor || null)
        setHasMore(res.has_more)
        if (res.approx_count !== undefined && res.approx_count !== null) {
          setApproxCount(res.approx_count)
        }
      } catch (err: unknown) {
        setFeedbackError(getApiErrorMessage(err, 'Failed to fetch customer users.'))
      } finally {
        setLoading(false)
      }
    },
    [canRead, sortField, sortOrder, debouncedSearch, accountIdFilter, roleIdFilter, statusFilter]
  )

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchUsers(currentCursor)
    }, 0)
    return () => clearTimeout(timer)
  }, [fetchUsers, currentCursor])

  // Pagination navigation
  const handleNextPage = () => {
    if (!nextCursor) return
    setCursorHistory((prev) => [...prev, currentCursor])
    setCurrentCursor(nextCursor)
  }

  const handlePrevPage = () => {
    if (cursorHistory.length === 0) return
    const prevHistory = [...cursorHistory]
    const previousCursor = prevHistory.pop()
    setCursorHistory(prevHistory)
    setCurrentCursor(previousCursor)
  }

  // ── Action Handlers ──

  const handleOpenDetail = async (user: ConsoleUserItem) => {
    try {
      setActionLoading(true)
      const detail = await consoleUsersApi.get(user.user_id)
      setDetailUser(detail)
      setIsDetailDrawerOpen(true)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to retrieve detailed customer record.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleOpenEdit = async (user: ConsoleUserItem) => {
    try {
      setActionLoading(true)
      const detail = await consoleUsersApi.get(user.user_id)
      setUserToEdit(detail)
      setEditFormData({
        username: detail.username,
        phone: detail.phone || '',
        designation: detail.designation || '',
        employee_code: detail.employee_code || '',
        role_id: detail.role_id,
        reason: 'Updated profile via Platform Operator Console',
      })
      setEditModalOpen(true)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to retrieve user for editing.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleSaveEdit = async () => {
    if (!userToEdit) return
    setActionLoading(true)
    try {
      const updated = await consoleUsersApi.update(userToEdit.user_id, editFormData, userToEdit.version)
      showSuccess(`Successfully updated user ${updated.username} (v${updated.version}).`)
      setEditModalOpen(false)
      setUserToEdit(null)
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError && err.status === 409) {
        setConflictError(
          'Optimistic Locking Conflict: Another operator or user modified this record while you were editing. Please review the updated version and re-apply.'
        )
        setConflictModalOpen(true)
      } else {
        showError(getApiErrorMessage(err, 'Failed to update user profile.'))
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleCreateUser = async () => {
    setActionLoading(true)
    try {
      const result = await consoleUsersApi.create(createFormData)
      showSuccess(`Created customer user ${result.user.username} (${result.user.email}).`)
      if (result.temp_password) {
        setCreatedTempPassword(result.temp_password)
      } else {
        setCreateModalOpen(false)
      }
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to create customer user.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleSuspendUser = async () => {
    if (!userToSuspend || !suspendReason.trim()) return
    setActionLoading(true)
    try {
      await consoleUsersApi.suspend(userToSuspend.user_id, suspendReason.trim())
      showSuccess(`User ${userToSuspend.username} has been suspended.`)
      setSuspendModalOpen(false)
      setUserToSuspend(null)
      setSuspendReason('')
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to suspend user.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleReinstateUser = async () => {
    if (!userToReinstate) return
    setActionLoading(true)
    try {
      await consoleUsersApi.reinstate(userToReinstate.user_id, reinstateReason.trim())
      showSuccess(`User ${userToReinstate.username} has been reinstated to active status.`)
      setReinstateModalOpen(false)
      setUserToReinstate(null)
      setReinstateReason('')
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to reinstate user.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleUnlockUser = async (user: ConsoleUserItem) => {
    setActionLoading(true)
    try {
      await consoleUsersApi.unlock(user.user_id)
      showSuccess(`User ${user.username} account lock cleared.`)
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to unlock user account.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleResetPassword = async () => {
    if (!userToResetPassword) return
    setActionLoading(true)
    try {
      const res = await consoleUsersApi.resetPassword(
        userToResetPassword.user_id,
        passwordResetMode,
        'Password reset issued by Platform Operator Console'
      )
      setPasswordResetResult(res)
      showSuccess('Password reset successfully generated.')
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to reset user password.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleRevokeSessions = async (user: ConsoleUserItem) => {
    if (!confirm(`Are you sure you want to terminate all active sessions for ${user.username}?`)) return
    setActionLoading(true)
    try {
      const res = await consoleUsersApi.revokeSessions(user.user_id)
      showSuccess(`Terminated ${res.revoked_sessions_count} active session(s) for ${user.username}.`)
      if (detailUser?.user_id === user.user_id) {
        setDetailUser({ ...detailUser, active_sessions_count: 0 })
      }
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to revoke user sessions.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteUser = async () => {
    if (!userToDelete) return
    setActionLoading(true)
    try {
      const res = await consoleUsersApi.delete(userToDelete.user_id)
      showSuccess(`User ${userToDelete.username} soft-deleted. Purge scheduled for ${new Date(res.purge_after).toLocaleDateString()}.`)
      setDeleteModalOpen(false)
      setUserToDelete(null)
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to delete user.'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleRestoreUser = async (user: ConsoleUserItem) => {
    setActionLoading(true)
    try {
      await consoleUsersApi.restore(user.user_id)
      showSuccess(`User ${user.username} has been restored to active status.`)
      void fetchUsers(currentCursor)
    } catch (err: unknown) {
      showError(getApiErrorMessage(err, 'Failed to restore soft-deleted user.'))
    } finally {
      setActionLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    void navigator.clipboard.writeText(text)
    showSuccess('Copied to clipboard!')
  }

  return (
    <div className="space-y-6">
      {/* ── Top Header & Stats ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#e3f4ee] pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Users className="w-6 h-6 text-[#00a26d]" />
            Customer User Directory
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage multi-tenant user accounts, lifecycle transitions, password resets, and session revoking.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setPurgeDrawerOpen(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:text-slate-900 bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors shadow-sm"
            title="Two-Person Purge Requests Queue"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
            <span>Purge Requests</span>
            {pendingPurgesCount > 0 && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-600 text-white animate-pulse">
                {pendingPurgesCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveImpersonationsOpen(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:text-slate-900 bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors shadow-sm"
            title="Active Operator Impersonation Sessions"
          >
            <UserCheck className="w-3.5 h-3.5 text-amber-500" />
            <span>Impersonations</span>
          </button>

          <button
            onClick={() => setRetentionModalOpen(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors shadow-sm"
            title="Statutory Data Retention Policy Catalogue"
          >
            <FileText className="w-3.5 h-3.5 text-slate-600" />
            <span>Retention</span>
          </button>

          <button
            onClick={() => void fetchUsers(currentCursor)}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-slate-700 hover:text-slate-900 bg-white border border-[#dfeee8] hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
            title="Refresh list"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin text-[#00a26d]')} />
            Refresh
          </button>

          {canWrite && (
            <button
              onClick={() => {
                setCreatedTempPassword(null)
                setCreateModalOpen(true)
              }}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-[#00d09c] hover:bg-[#00b98a] shadow-md shadow-[#00d09c]/20 transition-all"
            >
              <Plus className="w-4 h-4" />
              Add Customer User
            </button>
          )}
        </div>
      </div>

      {/* ── Security & PII Compliance Indicator ── */}
      <div
        className={cn(
          'p-3.5 rounded-xl border flex items-center justify-between gap-3 text-xs',
          canReadPii
            ? 'bg-[#ebfff7] border-[#b8f5dc] text-[#00a26d]'
            : 'bg-white border-[#dfeee8] text-slate-600 shadow-sm'
        )}
      >
        <div className="flex items-center gap-2.5">
          {canReadPii ? (
            <Eye className="w-4 h-4 text-[#00a26d] shrink-0" />
          ) : (
            <EyeOff className="w-4 h-4 text-slate-400 shrink-0" />
          )}
          <div>
            <span className="font-semibold text-slate-800">
              {canReadPii ? 'Full PII Mode Active:' : 'Masked PII Mode:'}
            </span>{' '}
            <span className="text-slate-600">
              {canReadPii
                ? 'Operator holds `users.read_pii` badge. Inspecting plaintext records automatically appends to the immutable audit log.'
                : 'Email and phone numbers are redacted to protect customer privacy. Plaintext requires `users.read_pii` badge.'}
            </span>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-1.5 font-mono text-[11px] bg-white px-2.5 py-1 rounded-lg border border-[#cfeee0] text-slate-600 shadow-sm">
          <Hash className="w-3 h-3 text-[#00a26d]" />
          Approx records: {approxCount ?? '—'}
        </div>
      </div>

      {/* ── Flash Feedback Toasts ── */}
      {feedbackSuccess && (
        <div className="p-3 rounded-xl bg-[#ecfff7] border border-[#a7f3d0] text-[#00875a] text-xs flex items-center gap-2 shadow-sm">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{feedbackSuccess}</span>
        </div>
      )}
      {feedbackError && (
        <div className="p-3 rounded-xl bg-[#fff1f2] border border-[#fecaca] text-[#d92d20] text-xs flex items-center gap-2 shadow-sm">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{feedbackError}</span>
        </div>
      )}

      {/* ── Filters & Search Bar ── */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by username, email, or phone number..."
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Tabs */}
          <div className="flex items-center bg-white p-1 rounded-xl border border-[#dfeee8] text-xs font-medium shadow-sm">
            {(['all', 'active', 'suspended', 'locked', 'deleted'] as const).map((st) => (
              <button
                key={st}
                onClick={() => {
                  setStatusFilter(st)
                  setCurrentCursor(undefined)
                  setCursorHistory([])
                }}
                className={cn(
                  'px-3 py-1.5 rounded-lg capitalize transition-colors',
                  statusFilter === st
                    ? 'bg-[#00d09c] text-white font-semibold shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                )}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Account Filter */}
          {lookups && lookups.accounts.length > 0 && (
            <select
              value={accountIdFilter ?? ''}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : null
                setAccountIdFilter(val)
                setCurrentCursor(undefined)
                setCursorHistory([])
              }}
              className="bg-white border border-[#dfeee8] text-slate-700 text-xs rounded-xl px-3 py-2 shadow-sm focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20"
            >
              <option value="">All Accounts</option>
              {lookups.accounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id}>
                  {acc.name}
                </option>
              ))}
            </select>
          )}

          {/* Role Filter */}
          {lookups && lookups.roles.length > 0 && (
            <select
              value={roleIdFilter ?? ''}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : null
                setRoleIdFilter(val)
                setCurrentCursor(undefined)
                setCursorHistory([])
              }}
              className="bg-white border border-[#dfeee8] text-slate-700 text-xs rounded-xl px-3 py-2 shadow-sm focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20"
            >
              <option value="">All Roles</option>
              {lookups.roles.map((r) => (
                <option key={r.role_id} value={r.role_id}>
                  {r.name}
                </option>
              ))}
            </select>
          )}

          {/* Sort Filter */}
          <select
            value={`${sortField}:${sortOrder}`}
            onChange={(e) => {
              const [f, o] = e.target.value.split(':') as [
                'created_at' | 'last_login' | 'username',
                'desc' | 'asc',
              ]
              setSortField(f)
              setSortOrder(o)
              setCurrentCursor(undefined)
              setCursorHistory([])
            }}
            className="bg-white border border-[#dfeee8] text-slate-700 text-xs rounded-xl px-3 py-2 shadow-sm focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20"
          >
            <option value="created_at:desc">Newest First</option>
            <option value="created_at:asc">Oldest First</option>
            <option value="username:asc">Username (A-Z)</option>
            <option value="last_login:desc">Recent Login</option>
          </select>
        </div>
      </div>

      {/* ── User Table ── */}
      <div className="bg-white border border-[#dfeee8] rounded-2xl overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#f9fffc] border-b border-[#e3f4ee] text-slate-600 font-semibold">
              <tr>
                <th className="py-3.5 px-4">User</th>
                <th className="py-3.5 px-4">Company &amp; Account</th>
                <th className="py-3.5 px-4">Role</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Last Login</th>
                <th className="py-3.5 px-4">Version</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eef7f3]">
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-slate-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#00a26d]" />
                    Loading customer directory...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-slate-400">
                    <UserX className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    No customer users match the selected criteria.
                  </td>
                </tr>
              ) : (
                users.map((user) => {
                  const isDeleted = Boolean(user.deleted_at || user.status === 'deleted')
                  const isSuspended = user.status === 'suspended'
                  const isLocked = user.status === 'locked'

                  return (
                    <tr
                      key={user.user_id}
                      className={cn(
                        'hover:bg-slate-50/70 transition-colors group',
                        isDeleted && 'opacity-60 bg-slate-50/50'
                      )}
                    >
                      {/* User (Username + Email) */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-xl bg-[#ebfff7] border border-[#cfeee0] flex items-center justify-center font-bold text-xs text-[#00a26d]">
                            {user.username.slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                              <span className={cn(isDeleted && 'line-through text-slate-400')}>{user.username}</span>
                              {user.email_verified_at && (
                                <span title="Email verified">
                                  <ShieldCheck className="w-3.5 h-3.5 text-[#00a26d] shrink-0" />
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-500 font-mono flex items-center gap-1 truncate">
                              <span>{user.email}</span>
                              <button
                                onClick={() => copyToClipboard(user.email)}
                                className="opacity-0 group-hover:opacity-100 hover:text-slate-800 transition-opacity"
                                title="Copy Email"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Company & Account */}
                      <td className="py-3.5 px-4">
                        <div className="text-slate-800 font-medium truncate max-w-[180px]">
                          {user.company_name || `Company #${user.company_id}`}
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {user.account_id ? `Account #${user.account_id}` : 'Unassigned Account'}
                        </div>
                      </td>

                      {/* Role */}
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-[11px] font-medium text-slate-700">
                          {user.role_name || `Role #${user.role_id}`}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        {user.purged_at ? (
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-medium"
                            title={`GDPR Anonymised on ${new Date(user.purged_at).toLocaleDateString()}`}
                          >
                            <ShieldAlert className="w-3 h-3 text-purple-600" />
                            Purged (GDPR)
                          </span>
                        ) : isDeleted ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200 text-[10px] font-medium">
                            <Trash2 className="w-3 h-3 text-slate-400" />
                            Deleted
                          </span>
                        ) : isSuspended ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-medium">
                            <AlertTriangle className="w-3 h-3 text-amber-500" />
                            Suspended
                          </span>
                        ) : isLocked ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-medium">
                            <Lock className="w-3 h-3 text-rose-500" />
                            Locked
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] text-[10px] font-medium">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#00a26d] animate-pulse" />
                            Active
                          </span>
                        )}
                      </td>

                      {/* Last Login */}
                      <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                        {user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}
                      </td>

                      {/* Version (Optimistic Concurrency) */}
                      <td className="py-3.5 px-4">
                        <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                          v{user.version}
                        </span>
                      </td>

                      {/* Action Menu */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Inspect / View button */}
                          <button
                            onClick={() => void handleOpenDetail(user)}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                            title="Inspect User Details"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>

                          {/* Quick Lifecycle Actions */}
                          {canWrite && !isDeleted && (
                            <>
                              <button
                                onClick={() => void handleOpenEdit(user)}
                                className="p-1.5 rounded-lg text-slate-500 hover:text-[#00a26d] hover:bg-[#ebfff7] transition-colors"
                                title="Edit Profile"
                              >
                                <Briefcase className="w-3.5 h-3.5" />
                              </button>

                              {canImpersonate && (
                                <button
                                  onClick={() => {
                                    setUserToImpersonate(user)
                                    setImpersonateModalOpen(true)
                                  }}
                                  className="p-1.5 rounded-lg text-amber-600 hover:text-amber-800 hover:bg-amber-50 transition-colors"
                                  title="Impersonate Customer User"
                                >
                                  <UserCheck className="w-3.5 h-3.5" />
                                </button>
                              )}

                              {isSuspended ? (
                                <button
                                  onClick={() => {
                                    setUserToReinstate(user)
                                    setReinstateReason('')
                                    setReinstateModalOpen(true)
                                  }}
                                  className="p-1.5 rounded-lg text-[#00a26d] hover:bg-[#ebfff7] transition-colors"
                                  title="Reinstate Account"
                                >
                                  <UserCheck className="w-3.5 h-3.5" />
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    setUserToSuspend(user)
                                    setSuspendReason('')
                                    setSuspendModalOpen(true)
                                  }}
                                  className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 transition-colors"
                                  title="Suspend User"
                                >
                                  <UserX className="w-3.5 h-3.5" />
                                </button>
                              )}

                              {isLocked && (
                                <button
                                  onClick={() => void handleUnlockUser(user)}
                                  className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 transition-colors"
                                  title="Unlock Account"
                                >
                                  <Unlock className="w-3.5 h-3.5" />
                                </button>
                              )}

                              <button
                                onClick={() => {
                                  setUserToResetPassword(user)
                                  setPasswordResetResult(null)
                                  setPasswordModalOpen(true)
                                }}
                                className="p-1.5 rounded-lg text-slate-500 hover:text-amber-600 hover:bg-amber-50 transition-colors"
                                title="Reset Password"
                              >
                                <KeyRound className="w-3.5 h-3.5" />
                              </button>

                              <button
                                onClick={() => void handleRevokeSessions(user)}
                                className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                                title="Revoke Active Sessions"
                              >
                                <LogOut className="w-3.5 h-3.5" />
                              </button>

                              <button
                                onClick={() => {
                                  setUserToDelete(user)
                                  setDeleteModalOpen(true)
                                }}
                                className="p-1.5 rounded-lg text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                                title="Soft Delete"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}

                          {canWrite && isDeleted && (
                            <>
                              <button
                                onClick={() => void handleRestoreUser(user)}
                                className="p-1.5 rounded-lg text-indigo-600 hover:bg-indigo-50 transition-colors"
                                title="Restore User"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>

                              {canHardDelete && !user.purged_at && (
                                <button
                                  onClick={() => {
                                    setUserToPurge(user)
                                    setPurgeRequestModalOpen(true)
                                  }}
                                  className="p-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition-colors"
                                  title="Request Irreversible GDPR Anonymisation / Purge"
                                >
                                  <ShieldAlert className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* ── Cursor Pagination Navigation ── */}
        <div className="p-4 border-t border-[#e3f4ee] bg-[#f9fffc] flex items-center justify-between text-xs text-slate-500">
          <div>
            Showing <span className="font-semibold text-slate-800">{users.length}</span> user(s) on this page
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handlePrevPage}
              disabled={cursorHistory.length === 0 || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 shadow-sm disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={!hasMore || !nextCursor || loading}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 shadow-sm disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          1. DETAIL DRAWER / INSPECTION MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      {isDetailDrawerOpen && detailUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-lg bg-white border-l border-[#dfeee8] p-6 flex flex-col h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-4 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#ebfff7] border border-[#cfeee0] flex items-center justify-center text-[#00a26d] font-bold text-base">
                  {detailUser.username.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">{detailUser.username}</h2>
                  <p className="text-xs text-slate-500 font-mono">User ID: #{detailUser.user_id}</p>
                </div>
              </div>
              <button
                onClick={() => setIsDetailDrawerOpen(false)}
                className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4 flex-1 text-xs">
              {/* Account & Company Details */}
              <div className="bg-[#f9fffc] p-4 rounded-xl border border-[#e3f4ee] space-y-2.5">
                <div className="font-semibold text-slate-800 flex items-center gap-2">
                  <Building className="w-4 h-4 text-[#00a26d]" />
                  Account &amp; Organization
                </div>
                <div className="grid grid-cols-2 gap-2 text-slate-600">
                  <div>
                    <span className="block text-[11px] text-slate-500">Account:</span>
                    <span className="text-slate-800 font-medium">{detailUser.account_name || `Account #${detailUser.account_id}`}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Company:</span>
                    <span className="text-slate-800 font-medium">{detailUser.company_name || `Company #${detailUser.company_id}`}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Assigned Role:</span>
                    <span className="text-slate-800 font-medium">{detailUser.role_name || `Role #${detailUser.role_id}`}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Designation:</span>
                    <span className="text-slate-800 font-medium">{detailUser.designation || 'None'}</span>
                  </div>
                </div>
              </div>

              {/* Contact Information (PII) */}
              <div className="bg-[#f9fffc] p-4 rounded-xl border border-[#e3f4ee] space-y-2.5">
                <div className="font-semibold text-slate-800 flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-[#00a26d]" />
                    Contact &amp; Privacy
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">
                    {canReadPii ? 'Unmasked' : 'Masked'}
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-2 text-slate-600">
                  <div>
                    <span className="block text-[11px] text-slate-500">Email Address:</span>
                    <span className="text-slate-800 font-mono font-medium select-all">{detailUser.email}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Phone Number:</span>
                    <span className="text-slate-800 font-mono">{detailUser.phone || 'Not provided'}</span>
                  </div>
                  {detailUser.employee_code && (
                    <div>
                      <span className="block text-[11px] text-slate-500">Employee Code:</span>
                      <span className="text-slate-800 font-mono">{detailUser.employee_code}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Lifecycle & Security State */}
              <div className="bg-[#f9fffc] p-4 rounded-xl border border-[#e3f4ee] space-y-2.5">
                <div className="font-semibold text-slate-800 flex items-center gap-2">
                  <Lock className="w-4 h-4 text-amber-500" />
                  Lifecycle &amp; Security
                </div>
                <div className="grid grid-cols-2 gap-2 text-slate-600">
                  <div>
                    <span className="block text-[11px] text-slate-500">Account Status:</span>
                    <span className="capitalize font-semibold text-slate-800">{detailUser.status}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Active Sessions:</span>
                    <span className="text-slate-800 font-mono font-semibold">{detailUser.active_sessions_count}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Must Change Password:</span>
                    <span className="text-slate-800 font-medium">{detailUser.must_change_password ? 'Yes' : 'No'}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] text-slate-500">Record Version:</span>
                    <span className="text-slate-800 font-mono font-medium">v{detailUser.version}</span>
                  </div>
                </div>

                {detailUser.suspended_at && (
                  <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 mt-2">
                    <span className="font-semibold">Suspended:</span> {new Date(detailUser.suspended_at).toLocaleString()}
                    <br />
                    <span className="font-semibold">Reason:</span> {detailUser.suspended_reason || 'No reason provided'}
                  </div>
                )}

                {detailUser.purged_at && (
                  <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 text-purple-800 mt-2 space-y-1">
                    <div className="font-bold flex items-center gap-1.5 text-purple-900">
                      <ShieldAlert className="w-4 h-4 text-purple-600" />
                      GDPR Anonymised &amp; Purged
                    </div>
                    <div className="text-[11px] text-purple-700 font-mono">
                      Purged on {new Date(detailUser.purged_at).toLocaleString()}
                    </div>
                    <p className="text-[10px] text-purple-600 leading-relaxed">
                      All PII has been permanently scrubbed. Accounting vouchers and audit traces remain intact under statutory retention schedules.
                    </p>
                  </div>
                )}

                {detailUser.deleted_at && !detailUser.purged_at && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 mt-2">
                    <span className="font-semibold">Soft Deleted:</span> {new Date(detailUser.deleted_at).toLocaleString()}
                    <br />
                    <span className="font-semibold">Scheduled Purge:</span>{' '}
                    {detailUser.purge_after ? new Date(detailUser.purge_after).toLocaleString() : 'After 30 days'}
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Actions inside Drawer */}
            <div className="border-t border-[#e3f4ee] pt-4 mt-6 flex flex-wrap items-center justify-between gap-2">
              {!detailUser.deleted_at && !detailUser.purged_at && (
                <>
                  <button
                    onClick={() => {
                      setIsDetailDrawerOpen(false)
                      void handleOpenEdit(detailUser)
                    }}
                    className="flex-1 py-2 px-3 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs shadow-sm transition-colors"
                  >
                    Edit Profile
                  </button>

                  {canImpersonate && (
                    <button
                      onClick={() => {
                        setUserToImpersonate(detailUser)
                        setImpersonateModalOpen(true)
                      }}
                      className="py-2 px-3 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                      title="Start Time-Boxed Impersonation"
                    >
                      <UserCheck className="w-3.5 h-3.5 text-amber-600" />
                      Impersonate
                    </button>
                  )}
                </>
              )}

              {detailUser.deleted_at && !detailUser.purged_at && canHardDelete && (
                <button
                  onClick={() => {
                    setUserToPurge(detailUser)
                    setPurgeRequestModalOpen(true)
                  }}
                  className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs flex items-center justify-center gap-1.5 shadow-sm"
                  title="Request Irreversible Purge"
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  Request GDPR Purge
                </button>
              )}

              {!detailUser.purged_at && (
                <button
                  onClick={() => void handleRevokeSessions(detailUser)}
                  className="py-2 px-3 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold transition-colors"
                  title="Revoke Sessions"
                >
                  Revoke Sessions
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          2. CREATE USER MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#00a26d]" />
                Add New Customer User
              </h2>
              <button
                onClick={() => setCreateModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {createdTempPassword ? (
              <div className="space-y-4 py-2">
                <div className="p-4 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] text-[#00a26d] text-xs space-y-2">
                  <div className="font-semibold flex items-center gap-2 text-slate-900">
                    <CheckCircle2 className="w-4 h-4 text-[#00a26d]" />
                    Customer Account Created Successfully!
                  </div>
                  <p className="text-slate-600">
                    A secure temporary password was generated. Please copy and provide it to the customer. It expires in 72 hours.
                  </p>
                  <div className="flex items-center justify-between bg-white p-2.5 rounded-lg border border-[#cfeee0] font-mono text-slate-900 text-sm">
                    <span>{createdTempPassword}</span>
                    <button
                      onClick={() => copyToClipboard(createdTempPassword)}
                      className="px-2.5 py-1 rounded bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-sans font-medium shadow-sm"
                    >
                      Copy
                    </button>
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => {
                      setCreatedTempPassword(null)
                      setCreateModalOpen(false)
                    }}
                    className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                {/* Account Selection */}
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Target Account</label>
                  <select
                    value={createFormData.account_id}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, account_id: Number(e.target.value) })
                    }
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  >
                    {lookups?.accounts.map((acc) => (
                      <option key={acc.account_id} value={acc.account_id}>
                        {acc.name} (#{acc.account_id})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Company & Role */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Company</label>
                    <select
                      value={createFormData.company_id}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, company_id: Number(e.target.value) })
                      }
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    >
                      {lookups?.companies
                        .filter(
                          (c) =>
                            c.account_id === createFormData.account_id ||
                            c.account_id === null
                        )
                        .map((c) => (
                          <option key={c.company_id} value={c.company_id}>
                            {c.name}
                          </option>
                        ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Role</label>
                    <select
                      value={createFormData.role_id}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, role_id: Number(e.target.value) })
                      }
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    >
                      {lookups?.roles
                        .filter(
                          (r) =>
                            r.account_id === createFormData.account_id ||
                            r.account_id === null
                        )
                        .map((r) => (
                          <option key={r.role_id} value={r.role_id}>
                            {r.name}
                          </option>
                        ))}
                    </select>
                  </div>
                </div>

                {/* Username & Email */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Username</label>
                    <input
                      type="text"
                      required
                      value={createFormData.username}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, username: e.target.value })
                      }
                      placeholder="e.g. jdoe"
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Email</label>
                    <input
                      type="email"
                      required
                      value={createFormData.email}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, email: e.target.value })
                      }
                      placeholder="john@example.com"
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    />
                  </div>
                </div>

                {/* Phone & Designation */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Phone (Optional)</label>
                    <input
                      type="text"
                      value={createFormData.phone || ''}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, phone: e.target.value })
                      }
                      placeholder="+91 9876543210"
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Designation (Optional)</label>
                    <input
                      type="text"
                      value={createFormData.designation || ''}
                      onChange={(e) =>
                        setCreateFormData({ ...createFormData, designation: e.target.value })
                      }
                      placeholder="Senior Accountant"
                      className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                    />
                  </div>
                </div>

                {/* Checkboxes */}
                <div className="space-y-2 pt-1">
                  <label className="flex items-center gap-2 cursor-pointer text-slate-700">
                    <input
                      type="checkbox"
                      checked={createFormData.generate_temp_password}
                      onChange={(e) =>
                        setCreateFormData({
                          ...createFormData,
                          generate_temp_password: e.target.checked,
                        })
                      }
                      className="rounded border-[#dfeee8] text-[#00d09c] focus:ring-[#00d09c]"
                    />
                    <span>Generate high-entropy temporary password</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-slate-700">
                    <input
                      type="checkbox"
                      checked={createFormData.verified_by_us}
                      onChange={(e) =>
                        setCreateFormData({
                          ...createFormData,
                          verified_by_us: e.target.checked,
                        })
                      }
                      className="rounded border-[#dfeee8] text-[#00d09c] focus:ring-[#00d09c]"
                    />
                    <span>Mark email pre-verified by platform operator</span>
                  </label>
                </div>

                {/* Reason */}
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Operator Audit Note</label>
                  <input
                    type="text"
                    value={createFormData.reason || ''}
                    onChange={(e) =>
                      setCreateFormData({ ...createFormData, reason: e.target.value })
                    }
                    placeholder="Customer requested new staff account..."
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-[#e3f4ee]">
                  <button
                    onClick={() => setCreateModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => void handleCreateUser()}
                    disabled={actionLoading || !createFormData.username || !createFormData.email}
                    className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs disabled:opacity-50 flex items-center gap-2 shadow-sm"
                  >
                    {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Create User
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          3. EDIT USER MODAL (With Optimistic Concurrency v{version})
         ───────────────────────────────────────────────────────────────────────────── */}
      {editModalOpen && userToEdit && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-3">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Briefcase className="w-4 h-4 text-[#00a26d]" />
                  Edit Profile: {userToEdit.username}
                </h2>
                <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                  Concurrency Version: <span className="text-[#00a26d] font-semibold">v{userToEdit.version}</span>
                </div>
              </div>
              <button
                onClick={() => setEditModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Username</label>
                <input
                  type="text"
                  value={editFormData.username}
                  onChange={(e) => setEditFormData({ ...editFormData, username: e.target.value })}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Role Assignment</label>
                <select
                  value={editFormData.role_id}
                  onChange={(e) =>
                    setEditFormData({ ...editFormData, role_id: Number(e.target.value) })
                  }
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  {lookups?.roles
                    .filter(
                      (r) =>
                        r.account_id === userToEdit.account_id || r.account_id === null
                    )
                    .map((r) => (
                      <option key={r.role_id} value={r.role_id}>
                        {r.name}
                      </option>
                    ))}
                </select>
                <p className="text-[11px] text-slate-500 mt-1">
                  Note: Demoting the sole active Admin of an account will be rejected by the last-admin guard.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Phone</label>
                  <input
                    type="text"
                    value={editFormData.phone || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, phone: e.target.value })}
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Designation</label>
                  <input
                    type="text"
                    value={editFormData.designation || ''}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, designation: e.target.value })
                    }
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Change Reason / Audit Note</label>
                <input
                  type="text"
                  value={editFormData.reason || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, reason: e.target.value })}
                  placeholder="Reason for modifying customer user profile..."
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[#e3f4ee]">
                <button
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void handleSaveEdit()}
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs flex items-center gap-2 shadow-sm"
                >
                  {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Changes (v{userToEdit.version})
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          4. SUSPEND USER MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      {suspendModalOpen && userToSuspend && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white border border-amber-200 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Suspend Customer User</h3>
                <p className="text-xs text-slate-500">Account will be immediately blocked from signing in.</p>
              </div>
            </div>

            <div className="text-xs text-slate-600 space-y-2">
              <p>
                Suspending user <span className="font-semibold text-slate-900">{userToSuspend.username}</span> will immediately terminate existing login sessions and reject new token issuances.
              </p>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Suspension Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  value={suspendReason}
                  onChange={(e) => setSuspendReason(e.target.value)}
                  placeholder="Explain why this account is suspended (e.g. suspicious activity, customer dispute)..."
                  className="w-full bg-white border border-[#dfeee8] rounded-xl p-3 text-slate-900 focus:outline-none focus:border-amber-500 text-xs shadow-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#e3f4ee]">
              <button
                onClick={() => setSuspendModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleSuspendUser()}
                disabled={actionLoading || suspendReason.trim().length < 3}
                className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs disabled:opacity-50 flex items-center gap-2 shadow-sm"
              >
                {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Suspend Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          5. REINSTATE USER MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      {reinstateModalOpen && userToReinstate && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white border border-[#b8f5dc] rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-[#00a26d]">
              <div className="p-2.5 rounded-xl bg-[#ebfff7] border border-[#b8f5dc]">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Reinstate Customer User</h3>
                <p className="text-xs text-slate-500">Restore account status to active.</p>
              </div>
            </div>

            <div className="text-xs text-slate-600 space-y-2">
              <p>
                Reinstating <span className="font-semibold text-slate-900">{userToReinstate.username}</span> will clear the suspension lock and allow customer login.
              </p>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Audit Note (Optional)</label>
                <input
                  type="text"
                  value={reinstateReason}
                  onChange={(e) => setReinstateReason(e.target.value)}
                  placeholder="Account verified, issue resolved..."
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-[#00d09c] text-xs shadow-sm"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#e3f4ee]">
              <button
                onClick={() => setReinstateModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleReinstateUser()}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs flex items-center gap-2 shadow-sm"
              >
                {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Reinstate User
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          6. RESET PASSWORD MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      {passwordModalOpen && userToResetPassword && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white border border-[#dfeee8] rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#e3f4ee] pb-3">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-amber-500" />
                Reset Password: {userToResetPassword.username}
              </h3>
              <button
                onClick={() => setPasswordModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {passwordResetResult ? (
              <div className="space-y-4 text-xs py-2">
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-2">
                  <div className="font-semibold flex items-center gap-2 text-slate-900">
                    <CheckCircle2 className="w-4 h-4 text-amber-600" />
                    Temporary Password Ready
                  </div>
                  <p className="text-slate-600">
                    The user will be required to change this password on their next sign-in.
                  </p>
                  {passwordResetResult.temp_password && (
                    <div className="flex items-center justify-between bg-white p-2.5 rounded-lg border border-amber-200 font-mono text-slate-900 text-sm">
                      <span>{passwordResetResult.temp_password}</span>
                      <button
                        onClick={() => copyToClipboard(passwordResetResult.temp_password!)}
                        className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-700 text-white text-xs font-sans font-medium shadow-sm"
                      >
                        Copy
                      </button>
                    </div>
                  )}
                  {passwordResetResult.expires_at && (
                    <div className="text-[11px] text-slate-500 font-mono">
                      Expires: {new Date(passwordResetResult.expires_at).toLocaleString()}
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => {
                      setPasswordResetResult(null)
                      setPasswordModalOpen(false)
                    }}
                    className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <p className="text-slate-600">
                  Select password reset strategy for <span className="font-semibold text-slate-900">{userToResetPassword.email}</span>:
                </p>

                <div className="space-y-2">
                  <label className="flex items-center gap-2 p-2.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee] cursor-pointer">
                    <input
                      type="radio"
                      name="resetMode"
                      value="temporary"
                      checked={passwordResetMode === 'temporary'}
                      onChange={() => setPasswordResetMode('temporary')}
                      className="text-[#00d09c] focus:ring-[#00d09c]"
                    />
                    <div>
                      <div className="font-semibold text-slate-900">Temporary One-Time Password</div>
                      <div className="text-[11px] text-slate-500">
                        Generates a random 16-character password and forces password update on login.
                      </div>
                    </div>
                  </label>

                  <label className="flex items-center gap-2 p-2.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee] cursor-pointer">
                    <input
                      type="radio"
                      name="resetMode"
                      value="link"
                      checked={passwordResetMode === 'link'}
                      onChange={() => setPasswordResetMode('link')}
                      className="text-[#00d09c] focus:ring-[#00d09c]"
                    />
                    <div>
                      <div className="font-semibold text-slate-900">Reset Link / Token</div>
                      <div className="text-[11px] text-slate-500">
                        Dispatches a password reset link to user&apos;s registered email address.
                      </div>
                    </div>
                  </label>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-[#e3f4ee]">
                  <button
                    onClick={() => setPasswordModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => void handleResetPassword()}
                    disabled={actionLoading}
                    className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs flex items-center gap-2 shadow-sm"
                  >
                    {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Proceed
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          7. SOFT DELETE MODAL (With Last Admin Warning)
         ───────────────────────────────────────────────────────────────────────────── */}
      {deleteModalOpen && userToDelete && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white border border-rose-200 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Soft Delete Customer User</h3>
                <p className="text-xs text-slate-500">Record will be scheduled for purge after 90 days.</p>
              </div>
            </div>

            <div className="text-xs text-slate-600 space-y-2">
              <p>
                Are you sure you want to soft delete user <span className="font-semibold text-slate-900">{userToDelete.username}</span>?
              </p>
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-[11px] space-y-1">
                <strong>Last Admin Protection:</strong> If this user is the sole active Admin for their account, this action will be automatically rejected to prevent tenant lockout.
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#e3f4ee]">
              <button
                onClick={() => setDeleteModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-white border border-[#dfeee8] hover:bg-slate-50 text-slate-700 text-xs shadow-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteUser()}
                disabled={actionLoading}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs flex items-center gap-2 shadow-sm"
              >
                {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Confirm Soft Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          8. OPTIMISTIC CONCURRENCY CONFLICT DIALOG (409 Conflict)
         ───────────────────────────────────────────────────────────────────────────── */}
      {conflictModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white border border-amber-300 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-amber-600">
              <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Concurrent Modification Detected</h3>
                <p className="text-xs text-amber-700">HTTP 409 Conflict</p>
              </div>
            </div>

            <p className="text-xs text-slate-600">{conflictError}</p>

            <div className="flex justify-end gap-2 pt-2 border-t border-[#e3f4ee]">
              <button
                onClick={() => {
                  setConflictModalOpen(false)
                  void fetchUsers(currentCursor)
                }}
                className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-semibold shadow-sm"
              >
                Reload Latest Record
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          9. PHASE 5: REQUEST PURGE MODAL (GDPR Anonymisation Request)
         ───────────────────────────────────────────────────────────────────────────── */}
      <RequestPurgeModal
        isOpen={purgeRequestModalOpen}
        user={userToPurge}
        onClose={() => setPurgeRequestModalOpen(false)}
        onSuccess={(reqId) => {
          showSuccess(`Purge request #${reqId} submitted. Awaiting approval from a second operator.`)
          void refreshPurgesCount()
        }}
      />

      {/* ─────────────────────────────────────────────────────────────────────────────
          10. PHASE 5: TWO-PERSON PURGE REQUESTS QUEUE DRAWER
         ───────────────────────────────────────────────────────────────────────────── */}
      <PurgeRequestsDrawer
        isOpen={purgeDrawerOpen}
        onClose={() => setPurgeDrawerOpen(false)}
        onActionComplete={() => {
          void fetchUsers(currentCursor)
          void refreshPurgesCount()
        }}
      />

      {/* ─────────────────────────────────────────────────────────────────────────────
          11. PHASE 5: STATUTORY DATA RETENTION POLICY CATALOGUE MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      <RetentionPoliciesModal
        isOpen={retentionModalOpen}
        onClose={() => setRetentionModalOpen(false)}
      />

      {/* ─────────────────────────────────────────────────────────────────────────────
          12. PHASE 5: TIME-BOXED OPERATOR IMPERSONATION MODAL
         ───────────────────────────────────────────────────────────────────────────── */}
      <StartImpersonationModal
        isOpen={impersonateModalOpen}
        user={userToImpersonate}
        onClose={() => setImpersonateModalOpen(false)}
        onSuccess={(res: ImpersonationStartResponse) => {
          showSuccess(
            `Impersonation session #${res.impersonation_id} active (${res.write_access ? 'Read-Write' : 'Read-Only'}). Token stored. Customer portal banner is now live.`
          )
        }}
      />

      {/* ─────────────────────────────────────────────────────────────────────────────
          13. PHASE 5: ACTIVE OPERATOR IMPERSONATIONS DRAWER
         ───────────────────────────────────────────────────────────────────────────── */}
      <ActiveImpersonationsDrawer
        isOpen={activeImpersonationsOpen}
        onClose={() => setActiveImpersonationsOpen(false)}
      />
    </div>
  )
}
