'use client'

import { useState, useEffect } from 'react'
import {
  Lock,
  ShieldAlert,
  ArrowRight,
  MessageCircle,
  PhoneCall,
  LogOut,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { fetchCurrentSubscription, SubscriptionDetails, salesTelUrl, salesWhatsAppUrl } from '@/lib/billing'
import { useSalesContact } from '@/hooks/useSalesContact'
import Link from 'next/link'

export default function BillingLockedPage() {
  const { user, token, logout } = useAuth()
  const salesContact = useSalesContact()
  const [sub, setSub] = useState<SubscriptionDetails | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) {
      const timer = setTimeout(() => setLoading(false), 0)
      return () => clearTimeout(timer)
    }
    let active = true
    fetchCurrentSubscription(token)
      .then((data) => {
        if (!active) return
        setSub(data)
        // If the account has paid and is no longer locked, redirect back to dashboard
        if (data.status === 'active' || data.status === 'legacy') {
          window.location.href = '/'
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [token])

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-muted/30 to-background flex flex-col items-center justify-center p-4 sm:p-6 text-foreground">
      {/* Container */}
      <div className="w-full max-w-xl bg-card border border-border/80 rounded-3xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Top Warning Strip */}
        <div className="bg-red-500/10 border-b border-red-500/20 px-6 py-3 flex items-center justify-between text-xs text-red-600 dark:text-red-400 font-bold">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" />
            <span>Account Access Temporarily Suspended</span>
          </div>
          <span className="uppercase text-[10px] tracking-wider bg-red-500/20 px-2 py-0.5 rounded-full font-mono">
            HTTP 402 Locked
          </span>
        </div>

        {/* Body */}
        <div className="p-8 text-center space-y-6">
          <div className="h-20 w-20 bg-red-500/10 border border-red-500/20 rounded-3xl flex items-center justify-center mx-auto text-red-500 shadow-lg shadow-red-500/10">
            <Lock className="h-10 w-10 animate-pulse" />
          </div>

          <div className="space-y-2">
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              Subscription Expired
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Your free trial and grace period for MyTally Cloud have ended. Tally background sync and web portal access are paused until a subscription plan is activated.
            </p>
          </div>

          {/* Account Snapshot */}
          <div className="p-4 bg-muted/40 rounded-2xl border border-border text-xs text-left space-y-2 font-mono">
            <div className="flex justify-between items-center text-muted-foreground font-sans">
              <span>Account ID</span>
              <span className="font-bold font-mono text-foreground">{sub?.account_id ?? user?.id ?? '—'}</span>
            </div>
            <div className="flex justify-between items-center text-muted-foreground font-sans">
              <span>Previous Tier</span>
              <span className="font-bold text-foreground capitalize">{sub?.plan || 'Gold Trial'}</span>
            </div>
            <div className="flex justify-between items-center text-muted-foreground font-sans">
              <span>Sync Agent Status</span>
              <span className="text-amber-500 font-bold">Paused (Awaiting Payment)</span>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="space-y-3 pt-2">
            <Link
              href="/pricing"
              className="w-full py-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-black text-sm shadow-xl shadow-emerald-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <Sparkles className="h-4 w-4" />
              Choose a Plan & Unlock Account
              <ArrowRight className="h-4 w-4" />
            </Link>

            {salesContact && (
              <a
                href={salesWhatsAppUrl(salesContact, 'Hi MyTally Team, my account is currently locked. Please help me activate a plan.')}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full py-3.5 rounded-2xl bg-[#25D366] hover:bg-[#20ba59] text-white font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <MessageCircle className="h-4 w-4" /> Chat with Sales Concierge on WhatsApp
              </a>
            )}
          </div>

          <div className="pt-4 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            {salesContact ? (
              <a href={salesTelUrl(salesContact)} className="flex items-center gap-1.5 hover:text-foreground">
                <PhoneCall className="h-3.5 w-3.5 text-blue-500" /> {salesContact.phone}
              </a>
            ) : <span />}
            <button
              onClick={() => logout()}
              className="flex items-center gap-1 hover:text-destructive cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign Out
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
