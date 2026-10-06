'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Loader2, Share2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn, formatDate } from '@/lib/utils'
import { shareFile } from '@/lib/capacitor-pdf'

const money = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const drcr = (n: number) => `${money(Math.abs(n))} ${n < 0 ? 'Cr' : 'Dr'}`

type View = 'cash' | 'centres' | 'godown' | 'batch'
const VIEWS: { id: View; label: string }[] = [
  { id: 'cash', label: 'Cash & bank book' },
  { id: 'centres', label: 'Cost centres' },
  { id: 'godown', label: 'Stock by godown' },
  { id: 'batch', label: 'Stock by batch' },
]

async function load<T>(token: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE}/reports/${path}`, { headers: authHeaders(token) })
  if (!res.ok) {
    // FastAPI validation errors carry a list of {msg} objects, other errors a plain string
    const detail = (await res.json().catch(() => ({}))).detail
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) && detail[0]?.msg ? detail[0].msg : 'Could not load the report')
  }
  return res.json()
}

/** CSV with proper quoting, shared (phone) or downloaded (computer). */
async function shareCsv(name: string, header: string[], rows: (string | number)[][]) {
  const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  const csv = [header, ...rows].map(r => r.map(cell).join(',')).join('\n')
  const result = await shareFile(new Blob([csv], { type: 'text/csv' }), `${name}.csv`, name)
  if (result === 'downloaded') toast.success('Downloaded')
}

/** Reports → Books: cash & bank book, cost centres, stock by godown and by batch, for the page's period. */
export function BooksReports({ from, to }: { from: string; to: string }) {
  const { token } = useAuth()
  const [view, setView] = useState<View>('cash')
  const [data, setData] = useState<{ key: string; body: any } | null>(null) // eslint-disable-line @typescript-eslint/no-explicit-any
  const [error, setError] = useState<string | null>(null)
  const path = view === 'cash' ? 'cash-bank-book' : view === 'centres' ? 'cost-centres' : view === 'godown' ? 'stock-by-godown' : 'stock-by-batch'
  // Empty dates ("All time") are left out: the API then covers the company's whole history, and rejects `from=`
  const query = new URLSearchParams(Object.entries({ from, to }).filter(([, v]) => v)).toString()
  const key = query ? `${path}?${query}` : path

  useEffect(() => {
    if (!token) return
    let current = true
    load(token, key).then(body => { if (current) { setData({ key, body }); setError(null) } })
      .catch(e => { if (current) setError(e instanceof Error ? e.message : 'Could not load the report') })
    return () => { current = false }
  }, [token, key])

  const body = data?.key === key ? data.body : null
  // The period the API actually used, so the caption is right even when no dates were picked
  const periodFrom = body?.from || from
  const periodTo = body?.to || to
  const period = periodFrom && periodTo ? `${formatDate(periodFrom)} to ${formatDate(periodTo)}` : 'all time'
  const card = 'rounded-2xl border border-border bg-card'

  const share = () => {
    if (!body) return
    if (view === 'cash') {
      shareCsv(`Cash and bank book ${periodFrom} to ${periodTo}`, ['Ledger', 'Kind', 'Opening', 'Money in', 'Money out', 'Closing'],
        body.ledgers.map((r: any) => [r.name, r.kind, r.opening, r.money_in, r.money_out, r.closing])) // eslint-disable-line @typescript-eslint/no-explicit-any
    } else if (view === 'centres') {
      shareCsv(`Cost centres ${periodFrom} to ${periodTo}`, ['Cost centre', 'Debit', 'Credit', 'Net', 'Vouchers'],
        body.rows.map((r: any) => [r.name, r.debit, r.credit, r.net, r.vouchers])) // eslint-disable-line @typescript-eslint/no-explicit-any
    } else if (view === 'godown') {
      shareCsv(`Stock by godown ${periodFrom} to ${periodTo}`, ['Godown', 'Item', 'Unit', 'In', 'Out', 'Net'],
        body.godowns.flatMap((g: any) => g.items.map((i: any) => [g.godown, i.item, i.unit, i.qty_in, i.qty_out, i.net]))) // eslint-disable-line @typescript-eslint/no-explicit-any
    } else {
      shareCsv('Stock by batch', ['Item', 'Batch', 'Available', 'Unit', 'Expires'],
        body.batches.map((b: any) => [b.item, b.batch, b.available, b.unit, b.expires || ''])) // eslint-disable-line @typescript-eslint/no-explicit-any
    }
  }

  return (
    <section aria-labelledby="books-title" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="books-title" className="text-lg font-extrabold">Books & stock</h2>
          <p className="text-sm text-muted-foreground">{view === 'batch' ? 'Batches with stock left, soonest expiry first.' : `For ${period}. Cancelled and optional vouchers are left out.`}</p>
        </div>
        <button type="button" onClick={share} disabled={!body}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted disabled:opacity-50 cursor-pointer">
          <Share2 className="h-4 w-4" /> Share CSV
        </button>
      </div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Report">
        {VIEWS.map(v => (
          <button key={v.id} type="button" role="tab" aria-selected={view === v.id} onClick={() => setView(v.id)}
            className={cn('min-h-10 rounded-full border px-3.5 text-sm font-semibold cursor-pointer',
              view === v.id ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted')}>
            {v.label}
          </button>
        ))}
      </div>

      {error ? <p className={cn(card, 'p-6 text-center text-sm text-muted-foreground')}>{error}</p>
        : !body ? <div className={cn(card, 'flex justify-center p-8')}><Loader2 className="h-5 w-5 animate-spin text-primary" /></div>
        : view === 'cash' ? (
          body.ledgers.length === 0 ? <p className={cn(card, 'p-6 text-center text-sm text-muted-foreground')}>No cash or bank ledgers in Tally.</p> : (
            <div className={cn(card, 'overflow-x-auto')}>
              <table className="report-table w-full text-sm">
                <thead><tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="p-3">Ledger</th><th className="p-3 text-right">Opening</th><th className="p-3 text-right">Money in</th>
                  <th className="p-3 text-right">Money out</th><th className="p-3 text-right">Closing</th></tr></thead>
                <tbody>
                  {body.ledgers.map((r: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
                    <tr key={r.ledger_id} className="border-b border-border/60">
                      <td className="p-3"><Link href={`/ledgers/${r.ledger_id}`} className="font-semibold hover:underline">{r.name}</Link>
                        <span className="block text-xs text-muted-foreground">{r.kind} · {r.entries} entries</span></td>
                      <td className="p-3 text-right tabular-nums">{drcr(r.opening)}</td>
                      <td className="p-3 text-right tabular-nums text-emerald-700 dark:text-emerald-400">{money(r.money_in)}</td>
                      <td className="p-3 text-right tabular-nums text-rose-700 dark:text-rose-400">{money(r.money_out)}</td>
                      <td className="p-3 text-right font-semibold tabular-nums">{drcr(r.closing)}</td>
                    </tr>
                  ))}
                  <tr className="font-bold"><td className="p-3">Total</td><td className="p-3 text-right tabular-nums">{drcr(body.totals.opening)}</td>
                    <td className="p-3 text-right tabular-nums">{money(body.totals.money_in)}</td><td className="p-3 text-right tabular-nums">{money(body.totals.money_out)}</td>
                    <td className="p-3 text-right tabular-nums">{drcr(body.totals.closing)}</td></tr>
                </tbody>
              </table>
            </div>
          )
        ) : view === 'centres' ? (
          body.rows.length === 0 ? (
            <p className={cn(card, 'p-6 text-center text-sm text-muted-foreground')}>
              {body.cost_centres_in_tally === 0 ? 'No cost centres are set up in Tally.' : 'No cost-centre entries in this period.'}
            </p>
          ) : (
            <div className={cn(card, 'overflow-x-auto')}>
              <table className="report-table w-full text-sm">
                <thead><tr className="border-b border-border text-left text-xs text-muted-foreground"><th className="p-3">Cost centre</th>
                  <th className="p-3 text-right">Debit</th><th className="p-3 text-right">Credit</th><th className="p-3 text-right">Net</th></tr></thead>
                <tbody>{body.rows.map((r: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
                  <tr key={r.cost_centre_id} className="border-b border-border/60"><td className="p-3 font-semibold">{r.name}<span className="block text-xs font-normal text-muted-foreground">{r.vouchers} vouchers</span></td>
                    <td className="p-3 text-right tabular-nums">{money(r.debit)}</td><td className="p-3 text-right tabular-nums">{money(r.credit)}</td>
                    <td className="p-3 text-right font-semibold tabular-nums">{drcr(r.net)}</td></tr>))}</tbody>
              </table>
            </div>
          )
        ) : view === 'godown' ? (
          body.godowns.length === 0 ? <p className={cn(card, 'p-6 text-center text-sm text-muted-foreground')}>No stock moved in this period.</p> : (
            <div className="space-y-3">
              {body.godowns_in_tally <= 1 && <p className="text-xs text-muted-foreground">Tally has {body.godowns_in_tally || 'no'} godown{body.godowns_in_tally === 1 ? '' : 's'} set up, so this matches the stock summary.</p>}
              {body.godowns.map((g: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
                <div key={g.godown} className={cn(card, 'overflow-x-auto')}>
                  <p className="border-b border-border p-3 text-sm font-bold">{g.godown} <span className="font-normal text-muted-foreground">· in {g.qty_in.toLocaleString('en-IN')} · out {g.qty_out.toLocaleString('en-IN')}</span></p>
                  <table className="report-table w-full text-sm"><tbody>{g.items.map((i: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
                    <tr key={i.stock_item_id} className="border-b border-border/60"><td className="p-3">{i.item}</td>
                      <td className="p-3 text-right tabular-nums">+{i.qty_in} / −{i.qty_out} {i.unit}</td></tr>))}</tbody></table>
                </div>
              ))}
            </div>
          )
        ) : (
          body.batches.length === 0 ? <p className={cn(card, 'p-6 text-center text-sm text-muted-foreground')}>No batches with stock (batches aren&apos;t used in Tally).</p> : (
            <div className={cn(card, 'overflow-x-auto')}>
              <table className="report-table w-full text-sm">
                <thead><tr className="border-b border-border text-left text-xs text-muted-foreground"><th className="p-3">Item · batch</th>
                  <th className="p-3 text-right">Available</th><th className="p-3 text-right">Expires</th></tr></thead>
                <tbody>{body.batches.map((b: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
                  <tr key={b.batch_id} className="border-b border-border/60"><td className="p-3"><span className="font-semibold">{b.item}</span><span className="block text-xs text-muted-foreground">Batch {b.batch}</span></td>
                    <td className="p-3 text-right tabular-nums">{b.available} {b.unit}</td>
                    <td className={cn('p-3 text-right', b.days_to_expiry !== null && b.days_to_expiry < 30 && 'font-semibold text-rose-700 dark:text-rose-400')}>
                      {b.expires ? `${b.expires}${b.days_to_expiry !== null ? ` (${b.days_to_expiry < 0 ? 'expired' : `${b.days_to_expiry}d`})` : ''}` : '—'}</td></tr>))}</tbody>
              </table>
            </div>
          )
        )}
    </section>
  )
}
