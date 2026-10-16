/**
 * billing.ts – Client-side billing types and API methods.
 * Single source of truth for all billing network calls in the frontend.
 */

import { API_BASE, authHeaders } from '@/lib/utils'

export type DurationKey = '1_year' | '2_year' | '3_year' | 'monthly'

export interface CatalogTerm {
  interval: 'month' | 'year'
  count: number
  label: string
}

export interface PlanPrice {
  price_id: number
  total: number
  per_month?: number
  discount_pct?: number
  savings?: number
  autopay_allowed?: boolean
}

export interface PackagePrice {
  price_id: number
  interval: 'month' | 'year'
  count: number
  interval_count?: number
  amount_paise: number
  amount: number
  compare_at_paise?: number | null
  compare_at?: number | null
  per_month_paise?: number
  per_month?: number
  autopay_allowed?: boolean
}

export interface PlanLimits {
  companies: number | null
  companies_label: string
  users: number | null
  users_label: string
  devices_per_user: number | null
}

export interface BillingPackage {
  id: number
  code: string
  label: string
  max_companies: number | null
  max_users: number | null
  max_devices: number | null
  limits?: PlanLimits
  prices: PackagePrice[]
}

export interface BillingPlan {
  id: string               // plan code, e.g. "silver", "gold", "diamond"
  code?: string
  plan_db_id?: number       // database primary key of first package
  name: string
  tagline: string | null
  badge: string | null
  is_popular?: boolean
  color?: string
  accent?: string
  border?: string
  display?: Record<string, unknown>
  pricing: Record<string, PlanPrice>
  limits: PlanLimits
  feature_keys: string[]
  highlights?: string[]
  features?: Array<{ text: string; bold?: boolean }>
  missing?: string[]
  allow_extra_users?: boolean
  allow_extra_companies?: boolean
  packages?: BillingPackage[]
}

export interface BillingAddon {
  id: string               // e.g. "extra_user", "extra_company"
  addon_db_id: number
  name: string
  description: string | null
  kind: string
  unit: string
  price_per_year: number | null
  price_per_month: number | null
  credit_type: string | null
  credit_qty: number | null
}

export interface FeatureComparisonCategory {
  category: string
  features: Array<{
    key: string
    name: string
    info?: string
  }>
}

export interface BillingCatalog {
  success: boolean
  terms?: CatalogTerm[]
  plans: BillingPlan[]
  addons: BillingAddon[]
  comparison: FeatureComparisonCategory[]
  currency: string
  currency_symbol: string
  gst_percentage: number
  checkout_enabled: boolean
  autopay_enabled?: boolean
  gateways?: PaymentGateway[]
  /** The sales number as configured on the server (BILLING_SALES_PHONE); null when none is set */
  sales_phone: string | null
  sales_whatsapp: string | null
}

export interface QuoteRequest {
  plan_id: string | number
  price_id?: number
  duration_key?: string
  extra_users?: number
  extra_companies?: number
  coupon_code?: string
  buyer_state_code?: string
}

export interface QuoteResponse {
  success: boolean
  base_plan_paise: number
  extra_users_paise: number
  extra_companies_paise: number
  subtotal_paise: number
  discount_paise: number
  taxable_paise: number
  cgst_paise: number
  sgst_paise: number
  igst_paise: number
  total_paise: number

  // Rupee amounts for UI display
  base_plan: number
  extra_users: number
  extra_companies: number
  subtotal: number
  discount: number
  taxable: number
  cgst: number
  sgst: number
  igst: number
  total: number

  // Legacy convenience aliases
  net_taxable: number
  gst_amount: number
  grand_total: number

  plan_code: string
  plan_name: string
  interval: string
  interval_count: number
  coupon_code?: string | null
  years: number
  months: number
  buyer_state_code?: string | null
  igst_applied: boolean
  /** What the server decided this order is: new, renewal, upgrade, downgrade or addon */
  purpose?: string
  extra_users_count?: number
  extra_companies_count?: number
}

