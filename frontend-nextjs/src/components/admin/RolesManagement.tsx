'use client'

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Shield,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Plus,
  Trash2,
  Edit3,
  Copy,
  Search,
  SlidersHorizontal,
  Landmark,
  Package,
  MapPin,
  BarChart3,
  Users,
  Check,
  X,
  Loader2,
  Sparkles,
  Layers,
  AlertCircle
} from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export interface RoleItem {
  role_id: number
  name: string
  description?: string
  user_count: number
  is_system: boolean
}

export interface PermissionItem {
  module_id: number
  code: string
  name: string
  description?: string
  can_create: boolean
  can_read: boolean
  can_update: boolean
  can_delete: boolean
}

interface RolesManagementProps {
  roles: RoleItem[]
  onRolesChange: (roles: RoleItem[]) => void
  token: string
}

const MODULE_GROUPS = [
  {
    id: 'accounting',
    title: 'Financial & Accounting Masters',
    description: 'Chart of accounts, customer & supplier ledgers, vouchers, payments & debt aging',
    icon: Landmark,
    color: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
    codes: ['ledgers', 'ledger_customer', 'ledger_supplier', 'vouchers', 'payments']
  },
  {
    id: 'inventory',
    title: 'Inventory & Stock Management',
    description: 'Stock items, stock groups, godowns, unit conversion & BOM manufacturing',
    icon: Package,
    color: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
    codes: ['inventory']
  },
  {
    id: 'field_ops',
    title: 'Field Sales & Operations',
    description: 'Shop GPS check-in logs, mobile sales orders, visit history & staff attendance',
    icon: MapPin,
    color: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    codes: ['visits', 'orders', 'attendance']
  },
  {
    id: 'reports_tax',
    title: 'Reports, Tax & Compliance',
    description: 'Financial reports, Trial Balance, P&L, GST return filing, E-Invoicing & expenses',
    icon: BarChart3,
    color: 'text-purple-500 bg-purple-500/10 border-purple-500/20',
    codes: ['reports', 'gst', 'expenses', 'payroll']
  },
  {
    id: 'admin',
    title: 'System Administration',
    description: 'User management, role and permission matrices, company configuration',
    icon: Shield,
    color: 'text-rose-500 bg-rose-500/10 border-rose-500/20',
    codes: ['users', 'roles', 'settings']
  }
]

