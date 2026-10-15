'use client'

import React, { useState, useEffect } from 'react'
import Link from 'next/link'
import {
  Crown,
  Sparkles,
  Lock,
  ArrowRight,
  X,
  Zap,
  CheckCircle2,
  ShieldCheck,
  Building,
} from 'lucide-react'

export interface FeatureMeta {
  key: string
  title: string
  description: string
  requiredPlan: 'Gold' | 'Diamond'
  bullets: string[]
  accentColor: string
}

export const FEATURE_METADATA: Record<string, FeatureMeta> = {
  einvoice_eway_bill: {
    key: 'einvoice_eway_bill',
    title: 'Govt E-Invoicing & E-Way Bill',
    description: 'Generate real-time government certified IRN, QR code, and E-Way Bills directly from your Tally sales vouchers.',
    requiredPlan: 'Diamond',
    bullets: [
      'Instant IRN & QR generation without visiting GST portal',
      'Integrated E-Way Bill generation for consignments > ₹50,000',
      'Official GSP live integration with automatic retry logic',
      'Download certified PDF with signed QR code',
    ],
    accentColor: 'from-amber-500 to-rose-500',
  },
  bank_reconciliation: {
    key: 'bank_reconciliation',
    title: 'Bank Statement Auto-Reconciliation',
    description: 'Upload bank statements in Excel/CSV and auto-match transactions against Tally vouchers with 3-way reconciliation.',
    requiredPlan: 'Diamond',
    bullets: [
      'Automated 3-way matching with Tally vouchers and receipts',
      'Bank Reconciliation Statement (BRS) calculation',
      'Support for HDFC, ICICI, SBI, Axis and all major Indian banks',
      'Audit log of auto-matches and manual adjustments',
    ],
    accentColor: 'from-blue-600 to-indigo-600',
  },
  approval_rules_matrix: {
    key: 'approval_rules_matrix',
    title: 'Voucher Approval Matrix (Maker-Checker)',
    description: 'Enforce enterprise governance by requiring multi-level authorization on high-value sales, payments, or journals.',
    requiredPlan: 'Diamond',
    bullets: [
      'Role-based approval hierarchies and threshold amounts',
      'Holds unapproved vouchers from syncing to Tally until signed off',
      'Audit history of approvals, rejections, and revisits',
      'Real-time notifications to designated approvers',
    ],
    accentColor: 'from-purple-600 to-pink-600',
  },
  salesman_checkin_orders: {
    key: 'salesman_checkin_orders',
    title: 'Field Sales GPS Check-In & Orders',
    description: 'Empower sales representatives in the field with GPS shop visits, photo check-ins, and direct order capture.',
    requiredPlan: 'Gold',
    bullets: [
      'GPS-verified shop check-ins with client location log',
      'Real-time order booking synced straight to Tally',
      'Rep activity timeline and visit coverage reporting',
      'Offline-first order caching on mobile devices',
    ],
    accentColor: 'from-amber-500 to-orange-500',
  },
  auto_payment_reminders: {
    key: 'auto_payment_reminders',
    title: 'Automated WhatsApp Payment Reminders',
    description: 'Recover receivables up to 3x faster with scheduled, automated WhatsApp and email reminders to debtor accounts.',
    requiredPlan: 'Gold',
    bullets: [
      'Ageing bucket triggers (1-30, 30-60, 90+ days overdue)',
      'Meta-certified official WhatsApp business message templates',
      'Automated 9am–8pm sending window adhering to TRAI norms',
      'Includes instant UPI and QR payment links for immediate collection',
    ],
    accentColor: 'from-emerald-500 to-teal-600',
  },
  payment_links_collect: {
    key: 'payment_links_collect',
    title: 'Online Payment Collection Links',
    description: 'Collect outstanding payments directly from invoices via UPI, credit/debit cards, and net banking.',
    requiredPlan: 'Gold',
    bullets: [
      'Instant settlement direct to your linked bank account',
      'Razorpay and Cashfree gateway support',
      'Automatic receipt voucher generation in Tally upon settlement',
      'Shareable short payment links and dynamic QR codes',
    ],
    accentColor: 'from-cyan-500 to-blue-600',
  },
}

