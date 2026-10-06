'use client'

import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, CircleAlert, Eye, ImagePlus, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getBranding, imageFileToDataUrl, saveBranding, type Branding, type BrandingUpdate } from '@/lib/branding'
import { generateVoucherPdf } from '@/lib/pdf-generator'

const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

/** Admin → Invoice design: logo, signature, bank details, declaration and the UPI QR, with a sample invoice preview. */
export function InvoiceDesignPanel({ token, companyId }: { token: string | null; companyId?: number }) {
  const [branding, setBranding] = useState<Branding | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState<BrandingUpdate>({})
  const [saving, setSaving] = useState(false)
  const [previewing, setPreviewing] = useState(false)

  useEffect(() => {
    if (!token) return
    let current = true
    getBranding(token, companyId)
      .then(b => { if (current) setBranding(b) })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load') })
    return () => { current = false }
  }, [token, companyId])

  if (error) return <p className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">{error}</p>
  if (!branding || !token) {
    return <div className="flex justify-center rounded-2xl border border-border bg-card py-10"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
  }

  // What's shown: saved values with unsaved changes on top
  const logo = draft.logo !== undefined ? draft.logo || null : branding.logo
  const signature = draft.signature !== undefined ? draft.signature || null : branding.signature
  const bank = {
    bank_account_name: draft.bank_account_name ?? branding.bank.account_name ?? '',
    bank_name: draft.bank_name ?? branding.bank.bank_name ?? '',
    bank_account_no: draft.bank_account_no ?? branding.bank.account_no ?? '',
    bank_ifsc: draft.bank_ifsc ?? branding.bank.ifsc ?? '',
    bank_branch: draft.bank_branch ?? branding.bank.branch ?? '',
  }
  const declaration = draft.declaration ?? branding.declaration
  const showUpiQr = draft.show_upi_qr ?? branding.show_upi_qr
  const changed = Object.keys(draft).length > 0
  const c = branding.company
  const checklist: [string, boolean, string][] = [
    ['Company GSTIN', !!c.gstin, 'Tax invoices need it'],
    ['Address', c.address_lines.length > 0, 'Printed under the company name'],
    ['Phone and email', !!(c.phone && c.email), 'Printed under the company name'],
    ['UPI ID', !!c.upi_id, 'For the UPI QR code and WhatsApp reminders'],
  ]

  const current: Branding = {
    ...branding, logo, signature, declaration, show_upi_qr: showUpiQr,
    bank: { account_name: bank.bank_account_name || null, bank_name: bank.bank_name || null, account_no: bank.bank_account_no || null,
      ifsc: bank.bank_ifsc || null, branch: bank.bank_branch || null },
  }

  const save = async () => {
    setSaving(true)
    try {
      setBranding(await saveBranding(token, draft))
      setDraft({})
      toast.success('Invoice design saved')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  const preview = async () => {
    setPreviewing(true)
    try {
      const doc = await generateVoucherPdf({
        voucherGuid: 'sample',
        header: { voucherType: 'Sales', voucherNumber: 'SAMPLE-1', date: new Date().toISOString().slice(0, 10), partyName: 'Sample Customer' },
        accounts: [
          { ledger: 'Sample Customer', amount: '-11800' },
          { ledger: 'Output CGST', amount: '900' },
          { ledger: 'Output SGST', amount: '900' },
        ],
        inventory: [{ item: 'Sample item', quantity: 10, rate: 1000, amount: 10000, uom: 'PCS', gst_rate: 18, hsn_code: '8516' }],
        partyLedger: { mailingName: 'Sample Customer', mailingAddress: '1 Market Road, Meerut - 250001', gstn: '09AAAAA0000A1Z5', mailingState: 'Uttar Pradesh', mobile: '9800000000' },
        branding: current,
        shouldDownload: false,
      })
      window.open(doc.output('bloburl'), '_blank', 'noopener')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not make the preview')
    } finally {
      setPreviewing(false)
    }
  }

  return (
    <div className="space-y-4 font-sans">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <h2 className="text-sm font-extrabold uppercase tracking-wider">Invoice design</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          What invoice and statement PDFs show for this company. The company name, address, GSTIN, phone, email and UPI ID come from
          <strong> Company profile</strong> (tap the company name at the top → Company profile → Edit Profile Details).
        </p>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {checklist.map(([label, ok, why]) => (
            <li key={label} className="flex items-start gap-2 text-sm">
              {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
              <span><span className="font-semibold">{label}</span>{ok ? '' : ': not set.'} <span className="text-muted-foreground">{why}</span></span>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <ImagePicker label="Logo" hint="PNG or JPEG. Printed at the top left of invoices and top right of statements."
          value={logo} maxWidth={600} maxHeight={600} maxChars={420_000} onChange={v => setDraft(d => ({ ...d, logo: v }))} />
        <ImagePicker label="Signature" hint="A scan of the authorised signature, ideally on a white or transparent background."
          value={signature} maxWidth={500} maxHeight={200} maxChars={210_000} onChange={v => setDraft(d => ({ ...d, signature: v }))} />
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-bold">Bank details on invoices</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {([
            ['bank_account_name', "Account holder's name", 'Defaults to the company name'],
            ['bank_name', 'Bank name', 'e.g. Punjab National Bank'],
            ['bank_account_no', 'Account number', ''],
            ['bank_ifsc', 'IFSC', 'e.g. PUNB0400700'],
            ['bank_branch', 'Branch', ''],
          ] as const).map(([key, label, placeholder]) => (
            <label key={key} className="block text-sm">
              <span className="mb-1 block font-semibold">{label}</span>
              <input value={bank[key]} placeholder={placeholder} onChange={e => setDraft(d => ({ ...d, [key]: e.target.value }))} className={field} />
            </label>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 space-y-3">
        <label className="block text-sm">
          <span className="mb-1 block font-semibold">Declaration / terms</span>
          <textarea rows={3} maxLength={1000} value={declaration} onChange={e => setDraft(d => ({ ...d, declaration: e.target.value }))}
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30" />
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={showUpiQr} onChange={e => setDraft(d => ({ ...d, show_upi_qr: e.target.checked }))} className="mt-0.5 h-4 w-4 accent-primary" />
          <span>Print a UPI QR code for the bill amount on sales invoices {c.upi_id ? <span className="text-muted-foreground">(pays {c.upi_id})</span> : <span className="text-amber-700 dark:text-amber-300">(set the UPI ID in Company profile first)</span>}</span>
        </label>
      </section>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={preview} disabled={previewing}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-border px-4 text-sm font-bold hover:bg-muted disabled:opacity-60 cursor-pointer">
          {previewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />} Preview a sample invoice
        </button>
        <button type="button" onClick={save} disabled={!changed || saving}
          className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
          {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save
        </button>
        {changed && <span className="self-center text-sm text-muted-foreground">Unsaved changes</span>}
      </div>
    </div>
  )
}

function ImagePicker({ label, hint, value, maxWidth, maxHeight, maxChars, onChange }: {
  label: string
  hint: string
  value: string | null
  maxWidth: number
  maxHeight: number
  maxChars: number
  /** A data URL, or "" to remove */
  onChange: (value: string) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const pick = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    try {
      onChange(await imageFileToDataUrl(file, maxWidth, maxHeight, maxChars))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not read the image')
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <h3 className="text-sm font-bold">{label}</h3>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
      <div className={cn('mt-3 flex h-28 items-center justify-center rounded-xl border border-dashed border-border bg-white p-2')}>
        {/* eslint-disable-next-line @next/next/no-img-element -- a data URL preview */}
        {value ? <img src={value} alt={`${label} preview`} className="max-h-full max-w-full object-contain" /> : <span className="text-sm text-slate-500">No {label.toLowerCase()}</span>}
      </div>
      <input ref={input} type="file" accept="image/png,image/jpeg" className="hidden" onChange={e => pick(e.target.files?.[0])} />
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={() => input.current?.click()} disabled={busy}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted disabled:opacity-60 cursor-pointer">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />} {value ? 'Change' : 'Upload'}
        </button>
        {value && (
          <button type="button" onClick={() => onChange('')}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-rose-700 hover:bg-rose-500/10 dark:text-rose-400 cursor-pointer">
            <Trash2 className="h-4 w-4" /> Remove
          </button>
        )}
      </div>
    </div>
  )
}
