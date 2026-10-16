'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Sparkles,
  ShieldCheck,
  CreditCard,
  Building2,
  Users,
  Clock,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Plus,
  MessageCircle,
  PhoneCall,
  Download,
  Calendar,
  Layers,
  Zap,
  Check,
  Coins,
  ExternalLink
} from 'lucide-react'
import { API_BASE, authHeaders, formatDate } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { PlanCheckoutModal } from '@/components/pricing/PlanCheckoutModal'
import {
  fetchInvoices,
  fetchPlansCatalog,
  cancelAutopaySubscription,
  BillingInvoiceSummary,
  BillingPackage,
  CatalogTerm,
  PackagePrice,
  salesTelUrl,
  salesWhatsAppUrl,
  SubscriptionDetails,
  BillingPlan,
} from '@/lib/billing'
import { useSalesContact } from '@/hooks/useSalesContact'
import { toast } from 'sonner'
import Link from 'next/link'

export function SubscriptionBillingPanel() {
  const { user, token } = useAuth()
  const salesContact = useSalesContact()
  const [loading, setLoading] = useState(true)
  const [subscription, setSubscription] = useState<SubscriptionDetails | null>(null)
  const [plans, setPlans] = useState<BillingPlan[]>([])
  const [invoices, setInvoices] = useState<BillingInvoiceSummary[]>([])
  // Terms are whatever the catalog prices; the longest is picked first
  const [terms, setTerms] = useState<CatalogTerm[]>([])
  const [selectedTerm, setSelectedTerm] = useState<CatalogTerm | null>(null)
  // The package chosen on each plan's card (plan code -> package id)
  const [selectedPackageByPlan, setSelectedPackageByPlan] = useState<Record<string, number>>({})
  const [selectedPlanForModal, setSelectedPlanForModal] = useState<BillingPlan | null>(null)
  const [selectedPackageForModal, setSelectedPackageForModal] = useState<BillingPackage | null>(null)
  const [selectedPriceForModal, setSelectedPriceForModal] = useState<PackagePrice | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)

  const applyCatalog = (catalogPlans: BillingPlan[], catalogTerms: CatalogTerm[]) => {
    setPlans(catalogPlans)
    setTerms(catalogTerms)
    // Keep the term already chosen if it is still sold; otherwise the longest one
    setSelectedTerm((current) =>
      (current && catalogTerms.find((t) => t.interval === current.interval && t.count === current.count))
      || catalogTerms[catalogTerms.length - 1]
      || null
    )
  }

  const fetchSubscriptionData = async (_options?: unknown) => {
    try {
      setLoading(true)
      const [subRes, plansData] = await Promise.all([
        fetch(`${API_BASE}/billing/current-subscription`, {
          headers: token ? authHeaders(token) : {}
        }),
        // Signed in, so the catalog also carries any plan made for this account
        fetchPlansCatalog(token || undefined),
      ])
      const subData = await subRes.json()

      if (!subData.success || !plansData.success) throw new Error('Billing data unavailable')
      setSubscription(subData)
      applyCatalog(plansData.plans, plansData.terms || [])
      setLoadFailed(false)

      if (token) {
        fetchInvoices(token)
          .then((r) => setInvoices(r.invoices || []))
          .catch(() => setInvoices([]))
      }
    } catch (err) {
      console.error('Failed to load subscription data:', err)
      setLoadFailed(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true

    Promise.all([
      fetch(`${API_BASE}/billing/current-subscription`, {
        headers: token ? authHeaders(token) : {}
      }),
      fetchPlansCatalog(token || undefined),
    ])
      .then(async ([subRes, plansData]) => {
        const subData = await subRes.json()
        if (!active) return
        if (!subData.success || !plansData.success) throw new Error('Billing data unavailable')
        setSubscription(subData)
        applyCatalog(plansData.plans, plansData.terms || [])
        setLoadFailed(false)

        if (token) {
          fetchInvoices(token)
            .then((r) => {
              if (active) setInvoices(r.invoices || [])
            })
            .catch(() => {
              if (active) setInvoices([])
            })
        }
      })
      .catch((err) => {
        if (!active) return
        console.error('Failed to load subscription data:', err)
        setLoadFailed(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [token])

  const [cancellingAutopay, setCancellingAutopay] = useState(false)

  const handleOpenCheckout = (plan: BillingPlan, pkg: BillingPackage | null, price: PackagePrice | null) => {
    setSelectedPlanForModal(plan)
    setSelectedPackageForModal(pkg)
    setSelectedPriceForModal(price)
    setIsModalOpen(true)
  }

  // The account's own package, at the chosen term (or the first term it is sold for); else the first plan
  const openCurrentPlanCheckout = () => {
    const plan = plans.find((p) => (p.packages || []).some((x) => x.code === subscription?.tier)) || plans[0]
    if (!plan) return
    const pkg = (plan.packages || []).find((x) => x.code === subscription?.tier) || plan.packages?.[0] || null
    const price = pkg?.prices.find(
      (pr) => selectedTerm && pr.interval === selectedTerm.interval && (pr.count ?? pr.interval_count) === selectedTerm.count
    ) || pkg?.prices[0] || null
    handleOpenCheckout(plan, pkg, price)
  }

  const durationKey = !selectedTerm
    ? '1_year'
    : selectedTerm.interval === 'year'
    ? `${selectedTerm.count}_year`
    : selectedTerm.count === 1 ? 'monthly' : `${selectedTerm.count}_month`

  const handleCancelAutopay = async () => {
    if (!token) return
    if (!window.confirm('Are you sure you want to cancel monthly autopay? Your subscription will remain active until the end of your billing cycle.')) return
    setCancellingAutopay(true)
    try {
      const res = await cancelAutopaySubscription(token)
      toast.success(res.message)
      fetchSubscriptionData(true)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(msg || 'Failed to cancel autopay')
    } finally {
      setCancellingAutopay(false)
    }
  }

  // A limit of null is unlimited: no gauge, no "slots left"
  const percentOf = (used?: number, max?: number | null) =>
    used != null && max ? Math.min(100, Math.round((used / max) * 100)) : 0
  const usage = subscription?.usage
  const companiesPercent = percentOf(usage?.companies_linked, usage?.max_companies)
  const usersPercent = percentOf(usage?.users_active, usage?.max_users)
  const slotsLeft = (used?: number, max?: number | null) =>
    max == null ? 'Unlimited' : `${Math.max(0, max - (used ?? 0))} available`
  const limitText = (used?: number, max?: number | null) => `${used ?? 0} of ${max ?? 'Unlimited'}`

  if (loading && !subscription) {
    return <div className="p-8 text-center text-sm text-muted-foreground">Loading subscription…</div>
  }
  if (loadFailed || !subscription) {
    return (
      <div className="p-8 text-center space-y-3">
        <p className="text-sm text-muted-foreground">We could not load your subscription details.</p>
        <button type="button" onClick={fetchSubscriptionData}
          className="px-4 py-2 rounded-xl bg-muted border border-border text-xs font-bold cursor-pointer">
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      
      {/* Active Subscription Status Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-emerald-500/20 bg-gradient-to-br from-emerald-500/10 via-card to-background p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                <Sparkles className="h-3.5 w-3.5" />
                {subscription.plan || 'Standard access'}
              </span>
              {subscription.autopay && !subscription.cancel_at_period_end && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black tracking-wide bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30">
                  <RefreshCw className="h-3.5 w-3.5" />
                  Monthly Autopay Active
                </span>
              )}
              {subscription.cancel_at_period_end && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black tracking-wide bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                  <Clock className="h-3.5 w-3.5" />
                  Cancels at Period End
                </span>
              )}
            </div>

            <div>
              <h2 className="text-2xl font-black text-foreground flex items-center gap-2">
                <span>{subscription.plan ? `${subscription.plan} plan` : 'Your current access'}</span>
                {subscription.package && (
                  <span className="text-sm font-semibold text-muted-foreground px-2.5 py-0.5 rounded-lg bg-muted border border-border">
                    {subscription.package}
                  </span>
                )}
              </h2>
              <p className="text-xs text-muted-foreground mt-1 max-w-xl">
                {subscription.plan
                  ? 'The limits below are what your account is allowed today.'
                  : 'No paid plan is recorded for this account yet. Talk to our team to choose one.'}
              </p>
            </div>

            {subscription.valid_until && (
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1">
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  Valid until: {formatDate(subscription.valid_until)}
                </span>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-2 shrink-0">
            {subscription.autopay && !subscription.cancel_at_period_end && (
              <button
                type="button"
                onClick={handleCancelAutopay}
                disabled={cancellingAutopay}
                className="px-4 py-3 rounded-2xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-bold text-xs border border-rose-500/30 transition-colors flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                title="Cancel recurring monthly charges"
              >
                <Clock className="h-3.5 w-3.5" /> {cancellingAutopay ? 'Cancelling...' : 'Cancel Autopay'}
              </button>
            )}
            <Link
              href={subscription.tier ? `/pricing?plan=${subscription.tier}` : '/pricing'}
              className="px-5 py-3 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-black text-xs shadow-md shadow-emerald-500/20 hover:opacity-95 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Zap className="h-4 w-4" /> Change Package
            </Link>
            <Link
              href="/pricing"
              target="_blank"
              className="px-4 py-3 rounded-2xl bg-muted hover:bg-muted/80 text-foreground font-bold text-xs border border-border transition-colors flex items-center justify-center gap-1.5"
            >
              View All Tiers <ExternalLink className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/platform/billing"
              className="px-4 py-3 rounded-2xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 dark:text-amber-400 font-bold text-xs border border-amber-500/30 transition-colors flex items-center justify-center gap-1.5"
            >
              <ShieldCheck className="h-3.5 w-3.5" /> Operator Console
            </Link>
          </div>
        </div>
      </div>

      {/* Resource Quota & Usage Gauges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        
        {/* Companies Quota Card */}
        <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
              <Building2 className="h-4 w-4 text-emerald-500" /> Connected Companies
            </div>
            <span className="text-xs font-bold text-emerald-600">
              {limitText(usage?.companies_linked, usage?.max_companies)} Slots Used
            </span>
          </div>

          <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${companiesPercent}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <span className="text-muted-foreground">
              {slotsLeft(usage?.companies_linked, usage?.max_companies)} company slots
            </span>
            <button
              type="button"
              onClick={() => {
                openCurrentPlanCheckout()
              }}
              className="text-emerald-600 font-bold hover:underline cursor-pointer flex items-center gap-1"
            >
              + Add company slots
            </button>
          </div>
        </div>

        {/* Users Quota Card */}
        <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
              <Users className="h-4 w-4 text-blue-500" /> Active User Licenses
            </div>
            <span className="text-xs font-bold text-blue-600">
              {limitText(usage?.users_active, usage?.max_users)} Licenses Used
            </span>
          </div>

          <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${usersPercent}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <span className="text-muted-foreground">
              {slotsLeft(usage?.users_active, usage?.max_users)} licenses
            </span>
            <button
              type="button"
              onClick={() => {
                openCurrentPlanCheckout()
              }}
              className="text-blue-600 font-bold hover:underline cursor-pointer flex items-center gap-1"
            >
              + Add user licenses
            </button>
          </div>
        </div>

      </div>

      {/* Metered Pack Credits (E-Invoicing & WhatsApp) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
              <Zap className="h-4 w-4 text-amber-500" /> E-Invoicing Credits
            </div>
            <span className="text-sm font-black text-amber-600 dark:text-amber-400">
              {(subscription.credits?.einvoice ?? 0).toLocaleString()} Credits
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Used for real-time IRN generation, e-way bills, and QR stamping directly from Tally vouchers.
          </p>
          <div className="flex items-center justify-between text-xs pt-1 border-t border-border/50">
            <span className="text-muted-foreground font-medium">Standard pack: 1,000 IRNs</span>
            <button
              type="button"
              onClick={() => {
                openCurrentPlanCheckout()
              }}
              className="text-amber-600 dark:text-amber-400 font-bold hover:underline cursor-pointer flex items-center gap-1"
            >
              + Top-up Credits
            </button>
          </div>
        </div>

        <div className="bg-card border border-border rounded-2xl p-5 space-y-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase">
              <MessageCircle className="h-4 w-4 text-emerald-500" /> WhatsApp Utility Credits
            </div>
            <span className="text-sm font-black text-emerald-600 dark:text-emerald-400">
              {(subscription.credits?.whatsapp ?? 0).toLocaleString()} Messages
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Used for automated invoice PDFs, payment reminders, and customer ledger statements via Meta Cloud API.
          </p>
          <div className="flex items-center justify-between text-xs pt-1 border-t border-border/50">
            <span className="text-muted-foreground font-medium">Standard pack: 1,000 messages</span>
            <button
              type="button"
              onClick={() => {
                openCurrentPlanCheckout()
              }}
              className="text-emerald-600 dark:text-emerald-400 font-bold hover:underline cursor-pointer flex items-center gap-1"
            >
              + Top-up Messages
            </button>
          </div>
        </div>
      </div>

      {/* Available Plans Selection Cards */}
      <div className="space-y-4 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-black text-foreground">Available Subscription Tiers</h3>
            <p className="text-xs text-muted-foreground">
              Compare plans. Our team activates the plan you choose and issues the GST invoice.
            </p>
          </div>

          {/* Term selector: the terms the catalog sells */}
          {terms.length > 1 && (
            <div className="inline-flex flex-wrap p-1 rounded-xl bg-muted border border-border self-start sm:self-auto gap-1">
              {terms.map((t) => {
                const active = selectedTerm?.interval === t.interval && selectedTerm?.count === t.count
                return (
                  <button
                    key={`${t.interval}-${t.count}`}
                    type="button"
                    onClick={() => setSelectedTerm(t)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      active ? 'bg-emerald-500 text-white shadow-sm' : 'text-muted-foreground'
                    }`}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((p) => {
            const packages = p.packages || []
            // The account's own package is on this plan when its code is one of the plan's packages
            const currentPkg = packages.find((pkg) => pkg.code === subscription.tier)
            const isCurrent = Boolean(currentPkg)
            const chosenId = selectedPackageByPlan[p.id] ?? currentPkg?.id ?? packages[0]?.id
            const pkg = packages.find((x) => x.id === chosenId) || packages[0] || null
            const price = pkg?.prices.find(
              (pr) => selectedTerm && pr.interval === selectedTerm.interval
                && (pr.count ?? pr.interval_count) === selectedTerm.count
            ) || null

            return (
              <div
                key={p.id}
                className={`rounded-2xl border bg-card p-5 space-y-4 transition-all relative ${
                  isCurrent ? 'ring-2 ring-emerald-500 border-emerald-500/50 bg-emerald-500/[0.02]' : 'border-border hover:shadow-md'
                }`}
              >
                {isCurrent && (
                  <span className="absolute -top-2.5 right-4 px-2.5 py-0.5 rounded-full bg-emerald-500 text-white font-bold text-[10px] uppercase tracking-wider">
                    Current Plan
                  </span>
                )}

                <div>
                  <div className="flex items-center justify-between">
                    <h4 className="font-black text-base">{p.name}</h4>
                    {p.badge && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-muted text-muted-foreground border border-border">
                        {p.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                    {p.tagline}
                  </p>
                </div>

                {packages.length > 1 && (
                  <select
                    value={pkg?.id ?? ''}
                    onChange={(e) => setSelectedPackageByPlan((prev) => ({ ...prev, [p.id]: Number(e.target.value) }))}
                    className="w-full text-xs font-semibold px-3 py-2 rounded-xl border border-border bg-background outline-none"
                    aria-label={`${p.name} package`}
                  >
                    {packages.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.label}{x.id === currentPkg?.id ? ' (current)' : ''}
                      </option>
                    ))}
                  </select>
                )}

                <div className="border-y border-border/60 py-3 space-y-0.5">
                  {price ? (
                    <>
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-black">₹{price.amount.toLocaleString('en-IN')}</span>
                        <span className="text-[11px] text-muted-foreground">/ {selectedTerm?.label}</span>
                      </div>
                      {price.per_month != null && (
                        <span className="text-xs font-bold text-emerald-600 block">
                          ₹{price.per_month.toLocaleString('en-IN')}/month
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground block py-1.5">
                      Not sold for {selectedTerm?.label || 'this term'}
                    </span>
                  )}
                </div>

                <div className="space-y-1.5 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5 font-bold text-foreground">
                    <Building2 className="h-3.5 w-3.5 text-emerald-500" />
                    <span>{pkg?.limits?.companies_label || p.limits.companies_label}</span>
                  </div>
                  <div className="flex items-center gap-1.5 font-bold text-foreground">
                    <Users className="h-3.5 w-3.5 text-blue-500" />
                    <span>{pkg?.limits?.users_label || p.limits.users_label}</span>
                  </div>
                  {(p.highlights || []).slice(0, 3).map((h: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-1.5 text-[11px]">
                      <Check className="h-3 w-3 text-emerald-500 shrink-0" />
                      <span>{h}</span>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => handleOpenCheckout(p, pkg, price)}
                  disabled={!price}
                  className={`w-full py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    isCurrent
                      ? 'bg-muted hover:bg-muted/80 text-foreground border border-border'
                      : 'bg-emerald-500 hover:bg-emerald-600 text-white'
                  }`}
                >
                  {isCurrent && pkg?.id === currentPkg?.id ? 'Renew' : `Choose ${p.name}`}
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* Invoices & Receipts */}
      {invoices.length > 0 && (
        <div className="space-y-3 pt-2">
          <div>
            <h3 className="text-lg font-black text-foreground">Invoices & Receipts</h3>
            <p className="text-xs text-muted-foreground">GST-compliant tax invoices for your subscription payments.</p>
          </div>
          <div className="border border-border rounded-2xl overflow-hidden bg-card">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/50 border-b border-border text-muted-foreground font-bold">
                  <tr>
                    <th className="px-4 py-3">Invoice Number</th>
                    <th className="px-4 py-3">Date</th>
                    <th className="px-4 py-3">Order Ref</th>
                    <th className="px-4 py-3">Place of Supply</th>
                    <th className="px-4 py-3 text-right">Amount (incl. GST)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3 font-mono font-bold text-foreground">{inv.invoice_number}</td>
                      <td className="px-4 py-3 text-muted-foreground">{inv.date ? formatDate(inv.date) : '—'}</td>
                      <td className="px-4 py-3 font-mono text-muted-foreground">{inv.order_ref}</td>
                      <td className="px-4 py-3 text-muted-foreground">State Code {inv.place_of_supply || '07'}</td>
                      <td className="px-4 py-3 text-right font-black text-foreground">₹{inv.total_rupees.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Enterprise & Custom Inquiries Support Card */}
      {/* Only when a sales number is set (BILLING_SALES_PHONE) */}
      {salesContact && (
        <div className="rounded-2xl border border-border bg-muted/40 p-5 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
              <MessageCircle className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold">Have Questions About Multi-Branch Licensing?</h4>
              <p className="text-xs text-muted-foreground">
                Our business onboarding specialists are available on WhatsApp and Phone (9:00 AM - 8:00 PM IST).
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <a
              href={salesWhatsAppUrl(salesContact, 'Hi MyTally Support, I have a billing inquiry regarding my account.')}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 rounded-xl bg-[#25D366] hover:bg-[#20ba59] text-white text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <MessageCircle className="h-3.5 w-3.5" /> Chat on WhatsApp
            </a>
            <a
              href={salesTelUrl(salesContact)}
              className="px-4 py-2 rounded-xl bg-card hover:bg-muted text-foreground border border-border text-xs font-bold flex items-center gap-1.5 transition-colors"
            >
              <PhoneCall className="h-3.5 w-3.5 text-blue-500" /> Call Support
            </a>
          </div>
        </div>
      )}

      {/* Checkout Modal */}
      <PlanCheckoutModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        plan={selectedPlanForModal}
        packageItem={selectedPackageForModal}
        priceId={selectedPriceForModal?.price_id ?? null}
        termLabel={selectedTerm?.label ?? null}
        durationKey={durationKey}
        onSuccess={() => {
          fetchSubscriptionData()
        }}
      />

    </div>
  )
}
