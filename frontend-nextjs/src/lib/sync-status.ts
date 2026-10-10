'use client'

import { useEffect, useState } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'

/** How fresh a company's data is, from what the Desktop Sync Agent last reported for it. */
export type Freshness = 'live' | 'behind' | 'closed' | 'offline' | 'attention' | 'never'

export interface CompanySyncStatus {
  company_id: number
  name: string
  gstin: string | null
  city: string | null
  state: string | null
  financial_year_start: string | null
  is_current: boolean
  freshness: Freshness
  last_synced_at: string | null
  last_checked_at: string | null
  agent_online: boolean
  last_error: string | null
  synced_from: string | null
  pending_to_tally: number
}

const REFRESH_MS = 60_000

// One poll shared by everything on the page that shows freshness (header, switcher, notes on reports)
let cached: CompanySyncStatus[] | null = null
let cachedFor = ''
let inFlight: Promise<void> | null = null
let timer: ReturnType<typeof setInterval> | null = null
const listeners = new Set<(rows: CompanySyncStatus[] | null) => void>()

async function load(token: string) {
  if (inFlight) return inFlight
  inFlight = fetch(`${API_BASE}/companies/sync-status`, { headers: authHeaders(token), cache: 'no-store' })
    .then(res => (res.ok ? res.json() : null))
    .then(rows => {
      if (Array.isArray(rows)) {
        cached = rows
        cachedFor = token
        listeners.forEach(listener => listener(rows))
      }
    })
    .catch(() => { /* keep showing the last answer; the next poll tries again */ })
    .finally(() => { inFlight = null })
  return inFlight
}

/** Ask again now, for example right after switching company. */
export function refreshSyncStatus(token: string | null) {
  if (token) load(token)
}

/** Sync status of every company the signed-in person can open, refreshed every minute. null until first loaded. */
export function useCompanySyncStatus(token: string | null): CompanySyncStatus[] | null {
  const [rows, setRows] = useState<CompanySyncStatus[] | null>(token && cachedFor === token ? cached : null)

  useEffect(() => {
    if (!token) return
    listeners.add(setRows)
    if (cachedFor !== token) cached = null
    load(token)
    if (!timer) timer = setInterval(() => { if (listeners.size) load(token) }, REFRESH_MS)
    return () => {
      listeners.delete(setRows)
      if (listeners.size === 0 && timer) {
        clearInterval(timer)
        timer = null
      }
    }
  }, [token])

  return rows
}

/** "3 min ago" under an hour, a clock time today, a date before that. */
export function whenText(iso: string | null, now: Date = new Date()): string {
  if (!iso) return ''
  const at = new Date(iso)
  const minutes = Math.floor((now.getTime() - at.getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const time = at.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })
  if (at.toDateString() === now.toDateString()) return `today ${time}`
  return `${at.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}, ${time}`
}

/** The sentence shown beside a company, and the colour of its dot. */
export function describeFreshness(status: CompanySyncStatus, now: Date = new Date()): { text: string; dot: string } {
  const synced = status.last_synced_at ? `Last synced ${whenText(status.last_synced_at, now)}` : 'Not synced yet'
  switch (status.freshness) {
    case 'live':
      return { text: `Synced ${whenText(status.last_synced_at, now)}`, dot: 'bg-emerald-500' }
    case 'behind':
      return { text: `Synced ${whenText(status.last_synced_at, now)}`, dot: 'bg-amber-500' }
    case 'closed':
      return { text: `Open this company in Tally to sync. ${synced}`, dot: 'bg-slate-400' }
    case 'offline':
      return { text: `Sync agent offline since ${whenText(status.last_checked_at, now)}. ${synced}`, dot: 'bg-slate-400' }
    case 'attention':
      return { text: `Sync needs attention. ${synced}`, dot: 'bg-rose-500' }
    default:
      return { text: 'No sync agent has connected this company yet', dot: 'bg-slate-400' }
  }
}

/** Entries made in the app that have not reached Tally yet: a separate fact from how fresh the data is. */
export function pendingText(status: CompanySyncStatus): string {
  if (!status.pending_to_tally) return ''
  return `${status.pending_to_tally} ${status.pending_to_tally === 1 ? 'entry' : 'entries'} waiting to reach Tally`
}
