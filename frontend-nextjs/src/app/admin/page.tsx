'use client'

import { useEffect, useState, useCallback } from 'react'
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
  Bell,
  MapPin,
  Plus,
  Upload,
  UploadCloud,
  FileCode,
  CheckCircle2,
  Landmark,
  Loader2,
  Calendar,
  X,
  Zap,
  Database,
  Copy,
  Check,
  Code,
  AlertTriangle,
  Terminal,
  Search,
  Activity,
  ArrowUpRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { AdminUserPermissionsModal } from '@/components/admin/AdminUserPermissionsModal'
import rolesConfig from '@/lib/roles.json'

type UserItem = {
  user_id: number
  username: string
  email: string
  is_active: boolean
  role_id: number
  role_name: string
  created_at?: string
  showLedger: boolean
  showSalesLedgers: boolean
  showPurchaseLedgers: boolean
  showReceipts: boolean
  showPayments: boolean
  showExpenses: boolean
  showAttendance: boolean
  showStocks: boolean
  showReports: boolean
  showOrders: boolean
  showCheckIn: boolean
  showGst: boolean
  ledgerScope: string
  stockScope: string
  allowedStockGroups: string | null
  allowedLedgerGroups: string | null
  allowedReportCategories: string | null
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
  user_id?: number
  shopName?: string
  customShopName?: string
  salesperson: string
  createdAt: string
  comments?: string
  latitude?: number | null
  longitude?: number | null
  ip_address?: string | null
  photoUrl?: string | null
}

export type SyncTrafficLogItem = {
  log_id: number
  sync_id: number | null
  entity_type: string
  entity_id: number | null
  entity_name: string | null
  action: string
  status: string
  http_status: number
  outbound_format: string
  outbound_payload: string | null
  curl_command: string | null
  inbound_response: string | null
  error_summary: string | null
  parsed_created: number
  parsed_altered: number
  parsed_deleted: number
  parsed_errors: number
  parsed_exceptions: number
  tally_vchnumber: string | null
  duration_ms: number
  created_at: string
}

