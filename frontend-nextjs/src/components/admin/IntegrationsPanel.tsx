'use client'

import { useEffect, useState } from 'react'
import { Loader2, PlugZap } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { fetchIntegrations, setIntegration, type Integration, type IntegrationState } from '@/lib/integrations'
import { GstDocsSetup } from '@/components/admin/GstDocsSetup'

const STATUS: Record<IntegrationState, { label: string; tone: string; note: string }> = {
  off: { label: 'Off', tone: 'bg-muted text-muted-foreground', note: 'Hidden everywhere in the app.' },
  demo: {
    label: 'Demo',
    tone: 'bg-amber-500/15 text-amber-800 dark:text-amber-300',
    note: 'Not connected to the provider yet. Anything it makes is labelled DEMO and is not valid.',
  },
  unavailable: {
    label: 'Not available yet',
    tone: 'bg-muted text-foreground',
    note: "Not connected to the provider yet, and there's no safe demo, so it stays hidden.",
  },
  needs_setup: { label: 'Needs setup', tone: 'bg-sky-500/15 text-sky-800 dark:text-sky-300', note: "The provider's keys aren't set yet." },
  connected: { label: 'Connected', tone: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300', note: 'Working with the provider.' },
}

/** Admin → Integrations: switches for features that need another provider's keys or a paid subscription. */
export function IntegrationsPanel({ token }: { token: string | null }) {
  const [list, setList] = useState<Integration[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let current = true
    fetchIntegrations(token)
      .then(data => { if (current) setList(data) })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load integrations') })
    return () => { current = false }
  }, [token])

  const toggle = async (item: Integration) => {
    if (!token) return
    setSaving(item.key)
    try {
      const updated = await setIntegration(token, item.key, !item.enabled)
      setList(l => l?.map(i => (i.key === updated.key ? updated : i)) ?? l)
      toast.success(`${updated.label}: ${STATUS[updated.status].label}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not change the switch')
    } finally {
      setSaving(null)
    }
  }

  return (
    <section aria-labelledby="integrations-title" className="space-y-3 font-sans">
      <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600">
            <PlugZap className="h-5 w-5" />
          </div>
          <div>
            <h2 id="integrations-title" className="text-sm font-extrabold uppercase tracking-wider">Integrations</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Features that need another company&apos;s API keys or a paid subscription. Each is off until you switch it on for this
              company. Free features (UPI links and QR codes, WhatsApp messages, PDFs, reports) don&apos;t need a switch.
            </p>
          </div>
        </div>
      </div>

      {error ? (
        <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
      ) : !list ? (
        <div className="flex justify-center rounded-2xl border border-border bg-card py-10" role="status">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="sr-only">Loading integrations</span>
        </div>
      ) : (
        <ul className="space-y-2">
          {list.map(item => {
            const status = STATUS[item.status]
            return (
              <li key={item.key} className="rounded-2xl border border-border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-bold">{item.label}</h3>
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', status.tone)}>{status.label}</span>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={item.enabled}
                    aria-label={`${item.label}: ${item.enabled ? 'on' : 'off'}`}
                    disabled={saving !== null}
                    onClick={() => toggle(item)}
                    className={cn(
                      'relative mt-0.5 inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full transition-colors disabled:opacity-60',
                      item.enabled ? 'bg-emerald-500' : 'bg-muted-foreground/30'
                    )}
                  >
                    {saving === item.key ? (
                      <Loader2 className="mx-auto h-4 w-4 animate-spin text-white" />
                    ) : (
                      <span className={cn('inline-block h-5 w-5 rounded-full bg-white shadow transition-transform', item.enabled ? 'translate-x-6' : 'translate-x-1')} />
                    )}
                  </button>
                </div>
                <dl className="mt-3 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                  <div><dt className="inline text-muted-foreground">Provider: </dt><dd className="inline">{item.provider}</dd></div>
                  <div><dt className="inline text-muted-foreground">Cost: </dt><dd className="inline">{item.cost}</dd></div>
                  <div><dt className="inline text-muted-foreground">Real connection: </dt><dd className="inline">{item.live ? 'Built' : item.phase}</dd></div>
                </dl>
                {item.enabled && <p className="mt-2 text-xs text-muted-foreground">{status.note}</p>}
              </li>
            )
          })}
        </ul>
      )}
      {token && list?.some(i => (i.key === 'einvoice' || i.key === 'eway_bill') && i.enabled) && <GstDocsSetup token={token} />}
    </section>
  )
}
