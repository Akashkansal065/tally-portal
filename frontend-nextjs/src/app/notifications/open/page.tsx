'use client'

import { Suspense, useEffect, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { useOpenNotification } from '@/hooks/useOpenNotification'
import { getNotification } from '@/lib/notifications'

/*
 * Where push messages lead: /notifications/open?id=N. Looks the notification up, switches to its company,
 * marks it read and replaces this page with the notification's link, so Back returns to where you were.
 */
export default function OpenNotificationPage() {
  return (
    <Suspense fallback={<Opening />}>
      <OpenNotification />
    </Suspense>
  )
}

function OpenNotification() {
  const router = useRouter()
  const params = useSearchParams()
  const { token, isLoading } = useAuth()
  const openNotification = useOpenNotification()
  const started = useRef<string | null>(null)
  const id = Number(params.get('id'))

  useEffect(() => {
    // Signed-out visitors are sent to sign-in (and back here) by RouteGuard
    if (isLoading || !token) return
    const key = `${id}`
    if (started.current === key) return
    started.current = key
    if (!id) {
      router.replace('/notifications')
      return
    }
    getNotification(token, id)
      .then(n => openNotification(n, { replace: true }))
      .catch(() => {
        toast.error('That notification is no longer available')
        router.replace('/notifications')
      })
  }, [id, token, isLoading, router, openNotification])

  return <Opening />
}

function Opening() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center gap-2 text-sm text-muted-foreground" role="status">
      <Loader2 className="h-5 w-5 animate-spin text-primary" /> Opening…
    </div>
  )
}
