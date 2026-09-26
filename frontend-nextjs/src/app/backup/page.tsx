'use client'

import { useEffect, useState, useRef, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatDate, cn } from '@/lib/utils'
import {
  Database,
  Download,
  RotateCcw,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  Server,
  HardDrive,
  FileArchive,
  ShieldCheck,
  Search,
  Check,
  Clock,
  Layers,
  FileText,
  AlertTriangle,
  ArrowUpRight,
  ChevronDown
} from 'lucide-react'

type TallyCompany = {
  name: string
  guid?: string
  address?: string
  state?: string
  country?: string
  pincode?: string
  phone?: string
  mobile?: string
  email?: string
  website?: string
  gstin?: string
  starting_from?: string
  books_from?: string
}

type BackupRecord = {
  id: string
  company_name: string
  file_name: string
  file_size_bytes: number
  record_counts: Record<string, number>
  total_masters: number
  total_vouchers: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress_percent: number
  progress_message: string
  error_message: string
  checksum_sha256: string
  created_at: string
  completed_at?: string
}

type RestoreRecord = {
  id: string
  backup_id: string
  company_name: string
  target_company_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress_percent: number
  progress_message: string
  summary: Record<string, { total: number; created: number; altered: number; errors: number }>
  error_message: string
  started_at: string
  completed_at?: string
}

