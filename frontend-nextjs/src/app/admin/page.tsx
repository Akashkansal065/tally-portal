'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatDate } from '@/lib/utils'
import {
  Shield,
  Users,
  RefreshCw,
  FileText,
  Trash2,
  CheckCircle,
  XCircle,
  ArrowLeft,
  User as UserIcon,
  Laptop,
  Bell,
  MapPin,
  Plus,
  Upload,
  CheckCircle2
} from 'lucide-react'
import { cn } from '@/lib/utils'

type UserItem = {
  user_id: number
  username: string
  email: string
  is_active: boolean
  role_id: number
  role_name: string
  created_at?: string
}

type AuditLog = {
  id: number
  user_email: string
  action: string
  resource: string
  created_at: string
}

type VisitLog = {
  id: number
  shopName?: string
  customShopName?: string
  salesperson: string
  createdAt: string
  comments?: string
}

const SYNC_STEPS = [
  "Reading Tally XML file...",
  "Validating ERP Session Token...",
  "Sending collection load payload...",
  "Parsing Account Groups...",
  "Importing Master Ledgers...",
  "Validating Opening Balances...",
  "Mapping Debit/Credit signs...",
  "Committing Vouchers & Transactions..."
]

export default function AdminPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [tab, setTab] = useState<'users' | 'sync' | 'logs' | 'visits'>('users')
  const [users, setUsers] = useState<UserItem[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [visits, setVisits] = useState<VisitLog[]>([])
  const [loading, setLoading] = useState(false)
  const [alertsEnabled, setAlertsEnabled] = useState(true)

  // Sync state
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [syncRunning, setSyncRunning] = useState(false)
  const [syncStep, setSyncStep] = useState(-1)
  const [syncStats, setSyncStats] = useState<any>(null)
  const [syncError, setSyncError] = useState('')

// Roles and UI states
  const [roles, setRoles] = useState<any[]>([])
  const [adminCompanies, setAdminCompanies] = useState<any[]>([])
  const [adminModules, setAdminModules] = useState<any[]>([])
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [showRoleEdit, setShowRoleEdit] = useState<UserItem | null>(null)
  const [permissionsTab, setPermissionsTab] = useState<'role' | 'companies' | 'modules'>('role')
  
  const [editUserCompanies, setEditUserCompanies] = useState<number[]>([])
  const [editUserOverrides, setEditUserOverrides] = useState<any[]>([])
  
  // Create user form state
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '', role_id: 2 })
  const [createUserError, setCreateUserError] = useState('')
  const [createUserLoading, setCreateUserLoading] = useState(false)

  const fetchData = async () => {
    if (!permissions.isAdmin) return
    setLoading(true)
    try {
      if (tab === 'users') {
        const [uRes, rRes, cRes, mRes] = await Promise.all([
          fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/roles`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/companies`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/modules`, { headers: authHeaders(token) })
        ])
        const uData = await uRes.json()
        const rData = await rRes.json()
        const cData = await cRes.json()
        const mData = await mRes.json()
        setUsers(Array.isArray(uData) ? uData : [])
        setRoles(Array.isArray(rData) ? rData : [])
        setAdminCompanies(Array.isArray(cData) ? cData : [])
        setAdminModules(Array.isArray(mData) ? mData : [])
      } else if (tab === 'logs') {
        const res = await fetch(`${API_BASE}/admin/audit-logs`, { headers: authHeaders(token) })
        const data = await res.json()
        setLogs(Array.isArray(data) ? data : [])
      } else if (tab === 'visits') {
        const res = await fetch(`${API_BASE}/visits/logs`, { headers: authHeaders(token) })
        const data = await res.json()
        setVisits(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchData()
  }, [user, permissions, router, tab, token])

  const toggleUser = async (u: UserItem) => {
    try {
      await fetch(`${API_BASE}/admin/users/${u.user_id}`, {
        method: 'PATCH',
        headers: authHeaders(token),
        body: JSON.stringify({ is_active: !u.is_active }),
      })
      setUsers(v => v.map(x => x.user_id === u.user_id ? { ...x, is_active: !u.is_active } : x))
    } catch (err) {
      console.error(err)
    }
  }

  const deleteUserItem = async (u: UserItem) => {
    if (confirm(`Are you sure you want to delete user ${u.username}?`)) {
      try {
        await fetch(`${API_BASE}/admin/users/${u.user_id}`, {
          method: 'DELETE',
          headers: authHeaders(token)
        })
        setUsers(v => v.filter(x => x.user_id !== u.user_id))
      } catch (err) {
        console.error(err)
      }
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateUserError('')
    setCreateUserLoading(true)
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(newUser)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create user')
      }
      const data = await res.json()
      setUsers([...users, data])
      setShowCreateUser(false)
      setNewUser({ username: '', email: '', password: '', role_id: roles[0]?.role_id || 2 })
    } catch (err: any) {
      setCreateUserError(err.message)
    } finally {
      setCreateUserLoading(false)
    }
  }

const handleSavePermissions = async () => {
    if (!showRoleEdit) return
    try {
      if (permissionsTab === 'role') {
        // Handled directly on click
      } else if (permissionsTab === 'companies') {
        await fetch(`${API_BASE}/admin/users/${showRoleEdit.user_id}/companies`, {
          method: 'PUT',
          headers: authHeaders(token),
          body: JSON.stringify({ company_ids: editUserCompanies })
        })
        alert("Company access updated.")
      } else if (permissionsTab === 'modules') {
        await fetch(`${API_BASE}/admin/users/${showRoleEdit.user_id}/permissions`, {
          method: 'PUT',
          headers: authHeaders(token),
          body: JSON.stringify(editUserOverrides)
        })
        alert("Module permissions updated.")
      }
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleUpdateRole = async (roleId: number) => {
    if (!showRoleEdit) return
    try {
      const res = await fetch(`${API_BASE}/admin/users/${showRoleEdit.user_id}/role`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ role_id: roleId })
      })
      if (!res.ok) throw new Error('Failed to update role')
      
      const roleName = roles.find(r => r.role_id === roleId)?.name || 'Unknown'
      setUsers(users.map(u => u.user_id === showRoleEdit.user_id ? { ...u, role_id: roleId, role_name: roleName } : u))
      setShowRoleEdit(null)
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setXmlFile(file)
    setSyncError('')
    setSyncStats(null)
  }

  const startImport = async () => {
    if (!xmlFile) {
      setSyncError("Please select a Tally XML export file first.")
      return
    }
    setSyncError('')
    setSyncRunning(true)
    setSyncStats(null)
    setSyncStep(0)

    try {
      await new Promise(r => setTimeout(r, 600))
      setSyncStep(1)

      if (!token) throw new Error("No active session found. Please re-login.")
      
      await new Promise(r => setTimeout(r, 600))
      setSyncStep(2)

      const syncRes = await fetch(`${API_BASE}/sync/inbound`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/xml"
        },
        body: xmlFile
      })

      for (let i = 3; i < SYNC_STEPS.length; i++) {
        await new Promise(r => setTimeout(r, 700))
        setSyncStep(i)
      }

      if (!syncRes.ok) {
        const errData = await syncRes.json()
        throw new Error(errData.detail || "Failed to process Tally XML.")
      }

      const data = await syncRes.json()
      setSyncStats(data)
    } catch (err: any) {
      setSyncError(err.message || 'Import failed')
    } finally {
      setSyncRunning(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Top green header */}
      <header className="shrink-0 border-b border-border bg-emerald-500 text-white h-14 flex items-center px-4 justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push('/')} className="p-1 hover:bg-emerald-600 rounded-lg transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-white/20 flex items-center justify-center text-xs font-bold">S</div>
            <span className="font-bold text-sm">Sneh Distributors</span>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 pt-5 pb-6 max-w-xl mx-auto w-full space-y-5">
        {/* Title */}
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tight text-foreground">Admin Portal</h1>
              <p className="text-xs text-muted-foreground">Manage user roles and main menu visibility settings</p>
            </div>
          </div>
        </div>

        {/* Create User button (only shown when in users directory tab) */}
        {tab === 'users' && (
          <button 
            onClick={() => setShowCreateUser(true)}
            className="flex items-center gap-1.5 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-xl text-xs transition-all shadow-md shadow-emerald-500/10"
          >
            <Plus className="h-4 w-4" /> Create User
          </button>
        )}

        {/* Admin Alerts Switch Block */}
        <div className="bg-card border border-border rounded-2xl p-4 flex items-center justify-between gap-3 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
              <Bell className="h-4.5 w-4.5 text-emerald-600 animate-pulse" />
            </div>
            <div className="min-w-0">
              <p className="font-bold text-xs flex items-center gap-1.5 text-foreground">
                Admin Alerts
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              </p>
              <p className="text-[10px] text-muted-foreground leading-normal mt-0.5">
                Active! You will receive push notifications when users access ledgers, stocks, orders, or check-ins.
              </p>
            </div>
          </div>
          <button
            onClick={() => setAlertsEnabled(v => !v)}
            className={cn(
              'w-9 h-5 rounded-full p-0.5 transition-colors relative shrink-0',
              alertsEnabled ? 'bg-emerald-500' : 'bg-muted border border-border'
            )}
          >
            <div
              className={cn(
                'w-4 h-4 rounded-full bg-white shadow-sm transition-transform',
                alertsEnabled ? 'translate-x-4' : 'translate-x-0'
              )}
            />
          </button>
        </div>

        {/* Dynamic Pills Tabs */}
        <div className="flex gap-1.5 border-b border-border pb-1 overflow-x-auto scrollbar-none">
          <button
            onClick={() => setTab('users')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all shrink-0',
              tab === 'users' ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'
            )}
          >
            <UserIcon className="h-3.5 w-3.5" /> User Directory
          </button>
          <button
            onClick={() => setTab('sync')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all shrink-0',
              tab === 'sync' ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'
            )}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Tally Sync
          </button>
          <button
            onClick={() => setTab('logs')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all shrink-0',
              tab === 'logs' ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'
            )}
          >
            <FileText className="h-3.5 w-3.5" /> Audit Logs
          </button>
          <button
            onClick={() => setTab('visits')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all shrink-0',
              tab === 'visits' ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'
            )}
          >
            <MapPin className="h-3.5 w-3.5" /> Visit Logs
          </button>
        </div>

        {/* Directory/Logs Render Grid */}
        <div className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-10">
              <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : tab === 'users' ? (
            <div className="space-y-3">
              {users.length === 0 && <p className="text-xs text-muted-foreground text-center py-4">No users found.</p>}
              {users.map(u => (
                <div
                  key={u.user_id}
                  className={cn(
                    'bg-card border border-border rounded-2xl p-4 space-y-4 shadow-sm transition-opacity',
                    !u.is_active && 'opacity-65'
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground shrink-0">
                        <UserIcon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-xs text-foreground truncate">{u.username || u.email.split('@')[0]}</p>
                        <div className="flex gap-1.5 mt-1 items-center">
                          <span className="text-[9px] font-bold px-1.5 py-0.5 bg-muted text-muted-foreground rounded uppercase tracking-wider">
                            {u.role_name}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <button
                      onClick={() => toggleUser(u)}
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border transition-all active:scale-95 shrink-0',
                        u.is_active
                          ? 'bg-green-500/10 text-green-600 border-green-500/20'
                          : 'bg-destructive/10 text-destructive border-destructive/20'
                      )}
                    >
                      {u.is_active ? '✓ Active' : '✕ Disabled'}
                    </button>
                  </div>

                  <div className="flex flex-col gap-2 pt-3 border-t border-border">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>Registered</span>
                      <span>{formatDate(u.created_at || '2026-06-02')}</span>
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-1">
<button 
                        onClick={async () => {
                          setShowRoleEdit(u)
                          setPermissionsTab('role')
                          // Fetch companies and overrides
                          const [cRes, oRes] = await Promise.all([
                            fetch(`${API_BASE}/admin/users/${u.user_id}/companies`, { headers: authHeaders(token) }),
                            fetch(`${API_BASE}/admin/users/${u.user_id}/permissions`, { headers: authHeaders(token) })
                          ])
                          const cData = await cRes.json()
                          const oData = await oRes.json()
                          setEditUserCompanies(Array.isArray(cData) ? cData : [])
                          setEditUserOverrides(Array.isArray(oData) ? oData : [])
                        }}
                        className="h-8 px-3 text-[11px] font-bold border border-border hover:bg-muted text-foreground rounded-lg transition-colors flex items-center gap-1"
                      >
                        <Shield className="w-3.5 h-3.5" /> Permissions
                      </button>
                      <button className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors flex items-center justify-center">
                        <Laptop className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteUserItem(u)}
                        className="h-8 w-8 text-destructive/70 hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors flex items-center justify-center"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : tab === 'sync' ? (
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
              <h2 className="font-bold text-sm text-foreground">Tally XML Collection Import</h2>
              <p className="text-xs text-muted-foreground">Select and upload standard Tally Master/Voucher collections (.xml) to sync data with MyTally.</p>
              
              {syncError && (
                <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-xs font-semibold">
                  ⚠️ {syncError}
                </div>
              )}

              {syncStats && (
                <div className="p-3.5 rounded-xl bg-green-500/10 text-green-600 border border-green-500/20 text-xs font-semibold space-y-1">
                  <div className="flex items-center gap-1.5 text-sm mb-1.5"><CheckCircle2 className="h-4.5 w-4.5" /> Import completed successfully!</div>
                  <p>• Groups: {syncStats.imported_groups ?? syncStats.groups_processed ?? 0}</p>
                  <p>• Ledgers: {syncStats.imported_ledgers ?? syncStats.ledgers_processed ?? 0}</p>
                  <p>• Vouchers: {syncStats.imported_vouchers ?? syncStats.vouchers_processed ?? 0}</p>
                  <p>• Bills: {syncStats.imported_bills ?? syncStats.bills_processed ?? 0}</p>
                </div>
              )}

              {!syncRunning && !syncStats && (
                <div className="border-2 border-dashed border-border hover:border-emerald-500/50 rounded-xl p-6 text-center cursor-pointer transition-colors bg-muted/20 relative">
                  <input type="file" accept=".xml" onChange={handleFileChange} id="tally-file" className="hidden" />
                  <label htmlFor="tally-file" className="cursor-pointer block space-y-2">
                    <Upload className="h-8 w-8 mx-auto text-muted-foreground" />
                    <p className="text-xs font-bold text-foreground">{xmlFile ? xmlFile.name : 'Select Tally Export XML'}</p>
                    <p className="text-[10px] text-muted-foreground">Click to browse your device files</p>
                  </label>
                </div>
              )}

              {syncRunning && (
                <div className="border border-border rounded-xl p-4 bg-muted/10 space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin shrink-0" />
                    <p className="text-xs font-bold text-foreground">Import process running...</p>
                  </div>
                  <div className="space-y-1.5 pl-6 border-l border-border">
                    {SYNC_STEPS.map((step, idx) => (
                      <p
                        key={idx}
                        className={cn(
                          'text-[10px] transition-all',
                          syncStep > idx ? 'text-green-600 font-bold' : syncStep === idx ? 'text-emerald-500 font-black animate-pulse' : 'text-muted-foreground'
                        )}
                      >
                        {syncStep > idx ? '✓ ' : syncStep === idx ? '▸ ' : '• '}{step}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {!syncRunning && !syncStats && (
                <button
                  onClick={startImport}
                  className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-xl text-xs transition-all shadow-md"
                >
                  Start Import Process
                </button>
              )}

              {syncStats && (
                <button
                  onClick={() => { setSyncStats(null); setXmlFile(null) }}
                  className="w-full py-3 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-xs transition-all"
                >
                  Upload Another File
                </button>
              )}
            </div>
          ) : tab === 'logs' ? (
            <div className="space-y-2">
              {logs.map(l => (
                <div key={l.id} className="bg-card border border-border rounded-xl p-3 shadow-sm">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0 text-xs">
                      <p className="font-semibold text-foreground">
                        {l.action} <span className="text-muted-foreground">on</span> {l.resource}
                      </p>
                      <p className="text-[9px] text-muted-foreground mt-0.5">
                        {l.user_email} • {new Date(l.created_at).toLocaleString('en-IN')}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {logs.length === 0 && (
                <div className="text-center py-8 text-muted-foreground text-xs">No audit logs logged.</div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {visits.map(v => (
                <div key={v.id} className="bg-card border border-border rounded-xl p-3 shadow-sm">
                  <div className="flex items-start justify-between gap-2 text-xs">
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-foreground">
                        {v.shopName || v.customShopName || 'Unknown Shop'}
                      </p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        By: {v.salesperson} • {formatDate(v.createdAt)}
                      </p>
                      {v.comments && (
                        <p className="text-[10px] text-muted-foreground mt-1 bg-muted p-1.5 rounded-lg italic">
                          {v.comments}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {visits.length === 0 && (
                <div className="text-center py-8 text-muted-foreground text-xs">No visit logs logged.</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateUser && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-sm rounded-3xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center">
              <div>
                <h3 className="font-black text-lg text-foreground">Create New User</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Add a new team member to your organization.</p>
              </div>
              <button 
                onClick={() => setShowCreateUser(false)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              {createUserError && (
                <div className="p-3 bg-destructive/10 text-destructive text-xs font-bold rounded-xl">
                  {createUserError}
                </div>
              )}
              
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Username</label>
                <input 
                  type="text" 
                  required
                  value={newUser.username}
                  onChange={e => setNewUser({...newUser, username: e.target.value})}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="e.g. Rahul Sharma"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Email Address</label>
                <input 
                  type="email" 
                  required
                  value={newUser.email}
                  onChange={e => setNewUser({...newUser, email: e.target.value})}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="rahul@example.com"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Password</label>
                <input 
                  type="password" 
                  required
                  value={newUser.password}
                  onChange={e => setNewUser({...newUser, password: e.target.value})}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="Minimum 6 characters"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Assign Role</label>
                <select 
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all appearance-none"
                  value={newUser.role_id}
                  onChange={e => setNewUser({...newUser, role_id: Number(e.target.value)})}
                >
                  {roles.map(r => (
                    <option key={r.role_id} value={r.role_id}>{r.name} - {r.description}</option>
                  ))}
                </select>
              </div>

              <div className="pt-2">
                <button 
                  type="submit"
                  disabled={createUserLoading}
                  className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-xl text-sm transition-all shadow-md disabled:opacity-70"
                >
                  {createUserLoading ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

{/* Edit Role Modal */}
      {showRoleEdit && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-3xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200 flex flex-col max-h-[85vh]">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center shrink-0">
              <div>
                <h3 className="font-black text-lg text-foreground">Permissions</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Manage access for <span className="font-bold text-foreground">{showRoleEdit.username}</span></p>
              </div>
              <button 
                onClick={() => setShowRoleEdit(null)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex gap-2 px-6 pt-3 border-b border-border shrink-0">
              <button onClick={() => setPermissionsTab('role')} className={`pb-3 text-xs font-bold border-b-2 transition-all ${permissionsTab === 'role' ? 'border-emerald-500 text-emerald-500' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>Base Role</button>
              <button onClick={() => setPermissionsTab('companies')} className={`pb-3 text-xs font-bold border-b-2 transition-all ${permissionsTab === 'companies' ? 'border-emerald-500 text-emerald-500' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>Company Access</button>
              <button onClick={() => setPermissionsTab('modules')} className={`pb-3 text-xs font-bold border-b-2 transition-all ${permissionsTab === 'modules' ? 'border-emerald-500 text-emerald-500' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>Module Overrides</button>
            </div>

            <div className="p-4 space-y-2 overflow-y-auto flex-1">
              {permissionsTab === 'role' && roles.map(r => {
                const isActive = showRoleEdit.role_id === r.role_id;
                return (
                  <button
                    key={r.role_id}
                    onClick={() => handleUpdateRole(r.role_id)}
                    className={`w-full text-left p-4 rounded-2xl border transition-all flex items-start gap-3 ${isActive ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600" : "bg-card border-border hover:bg-muted/50 text-foreground"}`}
                  >
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5 ${isActive ? "border-emerald-500" : "border-muted-foreground"}`}>
                      {isActive && <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />}
                    </div>
                    <div>
                      <p className="font-bold text-sm">{r.name}</p>
                      <p className="text-xs opacity-70 mt-0.5 leading-relaxed">{r.description}</p>
                    </div>
                  </button>
                )
              })}

              {permissionsTab === 'companies' && (
                <div className="space-y-2 mt-2">
                  <p className="text-xs text-muted-foreground px-1 mb-3">Select the companies this user is allowed to access and view data for.</p>
                  {adminCompanies.map(c => (
                    <label key={c.company_id} className="flex items-center gap-3 p-3 rounded-xl border border-border hover:bg-muted/50 cursor-pointer transition-colors">
                      <input 
                        type="checkbox" 
                        checked={editUserCompanies.includes(c.company_id)}
                        onChange={(e) => {
                          if (e.target.checked) setEditUserCompanies([...editUserCompanies, c.company_id]);
                          else setEditUserCompanies(editUserCompanies.filter(id => id !== c.company_id));
                        }}
                        className="w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500/20 bg-card border-border"
                      />
                      <div className="text-sm font-semibold">{c.name}</div>
                    </label>
                  ))}
                  {adminCompanies.length === 0 && <p className="text-xs text-muted-foreground">No companies found.</p>}
                </div>
              )}

              {permissionsTab === 'modules' && (
                <div className="space-y-3 mt-2">
                  <p className="text-xs text-muted-foreground px-1 mb-3">Override permissions for specific modules. This will take precedence over their base role.</p>
                  {adminModules.map(m => {
                    const override = editUserOverrides.find(o => o.module_id === m.module_id) || { module_id: m.module_id, can_create: false, can_read: false, can_update: false, can_delete: false };
                    
                    const toggle = (field: string) => {
                      const newOverrides = editUserOverrides.filter(o => o.module_id !== m.module_id);
                      newOverrides.push({ ...override, [field]: !override[field] });
                      setEditUserOverrides(newOverrides);
                    };

                    return (
                      <div key={m.module_id} className="p-3 rounded-xl border border-border space-y-3 bg-muted/20">
                        <div className="font-bold text-sm text-foreground flex items-center justify-between">
                          {m.name}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {['read', 'create', 'update', 'delete'].map(action => (
                            <label key={action} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-card border border-border text-xs cursor-pointer hover:bg-muted transition-colors">
                              <input 
                                type="checkbox"
                                checked={override[`can_${action}`]}
                                onChange={() => toggle(`can_${action}`)}
                                className="rounded-sm w-3 h-3 text-emerald-500"
                              />
                              <span className="capitalize">{action}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-border bg-muted/20 flex gap-2 shrink-0">
              <button 
                onClick={() => setShowRoleEdit(null)}
                className="flex-1 py-3 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-sm transition-all"
              >
                Close
              </button>
              {permissionsTab !== 'role' && (
                <button 
                  onClick={handleSavePermissions}
                  className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm transition-all shadow-md"
                >
                  Save Changes
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
