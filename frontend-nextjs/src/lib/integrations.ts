'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'

/* Features that need another provider's API keys or a paid subscription. Each has a per-company switch, off by
   default (Admin → Integrations); a feature whose switch is off is hidden. See docs/livekeeping-parity-plan.md. */

export type IntegrationKey = 'email' | 'whatsapp_api' | 'einvoice' | 'eway_bill' | 'gst_portal' | 'gst_filing' | 'payment_gateway'

/** off: hidden · demo: on, made-up values labelled DEMO · unavailable: on, but not built and no safe demo ·
 *  needs_setup: built, keys missing · connected: built and keys set */
export type IntegrationState = 'off' | 'demo' | 'unavailable' | 'needs_setup' | 'connected'

export interface Integration {
  key: IntegrationKey
  label: string
  description: string
  provider: string
  cost: string
  phase: string
  live: boolean
  enabled: boolean
  status: IntegrationState
}

// One request per company, shared by every screen until a switch changes
const cache = new Map<string, Promise<Integration[]>>()

function load(token: string, companyId: number): Promise<Integration[]> {
  const key = String(companyId)
  let pending = cache.get(key)
  if (!pending) {
    pending = fetch(`${API_BASE}/integrations`, { headers: authHeaders(token) })
      .then(res => (res.ok ? res.json() : []))
      .catch(() => [])
    pending.then(list => { if (list.length === 0) cache.delete(key) })
    cache.set(key, pending)
  }
  return pending
}

export function useIntegrations() {
  const { token, user } = useAuth()
  const companyId = user?.company_id
  const [state, setState] = useState<{ companyId?: number; list: Integration[] | null }>({ list: null })

  useEffect(() => {
    if (!token || !companyId) return
    let current = true
    load(token, companyId).then(list => { if (current) setState({ companyId, list }) })
    return () => { current = false }
  }, [token, companyId])

  const list = state.companyId === companyId ? state.list : null
  const find = (key: IntegrationKey) => list?.find(i => i.key === key)
  return {
    integrations: list,
    loaded: list !== null,
    /** The switch is on and the feature can run (for real, or as a labelled demo) */
    canUse: (key: IntegrationKey) => {
      const status = find(key)?.status
      return status === 'demo' || status === 'needs_setup' || status === 'connected'
    },
    /** The feature runs as a demo: anything it makes must be labelled DEMO */
    isDemo: (key: IntegrationKey) => find(key)?.status === 'demo',
    /** Switched on with its real connection built and keys set */
    isConnected: (key: IntegrationKey) => find(key)?.status === 'connected',
  }
}

export async function setIntegration(token: string, key: IntegrationKey, enabled: boolean): Promise<Integration> {
  const res = await fetch(`${API_BASE}/integrations/${key}`, {
    method: 'PUT',
    headers: authHeaders(token),
    body: JSON.stringify({ enabled }),
  })
  if (!res.ok) {
    let detail = 'Could not change the switch'
    try { detail = (await res.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  cache.clear()
  return res.json()
}

export async function fetchIntegrations(token: string): Promise<Integration[]> {
  const res = await fetch(`${API_BASE}/integrations`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error('Could not load integrations')
  return res.json()
}
