'use client'

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  ShieldAlert,
  CreditCard,
  Building,
  Users,
  Search,
  Filter,
  RefreshCw,
  Plus,
  Lock,
  Unlock,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowLeft,
  Sparkles,
  Zap,
  Receipt,
  FileText,
  MessageSquare,
  Activity,
  Layers,
  ChevronRight,
  ExternalLink,
  Loader2,
  Check,
  X,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import {
  PlatformMetrics,
  PlatformAccountBilling,
  PlatformLead,
  PlatformWebhookEvent,
  fetchPlatformMetrics,
  fetchPlatformAccounts,
  assignPlanToAccount,
  createCustomPlan,
  lockAccountSubscription,
  unlockAccountSubscription,
  recordOfflinePayment,
  fetchPlatformLeads,
  fetchPlatformWebhooks,
} from '@/lib/billing'
import { FEATURE_METADATA } from '@/components/UpgradePrompt'
import { toast } from 'sonner'

export default function PlatformBillingConsolePage() {
  const router = useRouter()
  const { user, token } = useAuth()

  const [activeTab, setActiveTab] = useState<'accounts' | 'offline' | 'leads' | 'webhooks'>('accounts')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [unauthorized, setUnauthorized] = useState(false)

  // Data states
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null)
  const [accounts, setAccounts] = useState<PlatformAccountBilling[]>([])
  const [leads, setLeads] = useState<PlatformLead[]>([])
  const [webhooks, setWebhooks] = useState<PlatformWebhookEvent[]>([])

  // Search & Filters
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Modals state
  const [assignModalAccount, setAssignModalAccount] = useState<PlatformAccountBilling | null>(null)
  const [assignPlanCode, setAssignPlanCode] = useState('gold')
  const [assignDurationYears, setAssignDurationYears] = useState(1)
  const [assignExtraUsers, setAssignExtraUsers] = useState(0)
  const [assignExtraCompanies, setAssignExtraCompanies] = useState(0)

  const [customPlanModalAccount, setCustomPlanModalAccount] = useState<PlatformAccountBilling | null>(null)
  const [customPlanName, setCustomPlanName] = useState('')
  const [customPlanTagline, setCustomPlanTagline] = useState('')
  const [customPlanUsers, setCustomPlanUsers] = useState(5)
  const [customPlanCompanies, setCustomPlanCompanies] = useState(2)
  const [customPlanDevices, setCustomPlanDevices] = useState(5)
  const [customPlanPriceRupees, setCustomPlanPriceRupees] = useState(15000)
  const [customPlanFeatures, setCustomPlanFeatures] = useState<string[]>([
    'real_time_sync',
    'mobile_web_access',
    'sales_purchase_reports',
    'outstanding_aging',
    'einvoice_eway_bill',
  ])

  // Offline payment form
  const [offlineAccountInput, setOfflineAccountInput] = useState<string>('')
  const [offlinePlanCode, setOfflinePlanCode] = useState('gold')
  const [offlineDurationYears, setOfflineDurationYears] = useState(1)
  const [offlineExtraUsers, setOfflineExtraUsers] = useState(0)
  const [offlineExtraCompanies, setOfflineExtraCompanies] = useState(0)
  const [offlineRef, setOfflineRef] = useState('')
  const [offlineMethod, setOfflineMethod] = useState('neft')
  const [offlineStateCode, setOfflineStateCode] = useState('07')
  const [offlineSuccessResult, setOfflineSuccessResult] = useState<{
    invoice_number: string | null
    order_ref: string
    total_rupees: number
  } | null>(null)

  const loadData = async (_options?: unknown) => {
    if (!token) return
    setLoading(true)
    try {
      const [m, a, l, w] = await Promise.all([
        fetchPlatformMetrics(token),
        fetchPlatformAccounts(token),
        fetchPlatformLeads(token),
        fetchPlatformWebhooks(token),
      ])
      setMetrics(m)
      setAccounts(a)
      setLeads(l)
      setWebhooks(w)
      setUnauthorized(false)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (msg && (msg.includes('403') || msg.includes('run this server'))) {
        setUnauthorized(true)
      } else {
        toast.error(`Failed to load operator data: ${msg}`)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!token) return
    let active = true

    Promise.all([
      fetchPlatformMetrics(token),
      fetchPlatformAccounts(token),
      fetchPlatformLeads(token),
      fetchPlatformWebhooks(token),
    ])
      .then(([m, a, l, w]) => {
        if (!active) return
        setMetrics(m)
        setAccounts(a)
        setLeads(l)
        setWebhooks(w)
        setUnauthorized(false)
      })
      .catch((err: unknown) => {
        if (!active) return
        const msg = err instanceof Error ? err.message : String(err)
        if (msg && (msg.includes('403') || msg.includes('run this server'))) {
          setUnauthorized(true)
        } else {
          toast.error(`Failed to load operator data: ${msg}`)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [token])

  // Filtered accounts
  const filteredAccounts = useMemo(() => {
    return accounts.filter((acc) => {
      const matchesSearch =
        acc.account_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        String(acc.account_id).includes(searchTerm) ||
        (acc.plan_code && acc.plan_code.toLowerCase().includes(searchTerm.toLowerCase()))

      const matchesStatus =
        statusFilter === 'all'
          ? true
          : statusFilter === 'locked'
          ? acc.is_locked
          : acc.subscription_status === statusFilter

      return matchesSearch && matchesStatus
    })
  }, [accounts, searchTerm, statusFilter])

  // Action handlers
  const handleAssignPlan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !assignModalAccount) return
    setActionLoading(true)
    try {
      const res = await assignPlanToAccount(
        assignModalAccount.account_id,
        {
          plan_code: assignPlanCode,
          duration_years: assignDurationYears,
          extra_users: assignExtraUsers,
          extra_companies: assignExtraCompanies,
        },
        token
      )
      toast.success(res.message || 'Plan assigned successfully!')
      setAssignModalAccount(null)
      loadData(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`Assignment failed: ${msg}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleCreateCustomPlan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !customPlanModalAccount) return
    setActionLoading(true)
    try {
      const res = await createCustomPlan(
        customPlanModalAccount.account_id,
        {
          name: customPlanName,
          tagline: customPlanTagline,
          max_users: customPlanUsers,
          max_companies: customPlanCompanies,
          max_devices: customPlanDevices,
          feature_keys: customPlanFeatures,
          yearly_price_paise: Math.round(customPlanPriceRupees * 100),
        },
        token
      )
      toast.success(`Custom plan '${customPlanName}' created (Code: ${res.plan_code})!`)
      setCustomPlanModalAccount(null)
      loadData(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`Custom plan creation failed: ${msg}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleToggleLock = async (acc: PlatformAccountBilling) => {
    if (!token) return
    const isCurrentlyLocked = acc.is_locked || acc.subscription_status === 'locked'
    const confirmMsg = isCurrentlyLocked
      ? `Unlock account #${acc.account_id} (${acc.account_name})?`
      : `Lock account #${acc.account_id} (${acc.account_name})? This will block business API access with 402 Payment Required.`

    if (!window.confirm(confirmMsg)) return

    try {
      if (isCurrentlyLocked) {
        await unlockAccountSubscription(acc.account_id, token)
        toast.success(`Account #${acc.account_id} unlocked`)
      } else {
        await lockAccountSubscription(acc.account_id, token)
        toast.warning(`Account #${acc.account_id} locked`)
      }
      loadData(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`Action failed: ${msg}`)
    }
  }

  const handleRecordOfflinePayment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    const accId = parseInt(offlineAccountInput)
    if (isNaN(accId)) {
      toast.error('Please enter a valid numeric Account ID')
      return
    }
    if (!offlineRef.trim()) {
      toast.error('Please enter a bank reference or cheque number')
      return
    }

    setActionLoading(true)
    setOfflineSuccessResult(null)
    try {
      const res = await recordOfflinePayment(
        {
          account_id: accId,
          plan_code: offlinePlanCode,
          duration_years: offlineDurationYears,
          extra_users: offlineExtraUsers,
          extra_companies: offlineExtraCompanies,
          reference: offlineRef.trim(),
          method: offlineMethod,
          buyer_state_code: offlineStateCode,
        },
        token
      )
      toast.success(`Payment recorded! Invoice: ${res.invoice_number}`)
      setOfflineSuccessResult({
        invoice_number: res.invoice_number,
        order_ref: res.order_ref,
        total_rupees: res.total_rupees,
      })
      setOfflineRef('')
      loadData(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(`Recording offline payment failed: ${msg}`)
    } finally {
      setActionLoading(false)
    }
  }

  if (unauthorized) {
    return (
      <div className="min-h-[80vh] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 mb-4">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">Platform Admin Access Only</h1>
        <p className="text-sm text-zinc-400 max-w-md mb-6 leading-relaxed">
          The Operator Billing Console is restricted to server administrators configured in{' '}
          <code className="text-rose-400 bg-rose-950/40 px-1.5 py-0.5 rounded">PLATFORM_ADMIN_EMAILS</code>.
        </p>
        <Link
          href="/admin"
          className="px-4 py-2 rounded-xl text-sm font-semibold bg-zinc-800 text-zinc-200 hover:bg-zinc-700 transition"
        >
          Return to Admin Panel
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-zinc-800 mb-6">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-400 mb-1">
            <Link href="/admin" className="hover:text-white transition flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              Admin Panel
            </Link>
            <span>/</span>
            <span className="text-amber-400 font-medium">Platform Billing Console</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white flex items-center gap-2.5">
            <CreditCard className="w-6 h-6 text-amber-400" />
            Operator Billing Console
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Manage customer subscription tiers, offline NEFT/cheque reconciliations, bespoke plans & revenue.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <Link
            href="/pricing"
            target="_blank"
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-amber-400 hover:bg-amber-300 text-zinc-950 flex items-center gap-1.5 transition shadow-sm"
          >
            Public Pricing
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* KPI Cards */}
      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Revenue */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800">
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1 flex items-center justify-between">
              Total Revenue
              <Receipt className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-black text-white">
              ₹{metrics.revenue.total_rupees.toLocaleString('en-IN')}
            </div>
            <div className="text-xs text-emerald-400 mt-1 font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {metrics.revenue.paid_orders} paid orders processed
            </div>
          </div>

          {/* Subscriptions */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800">
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1 flex items-center justify-between">
              Subscriptions
              <Building className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-black text-white">
              {metrics.subscriptions.active + metrics.subscriptions.legacy + metrics.subscriptions.trialing}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-400 mt-1">
              <span className="text-emerald-400 font-semibold">{metrics.subscriptions.active} active</span>
              <span>•</span>
              <span className="text-zinc-400">{metrics.subscriptions.legacy} legacy</span>
              <span>•</span>
              <span className="text-blue-400">{metrics.subscriptions.trialing} trial</span>
            </div>
          </div>

          {/* Expiring Soon */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800">
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1 flex items-center justify-between">
              Expiring in 30 Days
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-black text-amber-400">
              {metrics.alerts.expiring_in_30_days}
            </div>
            <div className="text-xs text-zinc-400 mt-1">
              {metrics.alerts.trials_ending_in_7_days} trials ending in 7 days
            </div>
          </div>

          {/* Locked / Grace */}
          <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800">
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider mb-1 flex items-center justify-between">
              Grace & Locked
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-2xl font-black text-rose-400">
              {metrics.subscriptions.locked + metrics.subscriptions.grace}
            </div>
            <div className="flex items-center gap-2 text-[11px] text-zinc-400 mt-1">
              <span className="text-amber-400 font-semibold">{metrics.subscriptions.grace} in grace</span>
              <span>•</span>
              <span className="text-rose-400 font-semibold">{metrics.subscriptions.locked} locked (402)</span>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 mb-6 overflow-x-auto pb-1">
        <button
          onClick={() => setActiveTab('accounts')}
          className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 shrink-0 ${
            activeTab === 'accounts'
              ? 'bg-amber-400 text-zinc-950 shadow-sm'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
          }`}
        >
          <Building className="w-3.5 h-3.5" />
          Accounts & Subscriptions ({accounts.length})
        </button>

        <button
          onClick={() => setActiveTab('offline')}
          className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 shrink-0 ${
            activeTab === 'offline'
              ? 'bg-amber-400 text-zinc-950 shadow-sm'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
          }`}
        >
          <Receipt className="w-3.5 h-3.5" />
          Record Offline Payment
        </button>

        <button
          onClick={() => setActiveTab('leads')}
          className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 shrink-0 ${
            activeTab === 'leads'
              ? 'bg-amber-400 text-zinc-950 shadow-sm'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Sales Inquiries ({leads.length})
        </button>

        <button
          onClick={() => setActiveTab('webhooks')}
          className={`px-4 py-2.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 shrink-0 ${
            activeTab === 'webhooks'
              ? 'bg-amber-400 text-zinc-950 shadow-sm'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-900'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Webhook Events ({webhooks.length})
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 1: ACCOUNTS & SUBSCRIPTIONS
      ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'accounts' && (
        <div className="space-y-4">
          {/* Search & Filter Bar */}
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search by account ID, name, or plan..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400 transition"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Filter className="w-4 h-4 text-zinc-400 shrink-0" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full sm:w-auto px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-zinc-800 text-xs font-medium text-zinc-300 focus:outline-none focus:border-amber-400 transition"
              >
                <option value="all">All Subscription States</option>
                <option value="active">Active</option>
                <option value="legacy">Legacy (Grandfathered)</option>
                <option value="trialing">Trialing</option>
                <option value="grace">Grace Period</option>
                <option value="locked">Locked (402)</option>
              </select>
            </div>
          </div>

          {/* Accounts Table */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-zinc-300">
                <thead className="bg-zinc-900/90 border-b border-zinc-800 text-zinc-400 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="py-3 px-4">Account</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Plan</th>
                    <th className="py-3 px-4">Valid Until</th>
                    <th className="py-3 px-4">Extras</th>
                    <th className="py-3 px-4">Lock</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60">
                  {filteredAccounts.map((acc) => {
                    const statusColor =
                      acc.subscription_status === 'active'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : acc.subscription_status === 'legacy'
                        ? 'bg-zinc-800 text-zinc-300 border-zinc-700'
                        : acc.subscription_status === 'trialing'
                        ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        : acc.subscription_status === 'grace'
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'

                    return (
                      <tr key={acc.account_id} className="hover:bg-zinc-800/40 transition">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-white">{acc.account_name}</div>
                          <div className="text-[11px] text-zinc-500">ID: #{acc.account_id}</div>
                        </td>

                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${statusColor}`}
                          >
                            {acc.subscription_status}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          <span className="font-medium text-zinc-200">
                            {acc.plan_name || acc.plan_code || 'None'}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-zinc-400">
                          {acc.valid_until
                            ? new Date(acc.valid_until).toLocaleDateString('en-IN', {
                                day: 'numeric',
                                month: 'short',
                                year: 'numeric',
                              })
                            : acc.subscription_status === 'legacy'
                            ? 'Never (Legacy)'
                            : '—'}
                        </td>

                        <td className="py-3.5 px-4 text-zinc-400">
                          <div>+{acc.extra_users} Users</div>
                          <div>+{acc.extra_companies} Companies</div>
                        </td>

                        <td className="py-3.5 px-4">
                          <button
                            onClick={() => handleToggleLock(acc)}
                            className={`p-1.5 rounded-lg border text-xs transition flex items-center gap-1 ${
                              acc.is_locked || acc.subscription_status === 'locked'
                                ? 'bg-rose-500/10 border-rose-500/30 text-rose-400 hover:bg-rose-500/20'
                                : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-white'
                            }`}
                            title={acc.is_locked ? 'Click to Unlock' : 'Click to Lock (402)'}
                          >
                            {acc.is_locked || acc.subscription_status === 'locked' ? (
                              <>
                                <Lock className="w-3.5 h-3.5" />
                                Locked
                              </>
                            ) : (
                              <>
                                <Unlock className="w-3.5 h-3.5" />
                                Active
                              </>
                            )}
                          </button>
                        </td>

                        <td className="py-3.5 px-4 text-right space-x-1.5">
                          <button
                            onClick={() => {
                              setAssignModalAccount(acc)
                              setAssignPlanCode(acc.plan_code || 'gold')
                              setAssignExtraUsers(acc.extra_users)
                              setAssignExtraCompanies(acc.extra_companies)
                            }}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition"
                          >
                            Assign Plan
                          </button>
                          <button
                            onClick={() => {
                              setCustomPlanModalAccount(acc)
                              setCustomPlanName(`${acc.account_name} Enterprise`)
                            }}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 transition"
                          >
                            Custom Plan
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                  {filteredAccounts.length === 0 && (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-zinc-500">
                        No accounts match your search or filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 2: RECORD OFFLINE PAYMENT
      ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'offline' && (
        <div className="max-w-3xl mx-auto">
          <div className="p-6 sm:p-8 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl mb-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <Receipt className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">Record Offline Payment</h2>
                <p className="text-xs text-zinc-400">
                  Fulfills order via offline gateway, generates sequential GST invoice, and updates subscription.
                </p>
              </div>
            </div>

            {offlineSuccessResult && (
              <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                <div className="font-bold text-sm mb-1 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Offline Payment Captured Successfully!
                </div>
                <div>
                  Invoice Number:{' '}
                  <span className="font-mono font-bold text-white">
                    {offlineSuccessResult.invoice_number || 'N/A'}
                  </span>
                </div>
                <div>Order Ref: {offlineSuccessResult.order_ref}</div>
                <div>Amount: ₹{offlineSuccessResult.total_rupees.toLocaleString('en-IN')}</div>
              </div>
            )}

            <form onSubmit={handleRecordOfflinePayment} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Customer Account ID *
                  </label>
                  <input
                    type="number"
                    required
                    placeholder="e.g. 1"
                    value={offlineAccountInput}
                    onChange={(e) => setOfflineAccountInput(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">Plan Code *</label>
                  <select
                    value={offlinePlanCode}
                    onChange={(e) => setOfflinePlanCode(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="silver">Silver</option>
                    <option value="gold">Gold (Most Popular)</option>
                    <option value="diamond">Diamond (Enterprise)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Duration (Years) *
                  </label>
                  <select
                    value={offlineDurationYears}
                    onChange={(e) => setOfflineDurationYears(parseInt(e.target.value))}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value={1}>1 Year</option>
                    <option value={2}>2 Years</option>
                    <option value={3}>3 Years</option>
                    <option value={5}>5 Years</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Payment Method *
                  </label>
                  <select
                    value={offlineMethod}
                    onChange={(e) => setOfflineMethod(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  >
                    <option value="neft">NEFT / RTGS / IMPS</option>
                    <option value="cheque">Bank Cheque</option>
                    <option value="upi">Direct UPI Transfer</option>
                    <option value="cash">Cash Collection</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Reference / UTR / Cheque No. *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. UTR19028301928"
                    value={offlineRef}
                    onChange={(e) => setOfflineRef(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Buyer GST State Code (01-37)
                  </label>
                  <input
                    type="text"
                    maxLength={2}
                    placeholder="07 (Delhi), 27 (MH), etc."
                    value={offlineStateCode}
                    onChange={(e) => setOfflineStateCode(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Extra Users Add-On
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={offlineExtraUsers}
                    onChange={(e) => setOfflineExtraUsers(parseInt(e.target.value) || 0)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Extra Companies Add-On
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={offlineExtraCompanies}
                    onChange={(e) => setOfflineExtraCompanies(parseInt(e.target.value) || 0)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-950 border border-zinc-800 text-sm text-zinc-200 focus:outline-none focus:border-amber-400"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-zinc-800 flex justify-end">
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-6 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-amber-400 to-yellow-400 text-zinc-950 hover:from-amber-300 hover:to-yellow-300 transition shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Receipt className="w-4 h-4" />}
                  Record & Generate GST Invoice
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 3: SALES INQUIRIES
      ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'leads' && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="bg-zinc-900/90 border-b border-zinc-800 text-zinc-400 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="py-3 px-4">Contact</th>
                  <th className="py-3 px-4">Company</th>
                  <th className="py-3 px-4">Requested Plan</th>
                  <th className="py-3 px-4">Message</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4 text-right">Concierge</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-zinc-800/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-white">{lead.name || 'Anonymous'}</div>
                      <div className="text-[11px] text-zinc-400">{lead.phone || lead.email || '—'}</div>
                    </td>

                    <td className="py-3 px-4 text-zinc-300 font-medium">{lead.company || '—'}</td>

                    <td className="py-3 px-4">
                      <span className="font-semibold text-amber-400 uppercase">
                        {lead.plan_code || 'Custom'}
                      </span>
                      {lead.duration_key && (
                        <span className="text-[11px] text-zinc-500 ml-1">({lead.duration_key})</span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-zinc-400 max-w-xs truncate">{lead.message || '—'}</td>

                    <td className="py-3 px-4 text-zinc-500">
                      {lead.created_at
                        ? new Date(lead.created_at).toLocaleDateString('en-IN', {
                            day: 'numeric',
                            month: 'short',
                          })
                        : '—'}
                    </td>

                    <td className="py-3 px-4 text-right">
                      {lead.phone ? (
                        <a
                          href={`https://wa.me/91${lead.phone.replace(/\D/g, '')}?text=Hello%20${encodeURIComponent(
                            lead.name || ''
                          )},%20this%20is%20MyTally%20Concierge`}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition inline-flex items-center gap-1"
                        >
                          WhatsApp
                        </a>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
                {leads.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-zinc-500">
                      No inbound leads recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          TAB 4: WEBHOOK LOGS
      ───────────────────────────────────────────────────────────────────────────── */}
      {activeTab === 'webhooks' && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="bg-zinc-900/90 border-b border-zinc-800 text-zinc-400 uppercase tracking-wider font-semibold">
                <tr>
                  <th className="py-3 px-4">Gateway</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Event ID</th>
                  <th className="py-3 px-4">Signature</th>
                  <th className="py-3 px-4">Processed</th>
                  <th className="py-3 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {webhooks.map((w) => (
                  <tr key={w.id} className="hover:bg-zinc-800/40 transition">
                    <td className="py-3 px-4 font-semibold text-white capitalize">{w.gateway}</td>

                    <td className="py-3 px-4 font-mono text-zinc-200">{w.event_type}</td>

                    <td className="py-3 px-4 font-mono text-zinc-400 text-[11px] truncate max-w-xs">
                      {w.event_id}
                    </td>

                    <td className="py-3 px-4">
                      {w.signature_verified ? (
                        <span className="text-emerald-400 font-semibold flex items-center gap-1">
                          <Check className="w-3.5 h-3.5" /> Valid
                        </span>
                      ) : (
                        <span className="text-rose-400 font-semibold flex items-center gap-1">
                          <X className="w-3.5 h-3.5" /> Invalid
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4">
                      {w.processed ? (
                        <span className="text-emerald-400 font-semibold">Done</span>
                      ) : w.processing_error ? (
                        <span className="text-rose-400 truncate max-w-xs block" title={w.processing_error}>
                          Error: {w.processing_error}
                        </span>
                      ) : (
                        <span className="text-zinc-500">Pending</span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-zinc-500">
                      {w.created_at
                        ? new Date(w.created_at).toLocaleString('en-IN', {
                            dateStyle: 'short',
                            timeStyle: 'short',
                          })
                        : '—'}
                    </td>
                  </tr>
                ))}
                {webhooks.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-zinc-500">
                      No webhook deliveries logged yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: ASSIGN PLAN
      ───────────────────────────────────────────────────────────────────────────── */}
      {assignModalAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Assign Plan to #{assignModalAccount.account_id}
              </h3>
              <button
                onClick={() => setAssignModalAccount(null)}
                className="text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAssignPlan} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-zinc-300 mb-1">Select Tier *</label>
                <select
                  value={assignPlanCode}
                  onChange={(e) => setAssignPlanCode(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                >
                  <option value="silver">Silver (Starter)</option>
                  <option value="gold">Gold (Most Popular)</option>
                  <option value="diamond">Diamond (Enterprise)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-zinc-300 mb-1">Duration (Years) *</label>
                <select
                  value={assignDurationYears}
                  onChange={(e) => setAssignDurationYears(parseInt(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                >
                  <option value={1}>1 Year</option>
                  <option value={2}>2 Years</option>
                  <option value={3}>3 Years</option>
                  <option value={5}>5 Years</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-300 mb-1">Extra Users</label>
                  <input
                    type="number"
                    min={0}
                    value={assignExtraUsers}
                    onChange={(e) => setAssignExtraUsers(parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-300 mb-1">Extra Companies</label>
                  <input
                    type="number"
                    min={0}
                    value={assignExtraCompanies}
                    onChange={(e) => setAssignExtraCompanies(parseInt(e.target.value) || 0)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-zinc-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setAssignModalAccount(null)}
                  className="px-4 py-2 rounded-xl text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl font-semibold bg-amber-400 text-zinc-950 hover:bg-amber-300 transition flex items-center gap-1.5"
                >
                  {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  Confirm Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────────────────
          MODAL: CUSTOM BESPOKE PLAN
      ───────────────────────────────────────────────────────────────────────────── */}
      {customPlanModalAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-2xl my-8">
            <div className="flex items-center justify-between pb-4 border-b border-zinc-800 mb-4">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                Create Custom Plan for #{customPlanModalAccount.account_id}
              </h3>
              <button
                onClick={() => setCustomPlanModalAccount(null)}
                className="text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateCustomPlan} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-zinc-300 mb-1">Plan Name *</label>
                <input
                  type="text"
                  required
                  value={customPlanName}
                  onChange={(e) => setCustomPlanName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                />
              </div>

              <div>
                <label className="block font-semibold text-zinc-300 mb-1">Tagline</label>
                <input
                  type="text"
                  placeholder="Tailored enterprise package"
                  value={customPlanTagline}
                  onChange={(e) => setCustomPlanTagline(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-300 mb-1">Users</label>
                  <input
                    type="number"
                    min={1}
                    value={customPlanUsers}
                    onChange={(e) => setCustomPlanUsers(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-300 mb-1">Companies</label>
                  <input
                    type="number"
                    min={1}
                    value={customPlanCompanies}
                    onChange={(e) => setCustomPlanCompanies(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-300 mb-1">Devices</label>
                  <input
                    type="number"
                    min={1}
                    value={customPlanDevices}
                    onChange={(e) => setCustomPlanDevices(parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-zinc-300 mb-1">
                  Yearly Price (₹ Rupees) *
                </label>
                <input
                  type="number"
                  min={0}
                  required
                  value={customPlanPriceRupees}
                  onChange={(e) => setCustomPlanPriceRupees(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-200"
                />
              </div>

              <div>
                <label className="block font-semibold text-zinc-300 mb-2">Enabled Features</label>
                <div className="max-h-40 overflow-y-auto space-y-1.5 p-3 rounded-xl bg-zinc-950 border border-zinc-800">
                  {Object.values(FEATURE_METADATA).map((f) => {
                    const isChecked = customPlanFeatures.includes(f.key)
                    return (
                      <label
                        key={f.key}
                        className="flex items-center gap-2 cursor-pointer text-zinc-300 hover:text-white"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setCustomPlanFeatures([...customPlanFeatures, f.key])
                            } else {
                              setCustomPlanFeatures(customPlanFeatures.filter((k) => k !== f.key))
                            }
                          }}
                          className="rounded border-zinc-700 bg-zinc-900 text-amber-500"
                        />
                        <span>{f.title}</span>
                      </label>
                    )
                  })}
                </div>
              </div>

              <div className="pt-4 border-t border-zinc-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCustomPlanModalAccount(null)}
                  className="px-4 py-2 rounded-xl text-zinc-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl font-semibold bg-amber-400 text-zinc-950 hover:bg-amber-300 transition flex items-center gap-1.5"
                >
                  {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  Create Bespoke Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