export interface SubscriptionUsage {
  companies_linked: number
  max_companies: number | null
  users_active: number
  max_users: number | null
}

export interface SubscriptionDetails {
  success: boolean
  account_id: number | null
  plan: string | null
  package?: string | null
  tier: string | null
  status: 'legacy' | 'trialing' | 'active' | 'grace' | 'locked' | 'cancelled'
  valid_until: string | null
  usage: SubscriptionUsage
  features_available: string[] | null
  autopay?: boolean
  cancel_at_period_end?: boolean
  credits?: {
    einvoice?: number
    whatsapp?: number
    [key: string]: number | undefined
  }
}

export interface SalesInquiryRequest {
  plan_id: string
  duration_key?: string
  customer_name: string
  customer_phone: string
  customer_email?: string
  company_name?: string
  message?: string
}

export interface SalesInquiryResponse {
  success: boolean
  lead_id: number
  message: string
  whatsapp_url: string | null
  sales_phone: string | null
}

/** How to reach sales: the number to show and its digits for links. */
export interface SalesContact {
  phone: string
  whatsapp: string
}

/** The sales contact from a catalog response, or null when the server has no number set (then none is shown). */
export function salesContactFrom(catalog: Pick<BillingCatalog, 'sales_phone' | 'sales_whatsapp'> | null | undefined): SalesContact | null {
  if (!catalog?.sales_phone || !catalog.sales_whatsapp) return null
  return { phone: catalog.sales_phone, whatsapp: catalog.sales_whatsapp }
}

export function salesWhatsAppUrl(contact: SalesContact, text: string): string {
  return `https://wa.me/${contact.whatsapp}?text=${encodeURIComponent(text)}`
}

export function salesTelUrl(contact: SalesContact): string {
  return `tel:+${contact.whatsapp}`
}

/**
 * Fetch public plan catalog, active add-ons and feature comparison table.
 */
export async function fetchPlansCatalog(token?: string): Promise<BillingCatalog> {
  const headers = token ? authHeaders(token) : { 'Content-Type': 'application/json' }
  const res = await fetch(`${API_BASE}/billing/plans`, { headers })
  if (!res.ok) {
    throw new Error(`Failed to load plans: HTTP ${res.status}`)
  }
  return res.json()
}

let publicCatalog: Promise<BillingCatalog> | null = null

/** The public catalog (no sign-in), fetched once per page load and shared by everything that needs it. */
export function loadPublicCatalog(): Promise<BillingCatalog> {
  if (!publicCatalog) {
    publicCatalog = fetchPlansCatalog().catch((err) => {
      publicCatalog = null // let the next caller try again
      throw err
    })
  }
  return publicCatalog
}

/**
 * Calculate an exact, itemised server quote in integer paise.
 */
