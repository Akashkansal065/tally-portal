import { CompanyLinks } from '@/components/CompanyLinks'
import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/context/AuthContext'
import { PeriodProvider } from '@/context/PeriodContext'
import { ThemeProvider } from '@/components/ThemeProvider'
import { GlobalHeader } from '@/components/GlobalHeader'
import { MobileBottomNav } from '@/components/MobileBottomNav'
import { AppMain } from '@/components/AppMain'

import { PwaRegister } from '@/components/PwaRegister'
import { DatePickerInitializer } from '@/components/DatePickerInitializer'
import { MobileInstallPrompt } from '@/components/MobileInstallPrompt'
import { SessionRestorer } from '@/components/SessionRestorer'
import { AttendanceLocationTracker } from '@/components/AttendanceLocationTracker'
import { NativeAppBridge } from '@/components/NativeAppBridge'
import { NotificationNavigator } from '@/components/notifications/NotificationNavigator'
import { PushRegistration } from '@/components/notifications/PushRegistration'
import { UpgradePromptModal } from '@/components/UpgradePrompt'
import { ImpersonationBanner } from '@/components/ImpersonationBanner'

import { RouteGuard } from '@/components/RouteGuard'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Toaster } from 'sonner'
import { Outfit } from "next/font/google";
import { cn } from "@/lib/utils";

// latin-ext holds ₹ (U+20B9): without it the browser fetches that file late and every amount re-flows
const outfit = Outfit({ subsets: ['latin', 'latin-ext'], variable: '--font-sans', display: 'swap' });

export const metadata: Metadata = {
  title: 'SnehDist. — Sneh Distributors',
  description: 'Inventory and ledger management for Sneh Distributors',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'SnehDist.',
  },
  icons: {
    icon: '/icon-192.png',
    apple: [
      { url: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
  },
  formatDetection: {
    telephone: false,
  },
}

export const viewport = {
  themeColor: '#10b981',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning className={cn("font-sans", outfit.variable)}>
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <link rel="apple-touch-icon" sizes="192x192" href="/icon-192.png" />
        <link rel="apple-touch-icon" sizes="512x512" href="/icon-512.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="MyTally" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className="flex flex-col h-dvh overflow-hidden">
        <ThemeProvider>
          <AuthProvider>
            <PeriodProvider>
              <PwaRegister />
              <DatePickerInitializer />
              <MobileInstallPrompt />
              <SessionRestorer />
              <AttendanceLocationTracker />
              <NativeAppBridge />
              <NotificationNavigator />
              <PushRegistration />
              <UpgradePromptModal />
              <Toaster richColors position="top-center" closeButton />
              {/* Operator Impersonation Banner (if active) */}
              <ImpersonationBanner />
              {/* Top Header */}
              <GlobalHeader />

              {/* Main content shell (padded for bottom nav on customer pages, full-height on console) */}
              <AppMain>
                <CompanyLinks />
                <RouteGuard>{children}</RouteGuard>
              </AppMain>

              {/* Fixed bottom navigation */}
              <MobileBottomNav />
            </PeriodProvider>
          </AuthProvider>
        </ThemeProvider>
        {/* Only Vercel serves the Speed Insights script; elsewhere it 404s and logs a console error */}
        {process.env.VERCEL && <SpeedInsights />}
      </body>
    </html>
  )
}
