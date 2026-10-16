'use client'

import { useState, useEffect, useRef } from 'react'
import {
  X,
  MessageCircle,
  PhoneCall,
  CreditCard,
  Loader2,
  Sparkles,
  CheckCircle2,
  ShieldCheck,
  Building,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import {
  BillingPackage,
  BillingPlan,
  DurationKey,
  QuoteResponse,
  PaymentGateway,
  calculateQuote,
  createBillingOrder,
  confirmBillingOrder,
  fetchGateways,
  fetchBillingProfile,
  updateBillingProfile,
  submitSalesInquiry,
  salesWhatsAppUrl,
} from '@/lib/billing'
import { useSalesContact } from '@/hooks/useSalesContact'
import { loadScript } from '@/lib/loadScript'
import { toast } from 'sonner'

interface RazorpayInstance {
  open: () => void
}

interface CashfreeInstance {
  checkout: (opts: { paymentSessionId: string; redirectTarget: string }) => Promise<{
    paymentDetails?: Record<string, unknown>
    error?: unknown
  }>
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance
    Cashfree?: (config: { mode: string }) => CashfreeInstance
  }
}

// "Monthly", "3 Months", "1 Year", "2 Years"
function termName(interval: string | undefined, count: number | undefined): string {
  const n = count || 1
  if (interval === 'month') return n === 1 ? 'Monthly' : `${n} Months`
  return n === 1 ? '1 Year' : `${n} Years`
}

// The term a duration key names: "monthly", "N_month" or "N_year"
function termOfKey(key: string): [string, number] {
  if (key === 'monthly') return ['month', 1]
  const [count, unit] = key.split('_')
  return [unit === 'month' ? 'month' : 'year', Number(count) || 1]
}

// A short, stable fingerprint of what is being bought, so the same purchase sent twice (a double click, a retry
// after the gateway window was closed) reaches the server with the same request key and gets the same order
function fingerprint(text: string): string {
  let hash = 5381
  for (let i = 0; i < text.length; i++) hash = ((hash << 5) + hash + text.charCodeAt(i)) >>> 0
  return hash.toString(36)
}

interface PlanCheckoutModalProps {
  isOpen: boolean
  onClose: () => void
  plan: BillingPlan | null
  packageItem?: BillingPackage | null
  priceId?: number | null
  termLabel?: string | null
  durationKey?: DurationKey | string
  extraUsers?: number
  extraCompanies?: number
  onSuccess?: () => void
}

