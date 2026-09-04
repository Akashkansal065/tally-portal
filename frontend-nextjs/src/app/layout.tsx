import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/context/AuthContext'
import { PeriodProvider } from '@/context/PeriodContext'
import { ThemeProvider } from '@/components/ThemeProvider'
import { GlobalHeader } from '@/components/GlobalHeader'
import { MobileBottomNav } from '@/components/MobileBottomNav'

import { PwaRegister } from '@/components/PwaRegister'
import { DatePickerInitializer } from '@/components/DatePickerInitializer'
import { MobileInstallPrompt } from '@/components/MobileInstallPrompt'

import { RouteGuard } from '@/components/RouteGuard'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: 'MyTally — Sneh Distributors',
  description: 'Inventory and ledger management for Sneh Distributors',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'MyTally',
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
    <html lang="en" suppressHydrationWarning className={cn("font-sans", geist.variable)}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
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
              {/* Top Header */}
              <GlobalHeader />

              {/* Scrollable main content, padded for bottom nav and iOS home indicator */}
              <main
                className="flex-1 overflow-y-auto overflow-x-hidden"
                style={{ paddingBottom: 'calc(4.5rem + env(safe-area-inset-bottom, 0px))' }}
              >
                <RouteGuard>{children}</RouteGuard>
              </main>

              {/* Fixed bottom navigation */}
              <MobileBottomNav />
            </PeriodProvider>
          </AuthProvider>
        </ThemeProvider>
        <SpeedInsights />
      </body>
    </html>
  )
}
