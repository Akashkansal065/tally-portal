'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  Sparkles,
  Plus,
  Edit2,
  Copy,
  Power,
  PowerOff,
  Eye,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ExternalLink,
  ChevronRight,
  Shield,
  Layers,
  Building,
  Users,
  Smartphone,
  Info,
  X,
  IndianRupee,
  Lock,
} from 'lucide-react'
import {
  consoleBillingApi,
  ConsoleApiError,
  AdminCatalogPlan,
  AdminCatalogPackage,
  AdminCatalogPrice,
  AdminTrialSetting,
  AdminAddonItem,
} from '@/console/api'
import { cn } from '@/lib/utils'

export const FEATURE_CATEGORIES = [
  {
    name: 'Data Access & Sync Engine',
    features: [
      { key: 'real_time_sync', label: 'Real-time Two-Way Tally Sync', info: 'Continuous live sync with TallyPrime / Tally.ERP 9' },
      { key: 'mobile_web_access', label: 'Mobile App (Android & iOS) + Web Portal', info: 'Native apps and browser portal' },
      { key: 'multiple_devices', label: 'Simultaneous Devices per User', info: '' },
      { key: 'multi_company_switch', label: 'Multiple Tally Companies', info: '' },
      { key: 'unlimited_companies', label: 'Unlimited Tally Companies', info: '' },
    ],
  },
  {
    name: 'Sales & Ledger Management',
    features: [
      { key: 'outstanding_aging', label: 'Customer Outstandings & Ageing Buckets', info: '' },
      { key: 'pdf_whatsapp_share', label: 'Instant WhatsApp & PDF Invoicing Share', info: '' },
      { key: 'auto_payment_reminders', label: 'Automated WhatsApp Payment Reminders', info: 'Automated schedule with reminder links' },
      { key: 'payment_links_collect', label: 'Online Payment Collection Links', info: 'Collect via UPI, Cards, Netbanking directly into bank' },
      { key: 'salesman_checkin_orders', label: 'Salesperson GPS Check-In & Visits', info: 'Track sales reps geo-location and client visits' },
      { key: 'customer_portal', label: 'Customer Self-Service Statement Portal', info: '' },
    ],
  },
  {
    name: 'Inventory & Financial Reporting',
    features: [
      { key: 'daybook_cash_bank', label: 'Daybook, Cash & Bank Books', info: '' },
      { key: 'ratio_analysis', label: 'Ratio Analysis & Financial Metrics', info: '' },
      { key: 'sales_purchase_reports', label: 'Item-wise Stock Valuation & Godowns', info: '' },
      { key: 'stock_dead_fast', label: 'Dead Stock, Slow Movers & Fast Movers', info: 'Visual insights into non-moving inventory' },
      { key: 'financial_statements_drilldown', label: 'Profit & Loss, Balance Sheet Drilldown', info: '' },
      { key: 'bank_reconciliation', label: 'Bank Statement Reconciliation Auto-Match', info: 'Upload bank statement & auto-reconcile' },
      { key: 'multi_godown_branch', label: 'Multi-Branch & Multi-Godown Analytics', info: '' },
    ],
  },
  {
    name: 'Compliance & Enterprise Controls',
    features: [
      { key: 'custom_roles_rbac', label: 'Role-Based Permissions (RBAC)', info: 'Control ledger scope, stock group, and hide profit' },
      { key: 'einvoice_eway_bill', label: 'Govt E-Invoicing (IRN & QR) + E-Way Bill', info: 'Generate certified IRN & QR without visiting the portal' },
      { key: 'audit_trail_deleted_logs', label: 'Audit Trail & Deleted Records History', info: 'Track what was edited or deleted in Tally' },
      { key: 'approval_rules_matrix', label: 'Custom Voucher Approval Matrix', info: '' },
      { key: 'dedicated_account_manager', label: 'Dedicated VIP Support Manager', info: '' },
      { key: 'custom_onboarding_vip', label: 'Custom Onboarding & VIP Support', info: '' },
      { key: 'priority_sync_support', label: 'Fast Sync Engine & Priority Support', info: '' },
    ],
  },
]

interface TermDefinition {
  interval: 'month' | 'year'
  count: number
  label: string
}

const STANDARD_TERMS: TermDefinition[] = [
  { interval: 'month', count: 1, label: '1 month' },
  { interval: 'month', count: 3, label: '3 months' },
  { interval: 'month', count: 6, label: '6 months' },
  { interval: 'year', count: 1, label: '1 year' },
  { interval: 'year', count: 2, label: '2 years' },
  { interval: 'year', count: 3, label: '3 years' },
]

