'use client'

import { useEffect, useState } from 'react'
import { loadPublicCatalog, salesContactFrom, type SalesContact } from '@/lib/billing'

/** The sales team's number as configured on the server (BILLING_SALES_PHONE), or null while loading or when none
 * is set. Pages show their call / WhatsApp links only when it is there. */
export function useSalesContact(): SalesContact | null {
  const [contact, setContact] = useState<SalesContact | null>(null)
  useEffect(() => {
    let live = true
    loadPublicCatalog()
      .then((catalog) => { if (live) setContact(salesContactFrom(catalog)) })
      .catch(() => {})
    return () => { live = false }
  }, [])
  return contact
}
