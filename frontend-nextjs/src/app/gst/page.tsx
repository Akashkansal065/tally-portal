'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, cn } from '@/lib/utils'
import {
  FileSpreadsheet, Plus, RefreshCw, CheckCircle2, Download, Calendar,
  ChevronDown, Loader2, ArrowUpDown, Receipt, ShieldCheck, FileText,
  AlertTriangle, Eye, Lock, ArrowRight, Activity, HelpCircle, Check, Info, Shield
} from 'lucide-react'

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
]

type ReturnPeriod = {
  return_period_id: number
  company_id: number
  return_type: 'GSTR1' | 'GSTR3B'
  period_month: number
  period_year: number
  status: 'Draft' | 'Filed'
  filed_date?: string
  arn?: string
  filed_by?: number
}

type Gstr1Line = {
  line_item_id: number
  return_period_id: number
  voucher_id: number
  supply_type: string
  party_gstin: string | null
  invoice_number: string
  invoice_date: string
  place_of_supply: string
  taxable_value: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  cess_amount: number
  invoice_value: number
}

type Gstr3bSummary = {
  summary_id: number
  return_period_id: number
  outward_taxable_value: number
  outward_cgst: number
  outward_sgst: number
  outward_igst: number
  outward_cess: number
  itc_igst_available: number
  itc_cgst_available: number
  itc_sgst_available: number
  itc_cess_available: number
  itc_reversed: number
  net_igst_payable: number
  net_cgst_payable: number
  net_sgst_payable: number
  net_cess_payable: number
  tax_paid_via_cash: number
  tax_paid_via_itc: number
  interest_paid: number
  late_fee_paid: number
}

type ItcEntry = {
  itc_entry_id: number
  company_id: number
  voucher_id: number
  supplier_gstin: string | null
  invoice_number: string
  invoice_date: string
  taxable_value: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  cess_amount: number
  eligibility: string
  claimed_return_period_id: number | null
}

type Gstr2bEntry = {
  entry_id: number
  company_id: number
  return_period_id: number | null
  supplier_gstin: string
  supplier_name: string | null
  invoice_number: string
  invoice_date: string
  invoice_type: string
  taxable_value: number
  cgst_amount: number
  sgst_amount: number
  igst_amount: number
  cess_amount: number
  itc_availability: string
  match_status: 'Matched' | 'Unmatched' | 'Mismatch'
  matched_voucher_id: number | null
}

type Gstr9AnnualReturn = {
  annual_return_id: number
  company_id: number
  financial_year: string
  status: 'Draft' | 'Filed'
  outward_taxable_supplies: number
  outward_tax_amount: number
  zero_rated_supplies: number
  nil_rated_supplies: number
  inward_taxable_supplies: number
  inward_tax_amount: number
  itc_claimed: number
  itc_reversed: number
  total_tax_payable: number
  tax_paid_via_cash: number
  tax_paid_via_itc: number
  interest_paid: number
  late_fee_paid: number
  filed_date?: string
  arn?: string
  filed_by?: number
}

type GstEinvoice = {
  voucher_id: number
  voucher_number: string
  voucher_date: string
  party_name: string
  party_gstin: string | null
  amount: number
  irn: string | null
  ack_no: string | null
  eway_bill_no: string | null
}

type TabId = 'periods' | 'gstr1' | 'gstr3b' | 'itc' | 'gstr2b' | 'gstr9' | 'einvoices'

