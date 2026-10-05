'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { announceNotificationsChanged, markNotificationRead, type AppNotification } from '@/lib/notifications'

/**
 * Opens a notification: switches to its company if it belongs to another one, marks it read in the
 * background (navigation never waits on the network), then goes to its link.
 */
export function useOpenNotification() {
  const router = useRouter()
  const { token, user, switchCompany } = useAuth()

  return useCallback(
    async (n: AppNotification, { replace = false }: { replace?: boolean } = {}) => {
      if (token && !n.is_read) {
        markNotificationRead(token, n.id).then(announceNotificationsChanged).catch(() => {})
      }
      const otherCompany = user && n.company_id !== user.company_id
        && user.allowedCompanies?.some(c => c.company_id === n.company_id)
      if (otherCompany) await switchCompany(n.company_id)
      if (replace) router.replace(n.link)
      else router.push(n.link)
    },
    [router, token, user, switchCompany],
  )
}
