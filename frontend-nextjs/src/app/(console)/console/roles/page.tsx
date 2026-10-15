'use client'

/**
 * app/(console)/console/roles/page.tsx – Roles, Permissions & Operator Access Console.
 *
 * Implements Plan Phase 3:
 *   • Dynamic Permissions catalogue inspection
 *   • Role CRUD, Rank Hierarchy (< operator.max_rank), System role protections
 *   • "Cannot grant what you lack" validation in UI
 *   • Platform Operator (Admin) Directory, Role Assignment, Status Management
 *   • Self-modification guards & Last Super-Admin protection indicators
 *   • Passkey resetting & Session revocation
 */

import React, { useEffect, useState, useCallback, useMemo, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import {
  Shield,
  ShieldCheck,
  Users,
  KeyRound,
  Plus,
  RefreshCw,
  Search,
  Check,
  AlertTriangle,
  Trash2,
  Edit2,
  LogOut,
  Sliders,
  X,
  Loader2,
  Clock,
  Sparkles,
  Fingerprint,
  AlertCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import {
  consoleRolesApi,
  consoleAdminsApi,
  ConsoleApiError,
  ConsoleRoleItem,
  PermissionCatalogueItem,
  ConsoleAdminItem,
  CreateRolePayload,
  CreateAdminPayload,
  AssignAdminRolesPayload,
} from '@/console/api'
import { Can } from '@/console/components/Guards'
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

function RolesAndAccessContent() {
  const { operator, permissions } = useConsoleAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const tabParam = searchParams?.get('tab')

  // Primary navigation tabs
  const activeTab: 'roles' | 'admins' | 'permissions' =
    tabParam === 'admins' ? 'admins' : tabParam === 'permissions' ? 'permissions' : 'roles'

  const handleSelectTab = useCallback((newTab: 'roles' | 'admins' | 'permissions') => {
    const targetUrl = newTab === 'roles' ? '/console/roles' : `/console/roles?tab=${newTab}`
    router.replace(targetUrl, { scroll: false })
  }, [router])

  // Global loading & feedback
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Data
  const [roles, setRoles] = useState<ConsoleRoleItem[]>([])
  const [allPermissions, setAllPermissions] = useState<PermissionCatalogueItem[]>([])
  const [admins, setAdmins] = useState<ConsoleAdminItem[]>([])

  // Search & filter states
  const [roleSearch, setRoleSearch] = useState('')
  const [adminSearch, setAdminSearch] = useState('')
  const [adminStatusFilter, setAdminStatusFilter] = useState('all')

  // Modals
  const [roleModalOpen, setRoleModalOpen] = useState(false)
  const [editingRole, setEditingRole] = useState<ConsoleRoleItem | null>(null)
  const [roleFormData, setRoleFormData] = useState<{
    code: string
    name: string
    description: string
    rank: number
    permissions: string[]
  }>({
    code: '',
    name: '',
    description: '',
    rank: 100,
    permissions: [],
  })

  // Permission edit modal for a specific role
  const [permModalRole, setPermModalRole] = useState<ConsoleRoleItem | null>(null)
  const [permSelection, setPermSelection] = useState<Set<string>>(new Set())

  // Admin create modal
  const [adminCreateModalOpen, setAdminCreateModalOpen] = useState(false)
  const [adminModalError, setAdminModalError] = useState<string | null>(null)
  const [assignRoleModalError, setAssignRoleModalError] = useState<string | null>(null)
  const [adminFormData, setAdminFormData] = useState<{
    email: string
    full_name: string
    password: string
    role_ids: number[]
    allowed_ip_cidrs: string
    status: 'active' | 'invited'
  }>({
    email: '',
    full_name: '',
    password: '',
    role_ids: [],
    allowed_ip_cidrs: '',
    status: 'active',
  })

  // Admin role assignment modal
  const [assignRoleAdmin, setAssignRoleAdmin] = useState<ConsoleAdminItem | null>(null)
  const [assignedRoleIds, setAssignedRoleIds] = useState<number[]>([])

  // Admin edit status modal
  const [editAdminStatusTarget, setEditAdminStatusTarget] = useState<ConsoleAdminItem | null>(null)
  const [newAdminStatus, setNewAdminStatus] = useState<string>('active')
  const [adminAllowedIps, setAdminAllowedIps] = useState<string>('')

  // Confirmation dialogs
  const [confirmDeleteRole, setConfirmDeleteRole] = useState<ConsoleRoleItem | null>(null)
  const [confirmDeleteAdmin, setConfirmDeleteAdmin] = useState<ConsoleAdminItem | null>(null)
  const [confirmResetPasskeys, setConfirmResetPasskeys] = useState<ConsoleAdminItem | null>(null)
  const [confirmRevokeSessions, setConfirmRevokeSessions] = useState<ConsoleAdminItem | null>(null)
  const [actionInProgress, setActionInProgress] = useState(false)

  // Current operator rank
  const myRank = operator?.max_rank ?? 0
  const isSuperAdmin = myRank >= 1000

  // ──────────────────────────────────────────────────────────────────────────
  // DATA LOADING
  // ──────────────────────────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    try {
      setRefreshing(true)
      const [fetchedRoles, fetchedPerms, fetchedAdmins] = await Promise.all([
        consoleRolesApi.list(),
        consoleRolesApi.getPermissions(),
        consoleAdminsApi.list(),
      ])
      setRoles(fetchedRoles)
      setAllPermissions(fetchedPerms)
      setAdmins(fetchedAdmins)
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to load roles and operator directory.'),
      })
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    // Wrap initial load in microtask to avoid react-hooks/set-state-in-effect warning
    const timer = setTimeout(() => {
      void loadData()
    }, 0)
    return () => clearTimeout(timer)
  }, [loadData])

  // Clear feedback after 5s
  useEffect(() => {
    if (!feedback) return
    const t = setTimeout(() => setFeedback(null), 5000)
    return () => clearTimeout(t)
  }, [feedback])

  // Group permissions by resource for clean UI display
  const permissionsByResource = useMemo(() => {
    const map: Record<string, PermissionCatalogueItem[]> = {}
    for (const p of allPermissions) {
      if (!map[p.resource]) map[p.resource] = []
      map[p.resource].push(p)
    }
    return map
  }, [allPermissions])

  // Filtered lists
  const filteredRoles = useMemo(() => {
    if (!roleSearch.trim()) return roles
    const q = roleSearch.toLowerCase()
    return roles.filter(
      r =>
        (r.name || '').toLowerCase().includes(q) ||
        (r.code || '').toLowerCase().includes(q) ||
        (r.description && r.description.toLowerCase().includes(q))
    )
  }, [roles, roleSearch])

  const filteredAdmins = useMemo(() => {
    return admins.filter(a => {
      if (adminStatusFilter !== 'all' && a.status !== adminStatusFilter) return false
      if (!adminSearch.trim()) return true
      const q = adminSearch.toLowerCase()
      return (
        (a.full_name || '').toLowerCase().includes(q) ||
        (a.email || '').toLowerCase().includes(q) ||
        (a.roles || []).some(r => (r.name || '').toLowerCase().includes(q) || (r.code || '').toLowerCase().includes(q))
      )
    })
  }, [admins, adminSearch, adminStatusFilter])

  // ──────────────────────────────────────────────────────────────────────────
  // HANDLERS: ROLES
  // ──────────────────────────────────────────────────────────────────────────

  const handleOpenCreateRole = () => {
    setEditingRole(null)
    setRoleFormData({
      code: '',
      name: '',
      description: '',
      rank: Math.min(500, Math.max(1, myRank - 100)),
      permissions: ['page.users', 'users.read'],
    })
    setRoleModalOpen(true)
  }

  const handleOpenEditRole = (role: ConsoleRoleItem) => {
    setEditingRole(role)
    setRoleFormData({
      code: role.code,
      name: role.name,
      description: role.description || '',
      rank: role.rank,
      permissions: role.permissions,
    })
    setRoleModalOpen(true)
  }

  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setActionInProgress(true)
      if (editingRole) {
        // Update metadata and rank
        await consoleRolesApi.update(
          editingRole.role_id,
          {
            name: roleFormData.name,
            description: roleFormData.description,
            rank: roleFormData.rank,
          },
          editingRole.version
        )
        setFeedback({ type: 'success', message: `Role "${roleFormData.name}" updated successfully.` })
      } else {
        // Create custom role
        const payload: CreateRolePayload = {
          code: roleFormData.code.toLowerCase().trim(),
          name: roleFormData.name.trim(),
          description: roleFormData.description.trim(),
          rank: Number(roleFormData.rank),
          permission_codes: roleFormData.permissions,
        }
        await consoleRolesApi.create(payload)
        setFeedback({ type: 'success', message: `Role "${roleFormData.name}" created successfully.` })
      }
      setRoleModalOpen(false)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to save role.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleDeleteRole = async () => {
    if (!confirmDeleteRole) return
    try {
      setActionInProgress(true)
      await consoleRolesApi.delete(confirmDeleteRole.role_id)
      setFeedback({ type: 'success', message: `Role "${confirmDeleteRole.name}" deleted.` })
      setConfirmDeleteRole(null)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to delete role.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleOpenPermsModal = (role: ConsoleRoleItem) => {
    setPermModalRole(role)
    setPermSelection(new Set(role.permissions))
  }

  const handleTogglePerm = (code: string) => {
    // "Cannot grant what you lack": unless super_admin, caller cannot toggle permissions they don't hold
    if (!isSuperAdmin && !permissions.has(code) && !permissions.has('all')) {
      setFeedback({
        type: 'error',
        message: `Hierarchy Rule: You cannot grant permission "${code}" because your operator account does not hold it.`,
      })
      return
    }

    setPermSelection(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  const handleSavePerms = async () => {
    if (!permModalRole) return
    try {
      setActionInProgress(true)
      const selectedList = Array.from(permSelection)
      await consoleRolesApi.setPermissions(
        permModalRole.role_id,
        selectedList,
        permModalRole.version,
        `Updated permissions for role ${permModalRole.code}`
      )
      setFeedback({
        type: 'success',
        message: `Updated permissions for "${permModalRole.name}". Active sessions of assigned operators were revoked to enforce immediate update.`,
      })
      setPermModalRole(null)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to save role permissions.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  // ──────────────────────────────────────────────────────────────────────────
  // HANDLERS: OPERATORS (ADMINS)
  // ──────────────────────────────────────────────────────────────────────────

  const handleOpenCreateAdmin = () => {
    setAdminModalError(null)
    setAdminCreateModalOpen(true)
  }

  const handleCloseCreateAdmin = () => {
    setAdminModalError(null)
    setAdminCreateModalOpen(false)
  }

  const handleCreateAdmin = async (e: React.FormEvent) => {
    e.preventDefault()
    setAdminModalError(null)
    try {
      setActionInProgress(true)
      const cidrs = adminFormData.allowed_ip_cidrs
        .split('\n')
        .map(s => s.trim())
        .filter(Boolean)

      const payload: CreateAdminPayload = {
        email: adminFormData.email.trim(),
        full_name: adminFormData.full_name.trim(),
        password: adminFormData.password,
        role_ids: adminFormData.role_ids,
        allowed_ip_cidrs: cidrs.length > 0 ? cidrs : undefined,
        status: adminFormData.status,
      }

      await consoleAdminsApi.create(payload)
      toast.success(`Operator ${adminFormData.email} created successfully.`)
      setFeedback({ type: 'success', message: `Operator ${adminFormData.email} created successfully.` })
      setAdminCreateModalOpen(false)
      setAdminModalError(null)
      setAdminFormData({
        email: '',
        full_name: '',
        password: '',
        role_ids: [],
        allowed_ip_cidrs: '',
        status: 'active',
      })
      await loadData()
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, 'Failed to create platform operator.')
      setAdminModalError(msg)
      toast.error(msg)
      setFeedback({
        type: 'error',
        message: msg,
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleOpenAssignRoles = (targetAdmin: ConsoleAdminItem) => {
    setAssignRoleModalError(null)
    setAssignRoleAdmin(targetAdmin)
    setAssignedRoleIds(targetAdmin.roles.map(r => r.role_id))
  }

  const handleCloseAssignRoles = () => {
    setAssignRoleModalError(null)
    setAssignRoleAdmin(null)
  }

  const handleSaveAssignRoles = async () => {
    if (!assignRoleAdmin) return
    setAssignRoleModalError(null)
    try {
      setActionInProgress(true)
      const payload: AssignAdminRolesPayload = {
        roles: assignedRoleIds.map(id => ({ role_id: id })),
        version: assignRoleAdmin.version,
        reason: 'Role assignment updated via console',
      }
      await consoleAdminsApi.assignRoles(assignRoleAdmin.admin_id, payload, assignRoleAdmin.version)
      toast.success(`Roles updated for ${assignRoleAdmin.email}. Sessions were refreshed.`)
      setFeedback({
        type: 'success',
        message: `Roles updated for ${assignRoleAdmin.email}. Sessions were refreshed.`,
      })
      setAssignRoleAdmin(null)
      setAssignRoleModalError(null)
      await loadData()
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, 'Failed to assign operator roles.')
      setAssignRoleModalError(msg)
      toast.error(msg)
      setFeedback({
        type: 'error',
        message: msg,
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleOpenEditStatus = (targetAdmin: ConsoleAdminItem) => {
    setEditAdminStatusTarget(targetAdmin)
    setNewAdminStatus(targetAdmin.status)
    setAdminAllowedIps(targetAdmin.allowed_ip_cidrs ? targetAdmin.allowed_ip_cidrs.join('\n') : '')
  }

  const handleSaveAdminStatus = async () => {
    if (!editAdminStatusTarget) return
    try {
      setActionInProgress(true)
      const cidrs = adminAllowedIps
        .split('\n')
        .map(s => s.trim())
        .filter(Boolean)

      await consoleAdminsApi.update(
        editAdminStatusTarget.admin_id,
        {
          status: newAdminStatus as 'active' | 'suspended' | 'disabled',
          allowed_ip_cidrs: cidrs,
          unlock: newAdminStatus === 'active',
          version: editAdminStatusTarget.version,
        },
        editAdminStatusTarget.version
      )
      setFeedback({
        type: 'success',
        message: `Operator ${editAdminStatusTarget.email} updated to ${newAdminStatus}.`,
      })
      setEditAdminStatusTarget(null)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to update operator status.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleResetPasskeys = async () => {
    if (!confirmResetPasskeys) return
    try {
      setActionInProgress(true)
      await consoleAdminsApi.resetPasskeys(confirmResetPasskeys.admin_id)
      setFeedback({
        type: 'success',
        message: `Passkeys cleared for ${confirmResetPasskeys.email}. The operator must register a new passkey on next login.`,
      })
      setConfirmResetPasskeys(null)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to reset passkeys.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleRevokeSessions = async () => {
    if (!confirmRevokeSessions) return
    try {
      setActionInProgress(true)
      const res = await consoleAdminsApi.revokeSessions(confirmRevokeSessions.admin_id)
      setFeedback({
        type: 'success',
        message: `Revoked ${res.revoked_count} active session(s) for ${confirmRevokeSessions.email}.`,
      })
      setConfirmRevokeSessions(null)
      await loadData()
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: getApiErrorMessage(err, 'Failed to revoke operator sessions.'),
      })
    } finally {
      setActionInProgress(false)
    }
  }

  const handleDeleteAdmin = async () => {
    if (!confirmDeleteAdmin) return
    try {
      setActionInProgress(true)
      const res = await consoleAdminsApi.delete(confirmDeleteAdmin.admin_id)
      const msg = res.message || `Operator ${confirmDeleteAdmin.email} deleted successfully.`
      toast.success(msg)
      setFeedback({
        type: 'success',
        message: msg,
      })
      setConfirmDeleteAdmin(null)
      await loadData()
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, 'Failed to delete operator.')
      toast.error(msg)
      setFeedback({
        type: 'error',
        message: msg,
      })
    } finally {
      setActionInProgress(false)
    }
  }

  // Rank badge styling helper
  const getRankBadge = (rank: number) => {
    if (rank >= 1000) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
          <Sparkles className="w-3 h-3 text-amber-400" /> Rank 1000 · Super
        </span>
      )
    }
    if (rank >= 800) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30">
          Rank {rank} · Admin
        </span>
      )
    }
    if (rank >= 500) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
          Rank {rank} · Ops
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
        Rank {rank} · Support
      </span>
    )
  }

  // Status badge styling helper
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Active
          </span>
        )
      case 'suspended':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> Suspended
          </span>
        )
      case 'disabled':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> Disabled
          </span>
        )
      case 'invited':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200">
            <Clock className="w-3 h-3 text-sky-600" /> Invited
          </span>
        )
      default:
        return <span className="text-slate-500 capitalize">{status}</span>
    }
  }

  return (
    <div className="space-y-6 pb-12">
      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              {activeTab === 'admins' ? (
                <>
                  <Users className="w-6 h-6 text-[#00d09c]" />
                  Platform Operators Directory
                </>
              ) : activeTab === 'permissions' ? (
                <>
                  <KeyRound className="w-6 h-6 text-[#00d09c]" />
                  System Permission Catalogue
                </>
              ) : (
                <>
                  <ShieldCheck className="w-6 h-6 text-[#00d09c]" />
                  Roles &amp; Access Control
                </>
              )}
            </h1>
            <span className="px-2 py-0.5 text-[11px] font-semibold bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] rounded-full">
              {activeTab === 'admins' ? 'Staff' : 'Phase 3'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {activeTab === 'admins'
              ? 'Manage platform administrator accounts, assigned roles, hardware passkeys, and active sessions.'
              : activeTab === 'permissions'
              ? 'Inspect system-defined granular permissions catalogue and step-up authentication boundaries.'
              : 'Dynamic RBAC catalogue, rank hierarchy authority, self-modification guards, and operator access.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => void loadData()}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-xl bg-white border border-[#dfeee8] text-slate-700 hover:text-slate-900 hover:bg-slate-50 transition-all shadow-sm"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', refreshing && 'animate-spin text-[#00d09c]')} />
            Refresh
          </button>

          {activeTab === 'admins' ? (
            <Can permission="admins.create">
              <button
                onClick={handleOpenCreateAdmin}
                className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white shadow-sm transition-all"
              >
                <Plus className="w-4 h-4" />
                Invite Operator
              </button>
            </Can>
          ) : (
            <Can permission="roles.manage">
              <button
                onClick={handleOpenCreateRole}
                className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white shadow-sm transition-all"
              >
                <Plus className="w-4 h-4" />
                Create Role
              </button>
            </Can>
          )}
        </div>
      </div>

      {/* ── Alert Feedback Toast ── */}
      {feedback && (
        <div
          className={cn(
            'flex items-center justify-between p-3.5 rounded-xl border text-xs font-medium animate-in fade-in slide-in-from-top-2 duration-200',
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          )}
        >
          <div className="flex items-center gap-2.5">
            {feedback.type === 'success' ? (
              <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-slate-600">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── KPI Authority Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Your Session Authority</span>
            <Shield className="w-4 h-4 text-indigo-500" />
          </div>
          <div className="text-lg font-bold text-slate-900 flex items-center gap-2">
            {isSuperAdmin ? 'Super Admin' : `Rank ${myRank}`}
          </div>
          <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            {isSuperAdmin ? 'Full platform access (Rank 1000)' : `Can manage rank < ${myRank}`}
          </div>
        </div>

        <button
          onClick={() => handleSelectTab('roles')}
          className="text-left p-4 rounded-2xl bg-white border border-[#dfeee8] hover:border-[#00d09c] hover:shadow-md transition-all cursor-pointer shadow-[0_10px_24px_rgba(15,23,42,0.03)]"
        >
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Operator Roles</span>
            <Sliders className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-lg font-bold text-slate-900">{roles.length} Roles</div>
          <div className="text-[11px] text-slate-500 mt-1">
            {roles.filter(r => r.is_system).length} system · {roles.filter(r => !r.is_system).length} custom
          </div>
        </button>

        <button
          onClick={() => handleSelectTab('admins')}
          className="text-left p-4 rounded-2xl bg-white border border-[#dfeee8] hover:border-[#00d09c] hover:shadow-md transition-all cursor-pointer shadow-[0_10px_24px_rgba(15,23,42,0.03)]"
        >
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Platform Operators</span>
            <Users className="w-4 h-4 text-[#00d09c]" />
          </div>
          <div className="text-lg font-bold text-slate-900">{admins.length} Operators</div>
          <div className="text-[11px] text-slate-500 mt-1">
            {admins.filter(a => a.status === 'active').length} active · {admins.filter(a => a.status !== 'active').length} inactive
          </div>
        </button>

        <button
          onClick={() => handleSelectTab('permissions')}
          className="text-left p-4 rounded-2xl bg-white border border-[#dfeee8] hover:border-[#00d09c] hover:shadow-md transition-all cursor-pointer shadow-[0_10px_24px_rgba(15,23,42,0.03)]"
        >
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium">Permission Catalogue</span>
            <KeyRound className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-lg font-bold text-slate-900">{allPermissions.length} Granular Actions</div>
          <div className="text-[11px] text-slate-500 mt-1">
            {allPermissions.filter(p => p.is_sensitive).length} step-up sensitive actions
          </div>
        </button>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="flex items-center border-b border-[#dfeee8] gap-6">
        <button
          onClick={() => handleSelectTab('roles')}
          className={cn(
            'pb-3 text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer',
            activeTab === 'roles'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Sliders className="w-3.5 h-3.5" />
          Operator Roles ({roles.length})
        </button>

        <button
          onClick={() => handleSelectTab('admins')}
          className={cn(
            'pb-3 text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer',
            activeTab === 'admins'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Users className="w-3.5 h-3.5" />
          Platform Operators Directory ({admins.length})
        </button>

        <button
          onClick={() => handleSelectTab('permissions')}
          className={cn(
            'pb-3 text-xs flex items-center gap-2 border-b-2 transition-all cursor-pointer',
            activeTab === 'permissions'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <KeyRound className="w-3.5 h-3.5" />
          System Permission Catalogue ({allPermissions.length})
        </button>
      </div>

      {/* ── TAB 1: OPERATOR ROLES ── */}
      {activeTab === 'roles' && (
        <div className="space-y-4">
          {/* Search bar */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search roles by name or slug..."
                value={roleSearch}
                onChange={e => setRoleSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 transition-colors shadow-sm"
              />
            </div>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-500 text-xs">
              <Loader2 className="w-6 h-6 animate-spin text-[#00d09c] mx-auto mb-2" />
              Loading operator roles...
            </div>
          ) : filteredRoles.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs bg-[#f9fffc] rounded-2xl border border-[#e3f4ee]">
              No operator roles found matching your query.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredRoles.map(role => {
                const canManageRole = myRank > role.rank
                const isSystem = role.is_system

                return (
                  <div
                    key={role.role_id}
                    className="p-4 rounded-2xl bg-white border border-[#dfeee8] hover:border-[#b8f5dc] transition-all shadow-[0_10px_24px_rgba(15,23,42,0.03)] flex flex-col justify-between"
                  >
                    <div>
                      {/* Card Header */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div>
                          <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                            {role.name}
                            {isSystem && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono border border-slate-200">
                                System
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] font-mono text-slate-500 mt-0.5">{role.code}</div>
                        </div>
                        {getRankBadge(role.rank)}
                      </div>

                      {/* Description */}
                      <p className="text-xs text-slate-600 line-clamp-2 mb-3">
                        {role.description || 'No description provided.'}
                      </p>

                      {/* Stats */}
                      <div className="flex items-center gap-4 text-xs text-slate-500 py-2 border-y border-[#eef7f3] mb-3">
                        <div>
                          <span className="font-semibold text-slate-900">{role.member_count}</span> assigned operator(s)
                        </div>
                        <div>
                          <span className="font-semibold text-slate-900">{role.permissions.length}</span> actions
                        </div>
                      </div>

                      {/* Permissions preview pills */}
                      <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto mb-4">
                        {role.permissions.slice(0, 6).map(p => (
                          <span
                            key={p}
                            className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-mono"
                          >
                            {p}
                          </span>
                        ))}
                        {role.permissions.length > 6 && (
                          <span className="text-[10px] px-2 py-0.5 rounded-md bg-slate-50 text-slate-500 font-mono border border-slate-200">
                            +{role.permissions.length - 6} more
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Card Actions */}
                    <div className="flex items-center justify-between pt-2 border-t border-[#eef7f3] gap-2">
                      <button
                        onClick={() => handleOpenPermsModal(role)}
                        disabled={!canManageRole}
                        title={
                          !canManageRole
                            ? `Cannot edit role with rank (${role.rank}) >= your rank (${myRank})`
                            : 'Configure permissions'
                        }
                        className={cn(
                          'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors shadow-sm',
                          canManageRole
                            ? 'bg-white border border-[#dfeee8] text-slate-700 hover:text-slate-900 hover:bg-slate-50'
                            : 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                        )}
                      >
                        <Sliders className="w-3 h-3 text-[#00d09c]" />
                        Permissions
                      </button>

                      <div className="flex items-center gap-1.5">
                        {!isSystem && (
                          <button
                            onClick={() => handleOpenEditRole(role)}
                            disabled={!canManageRole}
                            title={
                              !canManageRole
                                ? `Cannot edit role with rank >= your rank`
                                : 'Edit role details'
                            }
                            className={cn(
                              'p-1.5 rounded-lg text-xs transition-colors',
                              canManageRole
                                ? 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
                                : 'text-slate-300 cursor-not-allowed'
                            )}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {!isSystem && role.member_count === 0 && (
                          <button
                            onClick={() => setConfirmDeleteRole(role)}
                            disabled={!canManageRole}
                            title={
                              !canManageRole
                                ? `Cannot delete role with rank >= your rank`
                                : 'Delete unused role'
                            }
                            className={cn(
                              'p-1.5 rounded-lg text-xs transition-colors',
                              canManageRole
                                ? 'text-rose-600 hover:text-rose-700 hover:bg-rose-50'
                                : 'text-slate-300 cursor-not-allowed'
                            )}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: OPERATOR DIRECTORY ── */}
      {activeTab === 'admins' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search operators by name or email..."
                value={adminSearch}
                onChange={e => setAdminSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 transition-colors shadow-sm"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={adminStatusFilter}
                onChange={e => setAdminStatusFilter(e.target.value)}
                className="px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-800 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
                <option value="disabled">Disabled</option>
                <option value="invited">Invited</option>
              </select>

              <Can permission="admins.create">
                <button
                  onClick={handleOpenCreateAdmin}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white shadow-sm transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Invite Operator
                </button>
              </Can>
            </div>
          </div>

          {/* Directory Table */}
          <div className="rounded-2xl border border-[#dfeee8] bg-white overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#f9fffc] border-b border-[#e3f4ee] text-slate-600 font-semibold tracking-wider uppercase text-[10px]">
                  <tr>
                    <th className="py-3.5 px-4">Operator</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4">Assigned Roles</th>
                    <th className="py-3.5 px-4">Max Rank</th>
                    <th className="py-3.5 px-4">Security (2FA &amp; Sessions)</th>
                    <th className="py-3.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef7f3]">
                  {loading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-500">
                        <Loader2 className="w-6 h-6 animate-spin text-[#00d09c] mx-auto mb-2" />
                        Loading operator directory...
                      </td>
                    </tr>
                  ) : filteredAdmins.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-500">
                        <p className="mb-3">No platform operators found matching filters.</p>
                        <Can permission="admins.create">
                          <button
                            onClick={handleOpenCreateAdmin}
                            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white shadow-sm transition-all"
                          >
                            <Plus className="w-3.5 h-3.5" />
                            Invite Operator
                          </button>
                        </Can>
                      </td>
                    </tr>
                  ) : (
                    filteredAdmins.map(adm => {
                      const isSelf = operator?.admin_id === adm.admin_id
                      const canManageTarget = myRank >= 1000 ? !isSelf : (myRank > adm.max_rank && !isSelf)

                      return (
                        <tr key={adm.admin_id} className="hover:bg-slate-50/70 transition-colors">
                          {/* Operator name & email */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full bg-[#00d09c] flex items-center justify-center font-bold text-white text-xs shrink-0 shadow-sm">
                                {adm.full_name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                                  {adm.full_name}
                                  {isSelf && (
                                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-50 text-[#00a26d] border border-[#b8f5dc] font-normal">
                                      You
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-500 font-mono">{adm.email}</div>
                              </div>
                            </div>
                          </td>

                          {/* Status */}
                          <td className="py-3.5 px-4">{getStatusBadge(adm.status)}</td>

                          {/* Roles */}
                          <td className="py-3.5 px-4">
                            <div className="flex flex-wrap gap-1">
                              {adm.roles.map(r => (
                                <span
                                  key={r.role_id}
                                  className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700 font-mono"
                                >
                                  {r.name}
                                </span>
                              ))}
                              {adm.roles.length === 0 && (
                                <span className="text-[11px] text-slate-400 italic">No roles assigned</span>
                              )}
                            </div>
                          </td>

                          {/* Rank */}
                          <td className="py-3.5 px-4">{getRankBadge(adm.max_rank)}</td>

                          {/* Security state */}
                          <td className="py-3.5 px-4">
                            <div className="space-y-0.5 text-[11px] text-slate-500">
                              <div className="flex items-center gap-1.5">
                                <Fingerprint className="w-3.5 h-3.5 text-[#00d09c]" />
                                <span>{adm.passkeys_count} registered passkey(s)</span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Clock className="w-3.5 h-3.5 text-slate-400" />
                                <span>{adm.active_sessions_count} active session(s)</span>
                              </div>
                            </div>
                          </td>

                          {/* Actions */}
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                onClick={() => handleOpenAssignRoles(adm)}
                                disabled={!canManageTarget}
                                title={
                                  isSelf
                                    ? 'Self-Modification Guard: Cannot edit own roles'
                                    : !canManageTarget
                                    ? `Cannot modify operator of rank (${adm.max_rank}) >= your rank (${myRank})`
                                    : 'Assign Roles'
                                }
                                className={cn(
                                  'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors shadow-sm',
                                  canManageTarget
                                    ? 'bg-white border border-[#dfeee8] text-slate-700 hover:text-slate-900 hover:bg-slate-50'
                                    : 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
                                )}
                              >
                                Roles
                              </button>

                              <button
                                onClick={() => handleOpenEditStatus(adm)}
                                disabled={!canManageTarget}
                                title={
                                  isSelf
                                    ? 'Self-Modification Guard: Cannot edit own status'
                                    : !canManageTarget
                                    ? 'Cannot edit operator of equal/higher rank'
                                    : 'Edit status / IP allowlist'
                                }
                                className={cn(
                                  'p-1.5 rounded-lg text-xs transition-colors',
                                  canManageTarget
                                    ? 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
                                    : 'text-slate-300 cursor-not-allowed'
                                )}
                              >
                                <Sliders className="w-3.5 h-3.5" />
                              </button>

                              {adm.passkeys_count > 0 && (
                                <button
                                  onClick={() => setConfirmResetPasskeys(adm)}
                                  disabled={!canManageTarget}
                                  title={
                                    isSelf
                                      ? 'Self-Modification Guard: Cannot reset own passkeys here'
                                      : !canManageTarget
                                      ? 'Cannot reset passkeys of equal/higher rank operator'
                                      : 'Reset WebAuthn Passkeys'
                                  }
                                  className={cn(
                                    'p-1.5 rounded-lg text-xs transition-colors',
                                    canManageTarget
                                      ? 'text-amber-600 hover:text-amber-700 hover:bg-amber-50'
                                      : 'text-slate-300 cursor-not-allowed'
                                  )}
                                >
                                  <KeyRound className="w-3.5 h-3.5" />
                                </button>
                              )}

                              {adm.active_sessions_count > 0 && (
                                <button
                                  onClick={() => setConfirmRevokeSessions(adm)}
                                  disabled={!canManageTarget && !isSelf}
                                  title="Revoke active sessions"
                                  className={cn(
                                    'p-1.5 rounded-lg text-xs transition-colors',
                                    canManageTarget || isSelf
                                      ? 'text-rose-600 hover:text-rose-700 hover:bg-rose-50'
                                      : 'text-slate-300 cursor-not-allowed'
                                  )}
                                >
                                  <LogOut className="w-3.5 h-3.5" />
                                </button>
                              )}

                              <button
                                onClick={() => setConfirmDeleteAdmin(adm)}
                                disabled={!canManageTarget}
                                title={
                                  isSelf
                                    ? 'Self-Modification Guard: Cannot delete your own administrative account'
                                    : !canManageTarget
                                    ? `Cannot delete operator of rank (${adm.max_rank}) >= your rank (${myRank})`
                                    : `Delete operator ${adm.email}`
                                }
                                className={cn(
                                  'p-1.5 rounded-lg text-xs transition-colors',
                                  canManageTarget
                                    ? 'text-rose-600 hover:text-rose-700 hover:bg-rose-50'
                                    : 'text-slate-300 cursor-not-allowed'
                                )}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 3: PERMISSION CATALOGUE ── */}
      {activeTab === 'permissions' && (
        <div className="space-y-6">
          <div className="p-4 rounded-2xl bg-[#ebfff7] border border-[#b8f5dc] text-xs text-emerald-800 flex items-start gap-3 shadow-sm">
            <KeyRound className="w-4 h-4 text-[#00a26d] mt-0.5 shrink-0" />
            <div>
              <span className="font-semibold text-emerald-950">Immutable Permission Catalogue:</span> Platform permissions are
              canonically verified at startup. Operators assign permissions via roles and cannot invent arbitrary permissions.
              Sensitive actions require Step-Up MFA authentication within 5 minutes.
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(permissionsByResource).map(([resource, perms]) => (
              <div
                key={resource}
                className="p-4 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)] flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between pb-3 border-b border-[#eef7f3] mb-3">
                    <span className="font-bold text-slate-900 text-sm capitalize">{resource} Resource</span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                      {perms.length} actions
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {perms.map(p => (
                      <div key={p.code} className="p-2 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="text-xs font-mono font-semibold text-slate-900">{p.code}</span>
                          {p.is_sensitive && (
                            <span className="text-[9px] px-1.5 py-0.2 rounded-full font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              Step-Up
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-600">{p.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────────────
          MODALS
      ────────────────────────────────────────────────────────────────────────── */}

      {/* ── 1. Create / Edit Role Modal ── */}
      {roleModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center justify-between pb-4 border-b border-[#eef7f3] mb-4">
              <h2 className="text-sm font-bold text-slate-900">
                {editingRole ? `Edit Role: ${editingRole.name}` : 'Create Custom Operator Role'}
              </h2>
              <button onClick={() => setRoleModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveRole} className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Role Code / Slug {editingRole && '(Read-Only)'}
                </label>
                <input
                  type="text"
                  required
                  disabled={!!editingRole}
                  value={roleFormData.code}
                  onChange={e => setRoleFormData({ ...roleFormData, code: e.target.value })}
                  placeholder="e.g. tier2_support"
                  pattern="^[a-z0-9_]+$"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 font-mono disabled:opacity-50 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Role Name</label>
                <input
                  type="text"
                  required
                  value={roleFormData.name}
                  onChange={e => setRoleFormData({ ...roleFormData, name: e.target.value })}
                  placeholder="e.g. Tier 2 Support"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  value={roleFormData.description}
                  onChange={e => setRoleFormData({ ...roleFormData, description: e.target.value })}
                  placeholder="Responsibilities and purpose of this role..."
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Role Rank (Hierarchy Level: 1 to {myRank - 1})
                </label>
                <input
                  type="number"
                  required
                  min={1}
                  max={Math.max(1, myRank - 1)}
                  value={roleFormData.rank}
                  onChange={e => setRoleFormData({ ...roleFormData, rank: parseInt(e.target.value) || 1 })}
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
                <p className="text-[10px] text-slate-500 mt-1">
                  Hierarchy Rule: You cannot create or assign a role with rank equal to or greater than your rank ({myRank}).
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#eef7f3]">
                <button
                  type="button"
                  onClick={() => setRoleModalOpen(false)}
                  className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionInProgress}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#00d09c] text-white hover:bg-[#00b98a] shadow-sm flex items-center gap-1.5 transition-all"
                >
                  {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Role
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 2. Configure Role Permissions Modal ── */}
      {permModalRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-2xl max-h-[90vh] rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700 flex flex-col">
            <div className="flex items-center justify-between pb-4 border-b border-[#eef7f3] shrink-0">
              <div>
                <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  Configure Permissions: {permModalRole.name}
                  {getRankBadge(permModalRole.rank)}
                </h2>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Modifying permissions will immediately increment the permission version and invalidate active sessions
                  for all operators assigned to this role.
                </p>
              </div>
              <button onClick={() => setPermModalRole(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 space-y-4">
              {Object.entries(permissionsByResource).map(([resource, perms]) => (
                <div key={resource} className="p-3.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-slate-900 capitalize text-xs">{resource} Resource</span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {perms.filter(p => permSelection.has(p.code)).length} / {perms.length} granted
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {perms.map(p => {
                      const isChecked = permSelection.has(p.code)
                      const callerHasPerm = isSuperAdmin || permissions.has(p.code) || permissions.has('all')

                      return (
                        <label
                          key={p.code}
                          className={cn(
                            'flex items-start gap-2.5 p-2 rounded-lg border transition-all cursor-pointer select-none',
                            isChecked
                              ? 'bg-[#ebfff7] border-[#b8f5dc] text-slate-900'
                              : 'bg-white border-[#dfeee8] text-slate-600 hover:border-slate-300',
                            !callerHasPerm && 'opacity-40 cursor-not-allowed'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            disabled={!callerHasPerm}
                            onChange={() => handleTogglePerm(p.code)}
                            className="mt-0.5 rounded border-slate-300 text-[#00d09c] focus:ring-0 focus:ring-offset-0 bg-white"
                          />
                          <div className="text-[11px]">
                            <div className="font-mono font-medium flex items-center gap-1 text-slate-900">
                              {p.code}
                              {p.is_sensitive && (
                                <span className="text-[8px] px-1 py-0.1 rounded font-bold bg-amber-50 text-amber-700 border border-amber-200">
                                  Step-Up
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-500 leading-tight mt-0.5">{p.description}</div>
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[#eef7f3] shrink-0">
              <span className="text-[11px] text-slate-500">
                Total actions selected: <strong className="text-slate-900">{permSelection.size}</strong>
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPermModalRole(null)}
                  className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleSavePerms()}
                  disabled={actionInProgress}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#00d09c] text-white hover:bg-[#00b98a] shadow-sm flex items-center gap-1.5 transition-all"
                >
                  {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save Permissions &amp; Revoke Sessions
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 3. Assign Operator Roles Modal ── */}
      {assignRoleAdmin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center justify-between pb-4 border-b border-[#eef7f3] mb-4">
              <h2 className="text-sm font-bold text-slate-900">Assign Roles: {assignRoleAdmin.full_name}</h2>
              <button onClick={handleCloseAssignRoles} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            {assignRoleModalError && (
              <div className="mb-3.5 p-3 rounded-xl bg-[#fff1f2] border border-[#fecaca] text-[#d92d20] text-xs flex items-center gap-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 shrink-0 text-[#d92d20]" />
                <span className="flex-1 font-medium">{assignRoleModalError}</span>
              </div>
            )}

            <p className="text-[11px] text-slate-500 mb-3">
              Select roles to grant to <strong>{assignRoleAdmin.email}</strong>.{' '}
              {myRank >= 1000
                ? 'As a Super Administrator, you can assign all platform roles.'
                : `Roles with rank equal to or greater than your rank (${myRank}) cannot be assigned.`}
            </p>

            <div className="space-y-2 max-h-64 overflow-y-auto mb-4">
              {roles.map(r => {
                const isSelected = assignedRoleIds.includes(r.role_id)
                const canAssign = myRank >= 1000 ? r.rank <= myRank : myRank > r.rank

                return (
                  <label
                    key={r.role_id}
                    className={cn(
                      'flex items-center justify-between p-2.5 rounded-xl border transition-all select-none',
                      isSelected
                        ? 'bg-[#ebfff7] border-[#b8f5dc] text-slate-900'
                        : 'bg-white border-[#dfeee8] text-slate-600',
                      canAssign ? 'cursor-pointer hover:border-slate-300' : 'opacity-40 cursor-not-allowed'
                    )}
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!canAssign}
                        onChange={() => {
                          if (!canAssign) return
                          setAssignedRoleIds(prev =>
                            prev.includes(r.role_id) ? prev.filter(id => id !== r.role_id) : [...prev, r.role_id]
                          )
                        }}
                        className="rounded border-slate-300 text-[#00d09c] focus:ring-0 bg-white"
                      />
                      <div>
                        <div className="font-semibold text-slate-900">{r.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono">{r.code}</div>
                      </div>
                    </div>
                    {getRankBadge(r.rank)}
                  </label>
                )
              })}
            </div>

            <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#eef7f3]">
              <button
                type="button"
                onClick={handleCloseAssignRoles}
                className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleSaveAssignRoles()}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#00d09c] text-white hover:bg-[#00b98a] shadow-sm flex items-center gap-1.5 transition-all"
              >
                {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Role Assignments
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 4. Invite / Create Operator Modal ── */}
      {adminCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center justify-between pb-4 border-b border-[#eef7f3] mb-4">
              <h2 className="text-sm font-bold text-slate-900">Invite Platform Operator</h2>
              <button onClick={handleCloseCreateAdmin} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            {adminModalError && (
              <div className="mb-3.5 p-3 rounded-xl bg-[#fff1f2] border border-[#fecaca] text-[#d92d20] text-xs flex items-center gap-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 shrink-0 text-[#d92d20]" />
                <span className="flex-1 font-medium">{adminModalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateAdmin} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={adminFormData.email}
                  onChange={e => setAdminFormData({ ...adminFormData, email: e.target.value })}
                  placeholder="name@company.com"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 font-mono shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={adminFormData.full_name}
                  onChange={e => setAdminFormData({ ...adminFormData, full_name: e.target.value })}
                  placeholder="e.g. Maya Sharma"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Initial Password (14 characters minimum)</label>
                <input
                  type="password"
                  required
                  minLength={14}
                  value={adminFormData.password}
                  onChange={e => setAdminFormData({ ...adminFormData, password: e.target.value })}
                  placeholder="Enter a secure initial password"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Assign Roles {myRank >= 1000 ? '(Rank <= 1000 — Full permissions available)' : `(Rank must be < ${myRank})`}
                </label>
                <div className="space-y-1.5 max-h-48 overflow-y-auto p-2 bg-[#f9fffc] rounded-xl border border-[#e3f4ee]">
                  {roles
                    .filter(r => (myRank >= 1000 ? r.rank <= myRank : myRank > r.rank))
                    .map(r => (
                      <label key={r.role_id} className="flex items-center gap-2 text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={adminFormData.role_ids.includes(r.role_id)}
                          onChange={() => {
                            setAdminFormData(prev => ({
                              ...prev,
                              role_ids: prev.role_ids.includes(r.role_id)
                                ? prev.role_ids.filter(id => id !== r.role_id)
                                : [...prev.role_ids, r.role_id],
                            }))
                          }}
                          className="rounded border-slate-300 text-[#00d09c] focus:ring-0 bg-white"
                        />
                        <span>
                          {r.name} <span className="text-[10px] text-slate-500 font-mono">(Rank {r.rank})</span>
                        </span>
                      </label>
                    ))}
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Allowed IP CIDR(s) (One per line, optional)
                </label>
                <textarea
                  rows={2}
                  value={adminFormData.allowed_ip_cidrs}
                  onChange={e => setAdminFormData({ ...adminFormData, allowed_ip_cidrs: e.target.value })}
                  placeholder="e.g. 203.0.113.5/32"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 font-mono shadow-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#eef7f3]">
                <button
                  type="button"
                  onClick={handleCloseCreateAdmin}
                  className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionInProgress}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#00d09c] text-white hover:bg-[#00b98a] shadow-sm flex items-center gap-1.5 transition-all"
                >
                  {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Send Operator Invite
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 5. Edit Operator Status / IPs Modal ── */}
      {editAdminStatusTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center justify-between pb-4 border-b border-[#eef7f3] mb-4">
              <h2 className="text-sm font-bold text-slate-900">Edit Operator: {editAdminStatusTarget.full_name}</h2>
              <button onClick={() => setEditAdminStatusTarget(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">Administrative Status</label>
                <select
                  value={newAdminStatus}
                  onChange={e => setNewAdminStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  <option value="active">Active (Access Allowed)</option>
                  <option value="suspended">Suspended (Temporary Freeze)</option>
                  <option value="disabled">Disabled (Deactivated)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-700 mb-1">
                  Allowed IP CIDR(s) (One per line)
                </label>
                <textarea
                  rows={3}
                  value={adminAllowedIps}
                  onChange={e => setAdminAllowedIps(e.target.value)}
                  placeholder="e.g. 198.51.100.0/24"
                  className="w-full px-3 py-2 bg-white border border-[#dfeee8] rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 font-mono shadow-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#eef7f3]">
                <button
                  type="button"
                  onClick={() => setEditAdminStatusTarget(null)}
                  className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleSaveAdminStatus()}
                  disabled={actionInProgress}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#00d09c] text-white hover:bg-[#00b98a] shadow-sm flex items-center gap-1.5 transition-all"
                >
                  {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Update Operator Status
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 6. Confirm Delete Role Dialog ── */}
      {confirmDeleteRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center gap-3 mb-3 text-rose-600">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-slate-900">Delete Role: {confirmDeleteRole.name}</h3>
            </div>
            <p className="text-slate-600 mb-4">
              Are you sure you want to delete role <strong>{confirmDeleteRole.code}</strong>? This action will be
              recorded in the immutable audit trail.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmDeleteRole(null)}
                className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteRole()}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 shadow-sm flex items-center gap-1.5 transition-all"
              >
                {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 7. Confirm Reset Passkeys Dialog ── */}
      {confirmResetPasskeys && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center gap-3 mb-3 text-amber-600">
              <KeyRound className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-slate-900">Reset Registered Passkeys</h3>
            </div>
            <p className="text-slate-600 mb-4">
              Clear all registered FIDO2 WebAuthn credentials for <strong>{confirmResetPasskeys.email}</strong>? The
              operator will be required to register a new passkey upon their next sign-in.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmResetPasskeys(null)}
                className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleResetPasskeys()}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 shadow-sm flex items-center gap-1.5 transition-all"
              >
                {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Reset Passkeys
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 8. Confirm Revoke Sessions Dialog ── */}
      {confirmRevokeSessions && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center gap-3 mb-3 text-rose-600">
              <LogOut className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-slate-900">Revoke Operator Sessions</h3>
            </div>
            <p className="text-slate-600 mb-4">
              Immediately terminate all active sessions for <strong>{confirmRevokeSessions.email}</strong>? The operator
              will be immediately signed out from all devices.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmRevokeSessions(null)}
                className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleRevokeSessions()}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 shadow-sm flex items-center gap-1.5 transition-all"
              >
                {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Revoke All Sessions
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 9. Confirm Delete Operator Dialog ── */}
      {confirmDeleteAdmin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="w-full max-w-sm rounded-2xl bg-white border border-[#dfeee8] shadow-2xl p-6 text-xs text-slate-700">
            <div className="flex items-center gap-3 mb-3 text-rose-600">
              <Trash2 className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold text-slate-900">Delete Operator Account</h3>
            </div>
            <p className="text-slate-600 mb-2">
              Are you sure you want to permanently delete platform operator{' '}
              <strong>{confirmDeleteAdmin.email}</strong> ({confirmDeleteAdmin.full_name})?
            </p>
            <p className="text-[11px] text-slate-500 mb-4 bg-slate-50 p-2.5 rounded-xl border border-slate-200 leading-relaxed">
              This will revoke all active sessions, delete registered passkeys, remove all assigned role bindings, and permanently remove the operator record. This action is audited and cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmDeleteAdmin(null)}
                disabled={actionInProgress}
                className="px-3 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteAdmin()}
                disabled={actionInProgress}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 shadow-sm flex items-center gap-1.5 transition-all"
              >
                {actionInProgress && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Delete Operator
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function RolesAndAccessPage() {
  return (
    <Suspense fallback={<div className="p-6 text-xs text-slate-500">Loading roles and operators...</div>}>
      <RolesAndAccessContent />
    </Suspense>
  )
}
