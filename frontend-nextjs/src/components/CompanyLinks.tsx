'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { COMPANY_PARAM, takeCompanySwitchNotice } from '@/lib/current-company'

/**
 * Makes a link that names its company (…?company=3) open in that company. If this device is in another one it
 * switches first and says so; if the person cannot open that company it says that instead and stays put.
 * Also shows the "Now in …" notice after any switch. Renders nothing.
 */
export function CompanyLinks() {
  const pathname = usePathname()
  const { user, isLoading, switchCompany } = useAuth()

  useEffect(() => {
    if (isLoading || !user) return
    const notice = takeCompanySwitchNotice()
    if (notice?.name) toast.info(notice.forALink ? `Switched to ${notice.name} to open this` : `Now in ${notice.name}`)

    const url = new URL(window.location.href)
    const wanted = Number(url.searchParams.get(COMPANY_PARAM))
    if (!url.searchParams.has(COMPANY_PARAM)) return
    url.searchParams.delete(COMPANY_PARAM)
    const here = `${url.pathname}${url.search}${url.hash}`
    if (Number.isInteger(wanted) && wanted > 0 && wanted !== user.company_id) {
      if (user.allowedCompanies?.some(c => c.company_id === wanted)) {
        switchCompany(wanted, here)   // reloads at this page, in that company
        return
      }
      const current = user.allowedCompanies?.find(c => c.company_id === user.company_id)?.name
      toast.error(`This link is for a company you cannot open.${current ? ` You are still in ${current}.` : ''}`)
    }
    // Same company, or refused: drop the parameter so the address is clean and is not acted on twice
    window.history.replaceState(window.history.state, '', here)
  }, [pathname, user, isLoading, switchCompany])

  return null
}
