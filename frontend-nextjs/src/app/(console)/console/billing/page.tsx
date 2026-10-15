'use client'

/**
 * app/(console)/console/billing/page.tsx – Platform Billing Management Console.
 *
 * Provides platform operators full subscription lifecycle management:
 *   • Real-time MRR, ARR, active subscriptions, and revenue metrics
 *   • Tenant accounts subscription list with plan assignment, custom plans, and lock/unlock
 *   • Offline payment recording (Cheque, NEFT/RTGS, UPI, Cash)
 *   • Inbound sales leads and gateway webhook event monitors
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  CreditCard,
  Building,
  Users,
  Search,
  RefreshCw,
  Lock,
  Unlock,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Zap,
  Receipt,
  Activity,
  Loader2,
  X,
  IndianRupee,
} from 'lucide-react'
import { useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import {
  consoleBillingApi,
  ConsoleApiError,
  PlatformBillingMetrics,
  PlatformAccountBillingItem,
  PlatformLeadItem,
  PlatformWebhookEventItem,
} from '@/console/api'
import { cn } from '@/lib/utils'

export default function PlatformBillingPage() {
  const { permissions } = useConsoleAuth()
  const canManage = permissions.has('billing.manage') || permissions.has('all')

  const [activeTab, setActiveTab] = useState<'accounts' | 'offline' | 'leads' | 'webhooks'>('accounts')
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null)

  // Data states
  const [metrics, setMetrics] = useState<PlatformBillingMetrics | null>(null)
  const [accounts, setAccounts] = useState<PlatformAccountBillingItem[]>([])
  const [leads, setLeads] = useState<PlatformLeadItem[]>([])
  const [webhooks, setWebhooks] = useState<PlatformWebhookEventItem[]>([])

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('')
  const [planFilter, setPlanFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // Modals state
  const [assignModalAccount, setAssignModalAccount] = useState<PlatformAccountBillingItem | null>(null)
  const [customPlanAccount, setCustomPlanAccount] = useState<PlatformAccountBillingItem | null>(null)
  const [lockModalAccount, setLockModalAccount] = useState<PlatformAccountBillingItem | null>(null)
  const [unlockModalAccount, setUnlockModalAccount] = useState<PlatformAccountBillingItem | null>(null)
  const [offlineAccount, setOfflineAccount] = useState<PlatformAccountBillingItem | null>(null)

  // Form states
  const [assignPlanCode, setAssignPlanCode] = useState('gold')
  const [assignYears, setAssignYears] = useState(1)
  const [assignExtraUsers, setAssignExtraUsers] = useState(0)
  const [assignExtraCompanies, setAssignExtraCompanies] = useState(0)

  const [customPlanName, setCustomPlanName] = useState('')
  const [customPlanTagline, setCustomPlanTagline] = useState('')
  const [customMaxUsers, setCustomMaxUsers] = useState<number>(10)
  const [customMaxCompanies, setCustomMaxCompanies] = useState<number>(5)
  const [customPriceRupees, setCustomPriceRupees] = useState<number>(25000)

  const [lockReason, setLockReason] = useState('Subscription expired / pending payment')
  const [unlockReason, setUnlockReason] = useState('Payment confirmed / grace period granted')

  const [offlinePlanCode, setOfflinePlanCode] = useState('gold')
  const [offlineYears, setOfflineYears] = useState(1)
  const [offlineMethod, setOfflineMethod] = useState('NEFT')
  const [offlineRef, setOfflineRef] = useState('')

  const showSuccess = (msg: string) => {
    setFeedbackSuccess(msg)
    setTimeout(() => setFeedbackSuccess(null), 5000)
  }

  const showError = (msg: string) => {
    setFeedbackError(msg)
    setTimeout(() => setFeedbackError(null), 8000)
  }

  const loadData = useCallback(async () => {
    if (!canManage) return
    setLoading(true)
    setFeedbackError(null)
    try {
      const [m, a, l, w] = await Promise.all([
        consoleBillingApi.getMetrics().catch(() => null),
        consoleBillingApi.getAccounts().catch(() => []),
        consoleBillingApi.getLeads().catch(() => []),
        consoleBillingApi.getWebhooks().catch(() => []),
      ])
      setMetrics(m)
      setAccounts(a)
      setLeads(l)
      setWebhooks(w)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        setFeedbackError(err.detail)
      } else {
        setFeedbackError('Failed to load platform billing data')
      }
    } finally {
      setLoading(false)
    }
  }, [canManage])

  useEffect(() => {
    queueMicrotask(() => {
      void loadData()
    })
  }, [loadData])

  const filteredAccounts = useMemo(() => {
    return accounts.filter((acc) => {
      const companyName = (acc.company_name || acc.account_name || '').toLowerCase()
      const adminEmail = (acc.admin_email || '').toLowerCase()
      const accountId = String(acc.account_id ?? '')
      const query = (searchQuery || '').toLowerCase().trim()

      const matchSearch =
        !query ||
        companyName.includes(query) ||
        adminEmail.includes(query) ||
        accountId.includes(query)

      const currentPlan = (acc.current_plan || acc.plan_code || '').toLowerCase()
      const matchPlan =
        planFilter === 'all' ||
        currentPlan === planFilter.toLowerCase()

      const accStatus = (acc.status || acc.subscription_status || acc.account_status || '').toLowerCase()
      const matchStatus =
        statusFilter === 'all' ||
        (statusFilter === 'locked' && acc.is_locked) ||
        (statusFilter === 'active' && !acc.is_locked && (accStatus === 'active' || accStatus === 'trial')) ||
        (statusFilter === 'trial' && (accStatus === 'trial' || currentPlan.includes('trial')))

      return matchSearch && matchPlan && matchStatus
    })
  }, [accounts, searchQuery, planFilter, statusFilter])

  // Handlers
  const handleAssignPlan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!assignModalAccount) return
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.assignPlan(assignModalAccount.account_id, {
        plan_code: assignPlanCode,
        duration_years: assignYears,
        extra_users: assignExtraUsers,
        extra_companies: assignExtraCompanies,
      })
      showSuccess(res.message || 'Plan assigned successfully')
      setAssignModalAccount(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to assign plan')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCreateCustomPlan = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customPlanAccount) return
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.createCustomPlan(customPlanAccount.account_id, {
        name: customPlanName,
        tagline: customPlanTagline || undefined,
        max_users: customMaxUsers || undefined,
        max_companies: customMaxCompanies || undefined,
        feature_keys: ['all_features', 'priority_support'],
        yearly_price_paise: customPriceRupees * 100,
      })
      showSuccess(`Custom plan '${res.plan_code}' created for ₹${res.amount_rupees.toLocaleString('en-IN')}`)
      setCustomPlanAccount(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to create custom plan')
    } finally {
      setActionLoading(false)
    }
  }

  const handleLockAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!lockModalAccount) return
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.lockAccount(lockModalAccount.account_id, lockReason)
      showSuccess(res.message || 'Account locked')
      setLockModalAccount(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to lock account')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUnlockAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!unlockModalAccount) return
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.unlockAccount(unlockModalAccount.account_id, unlockReason)
      showSuccess(res.message || 'Account unlocked')
      setUnlockModalAccount(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to unlock account')
    } finally {
      setActionLoading(false)
    }
  }

  const handleRecordOfflinePayment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!offlineAccount) return
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.recordOfflinePayment({
        account_id: offlineAccount.account_id,
        plan_code: offlinePlanCode,
        duration_years: offlineYears,
        method: offlineMethod,
        reference: offlineRef,
      })
      showSuccess(res.message || 'Offline payment recorded and plan activated')
      setOfflineAccount(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to record payment')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#dfeee8] pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
              <CreditCard className="w-6 h-6 text-[#00d09c]" />
              Platform Billing Console
            </h1>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] font-semibold">
              Live Gateway
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Manage tenant subscriptions, custom enterprise plans, payments, and billing policies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white border border-[#dfeee8] text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 shadow-sm transition-colors"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Notifications */}
      {feedbackSuccess && (
        <div className="p-3 bg-[#ebfff7] border border-[#b8f5dc] rounded-xl text-[#00875a] text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#00a26d] shrink-0" />
            <span>{feedbackSuccess}</span>
          </div>
          <button onClick={() => setFeedbackSuccess(null)}>
            <X className="w-3.5 h-3.5 text-[#00a26d]" />
          </button>
        </div>
      )}

      {feedbackError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{feedbackError}</span>
          </div>
          <button onClick={() => setFeedbackError(null)}>
            <X className="w-3.5 h-3.5 text-rose-500" />
          </button>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Building className="w-3.5 h-3.5 text-slate-400" />
            Total Accounts
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {metrics?.total_accounts ?? '—'}
          </div>
        </div>

        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#00d09c]" />
            Active Subs
          </div>
          <div className="text-xl font-bold text-[#00a26d] mt-1">
            {metrics?.active_subscriptions ?? '—'}
          </div>
        </div>

        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-rose-500" />
            Locked Accounts
          </div>
          <div className="text-xl font-bold text-rose-600 mt-1">
            {metrics?.locked_accounts ?? '—'}
          </div>
        </div>

        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <IndianRupee className="w-3.5 h-3.5 text-[#00d09c]" />
            Total Revenue
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            ₹{metrics ? Math.round(metrics.total_revenue_rupees).toLocaleString('en-IN') : '—'}
          </div>
        </div>

        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            MRR
          </div>
          <div className="text-xl font-bold text-amber-600 mt-1">
            ₹{metrics ? Math.round(metrics.monthly_recurring_revenue).toLocaleString('en-IN') : '—'}
          </div>
        </div>

        <div className="bg-white border border-[#dfeee8] rounded-2xl p-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-violet-500" />
            ARR
          </div>
          <div className="text-xl font-bold text-violet-600 mt-1">
            ₹{metrics ? Math.round(metrics.annual_recurring_revenue).toLocaleString('en-IN') : '—'}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#dfeee8] gap-6 text-xs font-medium">
        <button
          onClick={() => setActiveTab('accounts')}
          className={cn(
            'pb-3 flex items-center gap-2 border-b-2 transition -mb-px',
            activeTab === 'accounts'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Building className="w-4 h-4" />
          Customer Accounts ({accounts.length})
        </button>

        <button
          onClick={() => setActiveTab('offline')}
          className={cn(
            'pb-3 flex items-center gap-2 border-b-2 transition -mb-px',
            activeTab === 'offline'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Receipt className="w-4 h-4" />
          Offline Payments
        </button>

        <button
          onClick={() => setActiveTab('leads')}
          className={cn(
            'pb-3 flex items-center gap-2 border-b-2 transition -mb-px',
            activeTab === 'leads'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Users className="w-4 h-4" />
          Sales Inquiries ({leads.length})
        </button>

        <button
          onClick={() => setActiveTab('webhooks')}
          className={cn(
            'pb-3 flex items-center gap-2 border-b-2 transition -mb-px',
            activeTab === 'webhooks'
              ? 'border-[#00d09c] text-slate-900 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700 font-medium'
          )}
        >
          <Activity className="w-4 h-4" />
          Gateway Webhooks ({webhooks.length})
        </button>
      </div>

      {/* Tab: Accounts */}
      {activeTab === 'accounts' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search account name, email, ID..."
                className="w-full bg-white border border-[#dfeee8] rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <select
                value={planFilter}
                onChange={(e) => setPlanFilter(e.target.value)}
                className="bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-700 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              >
                <option value="all">All Plans</option>
                <option value="free_trial">Trial</option>
                <option value="silver">Silver</option>
                <option value="gold">Gold</option>
                <option value="diamond">Diamond</option>
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-700 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="trial">Trial</option>
                <option value="locked">Locked</option>
              </select>
            </div>
          </div>

          {/* Accounts Table */}
          <div className="bg-white border border-[#dfeee8] rounded-2xl overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#e3f4ee] bg-[#f9fffc] text-slate-600 font-mono text-[11px] uppercase tracking-wider">
                    <th className="py-3 px-4">Account</th>
                    <th className="py-3 px-4">Plan</th>
                    <th className="py-3 px-4">Usage</th>
                    <th className="py-3 px-4">Period End</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef7f3]">
                  {loading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-500">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#00d09c]" />
                        Loading platform accounts...
                      </td>
                    </tr>
                  ) : filteredAccounts.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-500">
                        No customer accounts found matching criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredAccounts.map((acc) => (
                      <tr key={acc.account_id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-900">
                            {acc.company_name || acc.account_name || `Account #${acc.account_id}`}
                          </div>
                          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                            ID: {acc.account_id}
                            {acc.admin_email ? ` • ${acc.admin_email}` : ''}
                          </div>
                        </td>

                        <td className="py-3.5 px-4">
                          <span
                            className={cn(
                              'px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border',
                              (acc.current_plan || acc.plan_code) === 'diamond'
                                ? 'bg-cyan-50 text-cyan-700 border-cyan-200'
                                : (acc.current_plan || acc.plan_code) === 'gold'
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : (acc.current_plan || acc.plan_code) === 'silver'
                                ? 'bg-slate-100 text-slate-700 border-slate-200'
                                : 'bg-[#ebfff7] text-[#00a26d] border-[#b8f5dc]'
                            )}
                          >
                            {acc.plan_name || acc.current_plan || acc.plan_code || 'Trial'}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-slate-700">
                          <div>
                            Users: {acc.active_users ?? 0} / {acc.max_users ?? '∞'}
                          </div>
                          <div className="text-slate-500 text-[11px] mt-0.5">
                            Cos: {acc.active_companies ?? 0} / {acc.max_companies ?? '∞'}
                          </div>
                        </td>

                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-500">
                          {(acc.current_period_end || acc.valid_until)
                            ? new Date(acc.current_period_end || acc.valid_until!).toLocaleDateString()
                            : 'N/A'}
                        </td>

                        <td className="py-3.5 px-4">
                          {acc.is_locked ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                              <Lock className="w-2.5 h-2.5" />
                              Locked
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc]">
                              <CheckCircle2 className="w-2.5 h-2.5" />
                              Active
                            </span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                          <button
                            onClick={() => {
                              setAssignModalAccount(acc)
                              setAssignPlanCode(acc.current_plan || acc.plan_code || 'gold')
                            }}
                            className="px-2.5 py-1 rounded-lg bg-white hover:bg-slate-50 border border-[#dfeee8] text-slate-700 text-xs font-semibold shadow-sm transition"
                          >
                            Assign Plan
                          </button>

                          <button
                            onClick={() => {
                              setCustomPlanAccount(acc)
                              setCustomPlanName(`${acc.company_name || acc.account_name || `Account #${acc.account_id}`} Enterprise`)
                            }}
                            className="px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 text-xs font-semibold shadow-sm transition"
                          >
                            Custom Plan
                          </button>

                          {acc.is_locked ? (
                            <button
                              onClick={() => setUnlockModalAccount(acc)}
                              className="px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-[#00a26d] text-xs font-semibold shadow-sm transition"
                            >
                              Unlock
                            </button>
                          ) : (
                            <button
                              onClick={() => setLockModalAccount(acc)}
                              className="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 text-xs font-semibold shadow-sm transition"
                            >
                              Lock
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Offline Payments */}
      {activeTab === 'offline' && (
        <div className="bg-white border border-[#dfeee8] rounded-2xl p-6 max-w-2xl mx-auto space-y-5 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Receipt className="w-5 h-5 text-[#00d09c]" />
              Record Offline Direct Payment
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Manually activate or renew customer accounts paying via Bank NEFT, Cheque, UPI, or Cash.
            </p>
          </div>

          <form onSubmit={handleRecordOfflinePayment} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Select Customer Account
              </label>
              <select
                required
                onChange={(e) => {
                  const acc = accounts.find((a) => a.account_id === Number(e.target.value))
                  setOfflineAccount(acc || null)
                }}
                className="w-full bg-white border border-[#dfeee8] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
              >
                <option value="">-- Choose Account --</option>
                {accounts.map((a) => (
                  <option key={a.account_id} value={a.account_id}>
                    {a.company_name || a.account_name || `Account #${a.account_id}`} (ID: {a.account_id}{a.admin_email ? ` - ${a.admin_email}` : ''})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Plan Code</label>
                <select
                  value={offlinePlanCode}
                  onChange={(e) => setOfflinePlanCode(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  <option value="silver">Silver</option>
                  <option value="gold">Gold</option>
                  <option value="diamond">Diamond</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Duration</label>
                <select
                  value={offlineYears}
                  onChange={(e) => setOfflineYears(Number(e.target.value))}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  <option value={1}>1 Year</option>
                  <option value={2}>2 Years</option>
                  <option value={3}>3 Years</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">Payment Method</label>
                <select
                  value={offlineMethod}
                  onChange={(e) => setOfflineMethod(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  <option value="NEFT">Bank Transfer (NEFT/RTGS)</option>
                  <option value="CHEQUE">Bank Cheque</option>
                  <option value="UPI">UPI Direct</option>
                  <option value="CASH">Cash Deposit</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  UTR / Reference Number
                </label>
                <input
                  type="text"
                  required
                  value={offlineRef}
                  onChange={(e) => setOfflineRef(e.target.value)}
                  placeholder="e.g. UTR1234567890"
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3.5 py-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                disabled={!offlineAccount || actionLoading}
                className="px-4 py-2.5 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-semibold text-xs shadow-sm transition disabled:opacity-50 flex items-center gap-2"
              >
                {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Record Payment & Activate Subscription
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tab: Leads */}
      {activeTab === 'leads' && (
        <div className="bg-white border border-[#dfeee8] rounded-2xl overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#e3f4ee] bg-[#f9fffc] text-slate-600 font-mono text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4">Contact</th>
                <th className="py-3 px-4">Requested Plan</th>
                <th className="py-3 px-4">Created Date</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eef7f3]">
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    No enterprise sales inquiries found.
                  </td>
                </tr>
              ) : (
                leads.map((l) => (
                  <tr key={l.lead_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900">{l.company_name}</div>
                      <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                        {l.email} {l.phone && `• ${l.phone}`}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">
                      {l.requested_plan || 'Custom'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">
                      {new Date(l.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {l.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 max-w-xs truncate">
                      {l.notes || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Webhooks */}
      {activeTab === 'webhooks' && (
        <div className="bg-white border border-[#dfeee8] rounded-2xl overflow-hidden shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[#e3f4ee] bg-[#f9fffc] text-slate-600 font-mono text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4">Gateway</th>
                <th className="py-3 px-4">Event Type</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Error Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eef7f3]">
              {webhooks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    No gateway webhook events captured.
                  </td>
                </tr>
              ) : (
                webhooks.map((w) => (
                  <tr key={w.event_id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-semibold text-slate-900">
                      {w.gateway}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-slate-700">{w.event_type}</td>
                    <td className="py-3.5 px-4 text-slate-500 font-mono">
                      {new Date(w.created_at).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded-full text-[10px] font-semibold border',
                          w.status === 'processed'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border-rose-200'
                        )}
                      >
                        {w.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 text-[11px] max-w-sm truncate">
                      {w.error_detail || 'None'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Assign Plan Modal ── */}
      {assignModalAccount && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#dfeee8] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#dfeee8] pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-[#00d09c]" />
                Assign Subscription Plan
              </h3>
              <button
                onClick={() => setAssignModalAccount(null)}
                className="text-slate-400 hover:text-slate-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAssignPlan} className="space-y-3.5">
              <p className="text-xs text-slate-600">
                Target Account:{' '}
                <span className="font-semibold text-slate-900">
                  {assignModalAccount.company_name || assignModalAccount.account_name || `Account #${assignModalAccount.account_id}`} (ID: {assignModalAccount.account_id})
                </span>
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Plan</label>
                <select
                  value={assignPlanCode}
                  onChange={(e) => setAssignPlanCode(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                >
                  <option value="silver">Silver Plan</option>
                  <option value="gold">Gold Plan</option>
                  <option value="diamond">Diamond Plan</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Duration (Years)
                </label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={assignYears}
                  onChange={(e) => setAssignYears(Number(e.target.value))}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Extra Users
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={assignExtraUsers}
                    onChange={(e) => setAssignExtraUsers(Number(e.target.value))}
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Extra Companies
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={assignExtraCompanies}
                    onChange={(e) => setAssignExtraCompanies(Number(e.target.value))}
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setAssignModalAccount(null)}
                  className="px-3.5 py-2 rounded-xl bg-white border border-[#dfeee8] text-slate-700 text-xs font-semibold hover:bg-slate-50 shadow-sm transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Confirm Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Custom Plan Modal ── */}
      {customPlanAccount && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#dfeee8] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#dfeee8] pb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#00d09c]" />
                Create Custom Enterprise Plan
              </h3>
              <button
                onClick={() => setCustomPlanAccount(null)}
                className="text-slate-400 hover:text-slate-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateCustomPlan} className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Plan Name</label>
                <input
                  type="text"
                  required
                  value={customPlanName}
                  onChange={(e) => setCustomPlanName(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Tagline</label>
                <input
                  type="text"
                  value={customPlanTagline}
                  onChange={(e) => setCustomPlanTagline(e.target.value)}
                  placeholder="e.g. Dedicated Enterprise Bundle"
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Max Users</label>
                  <input
                    type="number"
                    min={1}
                    value={customMaxUsers}
                    onChange={(e) => setCustomMaxUsers(Number(e.target.value))}
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Max Companies
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={customMaxCompanies}
                    onChange={(e) => setCustomMaxCompanies(Number(e.target.value))}
                    className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Yearly Price (INR ₹)
                </label>
                <input
                  type="number"
                  min={100}
                  value={customPriceRupees}
                  onChange={(e) => setCustomPriceRupees(Number(e.target.value))}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCustomPlanAccount(null)}
                  className="px-3.5 py-2 rounded-xl bg-white border border-[#dfeee8] text-slate-700 text-xs font-semibold hover:bg-slate-50 shadow-sm transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Create & Activate Plan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Lock Account Modal ── */}
      {lockModalAccount && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#dfeee8] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#dfeee8] pb-3">
              <h3 className="text-sm font-bold text-rose-600 flex items-center gap-2">
                <Lock className="w-4 h-4 text-rose-600" />
                Lock Account Subscription
              </h3>
              <button
                onClick={() => setLockModalAccount(null)}
                className="text-slate-400 hover:text-slate-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleLockAccount} className="space-y-3.5">
              <p className="text-xs text-slate-600">
                Are you sure you want to lock subscription for{' '}
                <span className="font-semibold text-slate-900">
                  {lockModalAccount.company_name || lockModalAccount.account_name || `Account #${lockModalAccount.account_id}`}
                </span>
                ? Users under this tenant will be redirected to the locked renewal screen.
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Lock Reason</label>
                <input
                  type="text"
                  required
                  value={lockReason}
                  onChange={(e) => setLockReason(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setLockModalAccount(null)}
                  className="px-3.5 py-2 rounded-xl bg-white border border-[#dfeee8] text-slate-700 text-xs font-semibold hover:bg-slate-50 shadow-sm transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Lock Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Unlock Account Modal ── */}
      {unlockModalAccount && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#dfeee8] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#dfeee8] pb-3">
              <h3 className="text-sm font-bold text-[#00a26d] flex items-center gap-2">
                <Unlock className="w-4 h-4 text-[#00a26d]" />
                Unlock Account Subscription
              </h3>
              <button
                onClick={() => setUnlockModalAccount(null)}
                className="text-slate-400 hover:text-slate-700 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleUnlockAccount} className="space-y-3.5">
              <p className="text-xs text-slate-600">
                Unlock subscription and restore normal portal access for{' '}
                <span className="font-semibold text-slate-900">
                  {unlockModalAccount.company_name || unlockModalAccount.account_name || `Account #${unlockModalAccount.account_id}`}
                </span>
                .
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Unlock Reason
                </label>
                <input
                  type="text"
                  required
                  value={unlockReason}
                  onChange={(e) => setUnlockReason(e.target.value)}
                  className="w-full bg-white border border-[#dfeee8] rounded-xl px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#00d09c] focus:ring-2 focus:ring-[#00d09c]/20 shadow-sm"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setUnlockModalAccount(null)}
                  className="px-3.5 py-2 rounded-xl bg-white border border-[#dfeee8] text-slate-700 text-xs font-semibold hover:bg-slate-50 shadow-sm transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center gap-1.5"
                >
                  {actionLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Unlock Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
