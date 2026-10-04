'use client'

import React from 'react'
import { Globe, Laptop, Loader2, Monitor, Smartphone, Tablet } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  CLIENT_LABELS,
  REVOKE_REASON_LABELS,
  lastActiveLabel,
  relativeTime,
  type DeviceSession,
} from '@/lib/device-sessions'

/** Icon for a device: the Sync Agent gets a monitor, otherwise by form factor. */
export function DeviceIcon({ session, className }: { session: Pick<DeviceSession, 'client_type' | 'device_type'>; className?: string }) {
  const Icon =
    session.client_type === 'sync-agent' ? Monitor
      : session.device_type === 'mobile' ? Smartphone
        : session.device_type === 'tablet' ? Tablet
          : session.device_type === 'desktop' ? Laptop
            : Globe
  return <Icon className={className} aria-hidden="true" />
}

function Badge({ tone, children }: { tone: 'emerald' | 'sky' | 'red' | 'muted'; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        'text-[10px] font-extrabold px-2 py-0.5 rounded-full border whitespace-nowrap',
        tone === 'emerald' && 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
        tone === 'sky' && 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/20',
        tone === 'red' && 'bg-destructive/10 text-destructive border-destructive/20',
        tone === 'muted' && 'bg-muted text-muted-foreground border-border',
      )}
    >
      {children}
    </span>
  )
}

interface DeviceListProps {
  sessions: DeviceSession[]
  /** Show whose device it is (company-wide list) */
  showUser?: boolean
  /** Buttons for one device (sign out, block, ...) */
  actions?: (session: DeviceSession) => React.ReactNode
  emptyText?: string
}

export function DeviceList({ sessions, showUser = false, actions, emptyText = 'No devices.' }: DeviceListProps) {
  if (sessions.length === 0) {
    return <p className="text-xs text-muted-foreground text-center py-6">{emptyText}</p>
  }
  return (
    <ul className="divide-y divide-border/70 rounded-xl border border-border/80 bg-card">
      {sessions.map((s) => {
        const signedOut = Boolean(s.revoked_at)
        const details = [
          s.legacy ? 'Signed in before device tracking' : s.client_type ? CLIENT_LABELS[s.client_type] ?? s.client_type : null,
          s.os_name,
          s.client_type === 'web' ? null : s.browser_name,
          s.app_version ? `v${s.app_version}` : null,
          s.ip_address,
        ].filter(Boolean)
        return (
          <li key={s.session_id} className={cn('flex flex-wrap items-start gap-3 p-3', signedOut && 'opacity-70')}>
            <div className="relative shrink-0 w-9 h-9 rounded-xl bg-muted flex items-center justify-center text-muted-foreground">
              <DeviceIcon session={s} className="w-4.5 h-4.5" />
              {s.is_active_now && !signedOut && (
                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-card" title="Active now" />
              )}
            </div>

            <div className="min-w-0 flex-1 space-y-0.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="text-sm font-bold text-foreground truncate">{s.device_name}</p>
                {s.is_current && <Badge tone="sky">This device</Badge>}
                {s.is_blocked && <Badge tone="red">Blocked</Badge>}
                {signedOut && <Badge tone="muted">{REVOKE_REASON_LABELS[s.revoke_reason ?? ''] ?? 'Signed out'}</Badge>}
              </div>
              {showUser && s.username && <p className="text-xs font-semibold text-foreground/80">{s.username}</p>}
              {details.length > 0 && <p className="text-[11px] text-muted-foreground break-words">{details.join(' · ')}</p>}
              <p className="text-[11px] text-muted-foreground">
                {signedOut ? (
                  <>Signed out {relativeTime(s.revoked_at) ?? ''}</>
                ) : (
                  <>
                    <span className={cn(s.is_active_now && 'text-emerald-700 dark:text-emerald-400 font-bold')}>{lastActiveLabel(s)}</span>
                    {s.created_at && <> · signed in {relativeTime(s.created_at)}</>}
                  </>
                )}
              </p>
            </div>

            {/* On phones the buttons get their own line so the device name and details keep the width */}
            {actions && <div className="flex w-full sm:w-auto items-center justify-end gap-1.5 sm:ml-auto empty:hidden">{actions(s)}</div>}
          </li>
        )
      })}
    </ul>
  )
}

/** Small action button used in device rows. */
export function DeviceActionButton({
  onClick,
  tone = 'default',
  disabled,
  children,
  title,
}: {
  onClick: () => void
  tone?: 'default' | 'danger'
  disabled?: boolean
  children: React.ReactNode
  title?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'h-7 px-2.5 text-[11px] font-bold rounded-lg border transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed',
        tone === 'danger'
          ? 'border-destructive/30 text-destructive hover:bg-destructive/10'
          : 'border-border/80 text-foreground hover:bg-muted',
      )}
    >
      {children}
    </button>
  )
}

/** Inline confirmation for a destructive device action (dialogs can't use window.confirm on all platforms). */
export function ConfirmBar({
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  busy,
  children,
}: {
  message: React.ReactNode
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
  children?: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-3 space-y-2" role="alertdialog" aria-live="polite">
      <p className="text-xs font-semibold text-foreground">{message}</p>
      {children}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} disabled={busy} className="h-8 px-3 text-xs font-bold rounded-lg border border-border/80 hover:bg-muted cursor-pointer">
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="h-8 px-3 text-xs font-bold rounded-lg bg-destructive text-white hover:bg-destructive/90 flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
        >
          {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          {confirmLabel}
        </button>
      </div>
    </div>
  )
}