export async function calculateQuote(req: QuoteRequest, token?: string): Promise<QuoteResponse> {
  const headers = token ? authHeaders(token) : { 'Content-Type': 'application/json' }
  const res = await fetch(`${API_BASE}/billing/quote`, {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Failed to calculate quote: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch current subscription details, usage against limits, and entitlements.
 */
export async function fetchCurrentSubscription(token: string): Promise<SubscriptionDetails> {
  const res = await fetch(`${API_BASE}/billing/current-subscription`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    throw new Error(`Failed to load subscription: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Submit sales inquiry / WhatsApp lead.
 */
export async function submitSalesInquiry(req: SalesInquiryRequest): Promise<SalesInquiryResponse> {
  const res = await fetch(`${API_BASE}/billing/inquiry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Inquiry submission failed: HTTP ${res.status}`)
  }
  return res.json()
}

export interface PaymentGateway {
  code: string
  name: string
}

export interface GatewaysResponse {
  success: boolean
  gateways: PaymentGateway[]
  checkout_enabled: boolean
}

export interface CreateOrderRequest {
  plan_id: string | number
  price_id?: number
  duration_key?: string
  extra_users?: number
  extra_companies?: number
  coupon_code?: string
  gateway?: string
  client_request_key?: string
  buyer_state_code?: string
  buyer_snapshot?: Record<string, unknown>
  autopay?: boolean
}

export interface CheckoutConfig {
  key?: string
  amount?: number
  currency?: string
  order_id?: string
  subscription_id?: string
  env?: string
  payment_session_id?: string
  client_payload?: {
    payment_session_id?: string
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface CreateOrderResponse {
  success: boolean
  order_ref: string
  total_paise: number
  total_rupees: number
  status: string
  gateway: string
  checkout_config: CheckoutConfig
}

export interface ConfirmOrderResponse {
  success: boolean
  order_ref: string
  status: string
  fulfilled_at: string | null
}

export interface BillingOrderDetails {
  success: boolean
  order_ref: string
  status: string
  total_paise: number
  total_rupees: number
  gateway: string
  created_at: string | null
  paid_at: string | null
  fulfilled_at: string | null
}

export interface BillingInvoiceSummary {
  id: number
  invoice_number: string
  kind: string
  order_ref: string
  date: string | null
  place_of_supply: string | null
  sac: string | null
  taxable_paise: number
  taxable_rupees: number
  cgst_paise: number
  sgst_paise: number
  igst_paise: number
  total_paise: number
  total_rupees: number
  lines: Array<{ description: string; sac?: string; amount_paise: number }>
  pdf_path: string | null
}

export interface BillingInvoiceDetails extends BillingInvoiceSummary {
  buyer: Record<string, unknown>
  seller: Record<string, unknown>
}

export interface BillingProfile {
  legal_name: string | null
  gstin: string | null
  address: Record<string, unknown>
  state_code: string | null
  email: string | null
  phone: string | null
}

/**
 * Fetch available payment gateways.
 */
export async function fetchGateways(): Promise<GatewaysResponse> {
  const res = await fetch(`${API_BASE}/billing/gateways`)
  if (!res.ok) {
    throw new Error(`Failed to load gateways: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Create a billing order with the selected payment gateway.
 */
export async function createBillingOrder(req: CreateOrderRequest, token: string): Promise<CreateOrderResponse> {
  const res = await fetch(`${API_BASE}/billing/orders`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Order creation failed: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Confirm order payment details with the server.
 */
export async function confirmBillingOrder(
  orderRef: string,
  payload: Record<string, unknown>,
  token: string
): Promise<ConfirmOrderResponse> {
  const res = await fetch(`${API_BASE}/billing/orders/${encodeURIComponent(orderRef)}/confirm`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ payload }),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Payment confirmation failed: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Poll or fetch status of a billing order.
 */
export async function fetchBillingOrder(orderRef: string, token: string): Promise<BillingOrderDetails> {
  const res = await fetch(`${API_BASE}/billing/orders/${encodeURIComponent(orderRef)}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    throw new Error(`Failed to fetch order: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch list of tax invoices for account.
 */
export async function fetchInvoices(token: string): Promise<{ success: boolean; invoices: BillingInvoiceSummary[] }> {
  const res = await fetch(`${API_BASE}/billing/invoices`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    throw new Error(`Failed to load invoices: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch detail of a single invoice.
 */
export async function fetchInvoiceDetails(invoiceId: number, token: string): Promise<BillingInvoiceDetails> {
  const res = await fetch(`${API_BASE}/billing/invoices/${invoiceId}`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    throw new Error(`Failed to load invoice: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Fetch buyer billing profile.
 */
export async function fetchBillingProfile(token: string): Promise<{ success: boolean; profile: BillingProfile | null }> {
  const res = await fetch(`${API_BASE}/billing/profile`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    throw new Error(`Failed to load billing profile: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Update buyer billing profile.
 */
export async function updateBillingProfile(
  profile: Partial<BillingProfile>,
  token: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/billing/profile`, {
    method: 'PUT',
    headers: authHeaders(token),
    body: JSON.stringify(profile),
  })
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Failed to update billing profile: HTTP ${res.status}`)
  }
  return res.json()
}

/**
 * Cancel recurring autopay mandate for the account's subscription.
 */
export async function cancelAutopaySubscription(token: string): Promise<{
  success: boolean
  message: string
  cancel_at_period_end: boolean
  current_period_end: string | null
}> {
  const res = await fetch(`${API_BASE}/billing/subscription/autopay/cancel`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Failed to cancel autopay: HTTP ${res.status}`)
  }
  return res.json()
}

// ─────────────────────────────────────────────────────────────────────────────
// PLATFORM OPERATOR CONSOLE CLIENT METHODS
// ─────────────────────────────────────────────────────────────────────────────

export interface PlatformMetrics {
  subscriptions: {
    legacy: number
    trialing: number
    active: number
    grace: number
    locked: number
    cancelled: number
  }
  revenue: {
    total_paise: number
    total_rupees: number
    paid_orders: number
  }
  alerts: {
    expiring_in_30_days: number
    trials_ending_in_7_days: number
  }
}

export interface PlatformAccountBilling {
  account_id: number
  account_name: string
  account_status: string
  subscription_status: string
  plan_code: string | null
  plan_name: string | null
  valid_until: string | null
  extra_users: number
  extra_companies: number
  is_locked: boolean
}

export interface PlatformLead {
  id: number
  name: string | null
  phone: string | null
  email: string | null
  company: string | null
  plan_code: string | null
  duration_key: string | null
  message: string | null
  status: string
  created_at: string | null
}

export interface PlatformWebhookEvent {
  id: number
  gateway: string
  event_id: string
  event_type: string
  signature_verified: boolean
  processed: boolean
  processing_error: string | null
  created_at: string | null
}

export interface AssignPlanParams {
  plan_code: string
  duration_years: number
  extra_users?: number
  extra_companies?: number
}

export interface CustomPlanParams {
  name: string
  tagline?: string
  max_users?: number | null
  max_companies?: number | null
  max_devices?: number | null
  feature_keys: string[]
  yearly_price_paise: number
}

export interface OfflinePaymentParams {
  account_id: number
  plan_code: string
  duration_years: number
  extra_users?: number
  extra_companies?: number
  reference: string
  method: string
  buyer_state_code?: string
}

export async function fetchPlatformMetrics(token: string): Promise<PlatformMetrics> {
  const res = await fetch(`${API_BASE}/platform/billing/metrics`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPlatformAccounts(token: string): Promise<PlatformAccountBilling[]> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return data.accounts || []
}

export async function assignPlanToAccount(
  accountId: number,
  params: AssignPlanParams,
  token: string
): Promise<{ success: boolean; message: string; current_period_end: string }> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts/${accountId}/assign-plan`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function createCustomPlan(
  accountId: number,
  params: CustomPlanParams,
  token: string
): Promise<{ success: boolean; plan_id: number; plan_code: string; amount_rupees: number }> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts/${accountId}/custom-plan`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function setAccountOverrides(
  accountId: number,
  overrides: Record<string, unknown>,
  token: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts/${accountId}/overrides`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ overrides }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function lockAccountSubscription(
  accountId: number,
  token: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts/${accountId}/lock`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function unlockAccountSubscription(
  accountId: number,
  token: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/platform/billing/accounts/${accountId}/unlock`, {
    method: 'POST',
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function recordOfflinePayment(
  params: OfflinePaymentParams,
  token: string
): Promise<{ success: boolean; order_ref: string; invoice_number: string | null; total_rupees: number; status: string }> {
  const res = await fetch(`${API_BASE}/platform/billing/offline-payment`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchPlatformLeads(token: string): Promise<PlatformLead[]> {
  const res = await fetch(`${API_BASE}/platform/billing/leads`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return data.leads || []
}

export async function fetchPlatformWebhooks(token: string): Promise<PlatformWebhookEvent[]> {
  const res = await fetch(`${API_BASE}/platform/billing/webhooks`, {
    headers: authHeaders(token),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return data.events || []
}