function getFallbackMeta(featureKey: string): FeatureMeta {
  const formatted = featureKey.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  return {
    key: featureKey,
    title: formatted || 'Enterprise Feature',
    description: 'This powerful feature is exclusively available on higher-tier MyTally subscription plans.',
    requiredPlan: 'Gold',
    bullets: [
      'Unlock advanced capabilities tailored for expanding businesses',
      'Higher device, company, and user allowances',
      'Priority sync engine with fast-track processing',
      'Dedicated enterprise onboarding and support',
    ],
    accentColor: 'from-amber-500 to-yellow-600',
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// GLOBAL MODAL COMPONENT (Listens to 403 X-Billing-Reason: feature)
// ─────────────────────────────────────────────────────────────────────────────

export function UpgradePromptModal() {
  const [isOpen, setIsOpen] = useState(false)
  const [featureKey, setFeatureKey] = useState<string>('')

  useEffect(() => {
    const handler = (e: Event) => {
      const custom = e as CustomEvent<{ featureKey?: string }>
      if (custom.detail?.featureKey) {
        setFeatureKey(custom.detail.featureKey)
        setIsOpen(true)
      }
    }

    window.addEventListener('billing:upgrade-required', handler)
    return () => window.removeEventListener('billing:upgrade-required', handler)
  }, [])

  if (!isOpen) return null

  const meta = FEATURE_METADATA[featureKey] || getFallbackMeta(featureKey)

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Top Gradient Banner */}
        <div className={`h-2.5 w-full bg-gradient-to-r ${meta.accentColor}`} />

        {/* Close Button */}
        <button
          onClick={() => setIsOpen(false)}
          className="absolute top-4 right-4 p-1.5 rounded-full text-zinc-400 hover:text-white hover:bg-zinc-800 transition"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-6 sm:p-8">
          {/* Badge & Crown */}
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500/20 to-yellow-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-inner">
              <Crown className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <Sparkles className="w-3 h-3" />
                Available on {meta.requiredPlan} Plan
              </div>
              <h3 className="text-xl font-bold text-white mt-1">{meta.title}</h3>
            </div>
          </div>

          <p className="text-sm text-zinc-400 leading-relaxed mb-6">
            {meta.description}
          </p>

          {/* Value Bullets */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-4 mb-6 space-y-2.5">
            <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider mb-2">
              What you get with {meta.requiredPlan}:
            </div>
            {meta.bullets.map((b, i) => (
              <div key={i} className="flex items-start gap-2.5 text-xs text-zinc-300">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>{b}</span>
              </div>
            ))}
          </div>

          {/* Action CTAs */}
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <Link
              href="/pricing"
              onClick={() => setIsOpen(false)}
              className="w-full sm:flex-1 py-3 px-5 rounded-xl font-semibold text-sm text-zinc-950 bg-gradient-to-r from-amber-400 to-yellow-400 hover:from-amber-300 hover:to-yellow-300 transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
            >
              <Zap className="w-4 h-4 fill-current" />
              Upgrade to {meta.requiredPlan}
              <ArrowRight className="w-4 h-4" />
            </Link>
            <button
              onClick={() => setIsOpen(false)}
              className="w-full sm:w-auto py-3 px-4 rounded-xl text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition text-center"
            >
              Maybe Later
            </button>
          </div>

          <div className="mt-4 text-center">
            <span className="text-[11px] text-zinc-500">
              Need custom limits or multiple firms? Contact concierge at{' '}
              <a
                href="https://wa.me/919999999999?text=Hello%20MyTally%20team,%20I%20need%20custom%20enterprise%20pricing"
                target="_blank"
                rel="noreferrer"
                className="text-amber-400 hover:underline"
              >
                WhatsApp Concierge
              </a>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// INLINE CARD COMPONENT (Can be embedded into restricted feature pages)
// ─────────────────────────────────────────────────────────────────────────────

interface UpgradePromptCardProps {
  featureKey: string
  compact?: boolean
  className?: string
}

export function UpgradePromptCard({ featureKey, compact = false, className = '' }: UpgradePromptCardProps) {
  const meta = FEATURE_METADATA[featureKey] || getFallbackMeta(featureKey)

  if (compact) {
    return (
      <div className={`p-4 rounded-xl bg-zinc-900/80 border border-amber-500/30 flex items-center justify-between gap-4 ${className}`}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
            <Lock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">{meta.title}</div>
            <div className="text-xs text-zinc-400">Requires {meta.requiredPlan} plan or higher</div>
          </div>
        </div>
        <Link
          href="/pricing"
          className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-400 hover:bg-amber-300 text-zinc-950 transition flex items-center gap-1.5 shrink-0"
        >
          Upgrade
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    )
  }

  return (
    <div className={`max-w-2xl mx-auto my-8 p-8 rounded-2xl bg-zinc-900/90 border border-zinc-800 shadow-xl text-center ${className}`}>
      <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-amber-500/20 to-yellow-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-5 shadow-inner">
        <Crown className="w-8 h-8" />
      </div>

      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 mb-3">
        <Sparkles className="w-3.5 h-3.5" />
        Exclusively on {meta.requiredPlan} Plan
      </div>

      <h2 className="text-2xl font-bold text-white mb-2">{meta.title}</h2>
      <p className="text-sm text-zinc-400 max-w-lg mx-auto mb-6 leading-relaxed">
        {meta.description}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left max-w-lg mx-auto mb-8 bg-zinc-950/60 border border-zinc-800 p-4 rounded-xl">
        {meta.bullets.map((b, i) => (
          <div key={i} className="flex items-start gap-2 text-xs text-zinc-300">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>{b}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <Link
          href="/pricing"
          className="w-full sm:w-auto px-6 py-3 rounded-xl font-semibold text-sm text-zinc-950 bg-gradient-to-r from-amber-400 to-yellow-400 hover:from-amber-300 hover:to-yellow-300 transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
        >
          <Zap className="w-4 h-4 fill-current" />
          Upgrade to {meta.requiredPlan}
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  )
}
