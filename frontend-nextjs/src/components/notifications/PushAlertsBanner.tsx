'use client'

import { AlertCircle, BellRing, Loader2, Send, Share2 } from 'lucide-react'
import { usePushAlerts } from '@/hooks/usePushAlerts'
import { cn } from '@/lib/utils'

/** One line about device (lock-screen) alerts on this browser: how to get them, turn them on, or test them. */
export function PushAlertsBanner({ className }: { className?: string }) {
  const push = usePushAlerts()

  if (push.iosBrowser) {
    return (
      <div className={cn('flex items-start gap-2.5 bg-amber-500/10 px-4 py-3 text-sm', className)}>
        <Share2 className="mt-0.5 h-4 w-4 shrink-0 text-amber-700 dark:text-amber-400" aria-hidden="true" />
        <p className="text-muted-foreground">
          <span className="font-semibold text-foreground">Alerts on iPhone:</span>{' '}
          tap Safari&apos;s Share button, then{' '}
          <span className="font-semibold text-foreground">Add to Home Screen</span>, and open the app from there.
        </p>
      </div>
    )
  }

  if (push.supported && !push.subscribed && push.permission !== 'denied') {
    return (
      <div className={cn('bg-emerald-500/10 px-4 py-3 text-sm', className)}>
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <BellRing className="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" aria-hidden="true" />
            <div className="min-w-0">
              <p className="font-semibold text-foreground">Turn on device alerts</p>
              <p className="text-xs text-muted-foreground">Sound and lock-screen notifications on this device</p>
            </div>
          </div>
          <button
            type="button"
            onClick={push.enable}
            disabled={push.enabling}
            className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-60 cursor-pointer"
          >
            {push.enabling && <Loader2 className="h-4 w-4 animate-spin" />}
            {push.enabling ? 'Turning on…' : 'Turn on'}
          </button>
        </div>
        {push.error && (
          <p className="mt-2 rounded-lg bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-700 dark:text-rose-400" role="alert">
            {push.error}
          </p>
        )}
      </div>
    )
  }

  if (push.subscribed) {
    return (
      <div className={cn('flex items-center justify-between gap-3 bg-muted/40 px-4 py-2 text-sm', className)}>
        <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
          <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden="true" />
          <span className="truncate">Device alerts are on</span>
        </span>
        <button
          type="button"
          onClick={push.sendTest}
          disabled={push.testing}
          className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg px-2 text-sm font-semibold text-primary hover:underline disabled:opacity-60 cursor-pointer"
        >
          {push.testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Send test
        </button>
      </div>
    )
  }

  if (push.permission === 'denied') {
    return (
      <div className={cn('flex items-center gap-2 bg-rose-500/10 px-4 py-2.5 text-sm text-rose-700 dark:text-rose-400', className)}>
        <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>Device alerts are blocked in this browser&apos;s settings.</span>
      </div>
    )
  }

  return null
}
