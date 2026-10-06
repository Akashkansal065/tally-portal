'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getGstDocsSettings, saveGstDocsSettings, type GstDocsSettings } from '@/lib/edocs'

const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

/** e-Invoice / e-way bill set-up: Demo or Live, and this company's portal API users (passwords are write-only). */
export function GstDocsSetup({ token }: { token: string }) {
  const [data, setData] = useState<GstDocsSettings | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let current = true
    getGstDocsSettings(token).then(d => { if (current) setData(d) }).catch(() => {})
    return () => { current = false }
  }, [token])

  if (!data) return null
  const mode = (draft.mode as 'demo' | 'live' | undefined) ?? data.mode
  const save = async () => {
    setSaving(true)
    try {
      const body: Record<string, string> = {}
      for (const [k, v] of Object.entries(draft)) if (v !== '' || k.endsWith('username')) body[k] = v
      setData(await saveGstDocsSettings(token, body))
      setDraft({})
      toast.success('e-Invoice / e-way bill set-up saved')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }
  const checks: [string, boolean][] = [
    [`GST provider account keys on the server (${data.gsp_provider})`, data.gsp_account_ready],
    [`Company GSTIN${data.company_gstin ? `: ${data.company_gstin}` : ' (Company profile)'}`, !!data.company_gstin],
    ['e-Invoice portal API user', !!data.einvoice_username && data.has_einvoice_password],
    ['e-Way bill portal API user', !!data.eway_username && data.has_eway_password],
  ]

  return (
    <section className="space-y-4 rounded-2xl border border-border bg-card p-5" aria-labelledby="gst-docs-setup">
      <div>
        <h3 id="gst-docs-setup" className="text-sm font-bold">e-Invoice & e-way bill set-up</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Demo makes labelled, made-up numbers for trying the screens. Live sends to the GST portal through the GST provider; it needs the keys below.
        </p>
      </div>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {checks.map(([label, ok]) => (
          <li key={label} className="flex items-start gap-2 text-sm">
            {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
            <span>{label}{ok ? '' : ': not set'}</span>
          </li>
        ))}
      </ul>
      <div className="inline-flex rounded-xl bg-muted p-1" role="radiogroup" aria-label="Mode">
        {(['demo', 'live'] as const).map(m => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setDraft(d => ({ ...d, mode: m }))}
            className={cn('min-h-10 rounded-lg px-4 text-sm font-semibold cursor-pointer', mode === m ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
            {m === 'demo' ? 'Demo' : 'Live'}
          </button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {([
          ['einvoice_username', 'e-Invoice API username', data.einvoice_username || '', 'text'],
          ['einvoice_password', 'e-Invoice API password', '', 'password'],
          ['eway_username', 'e-Way bill API username', data.eway_username || '', 'text'],
          ['eway_password', 'e-Way bill API password', '', 'password'],
        ] as const).map(([key, label, saved, type]) => (
          <label key={key} className="block text-sm">
            <span className="mb-1 block font-semibold">{label}</span>
            <input type={type} autoComplete="off" value={draft[key] ?? saved} onChange={e => setDraft(d => ({ ...d, [key]: e.target.value }))}
              placeholder={type === 'password' && (key === 'einvoice_password' ? data.has_einvoice_password : data.has_eway_password) ? 'Saved; type to replace' : ''}
              className={field} />
          </label>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        The API users are created on the government portals and linked to the GST provider (setup guide A8). The provider&apos;s own account keys go in the server settings, not here.
      </p>
      <button type="button" onClick={save} disabled={saving || Object.keys(draft).length === 0}
        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
        {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save
      </button>
    </section>
  )
}
