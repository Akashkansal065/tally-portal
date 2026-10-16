'use client'

import React, { useState, useEffect, useMemo } from 'react'
import {
  Sparkles,
  Plus,
  Edit2,
  Power,
  PowerOff,
  Eye,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  X,
  Search,
  IndianRupee,
  Calendar,
  Layers,
  Users,
  Building,
  Info,
  Clock,
  ShieldAlert,
} from 'lucide-react'
import {
  consoleBillingApi,
  ConsoleApiError,
  AdminCouponDetail,
  AdminCouponItem,
  AdminCouponPayload,
  AdminCatalogPlan,
} from '@/console/api'
import { cn } from '@/lib/utils'

// The server keeps coupon dates as naive UTC. These turn them into the operator's local calendar day and back:
// a coupon runs from the start of its first day to the end of its last day, local time.
function serverDate(value: string | null | undefined): Date | null {
  if (!value) return null
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

function localDayInput(value: string | null | undefined): string {
  const d = serverDate(value)
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function dayStartIso(day: string): string | null {
  return day ? new Date(`${day}T00:00:00`).toISOString() : null
}

function dayEndIso(day: string): string | null {
  return day ? new Date(`${day}T23:59:59`).toISOString() : null
}

export function CouponsTab() {
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [coupons, setCoupons] = useState<AdminCouponItem[]>([])
  const [catalogPlans, setCatalogPlans] = useState<AdminCatalogPlan[]>([])

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingCoupon, setEditingCoupon] = useState<AdminCouponItem | null>(null)
  const [detailCouponId, setDetailCouponId] = useState<number | null>(null)
  const [deactivatingCoupon, setDeactivatingCoupon] = useState<AdminCouponItem | null>(null)

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
      const [couponsRes, catRes] = await Promise.all([
        consoleBillingApi.getCoupons(),
        consoleBillingApi.getCatalog().catch(() => []),
      ])
      setCoupons(couponsRes)
      setCatalogPlans(catRes)
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to load coupons')
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

  // Filtered coupons
  const filteredCoupons = useMemo(() => {
    return coupons.filter((c) => {
      const matchesSearch =
        searchQuery === '' ||
        c.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()))

      const matchesStatus = statusFilter === 'all' || c.status === statusFilter
      return matchesSearch && matchesStatus
    })
  }, [coupons, searchQuery, statusFilter])

  // Activate / Deactivate
  const handleToggleActive = async (c: AdminCouponItem) => {
    if (c.is_active) {
      setDeactivatingCoupon(c)
      return
    }

    setActionLoading(true)
    try {
      await consoleBillingApi.activateCoupon(c.id)
      showSuccess(`Coupon ${c.code} activated.`)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to activate coupon')
    } finally {
      setActionLoading(false)
    }
  }

  const confirmDeactivate = async () => {
    if (!deactivatingCoupon) return
    setActionLoading(true)
    try {
      await consoleBillingApi.deactivateCoupon(deactivatingCoupon.id)
      showSuccess(`Coupon ${deactivatingCoupon.code} switched off. Pending orders keep their quoted price.`)
      setDeactivatingCoupon(null)
      loadData()
    } catch (err: unknown) {
      showError(err instanceof ConsoleApiError ? err.detail : 'Failed to deactivate coupon')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Feedback Messages */}
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

      {/* Header & Controls */}
      <div className="bg-white dark:bg-card border border-border rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-black text-foreground">Discount Coupons</h3>
            <p className="text-xs text-muted-foreground">
              Manage promotional discount codes, validity periods, redemption limits, and plan targeting
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 flex items-center gap-1.5 shadow-sm cursor-pointer self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" /> New Coupon
          </button>
        </div>

        {/* Search & Status Filters */}
        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between pt-2 border-t border-border/60">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search code or description..."
              className="w-full bg-background border border-border rounded-xl pl-9 pr-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
            {['all', 'active', 'scheduled', 'expired', 'used_up', 'off'].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-xs font-bold capitalize transition-all cursor-pointer',
                  statusFilter === st
                    ? 'bg-slate-900 dark:bg-white text-white dark:text-slate-900 shadow-sm'
                    : 'bg-muted/60 text-muted-foreground hover:text-foreground'
                )}
              >
                {st.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Coupons Table */}
      <div className="bg-white dark:bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
        {loading && coupons.length === 0 ? (
          <div className="p-16 text-center text-sm text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-emerald-500" />
            <span>Loading coupons…</span>
          </div>
        ) : filteredCoupons.length === 0 ? (
          <div className="p-16 text-center text-xs text-muted-foreground">
            No coupons found matching your criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-muted-foreground">
                  <th className="py-3 px-4 font-bold">Code</th>
                  <th className="py-3 px-4 font-bold">Discount</th>
                  <th className="py-3 px-4 font-bold">Applies To</th>
                  <th className="py-3 px-4 font-bold">Validity</th>
                  <th className="py-3 px-4 font-bold text-center">Uses</th>
                  <th className="py-3 px-4 font-bold text-center">Status</th>
                  <th className="py-3 px-4 font-bold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredCoupons.map((c) => {
                  let statusBadge = (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                      Active
                    </span>
                  )
                  if (c.status === 'off') {
                    statusBadge = (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-muted text-muted-foreground border border-border">
                        Off
                      </span>
                    )
                  } else if (c.status === 'scheduled') {
                    statusBadge = (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-600 border border-blue-500/20">
                        Scheduled
                      </span>
                    )
                  } else if (c.status === 'expired') {
                    statusBadge = (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 border border-rose-500/20">
                        Expired
                      </span>
                    )
                  } else if (c.status === 'used_up') {
                    statusBadge = (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 border border-amber-500/20">
                        Used Up
                      </span>
                    )
                  }

                  const discountStr =
                    c.kind === 'percent'
                      ? `${c.value}%${c.max_discount_rupees ? ` (max ₹${c.max_discount_rupees.toLocaleString('en-IN')})` : ''}`
                      : `₹${(c.value_rupees ?? c.value / 100).toLocaleString('en-IN')} flat`

                  const appliesToStr =
                    c.plan_codes && c.plan_codes.length > 0
                      ? c.plan_codes.map((p) => p.toUpperCase()).join(', ')
                      : 'All Plans & Add-ons'
                  const validFrom = serverDate(c.valid_from)
                  const validUntil = serverDate(c.valid_until)

                  return (
                    <tr key={c.id} className="hover:bg-muted/20">
                      <td className="py-3.5 px-4 font-mono font-bold text-foreground">
                        <div className="flex items-center gap-1.5">
                          <span>{c.code}</span>
                          {c.account_id != null && (
                            <span
                              className="text-[9px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-600 font-sans font-bold"
                              title={`Only account #${c.account_id} can use it`}
                            >
                              Private
                            </span>
                          )}
                        </div>
                        {c.description && (
                          <div className="text-[10px] text-muted-foreground font-sans line-clamp-1 mt-0.5">
                            {c.description}
                          </div>
                        )}
                      </td>

                      <td className="py-3.5 px-4 font-bold text-foreground">
                        {discountStr}
                      </td>

                      <td className="py-3.5 px-4 text-muted-foreground max-w-xs truncate" title={appliesToStr}>
                        {appliesToStr}
                      </td>

                      <td className="py-3.5 px-4 text-muted-foreground text-[11px]">
                        {validFrom || validUntil ? (
                          <div>
                            {validFrom && <div>From: {validFrom.toLocaleDateString()}</div>}
                            {validUntil ? (
                              <div>Until: {validUntil.toLocaleDateString()}</div>
                            ) : (
                              <div>No expiry</div>
                            )}
                          </div>
                        ) : (
                          'Always valid'
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-center">
                        <span className="font-semibold text-foreground">
                          {c.uses.total} / {c.max_redemptions ?? '∞'}
                        </span>
                        {c.uses.pending > 0 && (
                          <span className="text-[10px] text-amber-600 block font-medium">
                            {c.uses.pending} awaiting payment
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 text-center">
                        {statusBadge}
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => setDetailCouponId(c.id)}
                            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                            title="View Redemptions"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingCoupon(c)}
                            className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                            title="Edit Coupon"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleToggleActive(c)}
                            className={cn(
                              'p-1.5 rounded-lg cursor-pointer',
                              c.is_active
                                ? 'text-rose-500 hover:bg-rose-500/10'
                                : 'text-emerald-500 hover:bg-emerald-500/10'
                            )}
                            title={c.is_active ? 'Switch off coupon' : 'Activate coupon'}
                          >
                            {c.is_active ? (
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

      {/* ── MODALS ── */}

      {/* Create / Edit Coupon Modal */}
      {(showCreateModal || editingCoupon) && (
        <CouponFormModal
          coupon={editingCoupon}
          catalogPlans={catalogPlans}
          onClose={() => {
            setShowCreateModal(false)
            setEditingCoupon(null)
          }}
          onSuccess={() => {
            setShowCreateModal(false)
            setEditingCoupon(null)
            showSuccess(editingCoupon ? 'Coupon updated.' : 'New coupon created.')
            loadData()
          }}
        />
      )}

      {/* Coupon Detail Drawer / Modal */}
      {detailCouponId !== null && (
        <CouponDetailModal
          couponId={detailCouponId}
          onClose={() => setDetailCouponId(null)}
        />
      )}

      {/* Deactivate Confirmation Modal */}
      {deactivatingCoupon && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-sm p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <ShieldAlert className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-black text-foreground">Switch Off Coupon?</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Switching off coupon <strong>{deactivatingCoupon.code}</strong> will prevent new checkouts from using it.
              <br />
              <strong className="text-foreground mt-1 block">
                Pending orders already created will keep their quoted price.
              </strong>
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeactivatingCoupon(null)}
                className="px-4 py-2 rounded-xl border border-border text-xs font-bold text-muted-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={actionLoading}
                onClick={confirmDeactivate}
                className="px-5 py-2 rounded-xl bg-rose-600 text-white text-xs font-bold hover:bg-rose-700 disabled:opacity-50 cursor-pointer"
              >
                {actionLoading ? 'Switching Off…' : 'Switch Off'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function CouponFormModal({
  coupon,
  catalogPlans,
  onClose,
  onSuccess,
}: {
  coupon: AdminCouponItem | null
  catalogPlans: AdminCatalogPlan[]
  onClose: () => void
  onSuccess: () => void
}) {
  const isEditing = Boolean(coupon)
  // Frozen once any order has used or reserved it, the same rule the server applies
  const isFrozen = Boolean(coupon && coupon.uses.total > 0)

  const [code, setCode] = useState(coupon ? coupon.code : '')
  const [description, setDescription] = useState(coupon?.description || '')
  const [kind, setKind] = useState<'percent' | 'flat'>(coupon?.kind || 'percent')
  const [value, setValue] = useState<number>(
    coupon ? (coupon.kind === 'flat' ? Math.round(coupon.value / 100) : coupon.value) : 20
  )
  const [maxDiscountRupees, setMaxDiscountRupees] = useState<number>(
    coupon?.max_discount_rupees ?? (coupon?.max_discount_paise ? Math.round(coupon.max_discount_paise / 100) : 0)
  )

  const [validFrom, setValidFrom] = useState(localDayInput(coupon?.valid_from))
  const [validUntil, setValidUntil] = useState(localDayInput(coupon?.valid_until))
  const [maxRedemptions, setMaxRedemptions] = useState<number | ''>(coupon?.max_redemptions ?? '')
  const [perAccountLimit, setPerAccountLimit] = useState<number>(coupon?.per_account_limit ?? 1)
  const [firstPurchaseOnly, setFirstPurchaseOnly] = useState(coupon?.first_purchase_only ?? false)
  const [accountId, setAccountId] = useState<number | ''>(coupon?.account_id ?? '')
  const [selectedPlanCodes, setSelectedPlanCodes] = useState<string[]>(coupon?.plan_codes || [])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Live discount preview calculation on Gold 1yr (₹24,999)
  const sampleAmount = 24999
  const sampleSavings = useMemo(() => {
    if (kind === 'percent') {
      const raw = Math.round((sampleAmount * value) / 100)
      return maxDiscountRupees > 0 ? Math.min(raw, maxDiscountRupees) : raw
    }
    return Math.min(sampleAmount, value)
  }, [kind, value, maxDiscountRupees])

  const togglePlanCode = (pCode: string) => {
    setSelectedPlanCodes((prev) =>
      prev.includes(pCode) ? prev.filter((c) => c !== pCode) : [...prev, pCode]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const payload: AdminCouponPayload = {
        description: description || null,
        valid_from: dayStartIso(validFrom),
        valid_until: dayEndIso(validUntil),
        max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
        per_account_limit: Number(perAccountLimit) || 1,
        first_purchase_only: firstPurchaseOnly,
        account_id: accountId ? Number(accountId) : null,
        plan_codes: selectedPlanCodes.length > 0 ? selectedPlanCodes : null,
      }

      if (!isEditing) {
        await consoleBillingApi.createCoupon({
          ...payload,
          code: code.trim().toUpperCase(),
          kind,
          value: kind === 'flat' ? Math.round(value * 100) : value,
          max_discount_paise: kind === 'percent' && maxDiscountRupees > 0 ? Math.round(maxDiscountRupees * 100) : null,
        })
      } else if (coupon) {
        if (!isFrozen) {
          payload.kind = kind
          payload.value = kind === 'flat' ? Math.round(value * 100) : value
          payload.max_discount_paise =
            kind === 'percent' && maxDiscountRupees > 0 ? Math.round(maxDiscountRupees * 100) : null
        }
        await consoleBillingApi.updateCoupon(coupon.id, payload)
      }
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof ConsoleApiError ? err.detail : 'Failed to save coupon')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-lg p-6 shadow-xl space-y-4 my-8">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="text-base font-black text-foreground">
            {isEditing ? `Edit Coupon: ${coupon?.code}` : 'Create New Coupon'}
          </h3>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {isFrozen && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <strong>Money terms are frozen.</strong>
              <p className="mt-0.5">
                This coupon has already been redeemed. To protect existing orders and financial audit records, discount rate and caps cannot be altered.
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
            <label className="text-xs font-bold text-foreground block mb-1">Coupon Code</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9_-]/g, ''))}
              disabled={isEditing}
              required
              placeholder="e.g. SUMMER30"
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none font-mono disabled:opacity-50"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-foreground block mb-1">Internal Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Internal operator note, not shown to customers"
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          {/* Discount Rate */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-xl border border-border/80 bg-muted/20">
            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Discount Type</label>
              <select
                value={kind}
                onChange={(e) => setKind(e.target.value as 'percent' | 'flat')}
                disabled={isFrozen}
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none disabled:opacity-50"
              >
                <option value="percent">Percentage (%)</option>
                <option value="flat">Flat Amount (₹)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-bold text-foreground block mb-1">
                {kind === 'percent' ? 'Percentage (1-100%)' : 'Flat Value (₹)'}
              </label>
              <input
                type="number"
                min={1}
                max={kind === 'percent' ? 100 : undefined}
                value={value}
                onChange={(e) => setValue(Number(e.target.value))}
                disabled={isFrozen}
                required
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none disabled:opacity-50"
              />
            </div>

            {kind === 'percent' && (
              <div className="sm:col-span-2">
                <label className="text-xs font-bold text-foreground block mb-1">
                  Maximum Discount Cap (₹, 0 for no cap)
                </label>
                <input
                  type="number"
                  min={0}
                  value={maxDiscountRupees}
                  onChange={(e) => setMaxDiscountRupees(Number(e.target.value))}
                  disabled={isFrozen}
                  className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none disabled:opacity-50"
                />
              </div>
            )}

            {/* Live Discount Preview Line */}
            <div className="sm:col-span-2 pt-2 border-t border-border/60 text-xs text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>
                On a ₹24,999 Gold plan, customer saves{' '}
                <strong className="text-emerald-600 font-black">
                  ₹{sampleSavings.toLocaleString('en-IN')}
                </strong>
                .
              </span>
            </div>
          </div>

          {/* Applicable Plans Checklist */}
          <div>
            <label className="text-xs font-bold text-foreground block mb-1.5">
              Applicable Plans & Packages (leave empty for all)
            </label>
            <div className="grid grid-cols-2 gap-2 max-h-36 overflow-y-auto p-2 rounded-xl border border-border bg-muted/20">
              {catalogPlans.map((p) => (
                <div key={p.id} className="col-span-2 space-y-1">
                  <label className="flex items-center gap-2 text-xs font-semibold text-foreground cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedPlanCodes.includes(p.code)}
                      onChange={() => togglePlanCode(p.code)}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                    />
                    <span>{p.name} — every package</span>
                  </label>
                  {p.packages.length > 1 && (
                    <div className="pl-6 grid grid-cols-1 sm:grid-cols-2 gap-1">
                      {p.packages.map((pkg) => (
                        <label
                          key={pkg.id}
                          className="flex items-center gap-2 text-[11px] text-muted-foreground cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedPlanCodes.includes(pkg.code)}
                            disabled={selectedPlanCodes.includes(p.code)}
                            onChange={() => togglePlanCode(pkg.code)}
                            className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                          />
                          <span>{pkg.label}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <label className="flex items-center gap-2 text-xs font-semibold text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedPlanCodes.includes('addon')}
                  onChange={() => togglePlanCode('addon')}
                  className="rounded border-border text-emerald-600 focus:ring-emerald-500"
                />
                <span>Add-ons Only</span>
              </label>
            </div>
          </div>

          {/* Dates & Limits */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Valid From</label>
              <input
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Valid Until</label>
              <input
                type="date"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground block mb-1">
                Max Redemptions (Total)
              </label>
              <input
                type="number"
                min={1}
                value={maxRedemptions}
                onChange={(e) => setMaxRedemptions(e.target.value ? Number(e.target.value) : '')}
                placeholder="Unlimited"
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground block mb-1">
                Per-Account Limit
              </label>
              <input
                type="number"
                min={1}
                value={perAccountLimit}
                onChange={(e) => setPerAccountLimit(Number(e.target.value))}
                className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
              />
            </div>
          </div>

          {/* Restrict to Single Account */}
          <div>
            <label className="text-xs font-bold text-foreground block mb-1">
              Restrict to Single Account ID (optional private coupon)
            </label>
            <input
              type="number"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : '')}
              placeholder="e.g. 42 (leave empty for public coupon)"
              className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
            />
          </div>

          <label className="flex items-center gap-2 p-2.5 rounded-xl border border-border bg-muted/20 cursor-pointer">
            <input
              type="checkbox"
              checked={firstPurchaseOnly}
              onChange={(e) => setFirstPurchaseOnly(e.target.checked)}
              className="rounded border-border text-emerald-600 focus:ring-emerald-500"
            />
            <span className="text-xs font-semibold text-foreground">
              First Purchase Only (account must have 0 prior paid orders)
            </span>
          </label>

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
              className="px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold hover:bg-emerald-700 disabled:opacity-50 cursor-pointer"
            >
              {loading ? 'Saving…' : isEditing ? 'Save Changes' : 'Create Coupon'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CouponDetailModal({
  couponId,
  onClose,
}: {
  couponId: number
  onClose: () => void
}) {
  const [data, setData] = useState<AdminCouponDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    consoleBillingApi
      .getCoupon(couponId)
      .then((res) => setData(res))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [couponId])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white dark:bg-card border border-border rounded-2xl w-full max-w-2xl p-6 shadow-xl space-y-5 my-8">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div>
            <h3 className="text-base font-black text-foreground">
              Coupon Details: {data ? data.code : '…'}
            </h3>
            <p className="text-xs text-muted-foreground">Redemptions history and usage metrics</p>
          </div>
          <button onClick={onClose}>
            <X className="w-4 h-4 text-muted-foreground hover:text-foreground" />
          </button>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
            <span>Loading coupon details…</span>
          </div>
        ) : !data ? (
          <div className="py-12 text-center text-xs text-rose-600">Failed to load coupon details.</div>
        ) : (
          <div className="space-y-4">
            {/* Metrics Row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl border border-border bg-muted/30">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                  Status
                </span>
                <span className="text-sm font-black text-foreground capitalize mt-0.5 block">
                  {data.status}
                </span>
              </div>

              <div className="p-3 rounded-xl border border-border bg-muted/30">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                  Paid Uses
                </span>
                <span className="text-sm font-black text-emerald-600 mt-0.5 block">
                  {data.uses?.paid ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-xl border border-border bg-muted/30">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                  Pending Orders
                </span>
                <span className="text-sm font-black text-amber-600 mt-0.5 block">
                  {data.uses?.pending ?? 0}
                </span>
              </div>

              <div className="p-3 rounded-xl border border-border bg-muted/30">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
                  Total Discount Given
                </span>
                <span className="text-sm font-black text-foreground mt-0.5 block">
                  ₹{(data.total_discount_given_rupees ?? 0).toLocaleString('en-IN')}
                </span>
              </div>
            </div>

            {/* Redemptions Table */}
            <div>
              <h4 className="text-xs font-black text-foreground mb-2">Redemptions Log</h4>
              {data.redemptions && data.redemptions.length > 0 ? (
                <div className="overflow-x-auto max-h-60 rounded-xl border border-border">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-muted-foreground">
                        <th className="py-2.5 px-3 font-bold">Account</th>
                        <th className="py-2.5 px-3 font-bold">Order Ref</th>
                        <th className="py-2.5 px-3 font-bold">Order Status</th>
                        <th className="py-2.5 px-3 font-bold text-right">Discount</th>
                        <th className="py-2.5 px-3 font-bold text-right">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {data.redemptions.map((r) => (
                        <tr key={r.id}>
                          <td className="py-2 px-3 font-semibold text-foreground">
                            {r.account_name}
                          </td>
                          <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground">
                            {r.order_reference || `#${r.order_id}`}
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={cn(
                                'text-[9px] px-1.5 py-0.2 rounded font-bold uppercase',
                                r.order_status === 'paid'
                                  ? 'bg-emerald-500/10 text-emerald-600'
                                  : 'bg-muted text-muted-foreground'
                              )}
                            >
                              {r.order_status || 'unknown'}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-foreground">
                            ₹{r.discount_rupees?.toLocaleString('en-IN')}
                          </td>
                          <td className="py-2 px-3 text-right text-muted-foreground text-[10px]">
                            {serverDate(r.created_at)?.toLocaleDateString() ?? '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground py-4 text-center border border-dashed border-border rounded-xl">
                  No redemptions recorded for this coupon yet.
                </p>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-muted text-xs font-bold text-foreground hover:bg-muted/80 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
