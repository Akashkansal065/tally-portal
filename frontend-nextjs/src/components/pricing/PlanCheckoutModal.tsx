'use client'

import { useState, useEffect } from 'react'
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

declare global {
  interface Window {
    Razorpay?: any
    Cashfree?: any
  }
}

interface PlanCheckoutModalProps {
  isOpen: boolean
  onClose: () => void
  plan: BillingPlan | null
  durationKey: DurationKey
  extraUsers?: number
  extraCompanies?: number
  onSuccess?: () => void
}

export function PlanCheckoutModal({
  isOpen,
  onClose,
  plan,
  durationKey,
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

  // Success State
  const [orderFulfilled, setOrderFulfilled] = useState<{
    orderRef: string
    planName: string
  } | null>(null)

  const durationLabel =
    durationKey === '1_year'
      ? '1 Year'
      : durationKey === '2_year'
      ? '2 Years'
      : durationKey === '3_year'
      ? '3 Years'
      : 'Monthly'

  // Load gateway capabilities and billing profile
  useEffect(() => {
    if (!isOpen) {
      setOrderFulfilled(null)
      return
    }

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
  }, [isOpen, token])

  // Fetch pure server quote whenever plan, duration, extras or coupon change
  useEffect(() => {
    if (!isOpen || !plan) {
      setQuote(null)
      return
    }

    let active = true
    setQuoteLoading(true)

    calculateQuote(
      {
        plan_id: plan.id,
        duration_key: durationKey,
        extra_users: extraUsers,
        extra_companies: extraCompanies,
        coupon_code: appliedCoupon || undefined,
        buyer_state_code: gstin && gstin.length >= 2 ? gstin.slice(0, 2) : undefined,
      },
      token || undefined
    )
      .then((q) => {
        if (active) {
          setQuote(q)
          setQuoteLoading(false)
        }
      })
      .catch((err) => {
        if (active) {
          console.error('Failed to calculate server quote:', err)
          setQuoteLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [isOpen, plan?.id, durationKey, extraUsers, extraCompanies, appliedCoupon, gstin, token])

  if (!isOpen || !plan) return null

  // Every amount comes from the server's quote. Until it arrives nothing is shown as a price and nothing can be paid.
  const years =
    durationKey === '1_year' ? 1 : durationKey === '2_year' ? 2 : durationKey === '3_year' ? 3 : 1
  const money = (amount: number) => (quote ? `₹${amount.toLocaleString()}` : '…')
  const displayBase = quote?.base_plan ?? 0
  const displayExtraUsers = quote?.extra_users ?? 0
  const displayExtraCompanies = quote?.extra_companies ?? 0
  const displayGst = quote ? (quote.igst_applied ? quote.igst : quote.cgst + quote.sgst) : 0
  const displayTotal = quote?.total ?? 0
  const displayPerMonth = Math.round(displayTotal / (years * 12))
  // Seats already paid for in a running term are carried on by the server, so its count can be higher
  const seatUsers = quote?.extra_users_count ?? extraUsers
  const seatCompanies = quote?.extra_companies_count ?? extraCompanies

  const handleApplyCoupon = (e: React.FormEvent) => {
    e.preventDefault()
    if (!couponCode.trim()) return
    setAppliedCoupon(couponCode.trim().toUpperCase())
    toast.info(`Applying coupon ${couponCode.trim().toUpperCase()}...`)
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

      // 2. Create order on server
      const orderRes = await createBillingOrder(
        {
          plan_id: plan.id,
          duration_key: durationKey,
          extra_users: extraUsers,
          extra_companies: extraCompanies,
          coupon_code: appliedCoupon || undefined,
          gateway: selectedGateway,
          buyer_state_code: gstin.trim().length >= 2 ? gstin.trim().slice(0, 2) : undefined,
          client_request_key: `REQ_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
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

        const options = {
          key: checkout_config.key,
          amount: checkout_config.amount,
          currency: checkout_config.currency || 'INR',
          name: 'MyTally Cloud',
          description: `Subscription ${order_ref} - ${plan.name} (${durationLabel})`,
          order_id: checkout_config.order_id,
          prefill: {
            name: customerName,
            email: customerEmail,
            contact: customerPhone,
          },
          theme: {
            color: '#10b981',
          },
          handler: async (response: any) => {
            try {
              toast.info('Verifying payment with bank...')
              const confirmRes = await confirmBillingOrder(
                order_ref,
                {
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_order_id: response.razorpay_order_id,
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
            } catch (err: any) {
              toast.error(err.message || 'Payment verification failed.')
            }
          },
          modal: {
            ondismiss: () => {
              setLoading(false)
            },
          },
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
        }).then(async (result: any) => {
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
    } catch (err: any) {
      toast.error(err.message || 'Payment initiation failed. Please try WhatsApp sales.')
      setLoading(false)
    }
  }

  const handleWhatsAppRedirect = async () => {
    try {
      setLoading(true)
      const data = await submitSalesInquiry({
        plan_id: plan.id,
        duration_key: durationKey,
        customer_name: customerName || 'Valued Customer',
        customer_phone: customerPhone || 'Not specified',
        customer_email: customerEmail,
        company_name: companyName,
        message: `Extra Users: ${extraUsers}, Extra Companies: ${extraCompanies}. Quoted Total: ${money(displayTotal)}`,
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
          `Hi MyTally Team! I want to upgrade to the ${plan.name} Plan (${durationLabel}) for ${companyName || 'my firm'}. Grand Total: ${money(displayTotal)}. Please contact me.`), '_blank')
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
        plan_id: plan.id,
        duration_key: durationKey,
        customer_name: customerName || 'Prospective Customer',
        customer_phone: customerPhone,
        customer_email: customerEmail,
        company_name: companyName,
        message: `Requested direct phone callback for plan upgrade (${plan.name} - ${durationLabel}). Extra Users: ${extraUsers}, Extra Companies: ${extraCompanies}.`,
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
                  {durationLabel}
                </span>
                {plan.badge && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-primary text-primary-foreground">
                    {plan.badge}
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {plan.limits.companies_label} • {plan.limits.users_label}
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
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Base Plan ({plan.name} × {durationLabel})</span>
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
                  <span>-₹{quote.discount.toLocaleString()}</span>
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
                    onChange={(e) => setCouponCode(e.target.value)}
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
                  &ldquo;Hi MyTally Team! I want to upgrade to the {plan.name} Plan ({durationLabel}) for {companyName || 'my firm'}. Total {money(displayTotal)}.&rdquo;
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