export function PlanCheckoutModal({
  isOpen,
  onClose,
  plan,
  packageItem,
  priceId,
  termLabel,
  durationKey = '1_year',
  extraUsers = 0,
  extraCompanies = 0,
  onSuccess,
}: PlanCheckoutModalProps) {
  const { user, token } = useAuth()
  const salesContact = useSalesContact()
  const [activeMode, setActiveMode] = useState<'online' | 'whatsapp' | 'callback'>('online')
  const [loading, setLoading] = useState(false)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [quote, setQuote] = useState<QuoteResponse | null>(null)

  // Gateways
  const [gateways, setGateways] = useState<PaymentGateway[]>([])
  const [selectedGateway, setSelectedGateway] = useState<string>('razorpay')
  const [checkoutEnabled, setCheckoutEnabled] = useState<boolean>(false)
  const [autopayEnabled, setAutopayEnabled] = useState<boolean>(false)

  // Customer Contact Details
  const [customerName, setCustomerName] = useState(user?.username || '')
  const [customerPhone, setCustomerPhone] = useState('')
  const [customerEmail, setCustomerEmail] = useState(user?.email || '')
  const [companyName, setCompanyName] = useState(user?.allowedCompanies?.[0]?.name || '')

  // GST & Invoicing
  const [gstin, setGstin] = useState('')
  const [showGstForm, setShowGstForm] = useState(false)
  const [couponCode, setCouponCode] = useState('')
  const [appliedCoupon, setAppliedCoupon] = useState<string | null>(null)
  // Why the server refused the coupon; shown under the coupon box
  const [couponError, setCouponError] = useState<string | null>(null)
  // Why no quote could be had at all (no coupon involved); shown in the price box with a retry
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [quoteAttempt, setQuoteAttempt] = useState(0)
  // The coupon the person just pressed Apply for, so its outcome is announced once
  const couponJustApplied = useRef<string | null>(null)

  // Success State
  const [orderFulfilled, setOrderFulfilled] = useState<{
    orderRef: string
    planName: string
  } | null>(null)

  // One per opening of the modal; with the purchase's fingerprint it makes the order's request key
  const checkoutSession = useRef<string | null>(null)

  // Reset modal state when closed
  useEffect(() => {
    if (!isOpen) {
      checkoutSession.current = null
      const timer = setTimeout(() => {
        setOrderFulfilled(null)
        setQuote(null)
      }, 0)
      return () => clearTimeout(timer)
    }
  }, [isOpen])

  // Load gateway capabilities and billing profile
  useEffect(() => {
    if (!isOpen) return

    fetchGateways()
      .then((res) => {
        setGateways(res.gateways || [])
        setCheckoutEnabled(res.checkout_enabled || false)
        if (res.gateways?.length > 0) {
          setSelectedGateway(res.gateways[0].code)
        }
        if (!res.checkout_enabled && activeMode === 'online') {
          setActiveMode('whatsapp')
        }
      })
      .catch(() => {
        setGateways([])
      })

    if (token) {
      fetchBillingProfile(token)
        .then((res) => {
          if (res.profile) {
            if (res.profile.legal_name) setCompanyName(res.profile.legal_name)
            if (res.profile.gstin) {
              setGstin(res.profile.gstin)
              setShowGstForm(true)
            }
            if (res.profile.phone) setCustomerPhone(res.profile.phone)
            if (res.profile.email) setCustomerEmail(res.profile.email)
          }
        })
        .catch(() => {})
    }
  }, [isOpen, token, activeMode])

  // The buyer's state counts only once a whole GSTIN is typed: its first two digits are the state code.
  // Re-quoting on every keystroke, with letters as a "state", is what this avoids.
  const gstinClean = gstin.trim().toUpperCase()
  const buyerStateCode = /^[0-9]{2}[A-Z0-9]{13}$/.test(gstinClean) ? gstinClean.slice(0, 2) : undefined

  // Fetch pure server quote whenever plan, duration, extras or coupon change
  useEffect(() => {
    if (!isOpen || !plan) return

    let active = true
    Promise.resolve().then(() => {
      if (active) setQuoteLoading(true)
    })

    const effectiveExtraUsers = plan?.allow_extra_users !== false ? extraUsers : 0
    const effectiveExtraCompanies = plan?.allow_extra_companies !== false ? extraCompanies : 0

    calculateQuote(
      {
        plan_id: packageItem?.id || plan.id,
        price_id: priceId || undefined,
        duration_key: durationKey,
        extra_users: effectiveExtraUsers,
        extra_companies: effectiveExtraCompanies,
        coupon_code: appliedCoupon || undefined,
        buyer_state_code: buyerStateCode,
      },
      token || undefined
    )
      .then((q) => {
        if (!active) return
        setQuote(q)
        setQuoteError(null)
        setQuoteLoading(false)
        if (couponJustApplied.current && couponJustApplied.current === appliedCoupon) {
          toast.success(`Coupon ${appliedCoupon} applied.`)
          couponJustApplied.current = null
        }
      })
      .catch((err: Error) => {
        if (!active) return
        setQuoteLoading(false)
        const message = err?.message || 'The price could not be worked out.'
        if (appliedCoupon) {
          // The coupon is what failed: say why, take it off, and price the order without it.
          // The last good quote stays on screen meanwhile.
          setCouponError(message)
          if (couponJustApplied.current === appliedCoupon) toast.error(message)
          couponJustApplied.current = null
          setAppliedCoupon(null)
        } else {
          setQuote(null)
          setQuoteError(message)
        }
      })

    return () => {
      active = false
    }
  }, [isOpen, plan?.id, packageItem?.id, priceId, durationKey, extraUsers, extraCompanies, appliedCoupon, buyerStateCode, token, quoteAttempt])

  if (!isOpen || !plan) return null

  const resolvedTermLabel =
    termLabel || (quote ? termName(quote.interval, quote.interval_count) : termName(...termOfKey(String(durationKey))))

  // Every amount comes from the server's quote. Until it arrives nothing is shown as a price and nothing can be paid.
  // ₹2,499 for whole rupees, ₹249.90 when there are paise
  const rupees = (amount: number) =>
    `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: Number.isInteger(amount) ? 0 : 2, maximumFractionDigits: 2 })}`
  const money = (amount: number) => (quote ? rupees(amount) : '…')
  const displayBase = quote?.base_plan ?? 0
  const displayExtraUsers = quote?.extra_users ?? 0
  const displayExtraCompanies = quote?.extra_companies ?? 0
  const displayGst = quote ? (quote.igst_applied ? quote.igst : quote.cgst + quote.sgst) : 0
  const displayTotal = quote?.total ?? 0
  const displayPerMonth = quote?.months ? Math.round(displayTotal / quote.months) : 0
  // Seats already paid for in a running term are carried on by the server, so its count can be higher
  const seatUsers = quote?.extra_users_count ?? (plan?.allow_extra_users !== false ? extraUsers : 0)
  const seatCompanies = quote?.extra_companies_count ?? (plan?.allow_extra_companies !== false ? extraCompanies : 0)

  const handleApplyCoupon = (e: React.FormEvent) => {
    e.preventDefault()
    const code = couponCode.trim().toUpperCase()
    if (!code || code === appliedCoupon) return
    setCouponError(null)
    couponJustApplied.current = code
    setAppliedCoupon(code)
  }

  const handleOnlinePayment = async () => {
    if (!token) {
      toast.error('Please sign in to complete online purchase.')
      window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`
      return
    }

    setLoading(true)
    try {
      // 1. Save profile if GSTIN or firm name entered
      if (gstin.trim() || companyName.trim()) {
        await updateBillingProfile(
          {
            legal_name: companyName.trim() || undefined,
            gstin: gstin.trim() ? gstin.trim().toUpperCase() : undefined,
            state_code: gstin.trim().length >= 2 ? gstin.trim().slice(0, 2) : undefined,
            phone: customerPhone.trim() || undefined,
            email: customerEmail.trim() || undefined,
          },
          token
        ).catch(() => {})
      }

      // 2. Create order on server. The same purchase from this opening of the modal always carries the same
      // request key, so a second click returns the order the first one made instead of making another.
      const purchase = {
        plan_id: packageItem?.id || plan.id,
        price_id: priceId || undefined,
        duration_key: durationKey,
        extra_users: plan?.allow_extra_users !== false ? extraUsers : 0,
        extra_companies: plan?.allow_extra_companies !== false ? extraCompanies : 0,
        coupon_code: appliedCoupon || undefined,
        gateway: selectedGateway,
        buyer_state_code: gstin.trim().length >= 2 ? gstin.trim().slice(0, 2) : undefined,
        autopay: autopayEnabled,
      }
      if (!checkoutSession.current) {
        checkoutSession.current = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
      }
      const orderRes = await createBillingOrder(
        {
          ...purchase,
          client_request_key: `REQ_${checkoutSession.current}_${fingerprint(JSON.stringify(purchase))}`,
        },
        token
      )

      const { order_ref, checkout_config } = orderRes

      // 3. Launch selected Gateway SDK
      if (selectedGateway === 'razorpay') {
        const loaded = await loadScript('https://checkout.razorpay.com/v1/checkout.js')
        if (!loaded || !window.Razorpay) {
          throw new Error('Could not load Razorpay payment SDK. Please try again.')
        }

        const options: Record<string, unknown> = {
          key: checkout_config.key,
          name: 'MyTally Cloud',
          description: `Subscription ${order_ref} - ${plan.name} (${packageItem ? packageItem.label + ' · ' : ''}${resolvedTermLabel})`,
          prefill: {
            name: customerName,
            email: customerEmail,
            contact: customerPhone,
          },
          theme: {
            color: '#10b981',
          },
          handler: async (response: {
            razorpay_payment_id?: string
            razorpay_order_id?: string
            razorpay_subscription_id?: string
            razorpay_signature?: string
          }) => {
            try {
              toast.info('Verifying payment with bank...')
              const confirmRes = await confirmBillingOrder(
                order_ref,
                {
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_subscription_id: response.razorpay_subscription_id,
                  razorpay_signature: response.razorpay_signature,
                },
                token
              )

              if (confirmRes.status === 'paid') {
                toast.success('Subscription activated successfully!')
                setOrderFulfilled({
                  orderRef: order_ref,
                  planName: plan.name,
                })
                onSuccess?.()
              }
            } catch (err: unknown) {
              const msg = err instanceof Error ? err.message : String(err)
              toast.error(msg || 'Payment verification failed.')
            }
          },
          modal: {
            ondismiss: () => {
              setLoading(false)
            },
          },
        }

        if (checkout_config.subscription_id) {
          options.subscription_id = checkout_config.subscription_id
        } else {
          options.order_id = checkout_config.order_id
          options.amount = checkout_config.amount
          options.currency = checkout_config.currency || 'INR'
        }

        const rzp = new window.Razorpay(options)
        rzp.open()
      } else if (selectedGateway === 'cashfree') {
        const loaded = await loadScript('https://sdk.cashfree.com/js/v3/cashfree.js')
        if (!loaded || !window.Cashfree) {
          throw new Error('Could not load Cashfree payment SDK.')
        }

        const cf = window.Cashfree({
          mode: checkout_config.env === 'production' ? 'production' : 'sandbox',
        })

        const session_id = checkout_config.client_payload?.payment_session_id || checkout_config.payment_session_id
        if (!session_id) {
          throw new Error('Payment session could not be established with Cashfree.')
        }

        cf.checkout({
          paymentSessionId: session_id,
          redirectTarget: '_modal',
        }).then(async (result: { paymentDetails?: Record<string, unknown> }) => {
          if (result.paymentDetails) {
            toast.info('Verifying payment...')
            const confirmRes = await confirmBillingOrder(
              order_ref,
              result.paymentDetails,
              token
            )
            if (confirmRes.status === 'paid') {
              toast.success('Subscription activated successfully!')
              setOrderFulfilled({
                orderRef: order_ref,
                planName: plan.name,
              })
              onSuccess?.()
            }
          }
          setLoading(false)
        })
      } else {
        // Offline / custom
        toast.info('Order placed. Our team will verify and activate your subscription.')
        setOrderFulfilled({
          orderRef: order_ref,
          planName: plan.name,
        })
        onSuccess?.()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(msg || 'Payment initiation failed. Please try WhatsApp sales.')
      setLoading(false)
    }
  }

  const handleWhatsAppRedirect = async () => {
    try {
      setLoading(true)
      const data = await submitSalesInquiry({
        plan_id: packageItem?.id ? String(packageItem.id) : plan.id,
        duration_key: durationKey,
        customer_name: customerName || 'Valued Customer',
        customer_phone: customerPhone || 'Not specified',
        customer_email: customerEmail,
        company_name: companyName,
        message: `Plan: ${plan.name} (${packageItem ? packageItem.label + ' · ' : ''}${resolvedTermLabel}). Extra Users: ${plan?.allow_extra_users !== false ? extraUsers : 0}, Extra Companies: ${plan?.allow_extra_companies !== false ? extraCompanies : 0}. Quoted Total: ${money(displayTotal)}`,
      })
      if (data.whatsapp_url) {
        window.open(data.whatsapp_url, '_blank')
        toast.success('Redirecting to WhatsApp sales concierge...')
      } else {
        // No sales WhatsApp number is set up: the request is saved and the team calls back
        toast.success('Request received. Our team will contact you shortly.')
      }
      onClose()
    } catch {
      if (salesContact) {
        window.open(salesWhatsAppUrl(salesContact,
          `Hi MyTally Team! I want to upgrade to ${plan.name} (${packageItem ? packageItem.label + ' · ' : ''}${resolvedTermLabel}) for ${companyName || 'my firm'}. Grand Total: ${money(displayTotal)}. Please contact me.`), '_blank')
        onClose()
      } else {
        toast.error('Unable to submit request. Please try again in a moment.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCallbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customerPhone) {
      toast.error('Please enter your mobile phone number.')
      return
    }
    setLoading(true)
    try {
      await submitSalesInquiry({
        plan_id: packageItem?.id ? String(packageItem.id) : plan.id,
        duration_key: durationKey,
        customer_name: customerName || 'Prospective Customer',
        customer_phone: customerPhone,
        customer_email: customerEmail,
        company_name: companyName,
        message: `Requested direct phone callback for plan upgrade (${plan.name} - ${packageItem ? packageItem.label + ' · ' : ''}${resolvedTermLabel}). Extra Users: ${plan?.allow_extra_users !== false ? extraUsers : 0}, Extra Companies: ${plan?.allow_extra_companies !== false ? extraCompanies : 0}.`,
      })
      toast.success('Callback requested! Our onboarding specialist will call you shortly.')
      onClose()
    } catch {
      toast.error(salesContact
        ? `Unable to submit request. Please call ${salesContact.phone} directly.`
        : 'Unable to submit request. Please try again in a moment.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      id="checkout-modal-overlay"
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div
        id="checkout-modal-dialog"
        className="relative w-full max-w-2xl bg-card border border-border/80 rounded-3xl shadow-2xl overflow-hidden text-foreground flex flex-col max-h-[92vh]"
      >
        {/* Header Banner */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-muted/40">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-500">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-black">{plan.name} Plan</h3>
                <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  {packageItem ? `${packageItem.label} · ` : ''}{resolvedTermLabel}
                </span>
                {plan.badge && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-primary text-primary-foreground">
                    {plan.badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {packageItem?.limits?.companies_label || plan.limits.companies_label} • {packageItem?.limits?.users_label || plan.limits.users_label}
              </p>
            </div>
          </div>
          <button
            id="btn-close-checkout-modal"
            onClick={onClose}
            className="h-9 w-9 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {orderFulfilled ? (
          /* SUCCESS STATE */
          <div className="p-8 text-center space-y-4">
            <div className="h-16 w-16 bg-emerald-500/10 border border-emerald-500/20 rounded-full flex items-center justify-center mx-auto text-emerald-500">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <h4 className="text-xl font-black">Plan Activated!</h4>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Your account has been upgraded to <strong>{orderFulfilled.planName}</strong>. Your GST tax invoice has been generated under Order reference{' '}
              <code className="bg-muted px-2 py-0.5 rounded text-xs">{orderFulfilled.orderRef}</code>.
            </p>
            <button
              onClick={onClose}
              className="px-6 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-sm shadow hover:opacity-90"
            >
              Done & Continue to Dashboard
            </button>
          </div>
        ) : (
          <div className="overflow-y-auto flex-1 p-6 space-y-5">
            {/* Mode Selector Tabs */}
            <div className="grid grid-cols-3 gap-2 p-1 bg-muted/60 rounded-2xl border border-border/80 text-center">
              <button
                type="button"
                onClick={() => setActiveMode('online')}
                className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-extrabold transition-all cursor-pointer ${
                  activeMode === 'online'
                    ? 'bg-card text-foreground shadow-sm border border-border'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <CreditCard className="h-3.5 w-3.5 text-emerald-500" />
                Pay Online
              </button>
              <button
                type="button"
                onClick={() => setActiveMode('whatsapp')}
                className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-extrabold transition-all cursor-pointer ${
                  activeMode === 'whatsapp'
                    ? 'bg-card text-foreground shadow-sm border border-border'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <MessageCircle className="h-3.5 w-3.5 text-green-500" />
                WhatsApp
              </button>
              <button
                type="button"
                onClick={() => setActiveMode('callback')}
                className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-extrabold transition-all cursor-pointer ${
                  activeMode === 'callback'
                    ? 'bg-card text-foreground shadow-sm border border-border'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <PhoneCall className="h-3.5 w-3.5 text-blue-500" />
                Callback
              </button>
            </div>

            {/* Order Price Breakdown Card */}
            <div className="bg-muted/30 border border-border rounded-2xl p-4 space-y-3 relative">
              {quoteLoading && (
                <div className="absolute top-2 right-2 flex items-center gap-1 text-[10px] text-muted-foreground bg-card/80 px-2 py-0.5 rounded-md border border-border">
                  <Loader2 className="h-3 w-3 animate-spin text-emerald-500" /> Updating quote…
                </div>
              )}
              {quoteError && !quote && (
                <div className="flex items-center justify-between gap-2 rounded-xl bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  <span>{quoteError}</span>
                  <button
                    type="button"
                    onClick={() => setQuoteAttempt((n) => n + 1)}
                    className="shrink-0 font-bold underline cursor-pointer"
                  >
                    Try again
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Base Plan ({plan.name} {packageItem ? `· ${packageItem.label}` : ''} × {resolvedTermLabel})</span>
                <span className="font-bold">{money(displayBase)}</span>
              </div>
              {seatUsers > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">
                    Extra Users ({seatUsers})
                  </span>
                  <span className="font-bold">{money(displayExtraUsers)}</span>
                </div>
              )}
              {seatCompanies > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">
                    Extra Companies ({seatCompanies})
                  </span>
                  <span className="font-bold">{money(displayExtraCompanies)}</span>
                </div>
              )}
              {quote?.discount ? (
                <div className="flex items-center justify-between text-xs text-emerald-600 font-bold">
                  <span>Coupon Discount ({quote.coupon_code})</span>
                  <span>-{rupees(quote.discount)}</span>
                </div>
              ) : null}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>GST (18%{quote?.igst_applied ? ' IGST' : ' CGST+SGST'})</span>
                <span>{money(displayGst)}</span>
              </div>
              <div className="border-t border-border pt-2 flex items-center justify-between">
                <div>
                  <span className="text-sm font-black text-foreground">Total Payable</span>
                  <span className="text-[10px] text-muted-foreground block">(Inclusive of 18% GST)</span>
                </div>
                <div className="text-right">
                  <span className="text-xl font-black text-emerald-600 dark:text-emerald-400">
                    {money(displayTotal)}
                  </span>
                  <span className="text-[10px] text-muted-foreground block">
                    ({money(displayPerMonth)}/month)
                  </span>
                </div>
              </div>
            </div>

            {/* Mode: PAY ONLINE */}
            {activeMode === 'online' && (
              <div className="space-y-4">
                {/* Gateway Picker */}
                {gateways.length > 1 && (
                  <div>
                    <label className="text-xs font-bold text-muted-foreground mb-1.5 block">Select Payment Gateway</label>
                    <div className="grid grid-cols-2 gap-2">
                      {gateways.map((gw) => (
                        <button
                          key={gw.code}
                          type="button"
                          onClick={() => setSelectedGateway(gw.code)}
                          className={`p-3 rounded-xl border text-left flex items-center justify-between transition-all cursor-pointer ${
                            selectedGateway === gw.code
                              ? 'border-emerald-500 bg-emerald-500/5'
                              : 'border-border bg-card hover:bg-muted/50'
                          }`}
                        >
                          <div>
                            <span className="text-xs font-black block">{gw.name}</span>
                            <span className="text-[10px] text-muted-foreground block">UPI, Cards, NetBanking</span>
                          </div>
                          {selectedGateway === gw.code && <ShieldCheck className="h-4 w-4 text-emerald-500" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Autopay Recurring Toggle */}
                {selectedGateway === 'razorpay' && (
                  <label className="flex items-start gap-3 p-3.5 rounded-2xl border border-border bg-card/60 hover:bg-muted/30 cursor-pointer transition-all">
                    <input
                      type="checkbox"
                      checked={autopayEnabled}
                      onChange={(e) => setAutopayEnabled(e.target.checked)}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500 h-4 w-4 mt-0.5"
                    />
                    <div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="text-xs font-bold text-foreground">Enable Autopay (UPI & Card Mandate)</span>
                        <span className="bg-emerald-500/15 text-emerald-600 text-[10px] font-extrabold px-1.5 py-0.2 rounded-md">Automated Renewal</span>
                      </div>
                      <span className="text-[11px] text-muted-foreground block leading-relaxed">
                        Authorize seamless recurring renewal per billing cycle. You can pause or cancel anytime from Settings with zero penalties.
                      </span>
                    </div>
                  </label>
                )}

                {/* GST Details Accordion */}
                <div className="border border-border/70 rounded-2xl p-3.5 bg-muted/20">
                  <button
                    type="button"
                    onClick={() => setShowGstForm(!showGstForm)}
                    className="w-full flex items-center justify-between text-xs font-bold text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <Building className="h-4 w-4 text-primary" />
                      <span>{gstin ? `GSTIN: ${gstin}` : 'Add GSTIN for Business Input Tax Credit (Optional)'}</span>
                    </div>
                    <span className="text-xs text-primary">{showGstForm ? 'Hide' : 'Add'}</span>
                  </button>

                  {showGstForm && (
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2 border-t border-border/50">
                      <div>
                        <label className="text-[10px] font-bold text-muted-foreground block mb-1">Company Legal Name</label>
                        <input
                          type="text"
                          value={companyName}
                          onChange={(e) => setCompanyName(e.target.value)}
                          placeholder="e.g. Sneh Distributors Pvt Ltd"
                          className="w-full px-3 py-1.5 text-xs rounded-xl bg-card border border-border"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-muted-foreground block mb-1">GSTIN (15 Digits)</label>
                        <input
                          type="text"
                          value={gstin}
                          maxLength={15}
                          onChange={(e) => setGstin(e.target.value.toUpperCase())}
                          placeholder="07AAAAA0000A1Z5"
                          className="w-full px-3 py-1.5 text-xs rounded-xl bg-card border border-border uppercase font-mono"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Coupon Code Input */}
                <form onSubmit={handleApplyCoupon} className="flex gap-2">
                  <input
                    type="text"
                    value={couponCode}
                    onChange={(e) => {
                      setCouponCode(e.target.value)
                      setCouponError(null)
                    }}
                    placeholder="Enter Coupon / Promo Code"
                    className="flex-1 px-3 py-2 text-xs rounded-xl bg-card border border-border uppercase"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-bold text-xs border border-border cursor-pointer"
                  >
                    Apply
                  </button>
                </form>
                {couponError && <p className="-mt-2 text-[11px] text-destructive">{couponError}</p>}
                {appliedCoupon && !couponError && quote?.coupon_code && (
                  <div className="-mt-2 flex items-center justify-between text-[11px] text-emerald-600">
                    <span>Coupon {quote.coupon_code} applied</span>
                    <button
                      type="button"
                      onClick={() => {
                        setAppliedCoupon(null)
                        setCouponCode('')
                      }}
                      className="font-bold underline cursor-pointer"
                    >
                      Remove
                    </button>
                  </div>
                )}

                {/* Checkout Trigger Button */}
                <button
                  type="button"
                  onClick={handleOnlinePayment}
                  disabled={loading || !quote}
                  className="w-full py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-black text-sm shadow-lg shadow-emerald-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Processing Payment…
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-4 w-4" /> Pay {money(displayTotal)} & Activate
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Mode: WHATSAPP SALES */}
            {activeMode === 'whatsapp' && (
              <div className="space-y-4 text-center py-2">
                <div className="h-12 w-12 rounded-2xl bg-green-500/10 border border-green-500/20 text-green-500 flex items-center justify-center mx-auto">
                  <MessageCircle className="h-6 w-6" />
                </div>
                <div>
                  <h4 className="text-base font-black">Chat Directly with Our Tally Specialists</h4>
                  <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                    Get answers about multi-firm licenses, onboarding assistance, GST input credit, and customized quotes.
                  </p>
                </div>
                <div className="p-3 bg-muted/40 rounded-xl text-xs text-left font-mono border border-border">
                  <p className="text-muted-foreground text-[10px] mb-1 font-sans">Pre-composed message:</p>
                  &ldquo;Hi MyTally Team! I want to upgrade to the {plan.name} Plan ({resolvedTermLabel}) for {companyName || 'my firm'}. Total {money(displayTotal)}.&rdquo;
                </div>
                <button
                  type="button"
                  onClick={handleWhatsAppRedirect}
                  disabled={loading}
                  className="w-full py-3.5 rounded-2xl bg-[#25D366] hover:bg-[#20ba59] text-white font-black text-sm shadow-lg shadow-green-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <MessageCircle className="h-4 w-4" /> Continue to WhatsApp Chat
                </button>
              </div>
            )}

            {/* Mode: REQUEST CALLBACK */}
            {activeMode === 'callback' && (
              <form onSubmit={handleCallbackSubmit} className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-bold text-muted-foreground mb-1 block">Contact Name *</label>
                    <input
                      type="text"
                      required
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      placeholder="e.g. Akash Kansal"
                      className="w-full px-3 py-2 text-xs rounded-xl bg-muted/40 border border-border focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-bold text-muted-foreground mb-1 block">Phone Number *</label>
                    <input
                      type="tel"
                      required
                      value={customerPhone}
                      onChange={(e) => setCustomerPhone(e.target.value)}
                      placeholder="Your mobile number"
                      className="w-full px-3 py-2 text-xs rounded-xl bg-muted/40 border border-border focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[11px] font-bold text-muted-foreground mb-1 block">Firm / Company Name</label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. Sneh Distributors"
                    className="w-full px-3 py-2 text-xs rounded-xl bg-muted/40 border border-border focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Our business executive will call you within 15 minutes during business hours (9:00 AM - 8:00 PM IST).
                </p>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3.5 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-black text-sm shadow-lg shadow-blue-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />}
                  Request Phone Callback
                </button>
              </form>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border bg-muted/30 flex items-center justify-between text-xs text-muted-foreground">
          <span>Official MyTally Billing</span>
          {salesContact && <span>Support: {salesContact.phone}</span>}
        </div>
      </div>
    </div>
  )
}
