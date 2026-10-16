'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  Check,
  X as CloseIcon,
  Sparkles,
  Shield,
  HelpCircle,
  Zap,
  Building2,
  Users,
  Smartphone,
  PhoneCall,
  MessageCircle,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ShieldCheck,
  Clock,
  Layers,
  FileSpreadsheet,
  Lock,
  Plus,
  Minus,
  CheckCircle2,
  Globe,
  Database
} from 'lucide-react'
import { PlanCheckoutModal } from '@/components/pricing/PlanCheckoutModal'
import {
  BillingPlan,
  BillingPackage,
  PackagePrice,
  CatalogTerm,
  BillingAddon,
  DurationKey,
  loadPublicCatalog,
  salesTelUrl,
  salesWhatsAppUrl
} from '@/lib/billing'
import { useSalesContact } from '@/hooks/useSalesContact'

const FAQS = [
  {
    q: 'How does MyTally connect with my Tally software?',
    a: 'MyTally uses a lightweight desktop sync agent that connects with TallyPrime or Tally.ERP 9 running on your computer. It reads data securely in read-only mode and syncs it to your private cloud instance using bank-grade 256-bit encryption.'
  },
  {
    q: 'Does Tally need to be kept running 24/7?',
    a: 'No! Once your data is synced, you can view your reports, outstanding balances, sales analytics, and inventory from your mobile phone or laptop anytime, even when your office Tally PC is turned off.'
  },
  {
    q: 'Can I add extra users or companies to my plan later?',
    a: 'Yes. Extra user licenses and extra company slots can be added to a plan when you buy it, or on top of a running plan for the time left in it. The current prices are shown in the add-ons section above.'
  },
  {
    q: 'Is there a free trial available?',
    a: 'Yes! Every new account gets an unrestricted 7-day free trial of our Gold Plan with zero setup fees and no credit card required.'
  },
  {
    q: 'Can I generate E-Invoices and E-Way Bills directly from MyTally?',
    a: 'Yes! Our Diamond (Enterprise) plan provides certified GSP integration. You can generate legally valid E-Invoices with IRN, signed QR code, and E-Way Bills directly from the mobile app or web portal in 1 click.'
  },
  {
    q: 'Is my financial data secure?',
    a: '100% secure. Your financial data is encrypted at rest and in transit using SHA-256 and SSL encryption. Each customer has complete tenant isolation, meaning your data is never accessible to anyone else.'
  }
]

