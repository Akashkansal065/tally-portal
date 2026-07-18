'use client'

import { useAuth } from '@/context/AuthContext'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import { Loader2 } from 'lucide-react'

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (isLoading) return

    const publicPaths = ['/login', '/signup']
    const isPublicPath = publicPaths.includes(pathname)

    if (!user && !isPublicPath) {
      router.replace('/login')
    } else if (user && isPublicPath) {
      router.replace('/')
    }
  }, [user, isLoading, pathname, router])

  if (isLoading) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-background min-h-[50vh]">
        <Loader2 className="animate-spin h-8 w-8 text-primary" />
        <p className="text-xs text-muted-foreground mt-2 font-medium">Verifying session...</p>
      </div>
    )
  }

  const publicPaths = ['/login', '/signup']
  const isPublicPath = publicPaths.includes(pathname)

  // Prevent rendering protected content before redirect completes
  if (!user && !isPublicPath) {
    return null
  }
  if (user && isPublicPath) {
    return null
  }

  return <>{children}</>
}