export default function BackupPage() {
  const { token } = useAuth()
  const router = useRouter()

  // Tally connection state
  const [tallyConnected, setTallyConnected] = useState<boolean | null>(null)
  const [tallyUrl, setTallyUrl] = useState<string>('http://192.168.1.42:9000')
  const [tallyMessage, setTallyMessage] = useState<string>('')
  const [companies, setCompanies] = useState<TallyCompany[]>([])
  const [checkingTally, setCheckingTally] = useState<boolean>(false)

  // Backup creation state
  const [selectedCompany, setSelectedCompany] = useState<string>('')
  const [customCompany, setCustomCompany] = useState<string>('')
  const [backupNotes, setBackupNotes] = useState<string>('')
  const [activeBackupId, setActiveBackupId] = useState<string | null>(null)
  const [activeBackup, setActiveBackup] = useState<BackupRecord | null>(null)
  const [creatingBackup, setCreatingBackup] = useState<boolean>(false)

  // Backups list state
  const [backups, setBackups] = useState<BackupRecord[]>([])
  const [loadingBackups, setLoadingBackups] = useState<boolean>(true)
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Restore state
  const [restoreModalBackup, setRestoreModalBackup] = useState<BackupRecord | null>(null)
  const [restoreTargetCompany, setRestoreTargetCompany] = useState<string>('')
  const [activeRestoreId, setActiveRestoreId] = useState<string | null>(null)
  const [activeRestore, setActiveRestore] = useState<RestoreRecord | null>(null)
  const [restoring, setRestoring] = useState<boolean>(false)
  const [showRestoreSummaryModal, setShowRestoreSummaryModal] = useState<boolean>(false)

  // Delete modal state
  const [deleteConfirmBackup, setDeleteConfirmBackup] = useState<BackupRecord | null>(null)
  const [deleting, setDeleting] = useState<boolean>(false)

  // Polling timers
  const backupPollRef = useRef<NodeJS.Timeout | null>(null)
  const restorePollRef = useRef<NodeJS.Timeout | null>(null)

  // Format bytes to human readable string
  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
  }

  // 1. Check Tally connectivity & fetch open companies
  const checkTallyStatus = async () => {
    setCheckingTally(true)
    try {
      const res = await fetch(`${API_BASE}/backup/tally/status`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setTallyConnected(data.connected)
        setTallyUrl(data.tally_url || 'http://192.168.1.42:9000')
        setTallyMessage(data.message || '')
        const compList = Array.isArray(data.companies) ? data.companies : []
        setCompanies(compList)
        if (compList.length > 0 && !selectedCompany) {
          setSelectedCompany(compList[0].name)
        }
      } else {
        setTallyConnected(false)
        setTallyMessage(`HTTP Error ${res.status}: Cannot reach backup service`)
      }
    } catch (e: any) {
      setTallyConnected(false)
      setTallyMessage(e.message || 'Cannot reach backup API endpoint')
    } finally {
      setCheckingTally(false)
    }
  }

  // 2. Fetch historical backups
  const fetchBackups = async () => {
    setLoadingBackups(true)
    try {
      const res = await fetch(`${API_BASE}/backup/list`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setBackups(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.error('Error fetching backups:', e)
    } finally {
      setLoadingBackups(false)
    }
  }

  useEffect(() => {
    checkTallyStatus()
    fetchBackups()

    return () => {
      if (backupPollRef.current) clearInterval(backupPollRef.current)
      if (restorePollRef.current) clearInterval(restorePollRef.current)
    }
  }, [])

  // 3. Polling for ongoing backup
  useEffect(() => {
    if (!activeBackupId) return

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/backup/${activeBackupId}/status`, {
          headers: authHeaders(token)
        })
        if (res.ok) {
          const data: BackupRecord = await res.json()
          setActiveBackup(data)
          if (data.status === 'completed' || data.status === 'failed') {
            setCreatingBackup(false)
            if (backupPollRef.current) {
              clearInterval(backupPollRef.current)
              backupPollRef.current = null
            }
            fetchBackups()
          }
        }
      } catch (err) {
        console.error('Error polling backup status:', err)
      }
    }

    poll()
    backupPollRef.current = setInterval(poll, 1500)

    return () => {
      if (backupPollRef.current) clearInterval(backupPollRef.current)
    }
  }, [activeBackupId])

  // 4. Polling for ongoing restore
  useEffect(() => {
    if (!activeRestoreId) return

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/backup/restore/${activeRestoreId}/status`, {
          headers: authHeaders(token)
        })
        if (res.ok) {
          const data: RestoreRecord = await res.json()
          setActiveRestore(data)
          if (data.status === 'completed' || data.status === 'failed') {
            setRestoring(false)
            setShowRestoreSummaryModal(true)
            if (restorePollRef.current) {
              clearInterval(restorePollRef.current)
              restorePollRef.current = null
            }
          }
        }
      } catch (err) {
        console.error('Error polling restore status:', err)
      }
    }

    poll()
    restorePollRef.current = setInterval(poll, 1500)

    return () => {
      if (restorePollRef.current) clearInterval(restorePollRef.current)
    }
  }, [activeRestoreId])

  // 5. Handle Start Backup
  const handleCreateBackup = async () => {
    const comp = selectedCompany === '__custom__' ? customCompany.trim() : (selectedCompany || customCompany.trim())
    if (!comp) {
      alert('Please select or specify a company to backup')
      return
    }

    setCreatingBackup(true)
    setActiveBackup(null)

    try {
      const res = await fetch(`${API_BASE}/backup/create`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          company_name: comp,
          notes: backupNotes.trim() || undefined
        })
      })

      const data = await res.json()
      if (res.ok && data.success && data.data?.backup_id) {
        setActiveBackupId(data.data.backup_id)
        setBackupNotes('')
      } else {
        alert(data.detail || data.message || 'Failed to start backup')
        setCreatingBackup(false)
      }
    } catch (e: any) {
      alert(`Error starting backup: ${e.message}`)
      setCreatingBackup(false)
    }
  }

  // 6. Handle Start Restore
  const handleConfirmRestore = async () => {
    if (!restoreModalBackup) return

    const targetComp = restoreTargetCompany.trim() || restoreModalBackup.company_name
    setRestoring(true)
    setRestoreModalBackup(null)
    setActiveRestore(null)

    try {
      const res = await fetch(`${API_BASE}/backup/restore`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          backup_id: restoreModalBackup.id,
          company_name: targetComp
        })
      })

      const data = await res.json()
      if (res.ok && data.success && data.data?.restore_id) {
        setActiveRestoreId(data.data.restore_id)
      } else {
        alert(data.detail || data.message || 'Failed to start restore')
        setRestoring(false)
      }
    } catch (e: any) {
      alert(`Error starting restore: ${e.message}`)
      setRestoring(false)
    }
  }

  // 7. Handle Delete Backup
  const handleDeleteBackup = async () => {
    if (!deleteConfirmBackup) return
    setDeleting(true)
    try {
      const res = await fetch(`${API_BASE}/backup/${deleteConfirmBackup.id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (res.ok) {
        setBackups(prev => prev.filter(b => b.id !== deleteConfirmBackup.id))
        setDeleteConfirmBackup(null)
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete backup')
      }
    } catch (e: any) {
      alert(`Error deleting backup: ${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  // Filtered backups list
  const filteredBackups = useMemo(() => {
    if (!searchQuery.trim()) return backups
    const q = searchQuery.toLowerCase()
    return backups.filter(b =>
      b.id.toLowerCase().includes(q) ||
      b.company_name.toLowerCase().includes(q) ||
      b.file_name.toLowerCase().includes(q)
    )
  }, [backups, searchQuery])

  return (
    <div className="min-h-screen bg-background text-foreground pb-20">
      {/* Top Header */}
      <div className="border-b border-border/60 bg-card/60 backdrop-blur-md sticky top-0 z-30 px-4 lg:px-8 py-4">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center font-bold shadow-sm">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-xl tracking-tight text-foreground">
                  Tally Backup & Restore
                </h1>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  Full XML Fidelity
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Exact XML backups of Tally Prime companies with one-click dependency-ordered restoration
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                checkTallyStatus()
                fetchBackups()
              }}
              disabled={checkingTally || loadingBackups}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border border-border bg-card hover:bg-accent hover:text-accent-foreground transition-all shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", (checkingTally || loadingBackups) && "animate-spin")} />
              Refresh Status
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 lg:px-8 py-6 space-y-6">

        {/* 1. Tally Status & Server Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 bg-card border border-border/80 rounded-2xl p-5 shadow-sm relative overflow-hidden flex flex-col justify-between">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Tally Prime XML Server
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className={cn(
                      "inline-block w-2.5 h-2.5 rounded-full",
                      tallyConnected === true && "bg-emerald-500 animate-pulse",
                      tallyConnected === false && "bg-rose-500",
                      tallyConnected === null && "bg-amber-400 animate-pulse"
                    )} />
                    <span className={cn(
                      "text-xs font-bold",
                      tallyConnected === true && "text-emerald-600 dark:text-emerald-400",
                      tallyConnected === false && "text-rose-600 dark:text-rose-400",
                      tallyConnected === null && "text-amber-500"
                    )}>
                      {tallyConnected === true ? "Online & Reachable" : tallyConnected === false ? "Offline / Unreachable" : "Checking..."}
                    </span>
                  </div>
                </div>

                <div className="text-sm font-mono text-muted-foreground pt-1 flex items-center gap-2">
                  <Server className="w-4 h-4 text-muted-foreground/80" />
                  <span>{tallyUrl}</span>
                </div>
              </div>

              <div className="text-right">
                <div className="text-2xl font-black text-foreground">
                  {companies.length}
                </div>
                <div className="text-[11px] font-medium text-muted-foreground">
                  Open Companies in Tally
                </div>
              </div>
            </div>

            {/* If disconnected, show helpful tips */}
            {tallyConnected === false && (
              <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-700 dark:text-rose-300 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>Cannot connect to Tally Prime XML server</span>
                </div>
                <p className="text-[11px] opacity-90 pl-5">
                  Make sure Tally Prime is running on the host machine and XML Server is enabled in <b>F1: Help &gt; Settings &gt; Connectivity</b> (Port 9000).
                </p>
              </div>
            )}

            {/* If connected, show active company badge pills */}
            {tallyConnected === true && companies.length > 0 && (
              <div className="mt-4 pt-3 border-t border-border/50 flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-medium text-muted-foreground">Active in Tally:</span>
                {companies.map((c, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md bg-primary/10 text-primary font-medium border border-primary/20"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                    {c.name}
                    {c.gstin && <span className="text-[10px] text-muted-foreground font-mono">({c.gstin})</span>}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Quick Storage Info Card */}
          <div className="bg-card border border-border/80 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Backup Archives
              </span>
              <HardDrive className="w-4 h-4 text-muted-foreground" />
            </div>

            <div className="space-y-1 my-3">
              <div className="text-3xl font-black text-foreground">
                {backups.length}
              </div>
              <div className="text-xs text-muted-foreground">
                Total archives stored locally
              </div>
            </div>

            <div className="pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
              <span>Total Archive Size:</span>
              <span className="font-bold text-foreground">
                {formatBytes(backups.reduce((acc, b) => acc + (b.file_size_bytes || 0), 0))}
              </span>
            </div>
          </div>
        </div>

        {/* 2. Active Operation Live Progress Bar (if a backup or restore is running) */}
        {(creatingBackup || activeBackup?.status === 'running') && (
          <div className="bg-primary/5 border border-primary/30 rounded-2xl p-5 shadow-md animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-primary animate-ping" />
                <span className="font-bold text-sm text-foreground">
                  Exporting Tally Backup ({activeBackup?.company_name || selectedCompany})
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-primary">
                {activeBackup?.progress_percent || 0}%
              </span>
            </div>

            <div className="w-full bg-muted rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-primary h-2.5 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${Math.max(activeBackup?.progress_percent || 5, 5)}%` }}
              />
            </div>

            <p className="text-xs text-muted-foreground mt-2 font-mono">
              {activeBackup?.progress_message || 'Contacting Tally XML Server...'}
            </p>
          </div>
        )}

        {(restoring || activeRestore?.status === 'running') && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 shadow-md animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-amber-500 animate-ping" />
                <span className="font-bold text-sm text-foreground">
                  Restoring to Tally ({activeRestore?.target_company_name})
                </span>
              </div>
              <span className="text-xs font-mono font-bold text-amber-600 dark:text-amber-400">
                {activeRestore?.progress_percent || 0}%
              </span>
            </div>

            <div className="w-full bg-muted rounded-full h-2.5 overflow-hidden">
              <div
                className="bg-amber-500 h-2.5 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${Math.max(activeRestore?.progress_percent || 5, 5)}%` }}
              />
            </div>

            <p className="text-xs text-muted-foreground mt-2 font-mono">
              {activeRestore?.progress_message || 'Initializing import into Tally...'}
            </p>
          </div>
        )}

        {/* 3. Create Backup Form Card */}
        <div className="bg-card border border-border rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2.5 pb-4 border-b border-border/70">
            <ShieldCheck className="w-5 h-5 text-primary" />
            <div>
              <h2 className="font-bold text-base text-foreground">Create New Tally Backup</h2>
              <p className="text-xs text-muted-foreground">
                Exports all 12 master and transaction entities directly from Tally Prime into a timestamped, integrity-checked ZIP archive.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mt-5">
            {/* Company selection */}
            <div className="md:col-span-5 space-y-1.5">
              <label className="text-xs font-bold text-foreground flex items-center justify-between">
                <span>Select Company to Backup</span>
                {tallyConnected && (
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                    ✓ From Active Tally Session
                  </span>
                )}
              </label>

              {companies.length > 0 ? (
                <div className="space-y-2">
                  <select
                    value={selectedCompany}
                    onChange={(e) => setSelectedCompany(e.target.value)}
                    disabled={creatingBackup}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-input bg-background text-sm font-medium focus:ring-2 focus:ring-primary focus:outline-none"
                  >
                    {companies.map((c, i) => (
                      <option key={i} value={c.name}>
                        {c.name} {c.gstin ? `(${c.gstin})` : ''}
                      </option>
                    ))}
                    <option value="__custom__">+ Enter Custom Company Name...</option>
                  </select>

                  {selectedCompany === '__custom__' && (
                    <input
                      type="text"
                      placeholder="Type exact company name as in Tally..."
                      value={customCompany}
                      onChange={(e) => setCustomCompany(e.target.value)}
                      disabled={creatingBackup}
                      className="w-full px-3.5 py-2 rounded-xl border border-input bg-background text-xs focus:ring-2 focus:ring-primary focus:outline-none"
                    />
                  )}
                </div>
              ) : (
                <input
                  type="text"
                  placeholder="e.g. Sneh Distributors Pvt Ltd"
                  value={customCompany}
                  onChange={(e) => {
                    setCustomCompany(e.target.value)
                    setSelectedCompany(e.target.value)
                  }}
                  disabled={creatingBackup}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-input bg-background text-sm focus:ring-2 focus:ring-primary focus:outline-none"
                />
              )}
            </div>

            {/* Optional Notes */}
            <div className="md:col-span-4 space-y-1.5">
              <label className="text-xs font-bold text-foreground">
                Backup Label / Notes <span className="text-muted-foreground font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Month-end close, Pre-audit snapshot..."
                value={backupNotes}
                onChange={(e) => setBackupNotes(e.target.value)}
                disabled={creatingBackup}
                className="w-full px-3.5 py-2.5 rounded-xl border border-input bg-background text-sm focus:ring-2 focus:ring-primary focus:outline-none"
              />
            </div>

            {/* Action Button */}
            <div className="md:col-span-3 flex items-end">
              <button
                onClick={handleCreateBackup}
                disabled={creatingBackup || (!selectedCompany && !customCompany)}
                className="w-full flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-sm shadow hover:bg-primary/90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none"
              >
                {creatingBackup ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Backing Up...</span>
                  </>
                ) : (
                  <>
                    <FileArchive className="w-4 h-4" />
                    <span>Create Full Backup</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 4. Backup History Table */}
        <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
          <div className="p-5 border-b border-border/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="font-bold text-base text-foreground">Backup Archives History</h2>
              <p className="text-xs text-muted-foreground">
                All saved snapshots with entity counts, checksums, and one-click restore.
              </p>
            </div>

            {/* Search Input */}
            <div className="relative w-full sm:w-72">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by company or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-input bg-background focus:ring-2 focus:ring-primary focus:outline-none"
              />
            </div>
          </div>

          {loadingBackups ? (
            <div className="p-12 text-center text-muted-foreground">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 opacity-50" />
              <p className="text-xs">Loading backup records...</p>
            </div>
          ) : filteredBackups.length === 0 ? (
            <div className="p-12 text-center space-y-2">
              <FileArchive className="w-10 h-10 text-muted-foreground/40 mx-auto" />
              <h3 className="font-bold text-sm text-foreground">No backup archives found</h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                {searchQuery ? "No backups match your search filter." : "Click 'Create Full Backup' above to create your first exact XML backup of Tally Prime."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/70 bg-muted/30 text-muted-foreground font-semibold">
                    <th className="py-3 px-4">Backup ID & Date</th>
                    <th className="py-3 px-4">Company</th>
                    <th className="py-3 px-4">Size</th>
                    <th className="py-3 px-4">Masters & Vouchers</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {filteredBackups.map((b) => (
                    <tr key={b.id} className="hover:bg-muted/30 transition-colors">
                      {/* ID and Date */}
                      <td className="py-3.5 px-4">
                        <div className="font-mono font-bold text-foreground">
                          {b.id}
                        </div>
                        <div className="text-[11px] text-muted-foreground flex items-center gap-1 mt-0.5">
                          <Clock className="w-3 h-3" />
                          <span>{formatDate(b.created_at)}</span>
                        </div>
                      </td>

                      {/* Company Name */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-foreground">
                          {b.company_name}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono truncate max-w-xs">
                          {b.file_name}
                        </div>
                      </td>

                      {/* File Size */}
                      <td className="py-3.5 px-4 font-mono font-medium text-foreground">
                        {formatBytes(b.file_size_bytes)}
                      </td>

                      {/* Masters and Vouchers count */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px]">
                            <Layers className="w-3 h-3" />
                            {b.total_masters} Masters
                          </span>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 font-semibold text-[10px]">
                            <FileText className="w-3 h-3" />
                            {b.total_vouchers} Vouchers
                          </span>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        {b.status === 'completed' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold text-[10px] border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" />
                            Completed
                          </span>
                        )}
                        {b.status === 'running' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px] border border-blue-500/20">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            Running ({b.progress_percent}%)
                          </span>
                        )}
                        {b.status === 'failed' && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold text-[10px] border border-rose-500/20">
                            <XCircle className="w-3 h-3" />
                            Failed
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Download */}
                          <a
                            href={`${API_BASE}/backup/${b.id}/download`}
                            download
                            className="p-1.5 rounded-lg border border-border hover:bg-accent text-foreground transition-colors"
                            title="Download ZIP Archive"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>

                          {/* Restore */}
                          <button
                            onClick={() => {
                              setRestoreModalBackup(b)
                              setRestoreTargetCompany(b.company_name)
                            }}
                            disabled={b.status !== 'completed' || restoring}
                            className="p-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-40"
                            title="Restore into Tally Prime"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                          </button>

                          {/* Delete */}
                          <button
                            onClick={() => setDeleteConfirmBackup(b)}
                            disabled={deleting}
                            className="p-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400 hover:bg-rose-500/20 transition-colors disabled:opacity-40"
                            title="Delete Archive"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 5. Restore Confirmation Modal */}
      {restoreModalBackup && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 pb-3 border-b border-border">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center">
                <RotateCcw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base text-foreground">Restore Tally Backup</h3>
                <p className="text-xs text-muted-foreground font-mono">{restoreModalBackup.id}</p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-muted/40 border border-border space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Original Company:</span>
                <span className="font-bold text-foreground">{restoreModalBackup.company_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Backup Size:</span>
                <span className="font-mono font-semibold">{formatBytes(restoreModalBackup.file_size_bytes)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Contents:</span>
                <span className="font-semibold">{restoreModalBackup.total_masters} Masters · {restoreModalBackup.total_vouchers} Vouchers</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-foreground">
                Target Company in Tally Prime
              </label>
              <input
                type="text"
                value={restoreTargetCompany}
                onChange={(e) => setRestoreTargetCompany(e.target.value)}
                placeholder="Target company name in Tally..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-input bg-background text-sm font-medium focus:ring-2 focus:ring-primary focus:outline-none"
              />
              <p className="text-[11px] text-muted-foreground">
                The target company must be currently open in Tally Prime.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300 space-y-1">
              <div className="flex items-center gap-1.5 font-bold">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Update Existing Mode</span>
              </div>
              <p className="text-[11px] opacity-90 pl-5">
                Existing masters and vouchers will be updated and merged using standard Tally XML import. New records will be created.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                onClick={() => setRestoreModalBackup(null)}
                className="px-4 py-2 rounded-xl border border-border text-xs font-bold hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRestore}
                className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold shadow transition-all flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Confirm & Start Restore</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Restore Summary Results Modal */}
      {showRestoreSummaryModal && activeRestore && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 pb-3 border-b border-border">
              <div className={cn(
                "w-10 h-10 rounded-xl flex items-center justify-center",
                activeRestore.status === 'completed' ? "bg-emerald-500/10 text-emerald-600" : "bg-rose-500/10 text-rose-600"
              )}>
                {activeRestore.status === 'completed' ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="font-bold text-base text-foreground">
                  {activeRestore.status === 'completed' ? "Restoration Completed" : "Restoration Encountered Issues"}
                </h3>
                <p className="text-xs text-muted-foreground font-mono">{activeRestore.id}</p>
              </div>
            </div>

            {activeRestore.error_message && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-700 dark:text-rose-300">
                {activeRestore.error_message}
              </div>
            )}

            {/* Per-entity breakdown table */}
            <div className="max-h-60 overflow-y-auto border border-border rounded-xl">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-muted/40 border-b border-border text-muted-foreground font-semibold">
                    <th className="p-2.5">Entity</th>
                    <th className="p-2.5 text-center">Total</th>
                    <th className="p-2.5 text-center">Created</th>
                    <th className="p-2.5 text-center">Altered</th>
                    <th className="p-2.5 text-center">Errors</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {Object.entries(activeRestore.summary || {}).map(([key, stats]) => (
                    <tr key={key} className="hover:bg-muted/20">
                      <td className="p-2.5 font-medium capitalize">{key.replace('_', ' ')}</td>
                      <td className="p-2.5 text-center font-mono">{stats.total}</td>
                      <td className="p-2.5 text-center font-mono text-emerald-600 dark:text-emerald-400">{stats.created}</td>
                      <td className="p-2.5 text-center font-mono text-blue-600 dark:text-blue-400">{stats.altered}</td>
                      <td className="p-2.5 text-center font-mono text-rose-600 dark:text-rose-400">{stats.errors}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => {
                  setShowRestoreSummaryModal(false)
                  setActiveRestoreId(null)
                  setActiveRestore(null)
                }}
                className="px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold shadow hover:bg-primary/90"
              >
                Close Summary
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Delete Confirmation Modal */}
      {deleteConfirmBackup && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-foreground">Delete Backup Archive?</h3>
                <p className="text-xs text-muted-foreground font-mono">{deleteConfirmBackup.id}</p>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              Are you sure you want to permanently delete this backup archive for <b>{deleteConfirmBackup.company_name}</b>? This action cannot be undone.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDeleteConfirmBackup(null)}
                disabled={deleting}
                className="px-3.5 py-1.5 rounded-xl border border-border text-xs font-bold hover:bg-accent"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteBackup}
                disabled={deleting}
                className="px-3.5 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow"
              >
                {deleting ? 'Deleting...' : 'Delete Permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