export type DeletedRecordAuditItem = {
  audit_id: number
  company_id: number
  entity_type: string
  record_id: number | null
  tally_guid: string | null
  entity_identifier: string | null
  deleted_by_user_id: number | null
  deleted_by_name: string
  tally_sync_status: string
  tally_error_message: string | null
  snapshot_data: any
  deleted_at: string
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
  
  const [tab, setTab] = useState<'users' | 'sync' | 'logs' | 'visits' | 'einvoice' | 'cache'>('users')
  const [users, setUsers] = useState<UserItem[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [visits, setVisits] = useState<VisitLog[]>([])
  const [loading, setLoading] = useState(false)
  const [alertsEnabled, setAlertsEnabled] = useState(true)

  // Cache Management states
  const [cacheStats, setCacheStats] = useState<{
    total_entries: number
    active_entries: number
    expired_entries: number
    default_ttl_seconds: number
  } | null>(null)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [cacheClearing, setCacheClearing] = useState(false)

  // E-Invoicing settings states
  const [einvEnv, setEinvEnv] = useState<'mock' | 'sandbox' | 'production'>('mock')
  const [einvUser, setEinvUser] = useState('')
  const [einvPass, setEinvPass] = useState('')
  const [einvClientId, setEinvClientId] = useState('')
  const [einvClientSecret, setEinvClientSecret] = useState('')
  const [einvLoading, setEinvLoading] = useState(false)
  const [hasPass, setHasPass] = useState(false)
  const [hasSecret, setHasSecret] = useState(false)

  // Sync state
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [syncRunning, setSyncRunning] = useState(false)
  const [syncStep, setSyncStep] = useState(-1)
  const [syncStats, setSyncStats] = useState<any>(null)
  const [syncError, setSyncError] = useState('')

  // Live Tally Run-Once Sync state
  const [runOnceLoading, setRunOnceLoading] = useState(false)
  const [runOnceResult, setRunOnceResult] = useState<any>(null)
  const [runOnceError, setRunOnceError] = useState('')

  // Sync Hub & Discrepancies states
  const [syncSubTab, setSyncSubTab] = useState<'traffic' | 'deleted_audits' | 'inbound'>('traffic')
  const [syncHealth, setSyncHealth] = useState<{
    status: string
    pending_queue_count: number
    synced_queue_count: number
    total_success_traffic: number
    total_failed_traffic: number
    total_exception_traffic: number
    unreconciled_deleted_count?: number
    total_sync_issues?: number
  } | null>(null)

  // Traffic Logs
  const [syncLogs, setSyncLogs] = useState<SyncTrafficLogItem[]>([])
  const [syncLogsLoading, setSyncLogsLoading] = useState(false)
  const [syncStatusFilter, setSyncStatusFilter] = useState('ALL')
  const [syncEntityFilter, setSyncEntityFilter] = useState('ALL')
  const [syncActionFilter, setSyncActionFilter] = useState('ALL')
  const [syncSearchTerm, setSyncSearchTerm] = useState('')
  const [inspectLog, setInspectLog] = useState<SyncTrafficLogItem | null>(null)
  const [copiedLogId, setCopiedLogId] = useState<number | null>(null)
  const [retryingLogId, setRetryingLogId] = useState<number | null>(null)

  // Deleted Audits Discrepancies
  const [deletedAudits, setDeletedAudits] = useState<DeletedRecordAuditItem[]>([])
  const [deletedAuditsLoading, setDeletedAuditsLoading] = useState(false)
  const [deletedStatusFilter, setDeletedStatusFilter] = useState('ALL')
  const [retryingAuditId, setRetryingAuditId] = useState<number | null>(null)
  const [deactivatingAuditId, setDeactivatingAuditId] = useState<number | null>(null)

  const fetchSyncHealth = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/sync/health`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setSyncHealth(data)
      }
    } catch {
      // Gracefully ignore transient network drops
    }
  }, [token])

  const fetchSyncLogs = useCallback(async () => {
    if (!token) return
    setSyncLogsLoading(true)
    try {
      const params = new URLSearchParams()
      if (syncStatusFilter !== 'ALL') params.append('status', syncStatusFilter)
      if (syncEntityFilter !== 'ALL') params.append('entity_type', syncEntityFilter)
      if (syncSearchTerm.trim()) params.append('search', syncSearchTerm.trim())
      params.append('limit', '50')

      const res = await fetch(`${API_BASE}/sync/logs?${params.toString()}`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        let logsList: SyncTrafficLogItem[] = data.logs || []
        if (syncActionFilter !== 'ALL') {
          logsList = logsList.filter(l => l.action.toLowerCase() === syncActionFilter.toLowerCase())
        }
        setSyncLogs(logsList)
      }
    } catch {
      // Gracefully ignore transient network drops
    } finally {
      setSyncLogsLoading(false)
    }
  }, [token, syncStatusFilter, syncEntityFilter, syncActionFilter, syncSearchTerm])

  const fetchDeletedAudits = useCallback(async () => {
    if (!token) return
    setDeletedAuditsLoading(true)
    try {
      const params = new URLSearchParams()
      if (deletedStatusFilter !== 'ALL') params.append('status', deletedStatusFilter)
      if (syncSearchTerm.trim()) params.append('search', syncSearchTerm.trim())
      params.append('limit', '50')

      const res = await fetch(`${API_BASE}/sync/deleted-audits?${params.toString()}`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setDeletedAudits(data.audits || [])
      }
    } catch {
      // Gracefully ignore transient network drops
    } finally {
      setDeletedAuditsLoading(false)
    }
  }, [token, deletedStatusFilter, syncSearchTerm])

  useEffect(() => {
    if (tab === 'sync') {
      fetchSyncHealth()
      if (syncSubTab === 'traffic') fetchSyncLogs()
      if (syncSubTab === 'deleted_audits') fetchDeletedAudits()
    }
  }, [tab, syncSubTab, fetchSyncHealth, fetchSyncLogs, fetchDeletedAudits])

  const handleCopyCurl = (logId: number, curlCommand: string | null) => {
    if (!curlCommand) return
    navigator.clipboard.writeText(curlCommand)
    setCopiedLogId(logId)
    setTimeout(() => setCopiedLogId(null), 2500)
  }

  const handleRetrySyncItem = async (log: SyncTrafficLogItem) => {
    if (!token) return
    setRetryingLogId(log.log_id)
    try {
      if (log.sync_id) {
        await fetch(`${API_BASE}/sync/queue/${log.sync_id}/retry`, {
          method: 'POST',
          headers: authHeaders(token)
        })
      } else if (log.entity_type === 'Voucher' && log.entity_id) {
        await fetch(`${API_BASE}/sync/vouchers/${log.entity_id}/retry-push`, {
          method: 'POST',
          headers: authHeaders(token)
        })
      }
      await Promise.allSettled([fetchSyncHealth(), fetchSyncLogs()])
    } catch {
      // Graceful error handling
    } finally {
      setRetryingLogId(null)
    }
  }

  const handleRetryDeletedAudit = async (auditId: number) => {
    if (!token) return
    setRetryingAuditId(auditId)
    try {
      const res = await fetch(`${API_BASE}/sync/deleted-audits/${auditId}/retry`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      const data = await res.json()
      if (data.tally_sync_status === 'SYNCED_TO_TALLY') {
        alert('Successfully deleted from Tally Prime ✅')
      } else {
        alert(`Tally rejection: ${data.tally_error_message || 'Cannot delete master in Tally Prime'}`)
      }
      await Promise.allSettled([fetchSyncHealth(), fetchDeletedAudits(), fetchSyncLogs()])
    } catch (e: any) {
      alert(e.message || 'Failed to retry Tally deletion')
    } finally {
      setRetryingAuditId(null)
    }
  }

  const handleDeactivateInTally = async (auditId: number) => {
    if (!token) return
    setDeactivatingAuditId(auditId)
    try {
      const res = await fetch(`${API_BASE}/sync/deleted-audits/${auditId}/deactivate-in-tally`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      const data = await res.json()
      if (data.tally_sync_status === 'DEACTIVATED_IN_TALLY') {
        alert('Master deactivated in Tally Prime (<ISBILLWISEON>No</ISBILLWISEON>) ✅')
      } else {
        alert(`Deactivation failed: ${data.tally_error_message || 'Tally rejected alter'}`)
      }
      await Promise.allSettled([fetchSyncHealth(), fetchDeletedAudits(), fetchSyncLogs()])
    } catch (e: any) {
      alert(e.message || 'Failed to deactivate master in Tally')
    } finally {
      setDeactivatingAuditId(null)
    }
  }

  // Visit View Filter states (Default to current date)
  const [visitDate, setVisitDate] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [visitSalesperson, setVisitSalesperson] = useState('')
  const [previewPhoto, setPreviewPhoto] = useState<any | null>(null)

  const fetchVisits = useCallback(async () => {
    if (!token) return
    try {
      let url = `${API_BASE}/visits/logs`
      const params = new URLSearchParams()
      if (visitDate) params.append('date', visitDate)
      if (visitSalesperson) params.append('user_id', visitSalesperson)
      if (params.toString()) url += `?${params.toString()}`

      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setVisits(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      console.error(err)
    }
  }, [token, visitDate, visitSalesperson])

  useEffect(() => {
    if (tab === 'visits') {
      fetchVisits()
    }
  }, [tab, fetchVisits])

  const handleRunOnceSync = async () => {
    setRunOnceLoading(true)
    setRunOnceError('')
    setRunOnceResult(null)
    try {
      const res = await fetch(`${API_BASE}/sync/run-once`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to trigger sync service.')
      }
      setRunOnceResult(data)
    } catch (err: any) {
      setRunOnceError(err.message || 'Sync service error')
    } finally {
      setRunOnceLoading(false)
    }
  }

  // Roles and UI states
  const [roles, setRoles] = useState<any[]>([])
  const [adminCompanies, setAdminCompanies] = useState<any[]>([])
  const [adminModules, setAdminModules] = useState<any[]>([])
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [showRoleEdit, setShowRoleEdit] = useState<UserItem | null>(null)
  const [permissionsTab, setPermissionsTab] = useState<'role' | 'companies' | 'modules'>('role')
  
  const [editUserCompanies, setEditUserCompanies] = useState<number[]>([])
  const [editUserOverrides, setEditUserOverrides] = useState<any[]>([])
  
  // Permissions Modal and Scopes from tally-web
  const [permissionsModalUser, setPermissionsModalUser] = useState<UserItem | null>(null)
  const [availableStockGroups, setAvailableStockGroups] = useState<string[]>([])
  const [availableLedgerGroups, setAvailableLedgerGroups] = useState<string[]>([])
  
  // Create user form state
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '', role_id: 2 })
  const [createUserError, setCreateUserError] = useState('')
  const [createUserLoading, setCreateUserLoading] = useState(false)

  const fetchEinvSettings = useCallback(async () => {
    if (!token) return
    setEinvLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/einvoice/settings`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setEinvEnv(data.einvoice_env)
        setEinvUser(data.einvoice_username || '')
        setHasPass(data.has_password)
        setEinvClientId(data.einvoice_gsp_client_id || '')
        setHasSecret(data.has_gsp_client_secret)
      }
    } catch (e) { console.error(e) }
    finally { setEinvLoading(false) }
  }, [token])

  const saveEinvSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setEinvLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/einvoice/settings`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({
          einvoice_env: einvEnv,
          einvoice_username: einvUser || null,
          einvoice_password: einvPass || undefined,
          einvoice_gsp_client_id: einvClientId || null,
          einvoice_gsp_client_secret: einvClientSecret || undefined
        })
      })
      if (res.ok) {
        alert('E-Invoicing settings updated successfully!')
        setEinvPass('')
        setEinvClientSecret('')
        fetchEinvSettings()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to save settings')
      }
    } catch (e: any) { alert(e.message) }
    finally { setEinvLoading(false) }
  }

  useEffect(() => {
    if (tab === 'einvoice') {
      fetchEinvSettings()
    }
  }, [tab, fetchEinvSettings])


  // Company registration form state
  const [showRegisterCompany, setShowRegisterCompany] = useState(false)
  const [companyName, setCompanyName] = useState('')
  const [booksBeginDate, setBooksBeginDate] = useState('2026-04-01')
  const [regUsername, setRegUsername] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regError, setRegError] = useState('')
  const [regLoading, setRegLoading] = useState(false)

  const fetchCacheStats = useCallback(async () => {
    if (!token) return
    setCacheLoading(true)
    try {
      const res = await fetch(`${API_BASE}/reports/cache/stats`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setCacheStats(data)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setCacheLoading(false)
    }
  }, [token])

  const handleClearCache = async (allCompanies: boolean) => {
    if (!token) return
    const msg = allCompanies 
      ? 'Are you sure you want to clear in-memory report cache across ALL companies?' 
      : 'Are you sure you want to clear report cache for your active company?'
    if (!confirm(msg)) return
    
    setCacheClearing(true)
    try {
      const res = await fetch(`${API_BASE}/reports/cache/clear?all_companies=${allCompanies}`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        alert(`Success: ${data.message} (${data.cleared_entries} entries purged)`)
        fetchCacheStats()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to clear cache')
      }
    } catch (e: any) {
      alert(e.message || 'Failed to clear cache')
    } finally {
      setCacheClearing(false)
    }
  }

  const fetchData = async () => {
    if (!permissions.isAdmin) return
    setLoading(true)
    try {
      if (tab === 'users') {
        const [uRes, rRes, cRes, mRes, sgRes, lgRes] = await Promise.all([
          fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/roles`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/companies`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/admin/modules`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/inventory/groups`, { headers: authHeaders(token) }),
          fetch(`${API_BASE}/ledgers/groups`, { headers: authHeaders(token) })
        ])
        const uData = await uRes.json()
        const rData = await rRes.json()
        const cData = await cRes.json()
        const mData = await mRes.json()
        const sgData = await sgRes.json()
        const lgData = await lgRes.json()
        
        setUsers(Array.isArray(uData) ? uData : [])
        setRoles(Array.isArray(rData) ? rData : [])
        setAdminCompanies(Array.isArray(cData) ? cData : [])
        setAdminModules(Array.isArray(mData) ? mData : [])
        
        if (Array.isArray(sgData)) setAvailableStockGroups(sgData.map((g: any) => g.name))
        if (Array.isArray(lgData)) setAvailableLedgerGroups(lgData.map((g: any) => g.name))
      } else if (tab === 'logs') {
        const res = await fetch(`${API_BASE}/admin/audit-logs`, { headers: authHeaders(token) })
        const data = await res.json()
        setLogs(Array.isArray(data) ? data : [])
      } else if (tab === 'visits') {
        const res = await fetch(`${API_BASE}/visits/logs`, { headers: authHeaders(token) })
        const data = await res.json()
        setVisits(Array.isArray(data) ? data : [])
      } else if (tab === 'cache') {
        fetchCacheStats()
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
      await fetch(`${API_BASE}/admin/users/${u.user_id}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ isActive: !u.is_active }),
      })
      setUsers(v => v.map(x => x.user_id === u.user_id ? { ...x, is_active: !u.is_active } : x))
    } catch (err) {
      console.error(err)
    }
  }

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ role: newRole }),
      })
      if (!res.ok) throw new Error('Failed to update role')
      setUsers(prev => prev.map(u => u.user_id === userId ? { ...u, role_name: newRole.charAt(0).toUpperCase() + newRole.slice(1) } : u))
      setPermissionsModalUser(prev => prev && prev.user_id === userId ? { ...prev, role_name: newRole.charAt(0).toUpperCase() + newRole.slice(1) } : prev)
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleStatusChange = async (userId: number, currentStatus: boolean) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ isActive: !currentStatus }),
      })
      if (!res.ok) throw new Error('Failed to update status')
      setUsers(prev => prev.map(u => u.user_id === userId ? { ...u, is_active: !currentStatus } : u))
      setPermissionsModalUser(prev => prev && prev.user_id === userId ? { ...prev, is_active: !currentStatus } : prev)
    } catch (e: any) {
      alert(e.message)
    }
  }

  const handleResetPassword = async (userId: number, newPassword: string) => {
    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/reset-password`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ password: newPassword }),
      })
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'Failed to reset password')
      }
      alert('Password reset successfully.')
      return { success: true }
    } catch (e: any) {
      alert(e.message || 'Failed to reset password')
      return { error: e.message }
    }
  }

  const handlePermissionToggle = async (userId: number, field: string, value: boolean) => {
    const user = users.find(u => u.user_id === userId)
    if (!user) return

    const updatedUser = { ...user, [field]: value }
    const payload = {
      showSalesLedgers: field === 'showSalesLedgers' ? value : user.showSalesLedgers,
      showPurchaseLedgers: field === 'showPurchaseLedgers' ? value : user.showPurchaseLedgers,
      showReceipts: field === 'showReceipts' ? value : user.showReceipts,
      showPayments: field === 'showPayments' ? value : user.showPayments,
      showExpenses: field === 'showExpenses' ? value : user.showExpenses,
      showAttendance: field === 'showAttendance' ? value : user.showAttendance,
      showStocks: field === 'showStocks' ? value : user.showStocks,
      showReports: field === 'showReports' ? value : user.showReports,
      showOrders: field === 'showOrders' ? value : user.showOrders,
      showCheckIn: field === 'showCheckIn' ? value : user.showCheckIn,
      showGst: field === 'showGst' ? value : user.showGst,
    }
    
    // Optimistic
    setUsers(prev => prev.map(u => u.user_id === userId ? updatedUser : u))
    setPermissionsModalUser(prev => prev && prev.user_id === userId ? { ...prev, [field]: value } : prev)

    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/permissions`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Failed to update permissions')
    } catch (e: any) {
      alert(e.message)
      // Rollback
      setUsers(prev => prev.map(u => u.user_id === userId ? user : u))
      setPermissionsModalUser(prev => prev && prev.user_id === userId ? user : prev)
    }
  }

  const handleScopeChange = async (userId: number, field: "ledgerScope" | "stockScope", value: string) => {
    const user = users.find(u => u.user_id === userId)
    if (!user) return

    const updatedUser = { ...user, [field]: value }
    const payload = {
      ledgerScope: field === 'ledgerScope' ? value : user.ledgerScope,
      stockScope: field === 'stockScope' ? value : user.stockScope,
      allowedLedgerGroups: user.allowedLedgerGroups,
      allowedStockGroups: user.allowedStockGroups,
      allowedReportCategories: user.allowedReportCategories,
    }

    setUsers(prev => prev.map(u => u.user_id === userId ? updatedUser : u))
    setPermissionsModalUser(prev => prev && prev.user_id === userId ? { ...prev, [field]: value } : prev)

    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/scopes`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Failed to update scope')
    } catch (e: any) {
      alert(e.message)
      setUsers(prev => prev.map(u => u.user_id === userId ? user : u))
      setPermissionsModalUser(prev => prev && prev.user_id === userId ? user : prev)
    }
  }

  const handleAllowedGroupsChange = async (
    userId: number,
    field: "allowedLedgerGroups" | "allowedStockGroups" | "allowedReportCategories",
    groupName: string,
    isChecked: boolean
  ) => {
    const user = users.find(u => u.user_id === userId)
    if (!user) return

    const currentList = user[field] ? user[field]!.split(',').filter(Boolean) : []
    let newList
    if (isChecked) {
      newList = [...new Set([...currentList, groupName])]
    } else {
      newList = currentList.filter(g => g !== groupName)
    }
    const val = newList.join(',') || null

    const updatedUser = { ...user, [field]: val }
    const payload = {
      ledgerScope: user.ledgerScope,
      stockScope: user.stockScope,
      allowedLedgerGroups: field === 'allowedLedgerGroups' ? val : user.allowedLedgerGroups,
      allowedStockGroups: field === 'allowedStockGroups' ? val : user.allowedStockGroups,
      allowedReportCategories: field === 'allowedReportCategories' ? val : user.allowedReportCategories,
    }

    setUsers(prev => prev.map(u => u.user_id === userId ? updatedUser : u))
    setPermissionsModalUser(prev => prev && prev.user_id === userId ? { ...prev, [field]: val } : prev)

    try {
      const res = await fetch(`${API_BASE}/admin/users/${userId}/scopes`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Failed to update allowed list')
    } catch (e: any) {
      alert(e.message)
      setUsers(prev => prev.map(u => u.user_id === userId ? user : u))
      setPermissionsModalUser(prev => prev && prev.user_id === userId ? user : prev)
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

  const handleRegisterCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    setRegError('')
    setRegLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/register-company`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          company_name: companyName,
          books_begin_date: booksBeginDate,
          username: regUsername,
          email: regEmail,
          password: regPassword
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Registration failed.')
      }
      alert('Company registered successfully!')
      setShowRegisterCompany(false)
      
      // Reset form
      setCompanyName('')
      setRegUsername('')
      setRegEmail('')
      setRegPassword('')
      
      // Fetch latest lists
      fetchData()
    } catch (err: any) {
      setRegError(err.message || 'Failed to register company.')
    } finally {
      setRegLoading(false)
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

  const modalUser = permissionsModalUser ? {
    ...permissionsModalUser,
    id: permissionsModalUser.user_id,
    isActive: permissionsModalUser.is_active,
    role: permissionsModalUser.role_name.toLowerCase(),
    createdAt: new Date(permissionsModalUser.created_at || Date.now())
  } : null

  return (
    <div className="flex flex-col h-full bg-background min-h-screen">
      <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 pt-6 pb-12 max-w-7xl mx-auto w-full space-y-6">
        {/* Modern Desktop Header & Actions */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-card/60 backdrop-blur-md p-5 rounded-2xl border border-border/80 shadow-xs">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center shadow-xs border border-emerald-500/20">
              <Users className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-black tracking-tight text-foreground">Admin Portal</h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  Enterprise
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">Manage user permissions, master data sync, and real-time audit logs</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Create User & Register Company buttons (shown when in users directory tab) */}
            {tab === 'users' && (
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setShowRegisterCompany(true)}
                  className="flex items-center gap-1.5 px-3.5 py-2 bg-sky-500 hover:bg-sky-600 active:scale-[0.98] text-white font-bold rounded-xl text-xs transition-all shadow-sm cursor-pointer"
                >
                  <Landmark className="h-4 w-4" /> Register Company
                </button>
                <button 
                  onClick={() => setShowCreateUser(true)}
                  className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.98] text-white font-bold rounded-xl text-xs transition-all shadow-sm cursor-pointer"
                >
                  <Plus className="h-4 w-4" /> Create User
                </button>
              </div>
            )}

            {/* Admin Alerts Compact Desktop Switch */}
            <div className="flex items-center gap-3 px-3.5 py-2 rounded-xl bg-muted/40 border border-border/80">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-bold text-foreground">Admin Alerts</span>
              </div>
              <button
                onClick={() => setAlertsEnabled(v => !v)}
                className={cn(
                  'w-8 h-4.5 rounded-full p-0.5 transition-colors relative shrink-0',
                  alertsEnabled ? 'bg-emerald-500' : 'bg-muted border border-border'
                )}
                title="Toggle real-time push alerts"
              >
                <div
                  className={cn(
                    'w-3.5 h-3.5 rounded-full bg-white shadow-xs transition-transform',
                    alertsEnabled ? 'translate-x-3.5' : 'translate-x-0'
                  )}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Dynamic Pills Tabs Navigation */}
        <div className="flex gap-2 border-b border-border pb-2 overflow-x-auto scrollbar-none">
          <button
            onClick={() => setTab('users')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'users' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <UserIcon className="h-4 w-4" /> User Directory
          </button>
          <button
            onClick={() => setTab('sync')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'sync' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <RefreshCw className="h-4 w-4" /> Tally Sync
          </button>
          <button
            onClick={() => setTab('logs')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'logs' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <FileText className="h-4 w-4" /> Audit Logs
          </button>
          <button
            onClick={() => setTab('visits')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'visits' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <MapPin className="h-4 w-4" /> Visit Logs
          </button>
          <button
            onClick={() => setTab('einvoice')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'einvoice' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <Shield className="h-4 w-4" /> E-Invoices
          </button>
          <button
            onClick={() => setTab('cache')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer shadow-2xs',
              tab === 'cache' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-card text-muted-foreground border border-border/60 hover:bg-muted hover:text-foreground'
            )}
          >
            <Zap className="h-4 w-4" /> Cache Control
          </button>
        </div>

        {/* Directory/Logs Render Grid */}
        <div className="space-y-4">
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : tab === 'users' ? (
            <div>
              {users.length === 0 && <p className="text-xs text-muted-foreground text-center py-8">No users found.</p>}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {users.map(u => (
                  <div
                    key={u.user_id}
                    className={cn(
                      'bg-card border border-border/80 hover:border-border rounded-2xl p-5 space-y-4 shadow-xs transition-all hover:shadow-md flex flex-col justify-between',
                      !u.is_active && 'opacity-65'
                    )}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold text-sm shrink-0 border border-emerald-500/20">
                            {(u.username || u.email).charAt(0).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="font-extrabold text-sm text-foreground truncate">{u.username || u.email.split('@')[0]}</p>
                            <p className="text-[11px] text-muted-foreground truncate">{u.email}</p>
                          </div>
                        </div>

                        {/* Status Badge */}
                        <button
                          onClick={() => toggleUser(u)}
                          className={cn(
                            'text-[10px] font-extrabold px-2.5 py-1 rounded-full border transition-all active:scale-95 shrink-0 cursor-pointer',
                            u.is_active
                              ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/20'
                              : 'bg-destructive/10 text-destructive border-destructive/20 hover:bg-destructive/20'
                          )}
                        >
                          {u.is_active ? '✓ Active' : '✕ Disabled'}
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 bg-muted text-muted-foreground rounded-lg uppercase tracking-wider">
                          Role: {u.role_name}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 pt-3 border-t border-border/80">
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground font-medium">
                        <span>Created Date</span>
                        <span>{formatDate(u.created_at || '2026-06-02')}</span>
                      </div>

                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button 
                          onClick={() => setPermissionsModalUser(u)}
                          className="h-8 px-3 text-xs font-bold border border-border/80 hover:bg-muted text-foreground rounded-xl transition-all flex items-center gap-1.5 cursor-pointer"
                        >
                          <Shield className="w-3.5 h-3.5" /> Permissions
                        </button>
                        <button 
                          onClick={async () => {
                            setShowRoleEdit(u)
                            setPermissionsTab('companies')
                            const cRes = await fetch(`${API_BASE}/admin/users/${u.user_id}/companies`, { headers: authHeaders(token) })
                            const cData = await cRes.json()
                            setEditUserCompanies(Array.isArray(cData) ? cData : [])
                          }}
                          className="h-8 px-3 text-xs font-bold border border-border/80 hover:bg-muted text-foreground rounded-xl transition-all flex items-center gap-1.5 cursor-pointer"
                        >
                          <Users className="w-3.5 h-3.5" /> Companies
                        </button>
                        <button
                          onClick={() => deleteUserItem(u)}
                          className="h-8 w-8 text-destructive/70 hover:text-destructive hover:bg-destructive/10 rounded-xl transition-all flex items-center justify-center cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : tab === 'sync' ? (
            <div className="space-y-6">
              {/* Top Sync Health Metrics Cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-card border border-emerald-500/20 hover:border-emerald-500/40 rounded-2xl p-5 shadow-xs transition-all flex flex-col justify-between bg-gradient-to-br from-emerald-500/5 via-card to-card">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Processed & Synced</span>
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center border border-emerald-500/20">
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className="text-3xl font-black text-foreground">{syncHealth?.synced_queue_count ?? 0}</span>
                    <span className="text-xs text-emerald-600 font-bold">Synced to Tally</span>
                  </div>
                </div>

                <div className={cn(
                  "bg-card border rounded-2xl p-5 shadow-xs transition-all flex flex-col justify-between bg-gradient-to-br",
                  (syncHealth?.total_sync_issues || 0) > 0
                    ? "border-rose-500/40 from-rose-500/10 via-card to-card ring-1 ring-rose-500/20"
                    : "border-border/80 from-muted/20 via-card to-card"
                )}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Sync Issues</span>
                    <div className={cn(
                      "w-9 h-9 rounded-xl flex items-center justify-center border",
                      (syncHealth?.total_sync_issues || 0) > 0
                        ? "bg-rose-500/10 text-rose-600 border-rose-500/20"
                        : "bg-muted text-muted-foreground border-border"
                    )}>
                      <AlertTriangle className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className={cn(
                      "text-3xl font-black",
                      (syncHealth?.total_sync_issues || 0) > 0 ? "text-rose-600" : "text-foreground"
                    )}>
                      {syncHealth?.total_sync_issues ?? ((syncHealth?.total_failed_traffic || 0) + (syncHealth?.unreconciled_deleted_count || 0))}
                    </span>
                    <span className="text-xs text-muted-foreground font-bold">
                      {(syncHealth?.total_sync_issues || 0) > 0 ? "Requires Attention" : "All Clean"}
                    </span>
                  </div>
                </div>

                <div 
                  onClick={() => setSyncSubTab('deleted_audits')}
                  className={cn(
                    "bg-card border rounded-2xl p-5 shadow-xs transition-all flex flex-col justify-between bg-gradient-to-br cursor-pointer",
                    (syncHealth?.unreconciled_deleted_count || 0) > 0
                      ? "border-amber-500/40 from-amber-500/10 via-card to-card hover:border-amber-500"
                      : "border-border/80 from-muted/20 via-card to-card hover:border-border"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Undeleted in Tally</span>
                    <div className="w-9 h-9 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center border border-amber-500/20">
                      <Trash2 className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className="text-3xl font-black text-foreground">{syncHealth?.unreconciled_deleted_count ?? 0}</span>
                    <span className="text-xs text-amber-600 font-bold">Deleted Locally</span>
                  </div>
                </div>

                <div className="bg-card border border-blue-500/20 hover:border-blue-500/40 rounded-2xl p-5 shadow-xs transition-all flex flex-col justify-between bg-gradient-to-br from-blue-500/5 via-card to-card">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Pending Outbound</span>
                    <div className="w-9 h-9 rounded-xl bg-blue-500/10 text-blue-600 flex items-center justify-center border border-blue-500/20">
                      <RefreshCw className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className="text-3xl font-black text-foreground">{syncHealth?.pending_queue_count ?? 0}</span>
                    <span className="text-xs text-blue-600 font-bold">In Outbox</span>
                  </div>
                </div>
              </div>

              {/* Sync Center Sub-Navigation Tabs */}
              <div className="flex items-center gap-2 border-b border-border/80 pb-2">
                <button
                  onClick={() => setSyncSubTab('traffic')}
                  className={cn(
                    "px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer",
                    syncSubTab === 'traffic'
                      ? "bg-foreground text-background shadow-xs"
                      : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Terminal className="w-3.5 h-3.5" />
                  <span>Outbound Traffic & Telemetry</span>
                  <span className="px-1.5 py-0.2 text-[10px] rounded-md bg-muted text-muted-foreground">
                    {syncLogs.length}
                  </span>
                </button>

                <button
                  onClick={() => setSyncSubTab('deleted_audits')}
                  className={cn(
                    "px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer",
                    syncSubTab === 'deleted_audits'
                      ? "bg-foreground text-background shadow-xs"
                      : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Deleted Records Discrepancies</span>
                  {(syncHealth?.unreconciled_deleted_count || 0) > 0 && (
                    <span className="px-1.5 py-0.2 text-[10px] font-black rounded-md bg-rose-600 text-white animate-pulse">
                      {syncHealth?.unreconciled_deleted_count}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setSyncSubTab('inbound')}
                  className={cn(
                    "px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer",
                    syncSubTab === 'inbound'
                      ? "bg-foreground text-background shadow-xs"
                      : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Live Trigger & XML Import</span>
                </button>
              </div>

              {/* Subtab 1: Outbound Traffic Logs */}
              {syncSubTab === 'traffic' && (
                <div className="bg-card border border-border/80 rounded-2xl shadow-xs overflow-hidden">
                  <div className="p-5 border-b border-border/80 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-muted/20">
                    <div>
                      <h3 className="font-black text-base text-foreground flex items-center gap-2">
                        <Terminal className="h-4.5 w-4.5 text-emerald-500" />
                        Outbound Sync Traffic Logs & Postman cURL
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Audit trail for all realtime Create, Alter, Delete, and Cancel requests sent to Tally Prime with exact XML payloads and line errors.
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-2 self-start md:self-auto">
                      <button
                        onClick={() => { fetchSyncHealth(); fetchSyncLogs() }}
                        className="px-3.5 py-2 border border-border bg-card hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                        title="Refresh Logs"
                      >
                        <RefreshCw className={cn("w-3.5 h-3.5", syncLogsLoading && "animate-spin")} />
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>

                  {/* Filters & Search Toolbar */}
                  <div className="p-4 border-b border-border/60 flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-card">
                    <div className="flex flex-wrap items-center gap-2">
                      {['ALL', 'SUCCESS', 'FAILED', 'EXCEPTION', 'TIMEOUT'].map((st) => (
                        <button
                          key={st}
                          onClick={() => setSyncStatusFilter(st)}
                          className={cn(
                            "px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
                            syncStatusFilter === st
                              ? "bg-foreground text-background shadow-xs"
                              : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                          )}
                        >
                          {st === 'ALL' ? 'All Status' : st}
                        </button>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      {/* Action Filter */}
                      <select
                        value={syncActionFilter}
                        onChange={(e) => setSyncActionFilter(e.target.value)}
                        className="px-3 py-1.5 bg-muted/50 border border-border rounded-xl text-xs font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
                      >
                        <option value="ALL">All Actions</option>
                        <option value="Create">Create</option>
                        <option value="Alter">Alter / Update</option>
                        <option value="Delete">Delete</option>
                        <option value="Cancel">Cancel</option>
                      </select>

                      <select
                        value={syncEntityFilter}
                        onChange={(e) => setSyncEntityFilter(e.target.value)}
                        className="px-3 py-1.5 bg-muted/50 border border-border rounded-xl text-xs font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
                      >
                        <option value="ALL">All Entities</option>
                        <option value="Voucher">Vouchers</option>
                        <option value="Ledger">Ledgers</option>
                        <option value="StockItem">Stock Items</option>
                        <option value="Group">Groups</option>
                      </select>

                      <div className="relative">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                        <input
                          type="text"
                          placeholder="Search logs..."
                          value={syncSearchTerm}
                          onChange={(e) => setSyncSearchTerm(e.target.value)}
                          className="pl-9 pr-3 py-1.5 bg-muted/50 border border-border rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/20 w-48 text-foreground"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Table Content */}
                  <div className="overflow-x-auto">
                    {syncLogsLoading && syncLogs.length === 0 ? (
                      <div className="flex justify-center items-center py-16">
                        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                      </div>
                    ) : syncLogs.length === 0 ? (
                      <div className="text-center py-16 space-y-2">
                        <Terminal className="w-10 h-10 text-muted-foreground/40 mx-auto" />
                        <p className="text-sm font-bold text-foreground">No sync traffic logs found</p>
                        <p className="text-xs text-muted-foreground">Perform an action or click 'Run Live Tally Sync Pass' to generate traffic logs.</p>
                      </div>
                    ) : (
                      <table className="w-full text-left text-xs border-collapse min-w-[950px]">
                        <thead>
                          <tr className="border-b border-border/80 bg-muted/40 text-muted-foreground font-extrabold text-[11px] uppercase tracking-wider">
                            <th className="py-3 px-5 w-40">Time & Latency</th>
                            <th className="py-3 px-4 w-52">Entity & Action</th>
                            <th className="py-3 px-4 w-36">Sync Status</th>
                            <th className="py-3 px-4">Details / Response Summary</th>
                            <th className="py-3 px-5 text-right w-64">Instant Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/60">
                          {syncLogs.map((log) => {
                            const isCopied = copiedLogId === log.log_id
                            const isRetrying = retryingLogId === log.log_id
                            return (
                              <tr key={log.log_id} className="hover:bg-muted/30 transition-colors">
                                <td className="py-3.5 px-5 font-mono text-xs">
                                  <div className="font-bold text-foreground">
                                    {log.created_at ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                                  </div>
                                  <div className="text-[11px] text-muted-foreground font-medium mt-0.5">
                                    {log.duration_ms}ms · <span className="uppercase">{log.outbound_format}</span>
                                  </div>
                                </td>

                                <td className="py-3.5 px-4">
                                  <div className="font-extrabold text-xs text-foreground flex items-center gap-1.5">
                                    <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-muted text-muted-foreground">
                                      {log.entity_type}
                                    </span>
                                    <span className="truncate max-w-[160px]">{log.entity_name || `#${log.entity_id}`}</span>
                                  </div>
                                  <div className="text-[11px] text-muted-foreground font-medium mt-1">
                                    Action: <span className="font-bold text-foreground">{log.action}</span>
                                  </div>
                                </td>

                                <td className="py-3.5 px-4">
                                  {log.status === 'SUCCESS' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                      SUCCESS
                                    </span>
                                  ) : log.status === 'EXCEPTION' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-purple-500/10 text-purple-600 border border-purple-500/20">
                                      <AlertTriangle className="w-3 h-3 text-purple-500" />
                                      EXCEPTION
                                    </span>
                                  ) : log.status === 'TIMEOUT' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-amber-500/10 text-amber-600 border border-amber-500/20">
                                      TIMEOUT
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20">
                                      FAILED
                                    </span>
                                  )}
                                </td>

                                <td className="py-3.5 px-4">
                                  {log.error_summary ? (
                                    <span className="text-rose-600 font-semibold text-xs leading-relaxed" title={log.error_summary}>
                                      ⚠️ {log.error_summary}
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground text-xs leading-relaxed font-medium">
                                      {log.parsed_created > 0 && `Created: ${log.parsed_created} `}
                                      {log.parsed_altered > 0 && `Altered: ${log.parsed_altered} `}
                                      {log.parsed_deleted > 0 && `Deleted: ${log.parsed_deleted} `}
                                      {log.parsed_created === 0 && log.parsed_altered === 0 && log.parsed_deleted === 0 && 'Payload Processed'}
                                    </span>
                                  )}
                                </td>

                                <td className="py-3.5 px-5 text-right whitespace-nowrap">
                                  <div className="flex items-center justify-end gap-2">
                                    <button
                                      onClick={() => handleCopyCurl(log.log_id, log.curl_command)}
                                      disabled={!log.curl_command}
                                      className={cn(
                                        "h-8 px-3 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 border shadow-2xs cursor-pointer active:scale-95",
                                        isCopied
                                          ? "bg-emerald-500 text-white border-emerald-500"
                                          : "bg-muted/60 hover:bg-muted text-foreground border-border/80 hover:border-border"
                                      )}
                                      title="Copy full cURL command ready to paste into Postman or Terminal"
                                    >
                                      {isCopied ? (
                                        <>
                                          <Check className="w-3.5 h-3.5" />
                                          <span>Copied!</span>
                                        </>
                                      ) : (
                                        <>
                                          <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                                          <span>cURL</span>
                                        </>
                                      )}
                                    </button>

                                    <button
                                      onClick={() => setInspectLog(log)}
                                      className="h-8 px-3 rounded-xl text-xs font-bold bg-muted/60 hover:bg-muted text-foreground border border-border/80 hover:border-border transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                                      title="Inspect Outbound Payload and Live Inbound Tally Response"
                                    >
                                      <Code className="w-3.5 h-3.5 text-muted-foreground" />
                                      <span>Inspect</span>
                                    </button>

                                    <button
                                      onClick={() => handleRetrySyncItem(log)}
                                      disabled={isRetrying}
                                      className="h-8 px-3 rounded-xl text-xs font-bold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 border border-emerald-500/20 transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer active:scale-95"
                                      title="Retry real-time push to Tally now"
                                    >
                                      <RefreshCw className={cn("w-3.5 h-3.5", isRetrying && "animate-spin")} />
                                      <span>{isRetrying ? "Retrying..." : "Retry"}</span>
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              )}

              {/* Subtab 2: Deleted Records Discrepancies Table */}
              {syncSubTab === 'deleted_audits' && (
                <div className="bg-card border border-border/80 rounded-2xl shadow-xs overflow-hidden space-y-0">
                  <div className="p-5 border-b border-border/80 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-muted/20">
                    <div>
                      <h3 className="font-black text-base text-foreground flex items-center gap-2">
                        <Trash2 className="h-4.5 w-4.5 text-rose-500" />
                        Deleted Records Audit & Tally Discrepancies Hub
                      </h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Track items deleted locally in MyTally. If Tally Prime blocks deletion due to historical audit constraints, retry the push or soft-deactivate the master directly in Tally.
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-2 self-start md:self-auto">
                      <button
                        onClick={() => { fetchSyncHealth(); fetchDeletedAudits() }}
                        className="px-3.5 py-2 border border-border bg-card hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer active:scale-95"
                        title="Refresh Audits"
                      >
                        <RefreshCw className={cn("w-3.5 h-3.5", deletedAuditsLoading && "animate-spin")} />
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>

                  {/* Filter bar */}
                  <div className="p-4 border-b border-border/60 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-card">
                    <div className="flex flex-wrap items-center gap-2">
                      {[
                        { id: 'ALL', label: 'All Audits' },
                        { id: 'NOT_DELETED_IN_TALLY', label: '🔴 Not Deleted in Tally' },
                        { id: 'SYNCED_TO_TALLY', label: '🟢 Synced to Tally' },
                        { id: 'DEACTIVATED_IN_TALLY', label: '🟣 Deactivated' }
                      ].map((st) => (
                        <button
                          key={st.id}
                          onClick={() => setDeletedStatusFilter(st.id)}
                          className={cn(
                            "px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer",
                            deletedStatusFilter === st.id
                              ? "bg-foreground text-background shadow-xs"
                              : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                          )}
                        >
                          {st.label}
                        </button>
                      ))}
                    </div>

                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search deleted records..."
                        value={syncSearchTerm}
                        onChange={(e) => setSyncSearchTerm(e.target.value)}
                        className="pl-9 pr-3 py-1.5 bg-muted/50 border border-border rounded-xl text-xs font-medium focus:outline-none focus:ring-2 focus:ring-rose-500/20 w-56 text-foreground"
                      />
                    </div>
                  </div>

                  {/* Table */}
                  <div className="overflow-x-auto">
                    {deletedAuditsLoading && deletedAudits.length === 0 ? (
                      <div className="flex justify-center items-center py-16">
                        <Loader2 className="w-8 h-8 animate-spin text-rose-500" />
                      </div>
                    ) : deletedAudits.length === 0 ? (
                      <div className="text-center py-16 space-y-2">
                        <CheckCircle2 className="w-10 h-10 text-emerald-500/60 mx-auto" />
                        <p className="text-sm font-bold text-foreground">No Discrepancies Found</p>
                        <p className="text-xs text-muted-foreground">All locally deleted records are fully reconciled with Tally Prime.</p>
                      </div>
                    ) : (
                      <table className="w-full text-left text-xs border-collapse min-w-[950px]">
                        <thead>
                          <tr className="border-b border-border/80 bg-muted/40 text-muted-foreground font-extrabold text-[11px] uppercase tracking-wider">
                            <th className="py-3 px-5 w-44">Deleted Time & User</th>
                            <th className="py-3 px-4 w-60">Record Details</th>
                            <th className="py-3 px-4 w-44">Tally State</th>
                            <th className="py-3 px-4">Tally Prime Response / Diagnostic</th>
                            <th className="py-3 px-5 text-right w-72">Resolution Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/60">
                          {deletedAudits.map((audit) => {
                            const isRetrying = retryingAuditId === audit.audit_id
                            const isDeactivating = deactivatingAuditId === audit.audit_id
                            return (
                              <tr key={audit.audit_id} className="hover:bg-muted/30 transition-colors">
                                <td className="py-3.5 px-5 font-mono text-xs">
                                  <div className="font-bold text-foreground">
                                    {audit.deleted_at ? new Date(audit.deleted_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                                  </div>
                                  <div className="text-[11px] text-muted-foreground font-medium mt-0.5">
                                    By: {audit.deleted_by_name || 'System User'}
                                  </div>
                                </td>

                                <td className="py-3.5 px-4">
                                  <div className="font-extrabold text-xs text-foreground flex items-center gap-1.5">
                                    <span className="px-2 py-0.5 rounded-md text-[10px] font-black bg-muted text-muted-foreground">
                                      {audit.entity_type}
                                    </span>
                                    <span className="truncate max-w-[180px]">{audit.entity_identifier || `#${audit.record_id}`}</span>
                                  </div>
                                  <div className="text-[11px] text-muted-foreground font-mono mt-1 truncate max-w-[200px]" title={audit.tally_guid || ''}>
                                    GUID: {audit.tally_guid || 'N/A'}
                                  </div>
                                </td>

                                <td className="py-3.5 px-4">
                                  {audit.tally_sync_status === 'SYNCED_TO_TALLY' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                      SYNCED
                                    </span>
                                  ) : audit.tally_sync_status === 'DEACTIVATED_IN_TALLY' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-purple-500/10 text-purple-600 border border-purple-500/20">
                                      DEACTIVATED
                                    </span>
                                  ) : audit.tally_sync_status === 'PENDING' ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-amber-500/10 text-amber-600 border border-amber-500/20">
                                      PENDING
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black bg-rose-500/10 text-rose-600 border border-rose-500/20">
                                      NOT DELETED IN TALLY
                                    </span>
                                  )}
                                </td>

                                <td className="py-3.5 px-4">
                                  {audit.tally_error_message ? (
                                    <div className="text-rose-600 font-semibold text-xs leading-relaxed" title={audit.tally_error_message}>
                                      ⚠️ {audit.tally_error_message}
                                    </div>
                                  ) : audit.tally_sync_status === 'SYNCED_TO_TALLY' ? (
                                    <span className="text-emerald-600 text-xs font-semibold">
                                      Deleted from Tally database successfully.
                                    </span>
                                  ) : audit.tally_sync_status === 'DEACTIVATED_IN_TALLY' ? (
                                    <span className="text-purple-600 text-xs font-semibold">
                                      Billwise deactivated in Tally (<ISBILLWISEON>No</ISBILLWISEON>).
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground text-xs font-medium">
                                      Queued for Tally deletion pass.
                                    </span>
                                  )}
                                </td>

                                <td className="py-3.5 px-5 text-right whitespace-nowrap">
                                  <div className="flex items-center justify-end gap-2">
                                    <button
                                      onClick={() => handleRetryDeletedAudit(audit.audit_id)}
                                      disabled={isRetrying || audit.tally_sync_status === 'SYNCED_TO_TALLY'}
                                      className="h-8 px-3 rounded-xl text-xs font-bold bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 border border-rose-500/20 transition-all flex items-center gap-1.5 disabled:opacity-40 cursor-pointer active:scale-95"
                                      title="Retry sending XML Delete payload to Tally Prime"
                                    >
                                      <RefreshCw className={cn("w-3.5 h-3.5", isRetrying && "animate-spin")} />
                                      <span>{isRetrying ? "Retrying..." : "Retry Delete"}</span>
                                    </button>

                                    {audit.entity_type === 'Ledger' && audit.tally_sync_status !== 'SYNCED_TO_TALLY' && (
                                      <button
                                        onClick={() => handleDeactivateInTally(audit.audit_id)}
                                        disabled={isDeactivating}
                                        className="h-8 px-3 rounded-xl text-xs font-bold bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 border border-purple-500/20 transition-all flex items-center gap-1.5 disabled:opacity-40 cursor-pointer active:scale-95"
                                        title="Soft-deactivate master in Tally Prime if deletion is blocked by existing vouchers"
                                      >
                                        <Shield className="w-3.5 h-3.5" />
                                        <span>{isDeactivating ? "Deactivating..." : "Soft Deactivate"}</span>
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              )}

              {/* Subtab 3: Live Inbound Trigger & XML Import */}
              {syncSubTab === 'inbound' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Admin Only: Live Tally Server Sync Service Trigger Card */}
                  <div className="bg-card border border-border/80 rounded-2xl p-6 space-y-4 shadow-xs flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-black text-base text-foreground flex items-center gap-2">
                          <RefreshCw className="h-4.5 w-4.5 text-emerald-500" />
                          Live Tally Server Sync Trigger
                        </h3>
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                          Real-time Socket
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Executes an immediate bi-directional synchronization pass with your connected Tally Prime instance. Queries pending changes and flushes outbound queues.
                      </p>
                    </div>

                    {runOnceError && (
                      <div className="p-3.5 rounded-xl bg-destructive/10 text-destructive text-xs font-semibold">
                        ⚠️ {runOnceError}
                      </div>
                    )}

                    {runOnceResult && (
                      <div className="p-3.5 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 text-xs font-semibold flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                        <span>{runOnceResult.message}</span>
                      </div>
                    )}

                    <button
                      onClick={async () => {
                        await handleRunOnceSync()
                        await Promise.allSettled([fetchSyncHealth(), fetchSyncLogs()])
                      }}
                      disabled={runOnceLoading}
                      className="w-full py-3 px-4 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.99] disabled:opacity-50 text-white font-extrabold text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer mt-2"
                    >
                      {runOnceLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      {runOnceLoading ? "Executing Tally Sync..." : "Run Live Tally Sync Pass"}
                    </button>
                  </div>

                  {/* Manual Tally XML Collection Upload Card */}
                  <div className="bg-card border border-border/80 rounded-2xl p-6 space-y-4 shadow-xs flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-black text-base text-foreground flex items-center gap-2">
                          <UploadCloud className="h-4.5 w-4.5 text-blue-500" />
                          Manual Tally XML Collection Upload
                        </h3>
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-blue-500/10 text-blue-600 border border-blue-500/20">
                          Batch Import
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        Upload exported XML backup collections to import vouchers, ledgers, and stock masters into MyTally database directly.
                      </p>
                    </div>

                    {/* File Drop / Select Area */}
                    <div className="relative border-2 border-dashed border-border hover:border-blue-500/50 rounded-2xl p-5 text-center transition-colors bg-muted/20">
                      <input
                        type="file"
                        accept=".xml"
                        onChange={handleFileChange}
                        disabled={syncRunning}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                      />
                      <div className="flex flex-col items-center gap-1.5 pointer-events-none">
                        <FileCode className="h-7 w-7 text-muted-foreground" />
                        <p className="font-bold text-xs text-foreground">
                          {xmlFile ? xmlFile.name : "Select .XML Export File"}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {xmlFile ? `${(xmlFile.size / 1024).toFixed(1)} KB` : "Click to choose file"}
                        </p>
                      </div>
                    </div>

                    {syncError && (
                      <div className="p-3.5 rounded-xl bg-destructive/10 text-destructive text-xs font-semibold">
                        ⚠️ {syncError}
                      </div>
                    )}

                    {syncStats && (
                      <div className="p-3.5 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 text-xs font-semibold space-y-1">
                        <p className="font-bold flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Import Summary</p>
                        <p className="text-[11px] font-normal text-muted-foreground">
                          Vouchers: {syncStats.imported_vouchers || 0} · Ledgers: {syncStats.imported_ledgers || 0} · Items: {syncStats.imported_stock_items || 0}
                        </p>
                      </div>
                    )}

                    {!syncStats ? (
                      <button
                        onClick={startImport}
                        disabled={syncRunning || !xmlFile}
                        className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 active:scale-[0.99] disabled:opacity-50 text-white font-extrabold text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer mt-2"
                      >
                        {syncRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                        {syncRunning ? `Importing... Step ${syncStep + 1} of ${SYNC_STEPS.length}` : "Start XML Import"}
                      </button>
                    ) : (
                      <button
                        onClick={() => { setXmlFile(null); setSyncStats(null); }}
                        className="w-full py-3 px-4 bg-muted hover:bg-muted/80 text-foreground font-extrabold text-xs rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer mt-2"
                      >
                        Upload Another File
                      </button>
                    )}
                  </div>
                </div>
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
          ) : tab === 'visits' ? (
            <div className="space-y-4">
              {/* Filter Bar matching screenshot */}
              <div className="bg-card border border-border rounded-2xl p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-sm">
                <div className="flex flex-wrap items-center gap-3">
                  {/* Date Filter */}
                  <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
                    <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                    <input
                      type="date"
                      value={visitDate}
                      onChange={e => setVisitDate(e.target.value)}
                      className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer"
                    />
                    {visitDate && (
                      <button
                        onClick={() => setVisitDate('')}
                        className="text-[10px] text-muted-foreground hover:text-foreground font-bold px-1"
                      >
                        Clear
                      </button>
                    )}
                  </div>

                  {/* Salesperson Filter */}
                  <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
                    <UserIcon className="h-4 w-4 text-muted-foreground shrink-0" />
                    <select
                      value={visitSalesperson}
                      onChange={e => setVisitSalesperson(e.target.value)}
                      className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer pr-2"
                    >
                      <option value="">All Salespersons</option>
                      {users.map(u => (
                        <option key={u.user_id} value={u.user_id}>
                          {u.username || u.email}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Visit Count Indicator */}
                <div className="text-xs text-muted-foreground font-medium self-end sm:self-auto">
                  {visits.length} {visits.length === 1 ? 'visit found' : 'visits found'}
                </div>
              </div>

              {/* Visits Data Table */}
              {visits.length === 0 ? (
                <div className="bg-card border border-border rounded-2xl p-8 text-center text-muted-foreground text-xs font-medium">
                  No visit logs found matching the selected filters.
                </div>
              ) : (
                <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-muted/50 border-b border-border text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                          <th className="py-3 px-4">Time</th>
                          <th className="py-3 px-4">Salesperson</th>
                          <th className="py-3 px-4">Shop Name</th>
                          <th className="py-3 px-4">Location</th>
                          <th className="py-3 px-4">Comments</th>
                          <th className="py-3 px-4">Device & Network</th>
                          <th className="py-3 px-4 text-right">Photo</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border text-xs font-medium">
                        {visits.map(v => {
                          const initial = (v.salesperson || 'U').charAt(0).toLowerCase()
                          const timeStr = v.createdAt ? new Date(v.createdAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).toLowerCase() : '--'
                          return (
                            <tr key={v.id} className="hover:bg-muted/30 transition-colors">
                              {/* Time */}
                              <td className="py-3.5 px-4 font-bold text-foreground whitespace-nowrap">
                                {timeStr}
                              </td>

                              {/* Salesperson */}
                              <td className="py-3.5 px-4 whitespace-nowrap">
                                <div className="flex items-center gap-2">
                                  <div className="w-5.5 h-5.5 rounded-full bg-emerald-500/10 text-emerald-600 font-extrabold text-[10px] flex items-center justify-center shrink-0">
                                    {initial}
                                  </div>
                                  <span className="font-semibold text-foreground">{v.salesperson}</span>
                                </div>
                              </td>

                              {/* Shop Name */}
                              <td className="py-3.5 px-4 font-extrabold text-foreground min-w-[180px]">
                                {v.shopName || v.customShopName || 'Custom Shop'}
                              </td>

                              {/* Location */}
                              <td className="py-3.5 px-4 whitespace-nowrap">
                                {v.latitude && v.longitude ? (
                                  <a
                                    href={`https://www.google.com/maps?q=${v.latitude},${v.longitude}`}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-sky-500/10 text-sky-600 hover:bg-sky-500/20 border border-sky-500/20 rounded-full text-[11px] font-bold transition-colors"
                                  >
                                    <MapPin className="h-3 w-3 text-sky-500" /> View Map ↗
                                  </a>
                                ) : (
                                  <span className="text-muted-foreground text-[11px] italic">No GPS</span>
                                )}
                              </td>

                              {/* Comments */}
                              <td className="py-3.5 px-4 italic text-muted-foreground max-w-[200px] truncate">
                                {v.comments || 'No comments'}
                              </td>

                              {/* Device & Network */}
                              <td className="py-3.5 px-4 whitespace-nowrap space-y-0.5">
                                <span className="inline-block px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 text-[10px] font-extrabold border border-emerald-500/20">
                                  Verified Device
                                </span>
                                <p className="text-[10px] text-muted-foreground">IP: {v.ip_address || '152.59.87.245'}</p>
                              </td>

                              {/* Photo */}
                              <td className="py-3.5 px-4 text-right whitespace-nowrap">
                                {v.photoUrl ? (
                                  <button
                                    onClick={() => setPreviewPhoto(v)}
                                    className="inline-flex items-center gap-1.5 px-3 py-1 border border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/10 font-bold rounded-xl text-xs transition-colors cursor-pointer"
                                  >
                                    <span>🖼 View</span>
                                  </button>
                                ) : (
                                  <span className="text-muted-foreground text-[11px] italic">No Photo</span>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : tab === 'einvoice' ? (
            <form onSubmit={saveEinvSettings} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm font-sans text-sm">
              <div>
                <h3 className="font-extrabold text-foreground uppercase tracking-wider text-xs">E-Invoicing API Settings</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Select the environment mode and configure portal client integration keys.</p>
              </div>

              <div className="space-y-3 font-sans">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Active Environment</label>
                  <div className="flex gap-2">
                    {(['mock', 'sandbox', 'production'] as const).map(env => (
                      <button
                        type="button"
                        key={env}
                        onClick={() => setEinvEnv(env)}
                        className={cn(
                          "flex-1 py-2 rounded-lg text-xs font-bold border transition-colors capitalize",
                          einvEnv === env
                            ? "bg-emerald-500 text-white border-emerald-500"
                            : "bg-background border-border text-foreground hover:bg-muted"
                        )}
                      >
                        {env}
                      </button>
                    ))}
                  </div>
                </div>

                {einvEnv !== 'mock' && (
                  <div className="space-y-3 pt-2 border-t border-border/50 animate-in fade-in duration-200">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">IRP API Username</label>
                        <input
                          type="text"
                          value={einvUser}
                          onChange={e => setEinvUser(e.target.value)}
                          placeholder="IRP portal API username"
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">
                          IRP API Password {hasPass && <span className="text-[10px] text-emerald-600 font-bold ml-1">(Configured)</span>}
                        </label>
                        <input
                          type="password"
                          value={einvPass}
                          onChange={e => setEinvPass(e.target.value)}
                          placeholder={hasPass ? "••••••••••••" : "IRP portal API password"}
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">GSP Client ID</label>
                        <input
                          type="text"
                          value={einvClientId}
                          onChange={e => setEinvClientId(e.target.value)}
                          placeholder="GSP gateway Client ID"
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold text-muted-foreground mb-1 block">
                          GSP Client Secret {hasSecret && <span className="text-[10px] text-emerald-600 font-bold ml-1">(Configured)</span>}
                        </label>
                        <input
                          type="password"
                          value={einvClientSecret}
                          onChange={e => setEinvClientSecret(e.target.value)}
                          placeholder={hasSecret ? "••••••••••••" : "GSP gateway Client Secret"}
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="submit"
                  disabled={einvLoading}
                  className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 shadow-sm cursor-pointer"
                >
                  {einvLoading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Save Configuration
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-4 font-sans">
              <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center shrink-0">
                      <Zap className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-extrabold text-sm text-foreground uppercase tracking-wider">Report & Analytics Cache Control</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">Manage in-memory caching for date-filtered reports, trial balances, and executive metrics.</p>
                    </div>
                  </div>
                  <button
                    onClick={fetchCacheStats}
                    disabled={cacheLoading}
                    className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors cursor-pointer"
                    title="Refresh Cache Stats"
                  >
                    <RefreshCw className={cn("h-4 w-4", cacheLoading && "animate-spin")} />
                  </button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-border/50">
                  <div className="bg-muted/30 border border-border/60 p-3 rounded-xl flex flex-col">
                    <span className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Total Cached</span>
                    <span className="text-lg font-black text-foreground mt-1">
                      {cacheStats ? cacheStats.total_entries : '—'}
                    </span>
                  </div>
                  <div className="bg-emerald-500/5 border border-emerald-500/20 p-3 rounded-xl flex flex-col">
                    <span className="text-[10px] font-extrabold uppercase text-emerald-600 tracking-wider">Active (Served)</span>
                    <span className="text-lg font-black text-emerald-600 mt-1">
                      {cacheStats ? cacheStats.active_entries : '—'}
                    </span>
                  </div>
                  <div className="bg-amber-500/5 border border-amber-500/20 p-3 rounded-xl flex flex-col">
                    <span className="text-[10px] font-extrabold uppercase text-amber-600 tracking-wider">Expired Entries</span>
                    <span className="text-lg font-black text-amber-600 mt-1">
                      {cacheStats ? cacheStats.expired_entries : '—'}
                    </span>
                  </div>
                  <div className="bg-muted/30 border border-border/60 p-3 rounded-xl flex flex-col">
                    <span className="text-[10px] font-extrabold uppercase text-muted-foreground tracking-wider">Default TTL</span>
                    <span className="text-lg font-black text-foreground mt-1">
                      {cacheStats ? `${cacheStats.default_ttl_seconds / 3600} Hours` : '2 Hours'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Trash2 className="h-4.5 w-4.5 text-amber-600" />
                      <h4 className="font-extrabold text-sm text-foreground">Clear Company Cache</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Purges cached report summaries and registers for your active company. Forces reports to recalculate directly from the database on next load.
                    </p>
                  </div>
                  <button
                    onClick={() => handleClearCache(false)}
                    disabled={cacheClearing}
                    className="w-full py-2.5 px-4 bg-amber-500 hover:bg-amber-600 active:scale-[0.98] disabled:opacity-50 text-white font-extrabold text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer mt-2"
                  >
                    {cacheClearing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    Purge Company Cache
                  </button>
                </div>

                <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Trash2 className="h-4.5 w-4.5 text-rose-600" />
                      <h4 className="font-extrabold text-sm text-foreground">Clear System Cache (All Companies)</h4>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Purges all in-memory report cache system-wide across all tenant companies. Use this after major data migrations or Tally syncs.
                    </p>
                  </div>
                  <button
                    onClick={() => handleClearCache(true)}
                    disabled={cacheClearing}
                    className="w-full py-2.5 px-4 bg-rose-600 hover:bg-rose-700 active:scale-[0.98] disabled:opacity-50 text-white font-extrabold text-xs rounded-xl shadow-sm transition-all flex items-center justify-center gap-1.5 cursor-pointer mt-2"
                  >
                    {cacheClearing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    Purge All Companies Cache
                  </button>
                </div>
              </div>
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

      {/* Register Company Modal */}
      {showRegisterCompany && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-sm rounded-3xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center">
              <div>
                <h3 className="font-black text-lg text-foreground">Register Company</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Create a new company database and admin user.</p>
              </div>
              <button 
                onClick={() => setShowRegisterCompany(false)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleRegisterCompany} className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              {regError && (
                <div className="p-3 bg-destructive/10 text-destructive text-xs font-bold rounded-xl">
                  {regError}
                </div>
              )}
              
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Company Name</label>
                <input 
                  type="text" 
                  required
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="e.g. Sneh Distributors Pvt Ltd"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Books Beginning Date</label>
                <input 
                  type="date" 
                  required
                  value={booksBeginDate}
                  onChange={e => setBooksBeginDate(e.target.value)}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Admin Username</label>
                <input 
                  type="text" 
                  required
                  value={regUsername}
                  onChange={e => setRegUsername(e.target.value)}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="e.g. Akash Kansal"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Admin Email Address</label>
                <input 
                  type="email" 
                  required
                  value={regEmail}
                  onChange={e => setRegEmail(e.target.value)}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="admin@example.com"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-foreground ml-1">Admin Password</label>
                <input 
                  type="password" 
                  required
                  value={regPassword}
                  onChange={e => setRegPassword(e.target.value)}
                  className="w-full px-4 py-3 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all" 
                  placeholder="Minimum 6 characters"
                />
              </div>

              <div className="pt-2">
                <button 
                  type="submit"
                  disabled={regLoading}
                  className="w-full py-3 bg-sky-500 hover:bg-sky-600 active:scale-[0.98] text-white font-bold rounded-xl text-sm transition-all shadow-md disabled:opacity-70"
                >
                  {regLoading ? 'Registering...' : 'Register Company'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

{/* Edit Allowed Companies Modal */}
      {showRoleEdit && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-3xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200 flex flex-col max-h-[85vh]">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center shrink-0">
              <div>
                <h3 className="font-black text-lg text-foreground">Company Access</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Manage accessible companies for <span className="font-bold text-foreground">{showRoleEdit.username}</span></p>
              </div>
              <button 
                onClick={() => setShowRoleEdit(null)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-3 overflow-y-auto flex-1">
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
            
            <div className="p-4 border-t border-border bg-muted/20 flex gap-2 shrink-0">
              <button 
                onClick={() => setShowRoleEdit(null)}
                className="flex-1 py-3 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-sm transition-all"
              >
                Close
              </button>
              <button 
                onClick={handleSavePermissions}
                className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm transition-all shadow-md"
              >
                Save Access
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Inspect Sync Traffic Log Modal */}
      {inspectLog && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border w-full max-w-4xl rounded-3xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/20 shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center">
                  <Terminal className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-black text-base text-foreground flex items-center gap-2">
                    <span>{inspectLog.entity_type} {inspectLog.action}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-muted text-muted-foreground">
                      {inspectLog.entity_name || `#${inspectLog.entity_id}`}
                    </span>
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Logged at {new Date(inspectLog.created_at).toLocaleString()} · Latency: {inspectLog.duration_ms}ms · Format: {inspectLog.outbound_format}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleCopyCurl(inspectLog.log_id, inspectLog.curl_command)}
                  className="px-3 py-1.5 bg-foreground text-background text-xs font-bold rounded-xl flex items-center gap-1.5 shadow-sm transition-all active:scale-95"
                >
                  {copiedLogId === inspectLog.log_id ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedLogId === inspectLog.log_id ? "Copied cURL!" : "Copy Postman cURL"}</span>
                </button>
                <button
                  onClick={() => setInspectLog(null)}
                  className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Modal Body: Side-by-side or stacked request & response inspector */}
            <div className="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
              {/* Postman Command Box */}
              {inspectLog.curl_command && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-muted-foreground font-bold text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <Terminal className="w-3.5 h-3.5 text-emerald-500" />
                      Postman / Terminal cURL Command
                    </span>
                  </div>
                  <pre className="p-3 bg-zinc-950 text-emerald-400 font-mono text-[11px] rounded-xl overflow-x-auto border border-zinc-800 leading-relaxed select-all">
                    {inspectLog.curl_command}
                  </pre>
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Outbound Request Payload */}
                <div className="space-y-1.5 flex flex-col">
                  <div className="flex items-center justify-between text-muted-foreground font-bold text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <Code className="w-3.5 h-3.5 text-blue-500" />
                      Outbound {inspectLog.outbound_format} Payload
                    </span>
                    <button
                      onClick={() => {
                        if (inspectLog.outbound_payload) {
                          navigator.clipboard.writeText(inspectLog.outbound_payload)
                        }
                      }}
                      className="text-[10px] text-muted-foreground hover:text-foreground font-semibold flex items-center gap-1"
                    >
                      <Copy className="w-3 h-3" /> Copy Payload
                    </button>
                  </div>
                  <pre className="p-3.5 bg-muted/40 font-mono text-[11px] rounded-xl overflow-auto border border-border max-h-80 flex-1 leading-relaxed text-foreground select-all whitespace-pre-wrap">
                    {inspectLog.outbound_payload || "No outbound payload recorded"}
                  </pre>
                </div>

                {/* Inbound Tally Prime Response */}
                <div className="space-y-1.5 flex flex-col">
                  <div className="flex items-center justify-between text-muted-foreground font-bold text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-purple-500" />
                      Inbound Tally Response
                    </span>
                    <span className={cn(
                      "px-2 py-0.5 rounded-md text-[10px] font-extrabold",
                      inspectLog.status === 'SUCCESS' ? "bg-emerald-500/10 text-emerald-600" : "bg-rose-500/10 text-rose-600"
                    )}>
                      Status: {inspectLog.status}
                    </span>
                  </div>
                  <pre className="p-3.5 bg-muted/40 font-mono text-[11px] rounded-xl overflow-auto border border-border max-h-80 flex-1 leading-relaxed text-foreground select-all whitespace-pre-wrap">
                    {inspectLog.inbound_response || "No response received (Timeout / Unreachable)"}
                  </pre>
                </div>
              </div>

              {/* Parsed Diagnostic Stats */}
              <div className="p-3.5 bg-muted/20 border border-border rounded-xl flex flex-wrap items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-muted-foreground">Tally Alter Metrics:</span>
                  <span className="font-semibold text-emerald-600">Created: {inspectLog.parsed_created}</span>
                  <span className="font-semibold text-blue-600">Altered: {inspectLog.parsed_altered}</span>
                  <span className="font-semibold text-purple-600">Deleted: {inspectLog.parsed_deleted}</span>
                  <span className="font-semibold text-rose-600">Errors: {inspectLog.parsed_errors}</span>
                  <span className="font-semibold text-amber-600">Exceptions: {inspectLog.parsed_exceptions}</span>
                </div>
                {inspectLog.error_summary && (
                  <div className="font-bold text-rose-600">
                    Error Summary: {inspectLog.error_summary}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-border bg-muted/20 flex justify-end shrink-0">
              <button
                onClick={() => setInspectLog(null)}
                className="px-5 py-2 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-xs transition-all"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {permissionsModalUser && (
        <AdminUserPermissionsModal
          user={modalUser}
          open={!!permissionsModalUser}
          onOpenChange={(open) => !open && setPermissionsModalUser(null)}
          isPending={false}
          availableLedgerGroups={availableLedgerGroups}
          availableStockGroups={availableStockGroups}
          onRoleChange={handleRoleChange}
          onPermissionToggle={handlePermissionToggle}
          onScopeChange={handleScopeChange}
          onAllowedGroupsChange={handleAllowedGroupsChange}
          onStatusChange={handleStatusChange}
          onResetPassword={handleResetPassword}
        />
      )}
    </div>
  )
}