export function RolesManagement({ roles, onRolesChange, token }: RolesManagementProps) {
  const [selectedRoleId, setSelectedRoleId] = useState<number | null>(null)
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [loadingPerms, setLoadingPerms] = useState(false)
  const [savingPerms, setSavingPerms] = useState(false)
  const [isDirty, setIsDirty] = useState(false)

  // Modal dialog states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDesc, setNewRoleDesc] = useState('')
  const [cloneFromId, setCloneFromId] = useState<string>('')
  const [createLoading, setCreateLoading] = useState(false)

  const [editRole, setEditRole] = useState<RoleItem | null>(null)
  const [editRoleName, setEditRoleName] = useState('')
  const [editRoleDesc, setEditRoleDesc] = useState('')
  const [editLoading, setEditLoading] = useState(false)

  const [deleteLoadingId, setDeleteLoadingId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Set default selected role
  useEffect(() => {
    if (roles.length > 0 && selectedRoleId === null) {
      setSelectedRoleId(roles[0].role_id)
    }
  }, [roles, selectedRoleId])

  const selectedRole = useMemo(() => {
    return roles.find((r) => r.role_id === selectedRoleId) || roles[0] || null
  }, [roles, selectedRoleId])

  const loadRolePermissions = useCallback(
    async (roleId: number) => {
      if (!token) return
      setLoadingPerms(true)
      setIsDirty(false)
      try {
        const res = await fetch(`${API_BASE}/admin/roles/${roleId}/permissions`, {
          headers: authHeaders(token)
        })
        if (res.ok) {
          const data = await res.json()
          setPermissions(Array.isArray(data) ? data : [])
        } else {
          toast.error('Failed to load permissions for this role')
        }
      } catch (e: any) {
        toast.error(e.message || 'Error loading permissions')
      } finally {
        setLoadingPerms(false)
      }
    },
    [token]
  )

  useEffect(() => {
    if (selectedRole?.role_id) {
      loadRolePermissions(selectedRole.role_id)
    }
  }, [selectedRole?.role_id, loadRolePermissions])

  // Permission modification helpers
  const handleToggleAction = (
    moduleId: number,
    action: 'can_read' | 'can_create' | 'can_update' | 'can_delete',
    val: boolean
  ) => {
    if (selectedRole?.name.toLowerCase() === 'admin') return
    setIsDirty(true)
    setPermissions((prev) =>
      prev.map((p) => {
        if (p.module_id !== moduleId) return p
        const updated = { ...p, [action]: val }
        // If enabling create/update/delete, automatically enable read
        if (val && action !== 'can_read') {
          updated.can_read = true
        }
        // If disabling read, disable all actions
        if (!val && action === 'can_read') {
          updated.can_create = false
          updated.can_update = false
          updated.can_delete = false
        }
        return updated
      })
    )
  }

  const handleToggleModuleAll = (moduleId: number, enable: boolean) => {
    if (selectedRole?.name.toLowerCase() === 'admin') return
    setIsDirty(true)
    setPermissions((prev) =>
      prev.map((p) => {
        if (p.module_id !== moduleId) return p
        return {
          ...p,
          can_read: enable,
          can_create: enable,
          can_update: enable,
          can_delete: enable
        }
      })
    )
  }

  const handleApplyPreset = (preset: 'all' | 'read' | 'clear') => {
    if (selectedRole?.name.toLowerCase() === 'admin') return
    setIsDirty(true)
    setPermissions((prev) =>
      prev.map((p) => {
        if (preset === 'all') {
          return { ...p, can_read: true, can_create: true, can_update: true, can_delete: true }
        } else if (preset === 'read') {
          return { ...p, can_read: true, can_create: false, can_update: false, can_delete: false }
        } else {
          return { ...p, can_read: false, can_create: false, can_update: false, can_delete: false }
        }
      })
    )
  }

  // Save permissions
  const handleSavePermissions = async () => {
    if (!token || !selectedRole) return
    if (selectedRole.name.toLowerCase() === 'admin') {
      toast.info('Administrator has permanent, unconditional full access to all features.')
      return
    }
    setSavingPerms(true)
    try {
      const res = await fetch(`${API_BASE}/admin/roles/${selectedRole.role_id}/permissions`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(permissions)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save permissions')
      }
      toast.success(`Permissions for '${selectedRole.name}' saved successfully!`)
      setIsDirty(false)
    } catch (err: any) {
      toast.error(err.message || 'Error saving permissions')
    } finally {
      setSavingPerms(false)
    }
  }

  // Create Role
  const handleCreateRoleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !newRoleName.trim()) return
    setCreateLoading(true)
    try {
      const payload: any = {
        name: newRoleName.trim(),
        description: newRoleDesc.trim() || undefined
      }
      if (cloneFromId) {
        payload.clone_from_role_id = Number(cloneFromId)
      }
      const res = await fetch(`${API_BASE}/admin/roles`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create role')
      }
      const created: RoleItem = await res.json()
      toast.success(`Role '${created.name}' created successfully!`)
      const updated = [...roles, created]
      onRolesChange(updated)
      setSelectedRoleId(created.role_id)
      setShowCreateModal(false)
      setNewRoleName('')
      setNewRoleDesc('')
      setCloneFromId('')
    } catch (err: any) {
      toast.error(err.message || 'Error creating role')
    } finally {
      setCreateLoading(false)
    }
  }

  // Update Role
  const handleEditRoleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !editRole) return
    setEditLoading(true)
    try {
      const res = await fetch(`${API_BASE}/admin/roles/${editRole.role_id}`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({
          name: editRoleName.trim() || undefined,
          description: editRoleDesc.trim() || undefined
        })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to update role')
      }
      const updatedRole: RoleItem = await res.json()
      toast.success(`Role '${updatedRole.name}' updated!`)
      onRolesChange(roles.map((r) => (r.role_id === updatedRole.role_id ? updatedRole : r)))
      setEditRole(null)
    } catch (err: any) {
      toast.error(err.message || 'Error updating role')
    } finally {
      setEditLoading(false)
    }
  }

  // Delete Role
  const handleDeleteRole = async (role: RoleItem) => {
    if (!token) return
    if (role.is_system || role.name.toLowerCase() === 'admin' || role.name.toLowerCase() === 'sales') {
      toast.error('System roles (Admin, Sales) cannot be deleted.')
      return
    }
    if (role.user_count > 0) {
      toast.error(`Cannot delete role '${role.name}' because ${role.user_count} user(s) are assigned to it.`)
      return
    }
    if (!confirm(`Are you sure you want to delete role '${role.name}'? This action cannot be undone.`)) {
      return
    }

    setDeleteLoadingId(role.role_id)
    try {
      const res = await fetch(`${API_BASE}/admin/roles/${role.role_id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to delete role')
      }
      toast.success(`Role '${role.name}' deleted successfully!`)
      const remaining = roles.filter((r) => r.role_id !== role.role_id)
      onRolesChange(remaining)
      if (selectedRoleId === role.role_id) {
        setSelectedRoleId(remaining[0]?.role_id || null)
      }
    } catch (err: any) {
      toast.error(err.message || 'Error deleting role')
    } finally {
      setDeleteLoadingId(null)
    }
  }

  const isAdminSelected = selectedRole?.name.toLowerCase() === 'admin'

  // Filtered permission modules based on search
  const filteredPermissions = useMemo(() => {
    if (!searchQuery.trim()) return permissions
    const q = searchQuery.toLowerCase()
    return permissions.filter(
      (p) => p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q) || (p.description && p.description.toLowerCase().includes(q))
    )
  }, [permissions, searchQuery])

  // Count active modules & total actions
  const stats = useMemo(() => {
    let activeModules = 0
    let totalActions = 0
    permissions.forEach((p) => {
      if (p.can_read) activeModules++
      if (p.can_read) totalActions++
      if (p.can_create) totalActions++
      if (p.can_update) totalActions++
      if (p.can_delete) totalActions++
    })
    return { activeModules, totalActions, maxActions: permissions.length * 4 }
  }, [permissions])

  return (
    <div className="space-y-6">
      {/* Top Banner & Title */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-card border border-border/70 rounded-2xl p-5 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-black text-foreground tracking-tight flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-500" />
              Roles & Permission Management
            </h2>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
              RBAC v2
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1 max-w-2xl leading-relaxed">
            Create custom roles, configure granular read/write/delete capabilities across accounting, inventory, and field sales, and assign them effortlessly to your team.
          </p>
        </div>

        <button
          onClick={() => {
            setNewRoleName('')
            setNewRoleDesc('')
            setCloneFromId('')
            setShowCreateModal(true)
          }}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-95 text-white font-bold rounded-xl text-xs transition-all shadow-md shrink-0 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          Create New Role
        </button>
      </div>

      {/* Role Cards Horizontal Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {roles.map((r) => {
          const isSelected = r.role_id === selectedRole?.role_id
          const isAdmin = r.name.toLowerCase() === 'admin'
          const isSales = r.name.toLowerCase() === 'sales'

          return (
            <div
              key={r.role_id}
              onClick={() => setSelectedRoleId(r.role_id)}
              className={cn(
                'group relative rounded-2xl p-4 border transition-all cursor-pointer flex flex-col justify-between text-left',
                isSelected
                  ? 'bg-card border-emerald-500 shadow-md ring-2 ring-emerald-500/20'
                  : 'bg-card/70 border-border/80 hover:border-border hover:bg-card shadow-2xs'
              )}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div
                      className={cn(
                        'w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-black shadow-2xs',
                        isAdmin
                          ? 'bg-amber-500/10 text-amber-600 border border-amber-500/20'
                          : isSales
                          ? 'bg-blue-500/10 text-blue-600 border border-blue-500/20'
                          : 'bg-purple-500/10 text-purple-600 border border-purple-500/20'
                      )}
                    >
                      {isAdmin ? '👑' : isSales ? '⚡' : '🛠️'}
                    </div>
                    <span className="font-bold text-sm text-foreground truncate">{r.name}</span>
                  </div>

                  {/* Badge */}
                  {isAdmin ? (
                    <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 border border-amber-500/20">
                      Superuser
                    </span>
                  ) : isSales ? (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-600 border border-blue-500/20">
                      Preset
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-600 border border-purple-500/20">
                      Custom
                    </span>
                  )}
                </div>

                <p className="text-xs text-muted-foreground line-clamp-2 min-h-[32px] leading-relaxed">
                  {r.description || 'Custom role with tailored portal permissions.'}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-border/60 flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-medium flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-muted-foreground/70" />
                  <strong className="text-foreground">{r.user_count}</strong> user{r.user_count === 1 ? '' : 's'}
                </span>

                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  {/* Clone button */}
                  <button
                    onClick={() => {
                      setNewRoleName(`${r.name} Copy`)
                      setNewRoleDesc(r.description || '')
                      setCloneFromId(String(r.role_id))
                      setShowCreateModal(true)
                    }}
                    title="Duplicate / Clone Role"
                    className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </button>

                  {/* Edit for custom roles */}
                  {!r.is_system && (
                    <>
                      <button
                        onClick={() => {
                          setEditRole(r)
                          setEditRoleName(r.name)
                          setEditRoleDesc(r.description || '')
                        }}
                        title="Edit Role Details"
                        className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => handleDeleteRole(r)}
                        disabled={deleteLoadingId === r.role_id || r.user_count > 0}
                        title={
                          r.user_count > 0
                            ? `Cannot delete role with ${r.user_count} assigned users`
                            : 'Delete Custom Role'
                        }
                        className={cn(
                          'p-1.5 rounded-lg transition-colors',
                          r.user_count > 0
                            ? 'text-muted-foreground/30 cursor-not-allowed'
                            : 'text-rose-500 hover:bg-rose-500/10 cursor-pointer'
                        )}
                      >
                        {deleteLoadingId === r.role_id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Selected Role Workspace */}
      {selectedRole && (
        <div className="bg-card border border-border/80 rounded-2xl shadow-xs overflow-hidden">
          {/* Workspace Header */}
          <div className="p-5 border-b border-border/70 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 bg-muted/20">
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 shadow-xs font-bold text-lg',
                  isAdminSelected
                    ? 'bg-amber-500/15 text-amber-600'
                    : 'bg-emerald-500/15 text-emerald-600'
                )}
              >
                {isAdminSelected ? '👑' : <SlidersHorizontal className="w-5 h-5 text-emerald-600" />}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-black text-base text-foreground">{selectedRole.name} Permissions</h3>
                  {isAdminSelected && (
                    <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 border border-amber-500/30">
                      Unrestricted Full Access
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {isAdminSelected
                    ? 'Administrators possess unconditional, bypass access to every portal capability.'
                    : `${stats.activeModules} active modules (${stats.totalActions}/${stats.maxActions} actions enabled)`}
                </p>
              </div>
            </div>

            {/* Actions Bar */}
            {!isAdminSelected && (
              <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
                <div className="flex items-center gap-1.5 bg-background border border-border rounded-xl p-1 shadow-2xs">
                  <button
                    onClick={() => handleApplyPreset('all')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                  >
                    Grant All
                  </button>
                  <button
                    onClick={() => handleApplyPreset('read')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                  >
                    Read Only
                  </button>
                  <button
                    onClick={() => handleApplyPreset('clear')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-rose-500 hover:bg-rose-500/10 transition-colors cursor-pointer"
                  >
                    Clear All
                  </button>
                </div>

                <button
                  onClick={handleSavePermissions}
                  disabled={savingPerms || !isDirty}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-md shrink-0 cursor-pointer',
                    isDirty
                      ? 'bg-emerald-500 hover:bg-emerald-600 text-white animate-pulse'
                      : 'bg-emerald-500/80 text-white disabled:opacity-50'
                  )}
                >
                  {savingPerms ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      Save Permissions {isDirty && '•'}
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Admin Special Callout Banner */}
          {isAdminSelected && (
            <div className="p-6 bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent border-b border-amber-500/20">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-600 flex items-center justify-center shrink-0 shadow-xs">
                  <Lock className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                    Superuser Security Guarantee
                    <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-500 text-black">
                      Protected
                    </span>
                  </h4>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed max-w-3xl">
                    The <strong>Admin</strong> role unconditionally bypasses all permission evaluation rules in both frontend navigation and backend API endpoints. To prevent administrator lockout, permissions for this role are permanently locked to 100% full access.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Search Filter Bar */}
          <div className="p-4 border-b border-border/70 flex items-center gap-3 bg-muted/10">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search modules & features..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-background border border-border rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>
            <span className="text-xs text-muted-foreground">
              Showing <strong>{filteredPermissions.length}</strong> modules
            </span>
          </div>

          {/* Matrix Groups */}
          {loadingPerms ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-500" />
              <p className="text-xs">Loading role permissions matrix...</p>
            </div>
          ) : (
            <div className="p-5 space-y-6">
              {MODULE_GROUPS.map((group) => {
                const groupModules = filteredPermissions.filter((p) => group.codes.includes(p.code.toLowerCase()))
                if (groupModules.length === 0) return null

                const GroupIcon = group.icon

                return (
                  <div key={group.id} className="rounded-2xl border border-border/80 overflow-hidden bg-card/60 shadow-2xs">
                    {/* Category Header */}
                    <div className="px-5 py-3.5 bg-muted/30 border-b border-border/70 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={cn('w-7 h-7 rounded-xl flex items-center justify-center shrink-0 border', group.color)}>
                          <GroupIcon className="w-3.5 h-3.5" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-foreground">{group.title}</h4>
                          <p className="text-[11px] text-muted-foreground">{group.description}</p>
                        </div>
                      </div>
                    </div>

                    {/* Modules Grid in Category */}
                    <div className="divide-y divide-border/60">
                      {groupModules.map((mod) => {
                        const isModuleActive = mod.can_read

                        return (
                          <div
                            key={mod.module_id}
                            className={cn(
                              'p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors',
                              isModuleActive ? 'hover:bg-muted/30' : 'bg-muted/10 opacity-75'
                            )}
                          >
                            {/* Left: Module Info */}
                            <div className="space-y-0.5 max-w-md">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-xs text-foreground">{mod.name}</span>
                                <code className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                  {mod.code}
                                </code>
                              </div>
                              <p className="text-[11px] text-muted-foreground leading-relaxed">
                                {mod.description || 'Feature access and management control.'}
                              </p>
                            </div>

                            {/* Right: Actions Toggles */}
                            <div className="flex flex-wrap items-center gap-2 shrink-0">
                              {/* Master Toggle */}
                              <button
                                type="button"
                                disabled={isAdminSelected}
                                onClick={() => handleToggleModuleAll(mod.module_id, !isModuleActive)}
                                className={cn(
                                  'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold transition-all border shrink-0',
                                  isAdminSelected || isModuleActive
                                    ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                                    : 'bg-muted text-muted-foreground border-border hover:text-foreground'
                                )}
                              >
                                <span
                                  className={cn(
                                    'w-2 h-2 rounded-full',
                                    isAdminSelected || isModuleActive ? 'bg-emerald-500' : 'bg-muted-foreground'
                                  )}
                                />
                                {isAdminSelected ? 'Active' : isModuleActive ? 'Active' : 'Disabled'}
                              </button>

                              {/* CRUD Actions */}
                              <div className="flex items-center gap-1 bg-muted/40 border border-border/80 rounded-xl p-1">
                                {[
                                  { key: 'can_read', label: 'View', short: 'R' },
                                  { key: 'can_create', label: 'Add', short: 'C' },
                                  { key: 'can_update', label: 'Edit', short: 'U' },
                                  { key: 'can_delete', label: 'Delete', short: 'D' }
                                ].map((act) => {
                                  const isChecked = isAdminSelected || Boolean(mod[act.key as keyof PermissionItem])

                                  return (
                                    <button
                                      key={act.key}
                                      type="button"
                                      disabled={isAdminSelected}
                                      onClick={() =>
                                        handleToggleAction(
                                          mod.module_id,
                                          act.key as 'can_read' | 'can_create' | 'can_update' | 'can_delete',
                                          !isChecked
                                        )
                                      }
                                      className={cn(
                                        'px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all flex items-center gap-1 cursor-pointer',
                                        isChecked
                                          ? 'bg-card text-foreground shadow-2xs font-bold border border-border/60'
                                          : 'text-muted-foreground hover:text-foreground'
                                      )}
                                    >
                                      {isChecked ? (
                                        <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                      ) : (
                                        <span className="w-3 h-3 rounded-full border border-border" />
                                      )}
                                      <span>{act.label}</span>
                                    </button>
                                  )
                                })}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}

              {/* Catch-all for any unmapped modules */}
              {(() => {
                const mappedCodes = MODULE_GROUPS.flatMap((g) => g.codes)
                const otherModules = filteredPermissions.filter((p) => !mappedCodes.includes(p.code.toLowerCase()))
                if (otherModules.length === 0) return null

                return (
                  <div className="rounded-2xl border border-border/80 overflow-hidden bg-card/60 shadow-2xs">
                    <div className="px-5 py-3.5 bg-muted/30 border-b border-border/70 flex items-center gap-3">
                      <div className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0 border bg-muted text-muted-foreground">
                        <Layers className="w-3.5 h-3.5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-foreground">Other Modules & Capabilities</h4>
                        <p className="text-[11px] text-muted-foreground">Additional features registered in database</p>
                      </div>
                    </div>
                    <div className="divide-y divide-border/60">
                      {otherModules.map((mod) => (
                        <div
                          key={mod.module_id}
                          className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs text-foreground">{mod.name}</span>
                              <code className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                {mod.code}
                              </code>
                            </div>
                            <p className="text-[11px] text-muted-foreground">{mod.description}</p>
                          </div>

                          <div className="flex items-center gap-2">
                            {[
                              { key: 'can_read', label: 'View' },
                              { key: 'can_create', label: 'Add' },
                              { key: 'can_update', label: 'Edit' },
                              { key: 'can_delete', label: 'Delete' }
                            ].map((act) => {
                              const isChecked = isAdminSelected || Boolean(mod[act.key as keyof PermissionItem])
                              return (
                                <button
                                  key={act.key}
                                  type="button"
                                  disabled={isAdminSelected}
                                  onClick={() =>
                                    handleToggleAction(
                                      mod.module_id,
                                      act.key as any,
                                      !isChecked
                                    )
                                  }
                                  className={cn(
                                    'px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all flex items-center gap-1 cursor-pointer',
                                    isChecked
                                      ? 'bg-card text-foreground shadow-2xs font-bold border border-border/60'
                                      : 'text-muted-foreground hover:text-foreground'
                                  )}
                                >
                                  {isChecked ? (
                                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                  ) : (
                                    <span className="w-3 h-3 rounded-full border border-border" />
                                  )}
                                  <span>{act.label}</span>
                                </button>
                              )
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      )}

      {/* CREATE ROLE MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-3xl shadow-xl overflow-hidden animate-in zoom-in-95 duration-200 border border-border">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center">
              <div>
                <h3 className="font-black text-lg text-foreground flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-emerald-500" />
                  Create New Role
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Define a customized role and clone permissions from an existing template.
                </p>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateRoleSubmit} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Role Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Branch Accountant, Field Lead, Auditor"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-muted/40 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Description</label>
                <textarea
                  rows={2}
                  placeholder="Briefly describe what responsibilities this role handles..."
                  value={newRoleDesc}
                  onChange={(e) => setNewRoleDesc(e.target.value)}
                  className="w-full px-4 py-2.5 bg-muted/40 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Clone Permissions From</label>
                <select
                  value={cloneFromId}
                  onChange={(e) => setCloneFromId(e.target.value)}
                  className="w-full px-4 py-2.5 bg-muted/40 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  <option value="">Start Empty (No initial permissions)</option>
                  {roles.map((r) => (
                    <option key={r.role_id} value={r.role_id}>
                      Clone from {r.name} {r.is_system ? '(System Preset)' : ''}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-muted-foreground ml-1">
                  Cloning instantly copies all module CRUD permissions from the selected template.
                </p>
              </div>

              <div className="pt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-2.5 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-xs transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading || !newRoleName.trim()}
                  className="flex-1 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-98 text-white font-bold rounded-xl text-xs transition-all shadow-md cursor-pointer disabled:opacity-50"
                >
                  {createLoading ? 'Creating...' : 'Create Role'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT ROLE MODAL */}
      {editRole && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-3xl shadow-xl overflow-hidden animate-in zoom-in-95 duration-200 border border-border">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center">
              <div>
                <h3 className="font-black text-lg text-foreground flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-emerald-500" />
                  Edit Role Details
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">Update name and description for {editRole.name}.</p>
              </div>
              <button
                onClick={() => setEditRole(null)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleEditRoleSubmit} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Role Name *</label>
                <input
                  type="text"
                  required
                  value={editRoleName}
                  onChange={(e) => setEditRoleName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-muted/40 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Description</label>
                <textarea
                  rows={2}
                  value={editRoleDesc}
                  onChange={(e) => setEditRoleDesc(e.target.value)}
                  className="w-full px-4 py-2.5 bg-muted/40 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="pt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => setEditRole(null)}
                  className="flex-1 py-2.5 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-xs transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editLoading || !editRoleName.trim()}
                  className="flex-1 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-98 text-white font-bold rounded-xl text-xs transition-all shadow-md cursor-pointer disabled:opacity-50"
                >
                  {editLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
