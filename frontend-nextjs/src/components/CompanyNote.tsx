'use client'

import { Building2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

/** "In Alpha Traders": shown in a delete or share dialog when the person can open more than one company. */
export function CompanyNote({ className }: { className?: string }) {
  const { user } = useAuth()
  const companies = user?.allowedCompanies ?? []
  const current = companies.find(c => c.company_id === user?.company_id)
  if (companies.length < 2 || !current) return null
  return (
    <p className={cn('mt-2 flex items-center gap-1.5 text-xs font-semibold text-foreground', className)}>
      <Building2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>In {current.name}</span>
    </p>
  )
}
