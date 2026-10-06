'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2, MessageCircle, PartyPopper, Search, Send } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import { getBranding, type Branding } from '@/lib/branding'
import { shareFile } from '@/lib/capacitor-pdf'
import { TEMPLATES, canvasToBlob, drawGreeting, type GreetingCategory } from '@/lib/greetings'
import { whatsappLink } from '@/lib/report-insights'

interface Recipient {
  ledger_id: number
  name: string
  last_sale: string | null
  days_since: number | null
  whatsapp: string | null
}

const WINDOWS = [
  { days: 30, label: '30+ days' },
  { days: 60, label: '60+ days' },
  { days: 90, label: '90+ days' },
  { days: 120, label: '120+ days' },
  { days: 0, label: 'All customers' },
]
const CATEGORIES: GreetingCategory[] = ['Festivals', 'Personal', 'Business']

/** Greetings: festival, birthday and thank-you cards with our branding, sent to customers who haven't bought lately. */
export default function GreetingsPage() {
  const { token, user, permissions } = useAuth()
  const [templateId, setTemplateId] = useState(TEMPLATES[0].id)
  const [category, setCategory] = useState<GreetingCategory>('Festivals')
  const [messages, setMessages] = useState<Record<string, string>>({})
  const [branding, setBranding] = useState<Branding | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [days, setDays] = useState(60)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [recipients, setRecipients] = useState<Recipient[] | null>(null)
  const [busy, setBusy] = useState<number | 'card' | null>(null)
  const [sent, setSent] = useState<Set<number>>(new Set())

  const template = TEMPLATES.find(t => t.id === templateId) ?? TEMPLATES[0]
  const message = messages[template.id] ?? template.message

  useEffect(() => {
    if (!token) return
    let current = true
    getBranding(token, user?.company_id).then(b => { if (current) setBranding(b) }).catch(() => {})
    return () => { current = false }
  }, [token, user?.company_id])

  // Preview without a name, redrawn when the card or message changes
  useEffect(() => {
    let current = true
    drawGreeting(template, branding, message).then(c => { if (current) setPreview(c.toDataURL('image/jpeg', 0.8)) })
    return () => { current = false }
  }, [template, branding, message])

  useEffect(() => {
    if (!token) return
    let current = true
    const params = new URLSearchParams({ days: String(days) })
    if (query) params.set('search', query)
    fetch(`${API_BASE}/greetings/customers?${params}`, { headers: authHeaders(token) })
      .then(r => (r.ok ? r.json() : []))
      .then(rows => { if (current) setRecipients(rows) })
      .catch(() => { if (current) setRecipients([]) })
    return () => { current = false }
  }, [token, days, query])

  const filtered = useMemo(() => TEMPLATES.filter(t => t.category === category), [category])
  if (!permissions?.showReports) {
    return <p className="p-6 text-center text-sm text-muted-foreground">Greetings need access to Reports.</p>
  }

  const text = (name?: string) => `${name ? `Dear ${name}, ` : ''}${template.title}! ${message}${branding?.company.name ? `\n— ${branding.company.name}` : ''}`

  const send = async (r?: Recipient) => {
    setBusy(r ? r.ledger_id : 'card')
    try {
      const card = await drawGreeting(template, branding, message, r?.name)
      const blob = await canvasToBlob(card)
      const result = await shareFile(blob, `${template.id}${r ? `-${r.name.replace(/[^A-Za-z0-9]+/g, '_')}` : ''}.png`, text(r?.name))
      if (result === 'downloaded') {
        if (r?.whatsapp) {
          window.open(whatsappLink(r.whatsapp, text(r.name)), '_blank', 'noopener')
          toast.message('The card was downloaded: attach it in the WhatsApp chat that just opened.')
        } else {
          toast.message('The card was downloaded.')
        }
      }
      if (r && result !== 'cancelled') setSent(s => new Set(s).add(r.ledger_id))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not make the card')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 pb-24">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-black"><PartyPopper className="h-5 w-5" /> Greetings</h1>
        <p className="text-sm text-muted-foreground">
          Send a festival, birthday or thank-you card with your logo and details, and win back customers who haven&apos;t bought lately.
          {!branding?.logo && ' Add your logo in Admin → Invoice design.'}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <section className="space-y-3 rounded-2xl border border-border bg-card p-4" aria-label="Card">
          <div className="inline-flex rounded-xl bg-muted p-1" role="tablist" aria-label="Card type">
            {CATEGORIES.map(c => (
              <button key={c} type="button" role="tab" aria-selected={category === c} onClick={() => setCategory(c)}
                className={cn('min-h-10 rounded-lg px-3 text-sm font-semibold cursor-pointer', category === c ? 'bg-card shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
                {c}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Card">
            {filtered.map(t => (
              <button key={t.id} type="button" role="radio" aria-checked={template.id === t.id} onClick={() => setTemplateId(t.id)}
                className={cn('min-h-10 rounded-full border px-3.5 text-sm font-semibold cursor-pointer',
                  template.id === t.id ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted')}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="mx-auto max-w-xs overflow-hidden rounded-xl border border-border shadow-sm">
            {/* eslint-disable-next-line @next/next/no-img-element -- a canvas preview */}
            {preview ? <img src={preview} alt={`${template.label} card preview`} className="w-full" /> : <div className="aspect-[4/5] animate-pulse bg-muted" />}
          </div>
          <label className="block text-sm">
            <span className="mb-1 block font-semibold">Message</span>
            <textarea rows={3} maxLength={240} value={message} onChange={e => setMessages(m => ({ ...m, [template.id]: e.target.value }))}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </label>
          <button type="button" onClick={() => send()} disabled={busy !== null}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border px-4 text-sm font-bold hover:bg-muted disabled:opacity-50 cursor-pointer">
            {busy === 'card' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Share card (for a status or group)
          </button>
        </section>

        <section className="space-y-3 rounded-2xl border border-border bg-card p-4" aria-labelledby="who-title">
          <h2 id="who-title" className="text-sm font-bold">Who to send it to</h2>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="No sale for">
            {WINDOWS.map(w => (
              <button key={w.days} type="button" role="radio" aria-checked={days === w.days} onClick={() => { setRecipients(null); setDays(w.days) }}
                className={cn('min-h-9 rounded-full border px-3 text-xs font-semibold cursor-pointer',
                  days === w.days ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted')}>
                {w.days ? `No sale ${w.label}` : w.label}
              </button>
            ))}
          </div>
          <form className="relative" onSubmit={e => { e.preventDefault(); setRecipients(null); setQuery(search.trim()) }}>
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search customers" aria-label="Search customers"
              className="h-10 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </form>
          {recipients === null ? (
            <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
          ) : recipients.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Nobody here.</p>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">{recipients.length} customer{recipients.length === 1 ? '' : 's'} · {recipients.filter(r => r.whatsapp).length} with a mobile number</p>
              <ul className="max-h-[60vh] divide-y divide-border overflow-y-auto">
                {recipients.slice(0, 200).map(r => (
                  <li key={r.ledger_id} className="flex items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{r.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {r.last_sale ? `Last sale ${r.days_since} days ago` : 'Never bought'}{r.whatsapp ? '' : ' · no mobile'}
                      </p>
                    </div>
                    <button type="button" onClick={() => send(r)} disabled={busy !== null}
                      className={cn('inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold disabled:opacity-50 cursor-pointer',
                        sent.has(r.ledger_id) ? 'border border-border text-muted-foreground' : 'bg-emerald-600 text-white hover:bg-emerald-700')}>
                      {busy === r.ledger_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
                      {sent.has(r.ledger_id) ? 'Sent' : 'Send'}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
