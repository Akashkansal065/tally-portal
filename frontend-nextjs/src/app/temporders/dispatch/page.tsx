'use client'

import { DailyDispatchSummary } from '@/components/orders/DailyDispatchSummary'
import Link from 'next/link'
import { ChevronLeft, ShoppingCart } from 'lucide-react'

export default function DispatchSummaryPage() {
  return (
    <div className="flex flex-col h-full bg-background font-sans">
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-3xl mx-auto w-full space-y-4">
        <div className="flex items-center justify-between no-print">
          <Link
            href="/temporders"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-card hover:bg-muted text-muted-foreground hover:text-foreground border border-border rounded-xl text-xs font-bold transition-colors shadow-2xs"
          >
            <ChevronLeft className="h-4 w-4" />
            <ShoppingCart className="h-3.5 w-3.5 text-amber-500" />
            <span>Back to Orders List</span>
          </Link>
        </div>

        <DailyDispatchSummary />

        {/* Scroll spacer */}
        <div className="h-16" />
      </div>
    </div>
  )
}