export default function GstPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<TabId>('periods')
  const [periods, setPeriods] = useState<ReturnPeriod[]>([])
  const [gstr1Lines, setGstr1Lines] = useState<Gstr1Line[]>([])
  const [gstr3b, setGstr3b] = useState<Gstr3bSummary | null>(null)
  const [itcEntries, setItcEntries] = useState<ItcEntry[]>([])
  const [gstr2bEntries, setGstr2bEntries] = useState<Gstr2bEntry[]>([])
  const [gstr9Returns, setGstr9Returns] = useState<Gstr9AnnualReturn[]>([])
  const [einvoices, setEinvoices] = useState<GstEinvoice[]>([])
  const [currentEinvEnv, setCurrentEinvEnv] = useState('mock')

  const [loading, setLoading] = useState(false)
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showFileModal, setShowFileModal] = useState(false)
  const [filePeriodId, setFilePeriodId] = useState<number | null>(null)
  const [fileArn, setFileArn] = useState('')
  const [createType, setCreateType] = useState<'GSTR1' | 'GSTR3B'>('GSTR1')
  const [createMonth, setCreateMonth] = useState(new Date().getMonth() + 1)
  const [createYear, setCreateYear] = useState(new Date().getFullYear())
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // GSTR-9 Modals
  const [showGstr9Modal, setShowGstr9Modal] = useState(false)
  const [gstr9Fy, setGstr9Fy] = useState('2025-2026')
  const [showFileGstr9Modal, setShowFileGstr9Modal] = useState(false)
  const [fileGstr9Id, setFileGstr9Id] = useState<number | null>(null)
  const [fileGstr9Arn, setFileGstr9Arn] = useState('')

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showGst && !permissions.isAdmin) { router.replace('/'); return }
  }, [user, permissions, router])

  // --- Data Fetching ---
  const fetchPeriods = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/periods`, { headers: authHeaders(token) })
      if (res.ok) setPeriods(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchGstr1Lines = useCallback(async (periodId: number) => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/periods/${periodId}/gstr1/lines`, { headers: authHeaders(token) })
      if (res.ok) setGstr1Lines(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchGstr3b = useCallback(async (periodId: number) => {
    if (!token) return
    setLoading(true)
    setGstr3b(null)
    try {
      const res = await fetch(`${API_BASE}/gst/periods/${periodId}/gstr3b`, { headers: authHeaders(token) })
      if (res.ok) setGstr3b(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchItc = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/itc`, { headers: authHeaders(token) })
      if (res.ok) setItcEntries(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchGstr2b = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/gstr2b`, { headers: authHeaders(token) })
      if (res.ok) setGstr2bEntries(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchGstr9 = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/gst/gstr9`, { headers: authHeaders(token) })
      if (res.ok) setGstr9Returns(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  const fetchEinvoices = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const settingsRes = await fetch(`${API_BASE}/gst/einvoice/settings`, { headers: authHeaders(token) })
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json()
        setCurrentEinvEnv(settingsData.einvoice_env)
      }
      const res = await fetch(`${API_BASE}/gst/einvoices`, { headers: authHeaders(token) })
      if (res.ok) setEinvoices(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [token])

  useEffect(() => {
    if (activeTab === 'periods') fetchPeriods()
    if (activeTab === 'itc') fetchItc()
    if (activeTab === 'gstr2b') fetchGstr2b()
    if (activeTab === 'gstr9') fetchGstr9()
    if (activeTab === 'einvoices') fetchEinvoices()
  }, [activeTab, fetchPeriods, fetchItc, fetchGstr2b, fetchGstr9, fetchEinvoices])

  useEffect(() => {
    if (selectedPeriodId) {
      if (activeTab === 'gstr1') fetchGstr1Lines(selectedPeriodId)
      if (activeTab === 'gstr3b') fetchGstr3b(selectedPeriodId)
    }
  }, [selectedPeriodId, activeTab, fetchGstr1Lines, fetchGstr3b])

  // --- Actions ---
  const handleCreatePeriod = async () => {
    setActionLoading('create')
    try {
      const res = await fetch(`${API_BASE}/gst/periods`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ return_type: createType, period_month: createMonth, period_year: createYear })
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail || 'Failed to create period')
        return
      }
      setShowCreateModal(false)
      fetchPeriods()
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleGenerate = async (periodId: number) => {
    setActionLoading(`gen-${periodId}`)
    try {
      const res = await fetch(`${API_BASE}/gst/periods/${periodId}/generate`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail || 'Failed to generate snapshot')
        return
      }
      alert('GST Return snapshots generated successfully!')
      fetchPeriods()
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleFile = async () => {
    if (!filePeriodId || !fileArn.trim()) return
    setActionLoading('file')
    try {
      const res = await fetch(`${API_BASE}/gst/periods/${filePeriodId}/file?arn=${encodeURIComponent(fileArn)}`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        alert(err.detail || 'Failed to mark as filed')
        return
      }
      setShowFileModal(false)
      setFileArn('')
      fetchPeriods()
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleExportJson = async (periodId: number) => {
    setActionLoading(`export-${periodId}`)
    try {
      const res = await fetch(`${API_BASE}/gst/periods/${periodId}/gstr1/json`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error('Failed to export')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const period = periods.find(p => p.return_period_id === periodId)
      a.download = `GSTR1_${period ? `${String(period.period_month).padStart(2,'0')}${period.period_year}` : periodId}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  // --- GSTR-2B, GSTR-9, E-Invoices Actions ---
  const handleReconcileGstr2b = async () => {
    setActionLoading('reconcile')
    try {
      const res = await fetch(`${API_BASE}/gst/gstr2b/reconcile`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        const result = await res.json()
        alert(`Reconciliation Completed:\n• ${result.matched} Invoices Matched Exactly\n• ${result.mismatches} Mismatched Amounts Found`)
        fetchGstr2b()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to reconcile GSTR-2B')
      }
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleCreateGstr9 = async () => {
    setActionLoading('create-gstr9')
    try {
      const res = await fetch(`${API_BASE}/gst/gstr9?financial_year=${encodeURIComponent(gstr9Fy)}`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        setShowGstr9Modal(false)
        fetchGstr9()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to create Annual Return')
      }
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleFileGstr9 = async () => {
    if (!fileGstr9Id || !fileGstr9Arn.trim()) return
    setActionLoading('file-gstr9')
    try {
      const res = await fetch(`${API_BASE}/gst/gstr9/${fileGstr9Id}/file?arn=${encodeURIComponent(fileGstr9Arn)}`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        setShowFileGstr9Modal(false)
        setFileGstr9Arn('')
        fetchGstr9()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to file Annual Return')
      }
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const handleGenerateEinvoice = async (voucherId: number) => {
    setActionLoading(`einv-${voucherId}`)
    try {
      const res = await fetch(`${API_BASE}/gst/einvoice/${voucherId}/generate`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (res.ok) {
        alert('E-Invoice (IRN & Acknowledgement) generated successfully!')
        fetchEinvoices()
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to generate e-invoice.')
      }
    } catch (e: any) { alert(e.message) }
    finally { setActionLoading(null) }
  }

  const selectedPeriod = periods.find(p => p.return_period_id === selectedPeriodId)

  const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
    { id: 'periods', label: 'Return Periods', icon: Calendar },
    { id: 'gstr1', label: 'GSTR-1', icon: FileText },
    { id: 'gstr3b', label: 'GSTR-3B', icon: ShieldCheck },
    { id: 'itc', label: 'ITC Register', icon: Receipt },
    { id: 'gstr2b', label: 'GSTR-2B (Reconcile)', icon: Activity },
    { id: 'gstr9', label: 'GSTR-9 (Annual)', icon: FileSpreadsheet },
    { id: 'einvoices', label: 'E-Invoices', icon: Shield },
  ]

  const fmt = (n: number) => formatCurrency(n)

  if (!user) return null

  return (
    <div className="p-4 space-y-5 max-w-4xl mx-auto pb-28">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-emerald-500/10">
            <FileSpreadsheet className="h-6 w-6 text-emerald-600" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">GST Returns</h1>
            <p className="text-xs text-muted-foreground">Manage GSTR-1, GSTR-3B, GSTR-2B Reconciliation, GSTR-9 Annual Return & E-Invoicing</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 p-1 rounded-xl overflow-x-auto no-scrollbar">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap
              ${activeTab === tab.id
                ? 'bg-background shadow-sm text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-background/50'}`}
          >
            <tab.icon className="h-3.5 w-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Period Selector (for GSTR-1 and GSTR-3B tabs) */}
      {(activeTab === 'gstr1' || activeTab === 'gstr3b') && (
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-muted-foreground">Select Period:</label>
          <div className="relative flex-1 max-w-xs">
            <select
              value={selectedPeriodId ?? ''}
              onChange={(e) => setSelectedPeriodId(e.target.value ? Number(e.target.value) : null)}
              className="w-full appearance-none bg-background border border-border rounded-lg px-3 py-2 text-sm font-medium pr-8 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            >
              <option value="">Choose a period...</option>
              {periods
                .filter(p => activeTab === 'gstr1' ? p.return_type === 'GSTR1' : p.return_type === 'GSTR3B')
                .map(p => (
                  <option key={p.return_period_id} value={p.return_period_id}>
                    {MONTHS[p.period_month - 1]} {p.period_year} — {p.status}
                  </option>
                ))}
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-emerald-500" />
        </div>
      )}

      {/* ========== TAB: Return Periods ========== */}
      {activeTab === 'periods' && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">All GST Periods</h2>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg transition-colors shadow-sm"
            >
              <Plus className="h-3.5 w-3.5" /> New Period
            </button>
          </div>

          {periods.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <FileSpreadsheet className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No GST return periods initiated yet</p>
              <p className="text-xs mt-1">Click &quot;New Period&quot; to create your first return period</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {periods.map(p => (
                <div key={p.return_period_id} className="bg-card border border-border rounded-xl p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${p.return_type === 'GSTR1' ? 'bg-blue-500/10' : 'bg-purple-500/10'}`}>
                        {p.return_type === 'GSTR1'
                          ? <FileText className="h-4 w-4 text-blue-600" />
                          : <ShieldCheck className="h-4 w-4 text-purple-600" />}
                      </div>
                      <div>
                        <span className="text-sm font-bold">{p.return_type}</span>
                        <p className="text-xs text-muted-foreground">
                          {MONTHS[p.period_month - 1]} {p.period_year}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider
                        ${p.status === 'Filed'
                          ? 'bg-emerald-500/10 text-emerald-600'
                          : 'bg-amber-500/10 text-amber-600'}`}
                      >
                        {p.status === 'Filed' ? <Lock className="inline h-3 w-3 mr-0.5 -mt-0.5" /> : null}
                        {p.status}
                      </span>
                    </div>
                  </div>

                  {p.status === 'Filed' && p.arn && (
                    <p className="text-xs text-muted-foreground mt-2">
                      ARN: <span className="font-mono font-semibold text-foreground">{p.arn}</span>
                      {p.filed_date && <> &middot; Filed on {new Date(p.filed_date).toLocaleDateString('en-IN')}</>}
                    </p>
                  )}

                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    {p.status === 'Draft' && (
                      <button
                        onClick={() => handleGenerate(p.return_period_id)}
                        disabled={actionLoading === `gen-${p.return_period_id}`}
                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 text-[11px] font-bold rounded-lg transition-colors disabled:opacity-50"
                      >
                        {actionLoading === `gen-${p.return_period_id}`
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <RefreshCw className="h-3 w-3" />}
                        Generate Snapshot
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setSelectedPeriodId(p.return_period_id)
                        setActiveTab(p.return_type === 'GSTR1' ? 'gstr1' : 'gstr3b')
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground text-[11px] font-bold rounded-lg transition-colors"
                    >
                      <Eye className="h-3 w-3" /> View Details
                    </button>
                    {p.return_type === 'GSTR1' && (
                      <button
                        onClick={() => handleExportJson(p.return_period_id)}
                        disabled={actionLoading === `export-${p.return_period_id}`}
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 text-[11px] font-bold rounded-lg transition-colors disabled:opacity-50"
                      >
                        {actionLoading === `export-${p.return_period_id}`
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : <Download className="h-3 w-3" />}
                        Export JSON
                      </button>
                    )}
                    {p.status === 'Draft' && (
                      <button
                        onClick={() => { setFilePeriodId(p.return_period_id); setShowFileModal(true) }}
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-[11px] font-bold rounded-lg transition-colors shadow-sm"
                      >
                        <CheckCircle2 className="h-3 w-3" /> Mark as Filed
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========== TAB: GSTR-1 ========== */}
      {activeTab === 'gstr1' && !loading && (
        <div className="space-y-4">
          {!selectedPeriodId ? (
            <div className="text-center py-16 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a GSTR-1 period above to view invoice details</p>
            </div>
          ) : gstr1Lines.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <AlertTriangle className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No GSTR-1 data generated yet</p>
              <p className="text-xs mt-1">Go to Return Periods tab and click &quot;Generate Snapshot&quot;</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                  Invoice Details — {selectedPeriod ? `${MONTHS[selectedPeriod.period_month - 1]} ${selectedPeriod.period_year}` : ''}
                </h2>
                <span className="text-xs font-semibold text-emerald-600 bg-emerald-500/10 px-2.5 py-1 rounded-full">
                  {gstr1Lines.length} Invoices
                </span>
              </div>

              <div className="overflow-x-auto -mx-4 px-4">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border text-muted-foreground">
                      <th className="text-left py-2.5 px-2 font-bold">Invoice #</th>
                      <th className="text-left py-2.5 px-2 font-bold">Date</th>
                      <th className="text-left py-2.5 px-2 font-bold">Type</th>
                      <th className="text-left py-2.5 px-2 font-bold">GSTIN</th>
                      <th className="text-right py-2.5 px-2 font-bold">Taxable</th>
                      <th className="text-right py-2.5 px-2 font-bold">CGST</th>
                      <th className="text-right py-2.5 px-2 font-bold">SGST</th>
                      <th className="text-right py-2.5 px-2 font-bold">IGST</th>
                      <th className="text-right py-2.5 px-2 font-bold text-emerald-600">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gstr1Lines.map(line => (
                      <tr key={line.line_item_id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-2 font-mono font-semibold">{line.invoice_number}</td>
                        <td className="py-2.5 px-2">{new Date(line.invoice_date).toLocaleDateString('en-IN')}</td>
                        <td className="py-2.5 px-2">
                          <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-600 rounded text-[10px] font-bold">{line.supply_type}</span>
                        </td>
                        <td className="py-2.5 px-2 font-mono text-[10px]">{line.party_gstin || '—'}</td>
                        <td className="py-2.5 px-2 text-right font-medium">{fmt(line.taxable_value)}</td>
                        <td className="py-2.5 px-2 text-right">{fmt(line.cgst_amount)}</td>
                        <td className="py-2.5 px-2 text-right">{fmt(line.sgst_amount)}</td>
                        <td className="py-2.5 px-2 text-right">{fmt(line.igst_amount)}</td>
                        <td className="py-2.5 px-2 text-right font-bold text-emerald-600">{fmt(line.invoice_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-border font-bold">
                      <td colSpan={4} className="py-2.5 px-2 text-right">Total:</td>
                      <td className="py-2.5 px-2 text-right">{fmt(gstr1Lines.reduce((s, l) => s + Number(l.taxable_value), 0))}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(gstr1Lines.reduce((s, l) => s + Number(l.cgst_amount), 0))}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(gstr1Lines.reduce((s, l) => s + Number(l.sgst_amount), 0))}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(gstr1Lines.reduce((s, l) => s + Number(l.igst_amount), 0))}</td>
                      <td className="py-2.5 px-2 text-right text-emerald-600">{fmt(gstr1Lines.reduce((s, l) => s + Number(l.invoice_value), 0))}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ========== TAB: GSTR-3B ========== */}
      {activeTab === 'gstr3b' && !loading && (
        <div className="space-y-4">
          {!selectedPeriodId ? (
            <div className="text-center py-16 text-muted-foreground">
              <ShieldCheck className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a GSTR-3B period above to view summary</p>
            </div>
          ) : !gstr3b ? (
            <div className="text-center py-16 text-muted-foreground">
              <AlertTriangle className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">GSTR-3B summary not generated yet</p>
              <p className="text-xs mt-1">Go to Return Periods tab and click &quot;Generate Snapshot&quot;</p>
            </div>
          ) : (
            <>
              <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">
                GSTR-3B Summary — {selectedPeriod ? `${MONTHS[selectedPeriod.period_month - 1]} ${selectedPeriod.period_year}` : ''}
              </h2>

              {/* Section 3.1 */}
              <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="bg-blue-500/10 px-4 py-2.5">
                  <h3 className="text-xs font-bold text-blue-700 uppercase tracking-wider">3.1 — Details of Outward Supplies</h3>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4">
                  <SummaryCard label="Taxable Value" value={gstr3b.outward_taxable_value} />
                  <SummaryCard label="CGST" value={gstr3b.outward_cgst} />
                  <SummaryCard label="SGST" value={gstr3b.outward_sgst} />
                  <SummaryCard label="IGST" value={gstr3b.outward_igst} />
                  <SummaryCard label="Cess" value={gstr3b.outward_cess} />
                </div>
              </div>

              {/* Section 4 */}
              <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="bg-emerald-500/10 px-4 py-2.5">
                  <h3 className="text-xs font-bold text-emerald-700 uppercase tracking-wider">4 — Eligible ITC</h3>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4">
                  <SummaryCard label="IGST Available" value={gstr3b.itc_igst_available} color="emerald" />
                  <SummaryCard label="CGST Available" value={gstr3b.itc_cgst_available} color="emerald" />
                  <SummaryCard label="SGST Available" value={gstr3b.itc_sgst_available} color="emerald" />
                  <SummaryCard label="Cess Available" value={gstr3b.itc_cess_available} color="emerald" />
                  <SummaryCard label="ITC Reversed" value={gstr3b.itc_reversed} color="rose" />
                </div>
              </div>

              {/* Section 6 */}
              <div className="bg-card border border-border rounded-xl overflow-hidden">
                <div className="bg-amber-500/10 px-4 py-2.5">
                  <h3 className="text-xs font-bold text-amber-700 uppercase tracking-wider">6 — Payment of Tax</h3>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 p-4">
                  <SummaryCard label="Net IGST Payable" value={gstr3b.net_igst_payable} color="amber" />
                  <SummaryCard label="Net CGST Payable" value={gstr3b.net_cgst_payable} color="amber" />
                  <SummaryCard label="Net SGST Payable" value={gstr3b.net_sgst_payable} color="amber" />
                  <SummaryCard label="Net Cess Payable" value={gstr3b.net_cess_payable} color="amber" />
                  <SummaryCard label="Paid via Cash" value={gstr3b.tax_paid_via_cash} />
                  <SummaryCard label="Paid via ITC" value={gstr3b.tax_paid_via_itc} />
                  <SummaryCard label="Interest" value={gstr3b.interest_paid} color="rose" />
                  <SummaryCard label="Late Fee" value={gstr3b.late_fee_paid} color="rose" />
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ========== TAB: ITC Register ========== */}
      {activeTab === 'itc' && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Input Tax Credit Register</h2>
            <span className="text-xs font-semibold text-muted-foreground">
              {itcEntries.length} entries
            </span>
          </div>

          {itcEntries.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Receipt className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No ITC entries recorded yet</p>
              <p className="text-xs mt-1">ITC entries are created from purchase vouchers</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left py-2.5 px-2 font-bold">Invoice #</th>
                    <th className="text-left py-2.5 px-2 font-bold">Date</th>
                    <th className="text-left py-2.5 px-2 font-bold">Supplier GSTIN</th>
                    <th className="text-right py-2.5 px-2 font-bold">Taxable</th>
                    <th className="text-right py-2.5 px-2 font-bold">CGST</th>
                    <th className="text-right py-2.5 px-2 font-bold">SGST</th>
                    <th className="text-right py-2.5 px-2 font-bold">IGST</th>
                    <th className="text-center py-2.5 px-2 font-bold">Eligibility</th>
                  </tr>
                </thead>
                <tbody>
                  {itcEntries.map(itc => (
                    <tr key={itc.itc_entry_id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-2 font-mono font-semibold">{itc.invoice_number}</td>
                      <td className="py-2.5 px-2">{new Date(itc.invoice_date).toLocaleDateString('en-IN')}</td>
                      <td className="py-2.5 px-2 font-mono text-[10px]">{itc.supplier_gstin || '—'}</td>
                      <td className="py-2.5 px-2 text-right font-medium">{fmt(itc.taxable_value)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(itc.cgst_amount)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(itc.sgst_amount)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(itc.igst_amount)}</td>
                      <td className="py-2.5 px-2 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold
                          ${itc.eligibility === 'Eligible' ? 'bg-emerald-500/10 text-emerald-600'
                            : itc.eligibility === 'Ineligible' ? 'bg-rose-500/10 text-rose-600'
                            : 'bg-amber-500/10 text-amber-600'}`}
                        >
                          {itc.eligibility}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========== TAB: GSTR-2B (Reconciliation) ========== */}
      {activeTab === 'gstr2b' && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">GSTR-2B Portal Reconciliation</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">Match vendor auto-drafted ITC statements against book purchase entries</p>
            </div>
            <button
              onClick={handleReconcileGstr2b}
              disabled={actionLoading === 'reconcile'}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg transition-colors shadow-sm disabled:opacity-50"
            >
              {actionLoading === 'reconcile' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Reconcile Books
            </button>
          </div>

          {gstr2bEntries.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Activity className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No GSTR-2B entries uploaded yet</p>
              <p className="text-xs mt-1">GSTR-2B reconciles auto-drafted ITC details from the GST portal</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left py-2.5 px-2 font-bold">Supplier Name</th>
                    <th className="text-left py-2.5 px-2 font-bold">Invoice #</th>
                    <th className="text-left py-2.5 px-2 font-bold">Date</th>
                    <th className="text-right py-2.5 px-2 font-bold">Taxable</th>
                    <th className="text-right py-2.5 px-2 font-bold">CGST</th>
                    <th className="text-right py-2.5 px-2 font-bold">SGST</th>
                    <th className="text-right py-2.5 px-2 font-bold">IGST</th>
                    <th className="text-center py-2.5 px-2 font-bold">Match Status</th>
                  </tr>
                </thead>
                <tbody>
                  {gstr2bEntries.map(entry => (
                    <tr key={entry.entry_id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-2 max-w-[150px] truncate">
                        <div className="font-semibold">{entry.supplier_name || 'Unknown Vendor'}</div>
                        <div className="text-[10px] text-muted-foreground font-mono">{entry.supplier_gstin}</div>
                      </td>
                      <td className="py-2.5 px-2 font-mono font-semibold">{entry.invoice_number}</td>
                      <td className="py-2.5 px-2">{new Date(entry.invoice_date).toLocaleDateString('en-IN')}</td>
                      <td className="py-2.5 px-2 text-right font-medium">{fmt(entry.taxable_value)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(entry.cgst_amount)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(entry.sgst_amount)}</td>
                      <td className="py-2.5 px-2 text-right">{fmt(entry.igst_amount)}</td>
                      <td className="py-2.5 px-2 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1
                          ${entry.match_status === 'Matched' ? 'bg-emerald-500/10 text-emerald-600'
                            : entry.match_status === 'Mismatch' ? 'bg-rose-500/10 text-rose-600'
                            : 'bg-amber-500/10 text-amber-600'}`}
                        >
                          {entry.match_status === 'Matched' && <Check className="h-3 w-3" />}
                          {entry.match_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========== TAB: GSTR-9 (Annual Returns) ========== */}
      {activeTab === 'gstr9' && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">GSTR-9 Annual Return Reports</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">Aggregate fiscal-year returns for final year-end filings</p>
            </div>
            <button
              onClick={() => setShowGstr9Modal(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg transition-colors shadow-sm"
            >
              <Plus className="h-3.5 w-3.5" /> Initiate GSTR-9
            </button>
          </div>

          {gstr9Returns.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <FileSpreadsheet className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No GSTR-9 filings initiated yet</p>
              <p className="text-xs mt-1">Initiate a filing for a financial year to aggregate your records</p>
            </div>
          ) : (
            <div className="space-y-4">
              {gstr9Returns.map(ret => (
                <div key={ret.annual_return_id} className="bg-card border border-border rounded-xl p-5 space-y-4 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-extrabold text-foreground">FY {ret.financial_year}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider
                        ${ret.status === 'Filed' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'}`}
                      >
                        {ret.status}
                      </span>
                    </div>

                    {ret.status === 'Draft' && (
                      <button
                        onClick={() => { setFileGstr9Id(ret.annual_return_id); setShowFileGstr9Modal(true) }}
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-[11px] font-bold rounded-lg transition-colors shadow-sm"
                      >
                        <CheckCircle2 className="h-3 w-3" /> Mark as Filed
                      </button>
                    )}
                  </div>

                  {ret.status === 'Filed' && ret.arn && (
                    <div className="bg-muted/30 p-2.5 rounded-lg text-xs flex justify-between items-center flex-wrap gap-2">
                      <span className="text-muted-foreground">Filing ARN: <strong className="font-mono text-foreground font-semibold">{ret.arn}</strong></span>
                      {ret.filed_date && <span className="text-muted-foreground">Date: <strong className="text-foreground font-semibold">{new Date(ret.filed_date).toLocaleDateString('en-IN')}</strong></span>}
                    </div>
                  )}

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="bg-muted/30 p-2.5 rounded-lg">
                      <span className="text-[10px] text-muted-foreground block uppercase font-bold">Outward Taxable</span>
                      <span className="text-sm font-extrabold text-foreground">{fmt(ret.outward_taxable_supplies)}</span>
                    </div>
                    <div className="bg-muted/30 p-2.5 rounded-lg">
                      <span className="text-[10px] text-muted-foreground block uppercase font-bold">ITC Claimed</span>
                      <span className="text-sm font-extrabold text-emerald-600">{fmt(ret.itc_claimed)}</span>
                    </div>
                    <div className="bg-muted/30 p-2.5 rounded-lg">
                      <span className="text-[10px] text-muted-foreground block uppercase font-bold">Total Payable</span>
                      <span className="text-sm font-extrabold text-amber-600">{fmt(ret.total_tax_payable)}</span>
                    </div>
                    <div className="bg-muted/30 p-2.5 rounded-lg">
                      <span className="text-[10px] text-muted-foreground block uppercase font-bold">Paid via Cash</span>
                      <span className="text-sm font-extrabold text-foreground">{fmt(ret.tax_paid_via_cash)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========== TAB: E-Invoices ========== */}
      {activeTab === 'einvoices' && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-muted-foreground uppercase tracking-wider">E-Invoicing Management Portal</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">Upload sales invoices to the government Invoice Registration Portal (IRP)</p>
            </div>
            <span className={cn(
              "px-3 py-1 rounded-full text-xs font-bold capitalize border shrink-0",
              currentEinvEnv === 'production' ? "bg-rose-500/10 text-rose-600 border-rose-500/20" :
              currentEinvEnv === 'sandbox' ? "bg-amber-500/10 text-amber-600 border-amber-500/20" :
              "bg-muted text-muted-foreground border-border"
            )}>
              Environment: {currentEinvEnv}
            </span>
          </div>

          {einvoices.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <Shield className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No Sales invoices synced yet</p>
              <p className="text-xs mt-1">E-invoices can only be generated for sales invoices synced from Tally</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left py-2.5 px-2 font-bold">Invoice #</th>
                    <th className="text-left py-2.5 px-2 font-bold">Date</th>
                    <th className="text-left py-2.5 px-2 font-bold">Party Name</th>
                    <th className="text-right py-2.5 px-2 font-bold">Amount</th>
                    <th className="text-center py-2.5 px-2 font-bold">IRN Status</th>
                    <th className="text-center py-2.5 px-2 font-bold">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {einvoices.map(einv => (
                    <tr key={einv.voucher_id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-2 font-mono font-semibold">
                        <Link href={`/vouchers/${einv.voucher_id}`} className="text-blue-600 hover:underline">
                          {einv.voucher_number}
                        </Link>
                      </td>
                      <td className="py-2.5 px-2 whitespace-nowrap">{new Date(einv.voucher_date).toLocaleDateString('en-IN')}</td>
                      <td className="py-2.5 px-2">
                        <div className="font-semibold">{einv.party_name}</div>
                        {einv.party_gstin && <div className="text-[10px] text-muted-foreground font-mono">GSTIN: {einv.party_gstin}</div>}
                      </td>
                      <td className="py-2.5 px-2 text-right font-medium">{fmt(einv.amount)}</td>
                      <td className="py-2.5 px-2 text-center">
                        {einv.irn ? (
                          <span className="px-2.5 py-0.5 bg-emerald-500/10 text-emerald-600 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
                            <Check className="h-3 w-3" /> Generated
                          </span>
                        ) : einv.party_gstin ? (
                          <span className="px-2.5 py-0.5 bg-amber-500/10 text-amber-600 rounded-full text-[10px] font-bold">
                            Pending Upload
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 bg-muted text-muted-foreground rounded-full text-[10px] font-bold">
                            B2C Exempt
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          {einv.party_gstin && !einv.irn && (
                            <button
                              onClick={() => handleGenerateEinvoice(einv.voucher_id)}
                              disabled={actionLoading === `einv-${einv.voucher_id}`}
                              className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-[10px] font-extrabold rounded-lg transition-colors cursor-pointer"
                            >
                              {actionLoading === `einv-${einv.voucher_id}` ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                'Generate IRN'
                              )}
                            </button>
                          )}
                          <Link
                            href={`/vouchers/${einv.voucher_id}`}
                            className="px-2.5 py-1 bg-muted hover:bg-muted/80 text-foreground text-[10px] font-bold rounded-lg transition-colors inline-block"
                          >
                            View
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========== MODAL: Create Period ========== */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setShowCreateModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-5" onClick={e => e.stopPropagation()}>
            <div>
              <h3 className="text-lg font-extrabold">Initiate GST Period</h3>
              <p className="text-xs text-muted-foreground mt-1">Create a new return filing period</p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Return Type</label>
                <div className="flex gap-2">
                  {(['GSTR1', 'GSTR3B'] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setCreateType(t)}
                      className={`flex-1 py-2 rounded-lg text-xs font-bold border transition-colors
                        ${createType === t
                          ? 'bg-emerald-500 text-white border-emerald-500'
                          : 'bg-background border-border text-foreground hover:bg-muted'}`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Month</label>
                  <select
                    value={createMonth}
                    onChange={e => setCreateMonth(Number(e.target.value))}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                  >
                    {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Year</label>
                  <input
                    type="number"
                    value={createYear}
                    onChange={e => setCreateYear(Number(e.target.value))}
                    className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                    min={2017} max={2030}
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 py-2.5 bg-muted text-foreground rounded-lg text-xs font-bold hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreatePeriod}
                disabled={actionLoading === 'create'}
                className="flex-1 py-2.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {actionLoading === 'create' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Create Period
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== MODAL: File Return ========== */}
      {showFileModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setShowFileModal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-5" onClick={e => e.stopPropagation()}>
            <div>
              <h3 className="text-lg font-extrabold">Mark as Filed</h3>
              <p className="text-xs text-muted-foreground mt-1">Enter the ARN received from the GST portal after filing</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Acknowledgement Reference Number (ARN)</label>
              <input
                type="text"
                value={fileArn}
                onChange={e => setFileArn(e.target.value)}
                placeholder="e.g. AA123456789012Z"
                className="w-full bg-background border border-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowFileModal(false)}
                className="flex-1 py-2.5 bg-muted text-foreground rounded-lg text-xs font-bold hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFile}
                disabled={actionLoading === 'file' || !fileArn.trim()}
                className="flex-1 py-2.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {actionLoading === 'file' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                Confirm Filed
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== MODAL: Initiate GSTR-9 ========== */}
      {showGstr9Modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setShowGstr9Modal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-5" onClick={e => e.stopPropagation()}>
            <div>
              <h3 className="text-lg font-extrabold">Initiate GSTR-9 Annual Return</h3>
              <p className="text-xs text-muted-foreground mt-1">Select the Financial Year to calculate and draft the annual return summary.</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Financial Year (FY)</label>
              <select
                value={gstr9Fy}
                onChange={e => setGstr9Fy(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              >
                <option value="2025-2026">FY 2025 - 2026</option>
                <option value="2026-2027">FY 2026 - 2027</option>
                <option value="2027-2028">FY 2027 - 2028</option>
              </select>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowGstr9Modal(false)}
                className="flex-1 py-2.5 bg-muted text-foreground rounded-lg text-xs font-bold hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateGstr9}
                disabled={actionLoading === 'create-gstr9'}
                className="flex-1 py-2.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {actionLoading === 'create-gstr9' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Calculate Return
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== MODAL: File GSTR-9 ========== */}
      {showFileGstr9Modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setShowFileGstr9Modal(false)}>
          <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-5" onClick={e => e.stopPropagation()}>
            <div>
              <h3 className="text-lg font-extrabold">File GSTR-9 Annual Return</h3>
              <p className="text-xs text-muted-foreground mt-1">Enter the filing Acknowledgement Reference Number (ARN) received from the GST portal.</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">Acknowledgement Reference Number (ARN)</label>
              <input
                type="text"
                value={fileGstr9Arn}
                onChange={e => setFileGstr9Arn(e.target.value)}
                placeholder="e.g. AA123456789012Z"
                className="w-full bg-background border border-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setShowFileGstr9Modal(false)}
                className="flex-1 py-2.5 bg-muted text-foreground rounded-lg text-xs font-bold hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFileGstr9}
                disabled={actionLoading === 'file-gstr9' || !fileGstr9Arn.trim()}
                className="flex-1 py-2.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {actionLoading === 'file-gstr9' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                Confirm Filed
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, color = 'blue' }: { label: string; value: number; color?: string }) {
  const colorMap: Record<string, string> = {
    blue: 'text-blue-600',
    emerald: 'text-emerald-600',
    amber: 'text-amber-600',
    rose: 'text-rose-600',
  }
  return (
    <div className="bg-muted/30 rounded-lg p-3">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className={`text-sm font-extrabold mt-0.5 ${colorMap[color] || 'text-foreground'}`}>
        {formatCurrency(Number(value))}
      </p>
    </div>
  )
}
