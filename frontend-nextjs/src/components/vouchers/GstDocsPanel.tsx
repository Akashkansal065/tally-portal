'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, FileCheck2, Loader2, ShieldCheck, Truck, XCircle } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import {
  EWB_CANCEL_REASONS,
  EdocError,
  IRN_CANCEL_REASONS,
  VEHICLE_REASONS,
  cancelEwaybill,
  cancelIrn,
  generateEwaybill,
  generateIrn,
  getVoucherEdocs,
  updateVehicle,
  type VoucherEdocs,
} from '@/lib/edocs'

const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—')

/**
 * A sales voucher's e-invoice (IRN) and e-way bill. Shown only when at least one of the two switches is on
 * (Admin → Integrations). In Demo mode the numbers are made up and labelled; in Live mode they come from the GST
 * portal through the GST Suvidha Provider.
 */
export function GstDocsPanel({ voucherId, token, onChanged }: { voucherId: number; token: string; onChanged?: () => void }) {
  const [data, setData] = useState<VoucherEdocs | null>(null)
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState<string | null>(null)
  const [issues, setIssues] = useState<string[]>([])
  const [vehicle, setVehicle] = useState('')
  const [distance, setDistance] = useState('0')
  const [transporterId, setTransporterId] = useState('')
  const [cancelReason, setCancelReason] = useState('2')
  const [newVehicle, setNewVehicle] = useState('')
  const [vehicleReason, setVehicleReason] = useState('1')
  const [fromPlace, setFromPlace] = useState('')

  useEffect(() => {
    let current = true
    getVoucherEdocs(token, voucherId).then(d => { if (current) setData(d) }).catch(() => { if (current) setData(null) })
    return () => { current = false }
  }, [token, voucherId, reload])

  if (!data || !(data.einvoice.switch_on || data.eway_bill.switch_on)) return null
  const r = data.record
  const demo = data.mode === 'demo'
  const irnActive = !!r?.irn && r.irn_status === 'active'
  const ewbActive = !!r?.eway_bill_no && r.ewb_status === 'active'

  const run = async (key: string, action: () => Promise<unknown>, success: string) => {
    setBusy(key)
    setIssues([])
    try {
      await action()
      toast.success(success)
      setReload(k => k + 1)
      onChanged?.()
    } catch (e) {
      if (e instanceof EdocError && e.problems.length) setIssues(e.problems)
      toast.error(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="mt-6 space-y-4 rounded-xl border border-border bg-muted/20 p-4 font-sans no-print" aria-label="e-Invoice and e-way bill">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-extrabold"><FileCheck2 className="h-4 w-4" /> e-Invoice & e-Way bill</h3>
        <span className={cn('rounded-full px-2 py-0.5 text-xs font-bold',
          demo ? 'bg-amber-500/15 text-amber-800 dark:text-amber-300' : 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300')}>
          {demo ? 'Demo mode: made-up numbers' : 'Live: GST portal'}
        </span>
      </div>

      {issues.length > 0 && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-900 dark:text-rose-200">
          <p className="mb-1 flex items-center gap-1.5 font-semibold"><AlertTriangle className="h-4 w-4" /> Fix these first:</p>
          <ul className="list-disc space-y-0.5 pl-5">{issues.map(p => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      {/* e-Invoice */}
      {data.einvoice.switch_on && (
        <div className="space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">e-Invoice (IRN)</h4>
          {r?.irn ? (
            <div className="space-y-2 text-sm">
              {r.demo && <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-900 dark:text-amber-200"><strong>DEMO – not valid.</strong> Made up by MyTally; nothing was registered.</p>}
              <p className="flex items-center gap-1.5">
                {r.irn_status === 'cancelled' ? <XCircle className="h-4 w-4 text-rose-600" /> : <ShieldCheck className="h-4 w-4 text-emerald-600" />}
                <span className="font-semibold">{r.irn_status === 'cancelled' ? 'Cancelled' : 'Registered'}</span>
                <span className="text-muted-foreground">· Ack {r.ack_no} · {when(r.ack_date)}</span>
              </p>
              <p className="break-all rounded-lg bg-background p-2 font-mono text-xs">{r.irn}</p>
              {data.can_cancel_irn && (
                <div className="flex flex-wrap items-center gap-2">
                  <select aria-label="Reason for cancelling the e-invoice" value={cancelReason} onChange={e => setCancelReason(e.target.value)} className={cn(field, 'w-auto')}>
                    {IRN_CANCEL_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button type="button" disabled={busy !== null} onClick={() => run('cancel-irn', () => cancelIrn(token, voucherId, cancelReason), 'e-Invoice cancelled')}
                    className="min-h-10 rounded-xl border border-rose-500/40 px-3 text-sm font-semibold text-rose-700 hover:bg-rose-500/10 disabled:opacity-60 dark:text-rose-300 cursor-pointer">
                    {busy === 'cancel-irn' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Cancel e-invoice'}
                  </button>
                  <span className="text-xs text-muted-foreground">Possible within 24 hours; cancel the e-way bill first.</span>
                </div>
              )}
            </div>
          ) : !data.is_b2b ? (
            <p className="text-sm text-muted-foreground">Not needed: the buyer has no GSTIN (e-invoices are for B2B sales).</p>
          ) : (
            <div className="space-y-2">
              {data.einvoice.problems.length > 0 && <Problems items={data.einvoice.problems} />}
              {!demo && !data.einvoice.keys_ready && <p className="text-xs text-muted-foreground">The e-invoice keys aren&apos;t set yet (Admin → Integrations).</p>}
              <button type="button" disabled={busy !== null || data.einvoice.problems.length > 0}
                onClick={() => run('irn', () => generateIrn(token, voucherId), demo ? 'Demo e-invoice created' : 'e-Invoice registered')}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-blue-600 px-4 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-50 cursor-pointer">
                {busy === 'irn' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                {demo ? 'Create demo e-invoice' : 'Generate e-invoice (IRN)'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* e-Way bill */}
      {data.eway_bill.switch_on && (
        <div className="space-y-2 border-t border-border pt-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">e-Way bill</h4>
          {r?.eway_bill_no && r.ewb_status ? (
            <div className="space-y-2 text-sm">
              {r.demo && <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-900 dark:text-amber-200"><strong>DEMO – not valid.</strong> Made up by MyTally.</p>}
              <p className="flex flex-wrap items-center gap-1.5">
                <Truck className="h-4 w-4" />
                <span className="font-mono font-semibold">{r.eway_bill_no}</span>
                <span className={r.ewb_status === 'cancelled' ? 'font-semibold text-rose-700 dark:text-rose-300' : 'text-muted-foreground'}>
                  {r.ewb_status === 'cancelled' ? 'Cancelled' : `· ${when(r.eway_bill_date)}${r.ewb_valid_till ? ` · valid till ${when(r.ewb_valid_till)}` : ''}`}
                </span>
              </p>
              {ewbActive && !demo && (
                <div className="grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto]">
                  <input aria-label="New vehicle number" placeholder="New vehicle no. (UP15AB1234)" value={newVehicle} onChange={e => setNewVehicle(e.target.value)} className={field} />
                  <select aria-label="Why the vehicle is changing" value={vehicleReason} onChange={e => setVehicleReason(e.target.value)} className={field}>
                    {VEHICLE_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <input aria-label="Where the goods are now" placeholder="Where the goods are now" value={fromPlace} onChange={e => setFromPlace(e.target.value)} className={field} />
                  <button type="button" disabled={busy !== null || !newVehicle.trim()}
                    onClick={() => run('vehicle', () => updateVehicle(token, voucherId, { vehicle_no: newVehicle, reason: vehicleReason, from_place: fromPlace }), 'Vehicle updated')}
                    className="min-h-10 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted disabled:opacity-50 cursor-pointer">
                    {busy === 'vehicle' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Update vehicle'}
                  </button>
                </div>
              )}
              {data.can_cancel_ewb && (
                <div className="flex flex-wrap items-center gap-2">
                  <select aria-label="Reason for cancelling the e-way bill" value={cancelReason} onChange={e => setCancelReason(e.target.value)} className={cn(field, 'w-auto')}>
                    {EWB_CANCEL_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button type="button" disabled={busy !== null} onClick={() => run('cancel-ewb', () => cancelEwaybill(token, voucherId, cancelReason), 'e-Way bill cancelled')}
                    className="min-h-10 rounded-xl border border-rose-500/40 px-3 text-sm font-semibold text-rose-700 hover:bg-rose-500/10 disabled:opacity-60 dark:text-rose-300 cursor-pointer">
                    {busy === 'cancel-ewb' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Cancel e-way bill'}
                  </button>
                  <span className="text-xs text-muted-foreground">Possible within 24 hours.</span>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {data.eway_bill.problems.length > 0 && <Problems items={data.eway_bill.problems} />}
              {data.invoice_total < 50000 && <p className="text-xs text-muted-foreground">Usually needed only for goods worth more than ₹50,000.</p>}
              {irnActive && <p className="text-xs text-muted-foreground">Made from the e-invoice above.</p>}
              <div className="grid gap-2 sm:grid-cols-3">
                <label className="text-sm"><span className="mb-1 block font-semibold">Vehicle number</span>
                  <input value={vehicle} onChange={e => setVehicle(e.target.value)} placeholder="UP15AB1234" className={field} /></label>
                <label className="text-sm"><span className="mb-1 block font-semibold">Distance (km)</span>
                  <input type="number" inputMode="numeric" min={0} max={4000} value={distance} onChange={e => setDistance(e.target.value)} className={field} />
                  <span className="text-xs text-muted-foreground">0 = worked out from the pincodes</span></label>
                <label className="text-sm"><span className="mb-1 block font-semibold">Transporter ID (optional)</span>
                  <input value={transporterId} onChange={e => setTransporterId(e.target.value)} placeholder="GSTIN or TRANSIN" className={field} /></label>
              </div>
              {!demo && !(irnActive ? data.einvoice.keys_ready : data.eway_bill.keys_ready) && (
                <p className="text-xs text-muted-foreground">The e-way bill keys aren&apos;t set yet (Admin → Integrations).</p>
              )}
              <button type="button" disabled={busy !== null || data.eway_bill.problems.length > 0}
                onClick={() => run('ewb', () => generateEwaybill(token, voucherId, {
                  vehicle_no: vehicle, distance_km: Math.max(0, Math.min(4000, Number(distance) || 0)), transporter_id: transporterId,
                }), demo ? 'Demo e-way bill created' : 'e-Way bill generated')}
                className="inline-flex min-h-10 items-center gap-1.5 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-50 cursor-pointer">
                {busy === 'ewb' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Truck className="h-4 w-4" />}
                {demo ? 'Create demo e-way bill' : 'Generate e-way bill'}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

function Problems({ items }: { items: string[] }) {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
      <p className="mb-1 font-semibold">Before this can be made:</p>
      <ul className="list-disc space-y-0.5 pl-5">{items.map(p => <li key={p}>{p}</li>)}</ul>
    </div>
  )
}
