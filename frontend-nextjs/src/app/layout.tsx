import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/context/AuthContext'
import { ThemeProvider } from '@/components/ThemeProvider'
import { GlobalHeader } from '@/components/GlobalHeader'
import { MobileBottomNav } from '@/components/MobileBottomNav'

import { PwaRegister } from '@/components/PwaRegister'

export const metadata: Metadata = {
  title: 'MyTally — Sneh Distributors',
  description: 'Inventory and ledger management for Sneh Distributors',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'MyTally',
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
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="flex flex-col h-dvh overflow-hidden">
        <ThemeProvider>
          <AuthProvider>
            <PwaRegister />
            {/* Top Header */}
            <GlobalHeader />

            {/* Scrollable main content, padded for bottom nav */}
            <main className="flex-1 overflow-y-auto overflow-x-hidden pb-16">
              {children}
            </main>

            {/* Fixed bottom navigation */}
            <MobileBottomNav />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