export function CatalogTab() {
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [plans, setPlans] = useState<AdminCatalogPlan[]>([])
  const [addons, setAddons] = useState<AdminAddonItem[]>([])
  const [trialSetting, setTrialSetting] = useState<AdminTrialSetting | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)

  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)

  // Modals
  const [showCreatePlanModal, setShowCreatePlanModal] = useState(false)
  const [showTrialModal, setShowTrialModal] = useState(false)
  const [showCreatePackageModal, setShowCreatePackageModal] = useState(false)
  const [editPackageItem, setEditPackageItem] = useState<AdminCatalogPackage | null>(null)
  const [priceEditorModal, setPriceEditorModal] = useState<{
    pkg: AdminCatalogPackage
    term: TermDefinition
    price?: AdminCatalogPrice | null
  } | null>(null)

  // Trial form
  const [trialPackageId, setTrialPackageId] = useState<number>(0)
  const [trialDaysInput, setTrialDaysInput] = useState<number>(7)

  // Add-on edit state
  const [editingAddonId, setEditingAddonId] = useState<number | null>(null)
  const [addonYearlyRupees, setAddonYearlyRupees] = useState<number>(0)
  const [addonMonthlyRupees, setAddonMonthlyRupees] = useState<number>(0)

  const showSuccess = (msg: string) => {
    setFeedbackSuccess(msg)
    setTimeout(() => setFeedbackSuccess(null), 5000)
  }

  const showError = (msg: string) => {
    setFeedbackError(msg)
    setTimeout(() => setFeedbackError(null), 8000)
  }

  const loadData = async () => {
    try {
      setLoading(true)
      const [catPlans, catAddons, catTrial] = await Promise.all([
        consoleBillingApi.getCatalog(),
        consoleBillingApi.getAddons().catch(() => []),
        consoleBillingApi.getTrialSetting().catch(() => null),
      ])
      setPlans(catPlans)
      setAddons(catAddons)
      setTrialSetting(catTrial)
      if (catPlans.length > 0) {
        setSelectedPlanId((current) => current ?? catPlans[0].id)
      }
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to load catalog tree')
    } finally {
      setLoading(false)
    }
  }

  // Load once on mount; later loads are explicit after each change
  useEffect(() => {
    queueMicrotask(() => {
      void loadData()
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedPlan = useMemo(() => {
    return plans.find((p) => p.id === selectedPlanId) || plans[0] || null
  }, [plans, selectedPlanId])

  // Plan Details Form State
  const [planForm, setPlanForm] = useState({
    name: '',
    tagline: '',
    badge: '',
    trial_days: 0,
    allow_extra_users: true,
    allow_extra_companies: true,
    is_public: true,
    sort_order: 0,
  })

  // The form follows the selected plan, and is refilled from the server's copy after every reload
  const [planFormSource, setPlanFormSource] = useState<AdminCatalogPlan | null>(null)
  if (selectedPlan && selectedPlan !== planFormSource) {
    setPlanFormSource(selectedPlan)
    setPlanForm({
      name: selectedPlan.name || '',
      tagline: selectedPlan.tagline || '',
      badge: selectedPlan.badge || '',
      trial_days: selectedPlan.trial_days || 0,
      allow_extra_users: selectedPlan.allow_extra_users ?? true,
      allow_extra_companies: selectedPlan.allow_extra_companies ?? true,
      is_public: selectedPlan.is_public ?? true,
      sort_order: selectedPlan.sort_order || 0,
    })
  }

  // Save Plan Details
  const handleSavePlanDetails = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedPlan) return
    setActionLoading(true)
    try {
      await consoleBillingApi.updatePlan(selectedPlan.id, planForm)
      showSuccess(`Plan "${planForm.name}" updated successfully.`)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to update plan')
    } finally {
      setActionLoading(false)
    }
  }

  // Toggle Plan Active
  const handleTogglePlanActive = async () => {
    if (!selectedPlan) return
    setActionLoading(true)
    try {
      if (selectedPlan.is_active) {
        await consoleBillingApi.deactivatePlan(selectedPlan.id)
        showSuccess(`Plan "${selectedPlan.name}" deactivated.`)
      } else {
        await consoleBillingApi.activatePlan(selectedPlan.id)
        showSuccess(`Plan "${selectedPlan.name}" activated.`)
      }
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to toggle plan active status')
    } finally {
      setActionLoading(false)
    }
  }

  // Feature Toggle
  const handleToggleFeature = async (featureKey: string) => {
    if (!selectedPlan) return
    const currentFeatures = new Set(selectedPlan.features || [])
    if (currentFeatures.has(featureKey)) {
      currentFeatures.delete(featureKey)
    } else {
      currentFeatures.add(featureKey)
    }
    const updated = Array.from(currentFeatures)
    setActionLoading(true)
    try {
      await consoleBillingApi.updatePlan(selectedPlan.id, { features: updated })
      showSuccess('Features updated.')
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to update features')
    } finally {
      setActionLoading(false)
    }
  }

  // Duplicate Package
  const handleDuplicatePackage = async (pkgId: number) => {
    setActionLoading(true)
    try {
      const res = await consoleBillingApi.duplicatePackage(pkgId)
      showSuccess(`Package duplicated as "${res.label}".`)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to duplicate package')
    } finally {
      setActionLoading(false)
    }
  }

  // Toggle Package Active
  const handleTogglePackageActive = async (pkg: AdminCatalogPackage) => {
    setActionLoading(true)
    try {
      if (pkg.is_active) {
        await consoleBillingApi.deactivatePackage(pkg.id)
        showSuccess(`Package "${pkg.label}" deactivated.`)
      } else {
        await consoleBillingApi.activatePackage(pkg.id)
        showSuccess(`Package "${pkg.label}" activated.`)
      }
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to toggle package active status')
    } finally {
      setActionLoading(false)
    }
  }

  // Save Trial Settings
  const handleSaveTrialSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!trialPackageId) return
    setActionLoading(true)
    try {
      await consoleBillingApi.setTrialSetting({
        package_id: trialPackageId,
        trial_days: trialDaysInput,
      })
      showSuccess('Trial settings updated successfully.')
      setShowTrialModal(false)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to update trial setting')
    } finally {
      setActionLoading(false)
    }
  }

  // Save Addon
  const handleSaveAddon = async (addonId: number) => {
    setActionLoading(true)
    try {
      await consoleBillingApi.updateAddon(addonId, {
        yearly_paise: addonYearlyRupees ? Math.round(addonYearlyRupees * 100) : null,
        monthly_paise: addonMonthlyRupees ? Math.round(addonMonthlyRupees * 100) : null,
      })
      showSuccess('Add-on pricing updated.')
      setEditingAddonId(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to update add-on')
    } finally {
      setActionLoading(false)
    }
  }

  // Toggle Addon Active
  const handleToggleAddonActive = async (addon: AdminAddonItem) => {
    setActionLoading(true)
    try {
      await consoleBillingApi.updateAddon(addon.id, {
        is_active: !addon.is_active,
      })
      showSuccess(`Add-on ${addon.name} ${!addon.is_active ? 'activated' : 'deactivated'}.`)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to toggle add-on')
    } finally {
      setActionLoading(false)
    }
  }

  if (loading && plans.length === 0) {
    return (
      <div className="p-16 text-center text-sm text-slate-500 flex items-center justify-center gap-2">
        <Loader2 className="w-5 h-5 animate-spin text-[#00d09c]" />
        <span>Loading catalog tree…</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
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

      {/* Top Banner: Trial Settings & Pricing Preview */}
      <div className="bg-gradient-to-r from-emerald-500/10 via-card to-background border border-emerald-500/20 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900 dark:text-foreground">
              {trialSetting ? (
                <>
                  New accounts get a <strong>{trialSetting.trial_days}-day</strong> trial of{' '}
                  <span className="text-emerald-600 font-extrabold">{trialSetting.plan_name}</span> ·{' '}
                  {trialSetting.package_label}.
                </>
              ) : (
                'Trial configuration is loading or not set.'
              )}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Assigned automatically when a tenant signs up.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            type="button"
            onClick={() => {
              if (trialSetting) {
                setTrialPackageId(trialSetting.package_id)
                setTrialDaysInput(trialSetting.trial_days)
              }
              setShowTrialModal(true)
            }}
            className="px-3.5 py-2 rounded-xl bg-white dark:bg-card border border-border text-xs font-bold text-foreground hover:bg-muted shadow-sm transition-colors cursor-pointer"
          >
            Change Trial Setting
          </button>
          <a
            href="/pricing"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3.5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 shadow-sm transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            Preview Pricing Page <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Plans List */}
        <div className="lg:col-span-4 bg-white dark:bg-card border border-border rounded-2xl p-4 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h3 className="text-sm font-black text-foreground">Catalog Plans</h3>
              <p className="text-[11px] text-muted-foreground">Select a plan to edit packages and prices</p>
            </div>
            <button
              type="button"
              onClick={() => setShowCreatePlanModal(true)}
              className="px-3 py-1.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 flex items-center gap-1 shadow-sm cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> New Plan
            </button>
          </div>

          <div className="space-y-2">
            {plans.map((p) => {
              const isSelected = selectedPlan?.id === p.id
              const totalSubs = p.packages.reduce((acc, pkg) => acc + (pkg.active_subscribers || 0), 0)
              const hasActivePackagesWithPrices = p.packages.some(
                (pkg) => pkg.is_active && pkg.prices.some((pr) => pr.is_active)
              )

              let statusLabel = 'On sale'
              let statusClass = 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'

              if (!p.is_active) {
                statusLabel = 'Hidden'
                statusClass = 'bg-slate-500/10 text-slate-500 border-slate-500/20'
              } else if (p.account_id) {
                statusLabel = `Private (#${p.account_id})`
                statusClass = 'bg-amber-500/10 text-amber-600 border-amber-500/20'
              } else if (!hasActivePackagesWithPrices) {
                statusLabel = 'Not on sale'
                statusClass = 'bg-rose-500/10 text-rose-600 border-rose-500/20'
              }

              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSelectedPlanId(p.id)}
                  className={cn(
                    'w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col gap-2',
                    isSelected
                      ? 'border-emerald-500 bg-emerald-500/5 shadow-sm'
                      : 'border-border/80 hover:border-border hover:bg-muted/40'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-black text-sm text-foreground">{p.name}</span>
                      <span className="text-[10px] text-muted-foreground uppercase font-mono tracking-wider">
                        ({p.code})
                      </span>
                    </div>
                    <span
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full border',
                        statusClass
                      )}
                    >
                      {statusLabel}
                    </span>
                  </div>

                  <p className="text-[11px] text-muted-foreground line-clamp-1">{p.tagline || 'No tagline set'}</p>

                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/40">
                    <span className="flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5" />
                      {p.packages.length} package{p.packages.length === 1 ? '' : 's'}
                    </span>
                    <span className="font-semibold text-foreground">
                      {totalSubs} active subscriber{totalSubs === 1 ? '' : 's'}
                    </span>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Add-on Rates Table Under Plans List */}
          <div className="pt-4 border-t border-border space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-black text-foreground">Add-on Rates</h4>
                <p className="text-[10px] text-muted-foreground">Universal add-on pricing</p>
              </div>
            </div>

            <div className="space-y-2">
              {addons.map((a) => (
                <div
                  key={a.id}
                  className="p-2.5 rounded-xl border border-border/80 bg-muted/30 text-xs flex items-center justify-between"
                >
                  <div>
                    <div className="font-bold text-foreground capitalize flex items-center gap-1.5">
                      <span>{a.name}</span>
                      <span
                        className={cn(
                          'text-[9px] px-1.5 py-0.2 rounded font-bold uppercase',
                          a.is_active ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground'
                        )}
                      >
                        {a.is_active ? 'Active' : 'Off'}
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      ₹{a.yearly_rupees ?? 0}/yr · ₹{a.monthly_rupees ?? 0}/mo
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setEditingAddonId(a.id)
                        setAddonYearlyRupees(a.yearly_rupees ?? 0)
                        setAddonMonthlyRupees(a.monthly_rupees ?? 0)
                      }}
                      className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                      title="Edit price"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleAddonActive(a)}
                      className={cn(
                        'p-1 rounded cursor-pointer',
                        a.is_active
                          ? 'text-rose-500 hover:bg-rose-500/10'
                          : 'text-emerald-500 hover:bg-emerald-500/10'
                      )}
                      title={a.is_active ? 'Deactivate' : 'Activate'}
                    >
                      {a.is_active ? <PowerOff className="w-3.5 h-3.5" /> : <Power className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Plan Details Editor, Features, Packages & Prices */}
        {selectedPlan ? (
          <div className="lg:col-span-8 space-y-6">
            {/* Section 1: Plan Details Form */}
            <div className="bg-white dark:bg-card border border-border rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
                <div>
                  <h3 className="text-base font-black text-foreground">
                    Plan Details: {selectedPlan.name}
                  </h3>
                  <p className="text-xs text-muted-foreground">General branding, visibility, and add-on permissions</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleTogglePlanActive}
                    disabled={actionLoading}
                    className={cn(
                      'px-3.5 py-1.5 rounded-xl text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5',
                      selectedPlan.is_active
                        ? 'bg-rose-500/10 text-rose-600 hover:bg-rose-500/20 border border-rose-500/20'
                        : 'bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border border-emerald-500/20'
                    )}
                  >
                    {selectedPlan.is_active ? (
                      <>
                        <PowerOff className="w-3.5 h-3.5" /> Deactivate Plan
                      </>
                    ) : (
                      <>
                        <Power className="w-3.5 h-3.5" /> Activate Plan
                      </>
                    )}
                  </button>
                </div>
              </div>

              <form onSubmit={handleSavePlanDetails} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-bold text-foreground block mb-1">Plan Name</label>
                    <input
                      type="text"
                      value={planForm.name}
                      onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
                      required
                      className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background focus:ring-2 focus:ring-emerald-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-foreground block mb-1">Badge Text (optional)</label>
                    <input
                      type="text"
                      placeholder="e.g. ⭐ Most Popular Choice"
                      value={planForm.badge}
                      onChange={(e) => setPlanForm({ ...planForm, badge: e.target.value })}
                      className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background focus:ring-2 focus:ring-emerald-500 outline-none"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="text-xs font-bold text-foreground block mb-1">Tagline</label>
                    <input
                      type="text"
                      value={planForm.tagline}
                      onChange={(e) => setPlanForm({ ...planForm, tagline: e.target.value })}
                      placeholder="One-line value proposition shown under the plan name"
                      className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background focus:ring-2 focus:ring-emerald-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-foreground block mb-1">Trial Days</label>
                    <input
                      type="number"
                      min={0}
                      max={90}
                      value={planForm.trial_days}
                      onChange={(e) => setPlanForm({ ...planForm, trial_days: Number(e.target.value) })}
                      className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background focus:ring-2 focus:ring-emerald-500 outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-bold text-foreground block mb-1">Sort Order</label>
                    <input
                      type="number"
                      value={planForm.sort_order}
                      onChange={(e) => setPlanForm({ ...planForm, sort_order: Number(e.target.value) })}
                      className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background focus:ring-2 focus:ring-emerald-500 outline-none"
                    />
                  </div>
                </div>

                {/* Toggles */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <label className="flex items-center gap-2 p-3 rounded-xl border border-border bg-muted/20 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={planForm.allow_extra_users}
                      onChange={(e) => setPlanForm({ ...planForm, allow_extra_users: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-xs font-semibold text-foreground">Allow Extra Users</span>
                  </label>

                  <label className="flex items-center gap-2 p-3 rounded-xl border border-border bg-muted/20 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={planForm.allow_extra_companies}
                      onChange={(e) => setPlanForm({ ...planForm, allow_extra_companies: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-xs font-semibold text-foreground">Allow Extra Companies</span>
                  </label>

                  <label className="flex items-center gap-2 p-3 rounded-xl border border-border bg-muted/20 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={planForm.is_public}
                      onChange={(e) => setPlanForm({ ...planForm, is_public: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                    />
                    <span className="text-xs font-semibold text-foreground">Public On Website</span>
                  </label>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    type="submit"
                    disabled={actionLoading}
                    className="px-5 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 shadow-sm cursor-pointer disabled:opacity-50"
                  >
                    Save Plan Details
                  </button>
                </div>
              </form>
            </div>

            {/* Section 2: Features Checkboxes */}
            <div className="bg-white dark:bg-card border border-border rounded-2xl p-6 shadow-sm space-y-4">
              <div className="border-b border-border pb-3">
                <h3 className="text-base font-black text-foreground">Features Checklist</h3>
                <p className="text-xs text-muted-foreground">
                  Features entitled to accounts subscribed to any package in this plan group
                </p>
              </div>

              <div className="space-y-6">
                {FEATURE_CATEGORIES.map((cat) => (
                  <div key={cat.name} className="space-y-2">
                    <h4 className="text-xs font-black uppercase tracking-wider text-muted-foreground">
                      {cat.name}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {cat.features.map((feat) => {
                        const isChecked = (selectedPlan.features || []).includes(feat.key)
                        return (
                          <label
                            key={feat.key}
                            className={cn(
                              'flex items-start gap-2.5 p-2.5 rounded-xl border text-xs cursor-pointer transition-colors',
                              isChecked
                                ? 'border-emerald-500/50 bg-emerald-500/5 text-foreground font-semibold'
                                : 'border-border/60 hover:bg-muted/30 text-muted-foreground'
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => handleToggleFeature(feat.key)}
                              className="mt-0.5 rounded border-border text-emerald-600 focus:ring-emerald-500"
                            />
                            <div>
                              <span>{feat.label}</span>
                              {feat.info && (
                                <p className="text-[10px] text-muted-foreground font-normal">{feat.info}</p>
                              )}
                            </div>
                          </label>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 3: Packages & Prices Grid */}
            <div className="bg-white dark:bg-card border border-border rounded-2xl p-6 shadow-sm space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
                <div>
                  <h3 className="text-base font-black text-foreground">Packages & Prices Grid</h3>
                  <p className="text-xs text-muted-foreground">
                    Click any price cell to edit or add a term. Hover a cell to view the per-month breakdown.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowCreatePackageModal(true)}
                  className="px-3.5 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 flex items-center gap-1.5 shadow-sm cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Package
                </button>
              </div>

              {selectedPlan.packages.length === 0 ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  No packages in this plan yet. Click &ldquo;Add Package&rdquo; above to create one.
                </div>
              ) : (
                <div className="overflow-x-auto -mx-6 px-6">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-muted-foreground">
                        <th className="py-3 px-3 font-bold">Package</th>
                        <th className="py-3 px-2 font-bold">Devices</th>
                        {STANDARD_TERMS.map((t) => (
                          <th key={`${t.interval}_${t.count}`} className="py-3 px-2 font-bold text-center">
                            {t.label}
                          </th>
                        ))}
                        <th className="py-3 px-3 font-bold text-center">In Use</th>
                        <th className="py-3 px-3 font-bold text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {selectedPlan.packages.map((pkg) => {
                        return (
                          <tr key={pkg.id} className="hover:bg-muted/20">
                            <td className="py-3 px-3 font-semibold text-foreground">
                              <div className="flex items-center gap-2">
                                <span>{pkg.label}</span>
                                {!pkg.is_active && (
                                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-600 font-bold">
                                    Retired
                                  </span>
                                )}
                              </div>
                              <span className="text-[10px] text-muted-foreground font-mono">{pkg.code}</span>
                            </td>

                            <td className="py-3 px-2 text-muted-foreground">
                              {pkg.max_devices ?? 'Unlimited'}
                            </td>

                            {STANDARD_TERMS.map((t) => {
                              const price = pkg.prices.find(
                                (pr) =>
                                  pr.is_active &&
                                  pr.interval === t.interval &&
                                  pr.interval_count === t.count
                              )
                              return (
                                <td
                                  key={`${t.interval}_${t.count}`}
                                  className="py-3 px-2 text-center"
                                >
                                  {price ? (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setPriceEditorModal({
                                          pkg,
                                          term: t,
                                          price,
                                        })
                                      }
                                      className="group px-2 py-1.5 rounded-lg border border-border/80 hover:border-emerald-500 bg-background hover:bg-emerald-500/5 transition-all text-xs font-bold text-foreground cursor-pointer block w-full"
                                      title={`₹${price.per_month_rupees}/mo • ${price.autopay_allowed ? 'Autopay allowed' : 'No autopay'}`}
                                    >
                                      <div>₹{price.amount_rupees.toLocaleString('en-IN')}</div>
                                      {price.compare_at_rupees && (
                                        <div className="text-[9px] text-muted-foreground line-through">
                                          ₹{price.compare_at_rupees.toLocaleString('en-IN')}
                                        </div>
                                      )}
                                      <div className="text-[9px] text-emerald-600 font-semibold opacity-0 group-hover:opacity-100 transition-opacity">
                                        ₹{price.per_month_rupees}/mo
                                      </div>
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() =>
                                        setPriceEditorModal({
                                          pkg,
                                          term: t,
                                          price: null,
                                        })
                                      }
                                      className="px-2 py-1.5 rounded-lg border border-dashed border-border/60 hover:border-emerald-500 text-muted-foreground hover:text-emerald-600 hover:bg-emerald-500/5 transition-colors text-xs font-bold cursor-pointer w-full"
                                    >
                                      + Add
                                    </button>
                                  )}
                                </td>
                              )
                            })}

                            <td className="py-3 px-3 text-center">
                              <span className="font-semibold text-foreground block">
                                {pkg.active_subscribers} subs
                              </span>
                              <span className="text-[10px] text-muted-foreground">
                                {pkg.paid_orders} orders
                              </span>
                            </td>

                            <td className="py-3 px-3 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => setEditPackageItem(pkg)}
                                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                                  title="Edit Package"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDuplicatePackage(pkg.id)}
                                  className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                                  title="Duplicate to change limits"
                                >
                                  <Copy className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleTogglePackageActive(pkg)}
                                  className={cn(
                                    'p-1.5 rounded-lg cursor-pointer',
                                    pkg.is_active
                                      ? 'text-rose-500 hover:bg-rose-500/10'
                                      : 'text-emerald-500 hover:bg-emerald-500/10'
                                  )}
                                  title={pkg.is_active ? 'Retire package' : 'Activate package'}
                                >
                                  {pkg.is_active ? (
                                    <PowerOff className="w-3.5 h-3.5" />
                                  ) : (
                                    <Power className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>

      {/* ── MODALS ── */}

      {/* Trial Setting Modal */}
      {showTrialModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-base font-black text-foreground">Configure Free Trial</h3>
              <button onClick={() => setShowTrialModal(false)}>
                <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
              </button>
            </div>

            <form onSubmit={handleSaveTrialSettings} className="space-y-4">
              <div>
                <label className="text-xs font-bold text-foreground block mb-1">
                  Default Trial Package
                </label>
                <select
                  value={trialPackageId}
                  onChange={(e) => setTrialPackageId(Number(e.target.value))}
                  required
                  className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
                >
                  <option value={0}>Select a package…</option>
                  {plans.map((p) =>
                    p.packages
                      .filter((pkg) => pkg.is_active)
                      .map((pkg) => (
                        <option key={pkg.id} value={pkg.id}>
                          {p.name} · {pkg.label}
                        </option>
                      ))
                  )}
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-foreground block mb-1">
                  Trial Duration (days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={trialDaysInput}
                  onChange={(e) => setTrialDaysInput(Number(e.target.value))}
                  required
                  className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTrialModal(false)}
                  className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !trialPackageId}
                  className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
                >
                  Save Setting
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Add-on Rate Modal */}
      {editingAddonId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-sm p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-base font-black text-foreground">Update Add-on Rates</h3>
              <button onClick={() => setEditingAddonId(null)}>
                <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-bold text-foreground block mb-1">
                  Yearly Price (₹)
                </label>
                <input
                  type="number"
                  min={0}
                  value={addonYearlyRupees}
                  onChange={(e) => setAddonYearlyRupees(Number(e.target.value))}
                  className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-foreground block mb-1">
                  Monthly Price (₹)
                </label>
                <input
                  type="number"
                  min={0}
                  value={addonMonthlyRupees}
                  onChange={(e) => setAddonMonthlyRupees(Number(e.target.value))}
                  className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingAddonId(null)}
                  className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={actionLoading}
                  onClick={() => handleSaveAddon(editingAddonId)}
                  className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Plan Modal */}
      {showCreatePlanModal && (
        <CreatePlanModal
          onClose={() => setShowCreatePlanModal(false)}
          onSuccess={() => {
            setShowCreatePlanModal(false)
            showSuccess('New plan created.')
            loadData()
          }}
        />
      )}

      {/* Create Package Modal */}
      {showCreatePackageModal && selectedPlan && (
        <CreatePackageModal
          plan={selectedPlan}
          onClose={() => setShowCreatePackageModal(false)}
          onSuccess={() => {
            setShowCreatePackageModal(false)
            showSuccess('New package created.')
            loadData()
          }}
        />
      )}

      {/* Edit Package Modal */}
      {editPackageItem && (
        <EditPackageModal
          pkg={editPackageItem}
          onClose={() => setEditPackageItem(null)}
          onSuccess={() => {
            setEditPackageItem(null)
            showSuccess('Package updated.')
            loadData()
          }}
        />
      )}

      {/* Price Editor Modal */}
      {priceEditorModal && (
        <PriceEditorModal
          pkg={priceEditorModal.pkg}
          term={priceEditorModal.term}
          price={priceEditorModal.price}
          onClose={() => setPriceEditorModal(null)}
          onSuccess={() => {
            setPriceEditorModal(null)
            showSuccess('Price point saved.')
            loadData()
          }}
        />
      )}
    </div>
  )
}

function CreatePlanModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: () => void
}) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [tagline, setTagline] = useState('')
  const [badge, setBadge] = useState('')
  const [trialDays, setTrialDays] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await consoleBillingApi.createPlan({
        code,
        name,
        tagline: tagline || undefined,
        badge: badge || undefined,
        trial_days: trialDays,
      })
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to create plan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="text-base font-black text-foreground">Create New Plan Group</h3>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-bold text-foreground block mb-1">
              Code (unique slug, e.g. platinum)
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Tagline</label>
            <input
              type="text"
              value={tagline}
              onChange={(e) => setTagline(e.target.value)}
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Badge</label>
            <input
              type="text"
              value={badge}
              onChange={(e) => setBadge(e.target.value)}
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
            >
              {loading ? 'Creating…' : 'Create Plan'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CreatePackageModal({
  plan,
  onClose,
  onSuccess,
}: {
  plan: AdminCatalogPlan
  onClose: () => void
  onSuccess: () => void
}) {
  const [maxCompanies, setMaxCompanies] = useState(1)
  const [maxUsers, setMaxUsers] = useState(1)
  const [maxDevices, setMaxDevices] = useState(3)
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await consoleBillingApi.createPackage(plan.id, {
        max_companies: maxCompanies,
        max_users: maxUsers,
        max_devices: maxDevices,
        label: label || undefined,
      })
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to create package')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="text-base font-black text-foreground">
            Add Package to {plan.name}
          </h3>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Max Companies</label>
              <input
                type="number"
                min={1}
                value={maxCompanies}
                onChange={(e) => setMaxCompanies(Number(e.target.value))}
                required
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Max Users</label>
              <input
                type="number"
                min={1}
                value={maxUsers}
                onChange={(e) => setMaxUsers(Number(e.target.value))}
                required
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Max Devices per User</label>
            <input
              type="number"
              min={1}
              value={maxDevices}
              onChange={(e) => setMaxDevices(Number(e.target.value))}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">
              Custom Label (leave blank for automatic)
            </label>
            <input
              type="text"
              placeholder={`${maxCompanies} company + ${maxUsers} user`}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
            >
              {loading ? 'Creating…' : 'Add Package'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function EditPackageModal({
  pkg,
  onClose,
  onSuccess,
}: {
  pkg: AdminCatalogPackage
  onClose: () => void
  onSuccess: () => void
}) {
  const [label, setLabel] = useState(pkg.label || '')
  const [maxDevices, setMaxDevices] = useState(pkg.max_devices ?? 3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await consoleBillingApi.updatePackage(pkg.id, {
        label,
        max_devices: maxDevices,
      })
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to update package')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="text-base font-black text-foreground">Edit Package</h3>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {pkg.in_use && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2">
            <Lock className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <strong>Package is in use ({pkg.active_subscribers} active subscribers).</strong>
              <p className="mt-0.5">
                Core company and user limits are frozen to protect active contracts. Use duplicate to modify limits.
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Package Label</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Max Devices per User</label>
            <input
              type="number"
              min={1}
              value={maxDevices}
              onChange={(e) => setMaxDevices(Number(e.target.value))}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
            >
              {loading ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function PriceEditorModal({
  pkg,
  term,
  price,
  onClose,
  onSuccess,
}: {
  pkg: AdminCatalogPackage
  term: TermDefinition
  price?: AdminCatalogPrice | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [amountRupees, setAmountRupees] = useState<number>(price ? price.amount_rupees : 999)
  const [compareAtRupees, setCompareAtRupees] = useState<number>(price?.compare_at_rupees ?? 0)
  const [autopayAllowed, setAutopayAllowed] = useState<boolean>(price ? price.autopay_allowed : false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isOrdered = Boolean(price && price.is_ordered)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const amountPaise = Math.round(amountRupees * 100)
      const compareAtPaise = compareAtRupees > 0 ? Math.round(compareAtRupees * 100) : null

      if (!price) {
        // Add new price
        await consoleBillingApi.addPrice(pkg.id, {
          interval: term.interval,
          interval_count: term.count,
          amount_paise: amountPaise,
          compare_at_paise: compareAtPaise,
          autopay_allowed: autopayAllowed,
        })
      } else if (isOrdered) {
        // Price ordered: replace=True creates a new price and retires this one
        await consoleBillingApi.addPrice(pkg.id, {
          interval: term.interval,
          interval_count: term.count,
          amount_paise: amountPaise,
          compare_at_paise: compareAtPaise,
          autopay_allowed: autopayAllowed,
          replace: true,
        })
      } else {
        // Price not ordered: directly editable
        await consoleBillingApi.updatePrice(price.id, {
          amount_paise: amountPaise,
          compare_at_paise: compareAtPaise,
          autopay_allowed: autopayAllowed,
        })
      }
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to save price point')
    } finally {
      setLoading(false)
    }
  }

  const handleDeactivate = async () => {
    if (!price) return
    setLoading(true)
    setError(null)
    try {
      await consoleBillingApi.deactivatePrice(price.id)
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to deactivate price')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div>
            <h3 className="text-base font-black text-foreground">
              {price ? 'Edit Price Point' : 'Add Price Point'}
            </h3>
            <p className="text-xs text-muted-foreground">
              {pkg.label} · {term.label}
            </p>
          </div>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {isOrdered && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <strong>Customers have bought this price.</strong>
              <p className="mt-0.5">
                Saving creates a new price for new checkouts; current subscribers keep theirs until renewal.
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-bold text-foreground block mb-1">
              Amount (₹, excluding GST)
            </label>
            <input
              type="number"
              min={1}
              value={amountRupees}
              onChange={(e) => setAmountRupees(Number(e.target.value))}
              required
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">
              Original / Compare-At Amount (₹, optional strikethrough)
            </label>
            <input
              type="number"
              min={0}
              value={compareAtRupees}
              onChange={(e) => setCompareAtRupees(Number(e.target.value))}
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <label className="flex items-center gap-2 p-3 rounded-xl border border-border bg-muted/20 cursor-pointer">
            <input
              type="checkbox"
              checked={autopayAllowed}
              onChange={(e) => setAutopayAllowed(e.target.checked)}
              className="rounded border-border text-emerald-600 focus:ring-emerald-500"
            />
            <span className="text-xs font-semibold text-foreground">
              Allow Recurring Autopay (Razorpay/Cashfree mandate)
            </span>
          </label>

          <div className="flex items-center justify-between pt-2">
            {price ? (
              <button
                type="button"
                disabled={loading}
                onClick={handleDeactivate}
                className="px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 text-xs font-bold border border-rose-500/20 cursor-pointer"
              >
                Retire Price
              </button>
            ) : (
              <div />
            )}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50"
              >
                {loading ? 'Saving…' : 'Save Price'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
