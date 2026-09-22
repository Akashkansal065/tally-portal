'use client'

import React from 'react'
import {
  MapPinOff,
  Compass,
  RefreshCw,
  AlertTriangle,
  X,
  Smartphone,
  Laptop,
} from 'lucide-react'
import { DevicePlatformInfo } from '@/lib/location'
import { cn } from '@/lib/utils'

export interface LocationPermissionModalProps {
  isOpen: boolean
  onClose: () => void
  onRetry: () => Promise<boolean>
  isRetrying: boolean
  error: string | null
  platform: DevicePlatformInfo
  activityName?: string
  shopName?: string
}

export function LocationPermissionModal({
  isOpen,
  onClose,
  onRetry,
  isRetrying,
  error,
  platform,
  activityName = 'Shop Check-In',
  shopName,
}: LocationPermissionModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-xs z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
        {/* Header with glowing alert icon */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400 flex items-center justify-center shrink-0 border border-rose-500/20">
              <MapPinOff className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-extrabold text-base text-foreground leading-tight">
                Location Access Blocked
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Mandatory for {activityName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1.5 rounded-xl hover:bg-muted transition-colors cursor-pointer"
            title="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Why Location is Needed */}
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-3.5 text-xs text-amber-700 dark:text-amber-300 space-y-1">
          <div className="flex items-center gap-1.5 font-bold">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>Why is this required?</span>
          </div>
          <p className="text-[11px] leading-relaxed text-amber-900/80 dark:text-amber-200/90">
            To prevent audit disputes and verify visits, on-site GPS coordinates must be recorded
            {shopName ? (
              <> for <strong>{shopName}</strong></>
            ) : null}
            . Actions are blocked until GPS is enabled.
          </p>
        </div>

        {/* Device-Specific Steps */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 text-xs font-bold text-foreground uppercase tracking-wide">
            {platform.isMobile ? (
              <Smartphone className="h-3.5 w-3.5 text-primary" />
            ) : (
              <Laptop className="h-3.5 w-3.5 text-primary" />
            )}
            <span>How to Unblock in {platform.browserName}:</span>
          </div>

          <div className="bg-muted/40 border border-border/80 rounded-2xl p-4 text-xs space-y-3">
            {platform.isIOS ? (
              // iOS Safari Instructions
              <ol className="list-decimal list-inside space-y-2 text-foreground font-medium">
                <li>
                  Tap the <strong className="px-1.5 py-0.5 bg-background border border-border rounded font-mono text-[11px]">aA</strong> icon on the left/right of the address bar.
                </li>
                <li>
                  Tap <strong>Website Settings</strong>.
                </li>
                <li>
                  Set <strong>Location</strong> to <strong className="text-emerald-600 dark:text-emerald-400">Allow</strong>.
                </li>
                <li>
                  Return here and tap <strong>Verify & Enable Access</strong> below.
                </li>
              </ol>
            ) : platform.isAndroid ? (
              // Android Chrome Instructions
              <ol className="list-decimal list-inside space-y-2 text-foreground font-medium">
                <li>
                  Tap the <strong className="px-1.5 py-0.5 bg-background border border-border rounded font-mono text-[11px]">🔒 Lock / Tune</strong> icon beside the website address.
                </li>
                <li>
                  Tap <strong>Permissions</strong> (or <em>Site Settings</em>).
                </li>
                <li>
                  Toggle <strong>Location</strong> to <strong className="text-emerald-600 dark:text-emerald-400">Allow / On</strong>.
                </li>
                <li>
                  Return here and tap <strong>Verify & Enable Access</strong> below.
                </li>
              </ol>
            ) : (
              // Desktop Browser Instructions
              <ol className="list-decimal list-inside space-y-2 text-foreground font-medium">
                <li>
                  Click the <strong className="px-1.5 py-0.5 bg-background border border-border rounded font-mono text-[11px]">🔒 Lock / Settings</strong> icon next to the URL address.
                </li>
                <li>
                  Set <strong>Location</strong> to <strong className="text-emerald-600 dark:text-emerald-400">Allow</strong>.
                </li>
                <li>
                  Click <strong>Verify & Enable Access</strong> below.
                </li>
              </ol>
            )}
          </div>
        </div>

        {/* Dynamic Error / Shake Alert */}
        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-600 dark:text-rose-400 text-xs font-semibold flex items-start gap-2 animate-in fade-in">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="leading-snug">{error}</div>
          </div>
        )}

        {/* Modal Action Buttons */}
        <div className="flex items-center justify-end gap-2.5 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 border border-border hover:bg-muted text-foreground rounded-xl text-xs font-bold transition-all cursor-pointer"
          >
            Dismiss
          </button>
          <button
            type="button"
            onClick={onRetry}
            disabled={isRetrying}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-emerald-500/20 cursor-pointer flex items-center gap-2 disabled:opacity-50"
          >
            {isRetrying ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Checking Access...</span>
              </>
            ) : (
              <>
                <Compass className="h-3.5 w-3.5" />
                <span>Verify & Enable Access</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