function PricingContent() {
  const searchParams = useSearchParams()
  const targetPlan = searchParams.get('plan')

  const [catalogTerms, setCatalogTerms] = useState<CatalogTerm[]>([])
  const [selectedTerm, setSelectedTerm] = useState<CatalogTerm | null>(null)
  const [selectedPackageByPlan, setSelectedPackageByPlan] = useState<Record<string, number>>({})

  const [extraUsers, setExtraUsers] = useState(0)
  const [extraCompanies, setExtraCompanies] = useState(0)
  const [selectedPlanForModal, setSelectedPlanForModal] = useState<BillingPlan | null>(null)
  const [selectedPackageForModal, setSelectedPackageForModal] = useState<BillingPackage | null>(null)
  const [selectedPriceIdForModal, setSelectedPriceIdForModal] = useState<number | null>(null)
  const [selectedTermLabelForModal, setSelectedTermLabelForModal] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0)
  const [isComparisonOpen, setIsComparisonOpen] = useState(false)

  // Catalog from API
  const [catalogPlans, setCatalogPlans] = useState<BillingPlan[]>([])
  const [catalogAddons, setCatalogAddons] = useState<BillingAddon[]>([])
  const [catalogLoaded, setCatalogLoaded] = useState(false)
  const salesContact = useSalesContact()

  useEffect(() => {
    loadPublicCatalog()
      .then(data => {
        if (data.success) {
          setCatalogPlans(data.plans || [])
          setCatalogAddons(data.addons || [])
          const terms = data.terms && data.terms.length > 0 ? data.terms : [
            { interval: 'year' as const, count: 1, label: '1 Year' },
            { interval: 'year' as const, count: 2, label: '2 Years' },
            { interval: 'year' as const, count: 3, label: '3 Years' },
          ]
          setCatalogTerms(terms)
          setSelectedTerm(terms[terms.length - 1])
        }
        setCatalogLoaded(true)
      })
      .catch(() => setCatalogLoaded(true))
  }, [])

  const activePlans = catalogPlans

  const durationKey: DurationKey | string = selectedTerm
    ? selectedTerm.interval === 'year'
      ? `${selectedTerm.count}_year`
      : selectedTerm.count === 1 ? 'monthly' : `${selectedTerm.count}_month`
    : '3_year'

  const termMonths = selectedTerm
    ? (selectedTerm.interval === 'year' ? selectedTerm.count * 12 : selectedTerm.count)
    : 36
  const termYears = termMonths / 12

  // Add-on unit prices from the catalog
  const userAddon = catalogAddons.find((a: BillingAddon) => a.id === 'extra_user')
  const companyAddon = catalogAddons.find((a: BillingAddon) => a.id === 'extra_company')
  const unitUserCost: number = userAddon?.price_per_year ?? 0
  const unitCompanyCost: number = companyAddon?.price_per_year ?? 0
  const extraUsersCost = Math.round(extraUsers * unitUserCost * termYears)
  const extraCompaniesCost = Math.round(extraCompanies * unitCompanyCost * termYears)

  const handleOpenCheckout = (
    plan: BillingPlan,
    pkg?: BillingPackage,
    price?: PackagePrice
  ) => {
    setSelectedPlanForModal(plan)
    setSelectedPackageForModal(pkg || plan.packages?.[0] || null)
    setSelectedPriceIdForModal(price?.price_id || null)
    setSelectedTermLabelForModal(selectedTerm?.label || null)
    setIsModalOpen(true)
  }

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-emerald-500/20">
      
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-background/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center text-white font-black shadow-md shadow-emerald-500/20">
              T
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-black text-lg tracking-tight text-foreground">MyTally</span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                Pricing
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {salesContact && (
              <a
                href={salesTelUrl(salesContact)}
                className="hidden sm:flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-muted"
              >
                <PhoneCall className="h-3.5 w-3.5 text-emerald-500" />
                {salesContact.phone}
              </a>
            )}
            <Link
              href="/"
              className="px-4 py-2 rounded-xl text-xs font-bold bg-primary text-primary-foreground hover:opacity-90 transition-opacity"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-12 pb-8 px-4 sm:px-6 max-w-5xl mx-auto text-center space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-black tracking-wider uppercase">
          <Sparkles className="h-3.5 w-3.5" /> Simple, Transparent Tally Cloud Pricing
        </div>
        <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-foreground leading-[1.15]">
          Power Up Your Tally Experience.<br />
          <span className="bg-gradient-to-r from-emerald-500 via-teal-500 to-blue-600 bg-clip-text text-transparent">
            Anytime. Anywhere. On Any Device.
          </span>
        </h1>
        <p className="text-sm sm:text-base text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          Access your live business data, outstanding debtors, customer statements, and inventory valuation on Mobile & Web. Real-time sync, zero lag.
        </p>

        {/* Value Badges */}
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2 text-xs font-bold text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> 7-Day Free Trial
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Zero Setup Fees
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Full TallyPrime & ERP 9 Support
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> GST Invoice on Every Purchase
          </span>
        </div>

        {/* Dynamic Duration Pills Selector */}
        <div className="pt-6">
          <div className="inline-flex flex-wrap items-center justify-center p-1.5 rounded-2xl bg-muted/70 border border-border shadow-inner gap-1">
            {catalogTerms.map((term, idx) => {
              const isSelected = selectedTerm?.interval === term.interval && selectedTerm?.count === term.count
              const isLongest = idx === catalogTerms.length - 1 && catalogTerms.length > 1
              return (
                <button
                  key={`${term.interval}_${term.count}`}
                  id={`btn-duration-${term.interval}-${term.count}`}
                  type="button"
                  onClick={() => setSelectedTerm(term)}
                  className={`px-5 py-2.5 rounded-xl text-xs font-black transition-all cursor-pointer flex items-center gap-1.5 ${
                    isSelected
                      ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                      : 'bg-card text-foreground/80 hover:text-foreground border border-border/60'
                  }`}
                >
                  <span>{term.label}</span>
                  {isLongest && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-black ${
                      isSelected ? 'bg-white/20 text-white' : 'bg-emerald-500/15 text-emerald-600'
                    }`}>
                      Best Value
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </section>

      {/* Pricing Cards Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {activePlans.length === 0 && (
          <p className="py-16 text-center text-sm text-muted-foreground">
            {catalogLoaded
              ? 'Plans could not be loaded just now. Please refresh, or call us and we will share the prices.'
              : 'Loading plans…'}
          </p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 items-stretch">
          {activePlans.map((plan) => {
            const isTarget = Boolean(targetPlan && (plan.id === targetPlan || plan.code === targetPlan))
            const packages = plan.packages || []
            const selectedPkgId = selectedPackageByPlan[plan.id] ?? packages[0]?.id
            const selectedPkg = packages.find(p => p.id === selectedPkgId) || packages[0]

            const pkgPrices = selectedPkg?.prices || []
            const activePrice = selectedTerm
              ? pkgPrices.find(p => p.interval === selectedTerm.interval && (p.count === selectedTerm.count || p.interval_count === selectedTerm.count))
              : pkgPrices[0]

            // The old per-plan price map, only for a plan that has no packages; never another term's price
            const legacyPricing = packages.length === 0 ? plan.pricing?.[durationKey] : undefined
            const hasPriceForTerm = Boolean(activePrice) || (packages.length === 0 && Boolean(legacyPricing))

            const totalPrice = activePrice ? activePrice.amount : (legacyPricing?.total ?? 0)
            const perMonthPrice = activePrice
              ? (activePrice.per_month ?? (selectedTerm?.interval === 'year' ? Math.round(activePrice.amount / (selectedTerm.count * 12)) : Math.round(activePrice.amount / (selectedTerm?.count || 1))))
              : (legacyPricing?.per_month ?? 0)
            const compareAtPrice = activePrice?.compare_at ?? null
            const savings = compareAtPrice && compareAtPrice > totalPrice ? compareAtPrice - totalPrice : (legacyPricing?.savings ?? 0)

            const companiesLabel = selectedPkg?.limits?.companies_label || plan.limits?.companies_label
            const usersLabel = selectedPkg?.limits?.users_label || plan.limits?.users_label

            return (
              <div
                key={plan.id}
                className={`relative flex flex-col rounded-3xl border bg-card p-6 sm:p-8 transition-all hover:shadow-xl ${plan.border || 'border-border'} ${
                  plan.is_popular ? 'ring-2 ring-emerald-500 dark:ring-emerald-400 shadow-lg' : ''
                } ${isTarget ? 'ring-2 ring-blue-500 shadow-xl' : ''}`}
              >
                {/* Popular Banner */}
                {plan.is_popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-black text-[11px] shadow-md uppercase tracking-wider">
                    ⭐ Most Popular Choice
                  </div>
                )}

                {/* Plan Header */}
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xl font-black text-foreground">{plan.name}</h3>
                    {plan.badge && (
                      <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-muted text-muted-foreground border border-border">
                        {plan.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground min-h-[36px]">
                    {plan.tagline}
                  </p>
                </div>

                {/* Package Dropdown / Label */}
                {packages.length > 1 && (
                  <div className="mb-4">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block mb-1">
                      Package
                    </label>
                    <div className="relative">
                      <select
                        value={selectedPkg?.id}
                        onChange={(e) => setSelectedPackageByPlan(prev => ({ ...prev, [plan.id]: Number(e.target.value) }))}
                        className="w-full text-xs font-bold rounded-xl border border-border bg-muted/60 px-3 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer appearance-none pr-8"
                      >
                        {packages.map((pkg) => (
                          <option key={pkg.id} value={pkg.id}>
                            {pkg.label}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    </div>
                  </div>
                )}
                {packages.length === 1 && (
                  <div className="mb-3 text-xs font-semibold text-muted-foreground">
                    Package: <span className="font-bold text-foreground">{packages[0].label}</span>
                  </div>
                )}

                {/* Pricing Block */}
                {!hasPriceForTerm ? (
                  <div className="py-6 border-y border-border/60 my-2 text-center space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground">
                      Not available for {selectedTerm?.label || 'this duration'}
                    </p>
                    {pkgPrices.length > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          const nearest = catalogTerms.find(t =>
                            pkgPrices.some(p => p.interval === t.interval && (p.count === t.count || p.interval_count === t.count))
                          )
                          if (nearest) setSelectedTerm(nearest)
                        }}
                        className="text-xs font-bold text-emerald-600 hover:text-emerald-500 underline cursor-pointer"
                      >
                        Switch to available duration
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="py-4 border-y border-border/60 my-2 space-y-1">
                    <div className="flex items-baseline gap-1">
                      <span className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
                        ₹{totalPrice.toLocaleString()}
                      </span>
                      <span className="text-xs text-muted-foreground font-semibold">
                        / {selectedTerm?.label || (durationKey === '1_year' ? '1 year' : durationKey === '2_year' ? '2 years' : '3 years')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs pt-1">
                      <span className="font-bold text-emerald-600 dark:text-emerald-400">
                        ₹{perMonthPrice}/month
                      </span>
                      {Boolean(savings && savings > 0) && (
                        <span className="text-[11px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 font-bold">
                          Save ₹{savings.toLocaleString()}
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground/80 pt-0.5">
                      + 18% GST • Inclusive of all cloud hosting
                    </p>
                  </div>
                )}

                {/* Limits Specs */}
                <div className="grid grid-cols-2 gap-2 my-4 p-3 rounded-2xl bg-muted/40 border border-border/60 text-xs">
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-emerald-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-muted-foreground block">Companies</span>
                      <strong className="font-bold text-foreground">{companiesLabel}</strong>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-blue-500 shrink-0" />
                    <div>
                      <span className="text-[10px] text-muted-foreground block">Users</span>
                      <strong className="font-bold text-foreground">{usersLabel}</strong>
                    </div>
                  </div>
                </div>

                {/* Feature Checklist */}
                <div className="space-y-2.5 flex-1 my-4">
                  <span className="text-[11px] uppercase font-black tracking-wider text-muted-foreground block">
                    Features Included:
                  </span>
                  {(plan.features || []).map((feat: {text: string; bold?: boolean}, idx: number) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs">
                      <div className="h-4 w-4 rounded-full bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5">
                        <Check className="h-3 w-3 stroke-[3]" />
                      </div>
                      <span className={feat.bold ? 'font-bold text-foreground' : 'text-muted-foreground'}>
                        {feat.text}
                      </span>
                    </div>
                  ))}
                  {(plan.missing || []).map((miss: string, idx: number) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs opacity-50">
                      <div className="h-4 w-4 rounded-full bg-muted text-muted-foreground flex items-center justify-center shrink-0 mt-0.5">
                        <CloseIcon className="h-2.5 w-2.5" />
                      </div>
                      <span className="text-muted-foreground line-through">
                        {miss}
                      </span>
                    </div>
                  ))}
                </div>

                {/* CTA Action Button */}
                <div className="pt-4 space-y-2">
                  <button
                    id={`btn-choose-${plan.id}`}
                    type="button"
                    disabled={!hasPriceForTerm}
                    onClick={() => handleOpenCheckout(plan, selectedPkg, activePrice)}
                    className={`w-full py-3.5 rounded-2xl font-black text-sm flex items-center justify-center gap-2 shadow-md transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                      plan.is_popular
                        ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:opacity-95 shadow-emerald-500/25'
                        : 'bg-primary text-primary-foreground hover:opacity-90'
                    }`}
                  >
                    {plan.id === 'diamond' ? 'Get Enterprise' : plan.id === 'gold' ? 'Upgrade to Gold' : 'Get Starter'}
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>

              </div>
            )
          })}
        </div>
      </section>

      {/* Add-on Calculator Section */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 text-[11px] font-bold uppercase mb-1">
                Customize Your Plan
              </div>
              <h3 className="text-xl font-black">Need Extra Users or Companies?</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Scale your team or entities without switching tiers. Add-ons are billed for the plan duration ({selectedTerm?.label || '3 years'}).
              </p>
            </div>
            <div className="text-right shrink-0">
              <span className="text-xs text-muted-foreground block">Add-ons Subtotal</span>
              <span className="text-2xl font-black text-emerald-600">
                +₹{(extraUsersCost + extraCompaniesCost).toLocaleString()}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            
            {/* Extra Users Counter */}
            <div className="p-4 rounded-2xl bg-muted/40 border border-border/80 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold flex items-center gap-1.5">
                    <Users className="h-4 w-4 text-blue-500" /> Additional Users
                  </h4>
                  <p className="text-[11px] text-muted-foreground">{userAddon ? `₹${unitUserCost.toLocaleString()} / user / year` : 'Price on request'}</p>
                </div>
                <div className="flex items-center gap-2 bg-card border border-border rounded-xl p-1">
                  <button
                    type="button"
                    onClick={() => setExtraUsers(Math.max(0, extraUsers - 1))}
                    className="h-7 w-7 rounded-lg flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <span className="w-8 text-center font-black text-sm">{extraUsers}</span>
                  <button
                    type="button"
                    onClick={() => setExtraUsers(extraUsers + 1)}
                    className="h-7 w-7 rounded-lg flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Total user cost: <strong>₹{extraUsersCost.toLocaleString()}</strong> for {selectedTerm?.label || '3 years'}.
              </p>
            </div>

            {/* Extra Companies Counter */}
            <div className="p-4 rounded-2xl bg-muted/40 border border-border/80 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold flex items-center gap-1.5">
                    <Building2 className="h-4 w-4 text-emerald-500" /> Additional Companies
                  </h4>
                  <p className="text-[11px] text-muted-foreground">{companyAddon ? `₹${unitCompanyCost.toLocaleString()} / company / year` : 'Price on request'}</p>
                </div>
                <div className="flex items-center gap-2 bg-card border border-border rounded-xl p-1">
                  <button
                    type="button"
                    onClick={() => setExtraCompanies(Math.max(0, extraCompanies - 1))}
                    className="h-7 w-7 rounded-lg flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </button>
                  <span className="w-8 text-center font-black text-sm">{extraCompanies}</span>
                  <button
                    type="button"
                    onClick={() => setExtraCompanies(extraCompanies + 1)}
                    className="h-7 w-7 rounded-lg flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Total company cost: <strong>₹{extraCompaniesCost.toLocaleString()}</strong> for {selectedTerm?.label || '3 years'}.
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* Feature Comparison Matrix Section */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        <div className="text-center mb-6">
          <button
            type="button"
            onClick={() => setIsComparisonOpen(!isComparisonOpen)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-muted/70 hover:bg-muted border border-border text-xs font-black transition-all cursor-pointer"
          >
            {isComparisonOpen ? 'Hide Full Feature Comparison' : 'View Full Feature-by-Feature Comparison Matrix'}
            {isComparisonOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {isComparisonOpen && (
          <div className="bg-card border border-border rounded-3xl overflow-hidden shadow-lg animate-in fade-in slide-in-from-top-4 duration-200">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="py-4 px-6 font-black text-sm text-foreground w-1/2">Features & Capabilities</th>
                    <th className="py-4 px-4 font-black text-sm text-center text-slate-700 dark:text-slate-300">Silver</th>
                    <th className="py-4 px-4 font-black text-sm text-center text-emerald-600 bg-emerald-500/5">Gold (Popular)</th>
                    <th className="py-4 px-4 font-black text-sm text-center text-indigo-600 dark:text-indigo-400">Diamond</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  
                  {/* Category: Sync & Access */}
                  <tr className="bg-muted/30">
                    <td colSpan={4} className="py-2.5 px-6 font-black text-[11px] uppercase tracking-wider text-muted-foreground">
                      Data Access & Sync Engine
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Tally Sync Engine</td>
                    <td className="py-3 px-4 text-center">Unlimited</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold text-emerald-600">Unlimited (Fast)</td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600">Dedicated Priority</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Companies Included</td>
                    <td className="py-3 px-4 text-center">1 Company</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold">5 Companies</td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600">Unlimited</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Users Included</td>
                    <td className="py-3 px-4 text-center">1 User</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold">3 Users</td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600">10 Users</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Simultaneous Devices per User</td>
                    <td className="py-3 px-4 text-center">3 Devices</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold">5 Devices</td>
                    <td className="py-3 px-4 text-center font-bold">10 Devices</td>
                  </tr>

                  {/* Category: Sales & Collections */}
                  <tr className="bg-muted/30">
                    <td colSpan={4} className="py-2.5 px-6 font-black text-[11px] uppercase tracking-wider text-muted-foreground">
                      Sales & Cash Collections
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Customer Ledgers & Ageing Buckets</td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">WhatsApp & PDF Bill Sharing</td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Automated WhatsApp Payment Reminders</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Salesperson GPS Check-In & Field Orders</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold text-emerald-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>

                  {/* Category: Inventory & Financials */}
                  <tr className="bg-muted/30">
                    <td colSpan={4} className="py-2.5 px-6 font-black text-[11px] uppercase tracking-wider text-muted-foreground">
                      Inventory & Financial Reports
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Daybook, Cash & Bank Books</td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Stock Valuation & Negative Stock Alerts</td>
                    <td className="py-3 px-4 text-center">Basic</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Dead Stock & Fast Moving Analytics</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold text-emerald-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Bank Statement Reconciliation (Auto Match)</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>

                  {/* Category: Compliance */}
                  <tr className="bg-muted/30">
                    <td colSpan={4} className="py-2.5 px-6 font-black text-[11px] uppercase tracking-wider text-muted-foreground">
                      Compliance & Enterprise Controls
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Govt E-Invoicing (IRN & QR Code Generation)</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">E-Way Bill Direct Generation</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Audit Trail & Deleted Records History</td>
                    <td className="py-3 px-4 text-center text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 text-muted-foreground"><CloseIcon className="h-3.5 w-3.5 text-muted-foreground mx-auto" /></td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600"><Check className="h-4 w-4 text-emerald-500 mx-auto" /></td>
                  </tr>
                  <tr>
                    <td className="py-3 px-6 font-semibold">Customer Support</td>
                    <td className="py-3 px-4 text-center">Standard</td>
                    <td className="py-3 px-4 text-center bg-emerald-500/5 font-bold">Priority Support</td>
                    <td className="py-3 px-4 text-center font-bold text-indigo-600">Dedicated Account Mgr</td>
                  </tr>

                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* FAQ Accordion Section */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 py-12 space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl sm:text-3xl font-black">Frequently Asked Questions</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Everything you need to know about MyTally pricing, sync compatibility, and billing.
          </p>
        </div>

        <div className="space-y-3">
          {FAQS.map((faq, idx) => {
            const isOpen = openFaqIndex === idx
            return (
              <div
                key={idx}
                className="bg-card border border-border rounded-2xl overflow-hidden transition-all"
              >
                <button
                  type="button"
                  onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between p-4 sm:p-5 text-left text-sm font-bold text-foreground cursor-pointer hover:bg-muted/40 transition-colors"
                >
                  <span>{faq.q}</span>
                  <div className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 transition-transform ${isOpen ? 'rotate-180 bg-emerald-500/10 text-emerald-600' : 'text-muted-foreground'}`}>
                    <ChevronDown className="h-4 w-4" />
                  </div>
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 pt-1 text-xs sm:text-sm text-muted-foreground leading-relaxed border-t border-border/40">
                    {faq.a}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Enterprise Contact Banner */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16">
        <div className="bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-700 rounded-3xl p-8 sm:p-10 text-white flex flex-col sm:flex-row items-center justify-between gap-6 shadow-xl shadow-emerald-500/10">
          <div className="space-y-2 text-center sm:text-left">
            <h3 className="text-2xl sm:text-3xl font-black">Need a Custom Enterprise Setup?</h3>
            <p className="text-xs sm:text-sm text-white/80 max-w-lg">
              Have 20+ companies, multi-state warehouses, or custom ERP workflows? Our enterprise architecture team is ready to design a tailored deployment.
            </p>
          </div>
          {salesContact && (
            <div className="flex flex-col sm:flex-row gap-3 shrink-0">
              <a
                href={salesWhatsAppUrl(salesContact, 'Hi MyTally Enterprise Team, I am looking for a custom multi-branch deployment.')}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 rounded-xl bg-white text-emerald-800 font-black text-xs hover:bg-white/90 transition-colors flex items-center justify-center gap-2"
              >
                <MessageCircle className="h-4 w-4" /> Chat on WhatsApp
              </a>
              <a
                href={salesTelUrl(salesContact)}
                className="px-6 py-3 rounded-xl bg-black/20 text-white font-bold text-xs hover:bg-black/30 transition-colors flex items-center justify-center gap-2 border border-white/20"
              >
                <PhoneCall className="h-4 w-4" /> Call {salesContact.phone}
              </a>
            </div>
          )}
        </div>
      </section>

      {/* Checkout / Sales Modal */}
      <PlanCheckoutModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        plan={selectedPlanForModal}
        packageItem={selectedPackageForModal}
        priceId={selectedPriceIdForModal}
        termLabel={selectedTermLabelForModal}
        durationKey={durationKey}
        extraUsers={extraUsers}
        extraCompanies={extraCompanies}
      />

    </div>
  )
}

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen p-8 text-center text-sm text-muted-foreground">Loading pricing…</div>}>
      <PricingContent />
    </Suspense>
  )
}
