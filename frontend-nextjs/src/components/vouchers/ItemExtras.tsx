'use client'

import { useEffect, useState } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'

/* Voucher entry, under each item line: batch, godown and alternate-unit details. Each part shows only when it applies
   (the item has batches; there's more than one godown; the item has an alternate unit), so nothing changes for
   businesses that don't use them. */

interface Batch { batch_id: number; batch_number: string; quantity_available: number | string; expiry_date: string | null }

// Batches per stock item, shared by every line and every time the form opens
const batchCache = new Map<string, Promise<Batch[]>>()

function loadBatches(token: string, stockItemId: string): Promise<Batch[]> {
  let pending = batchCache.get(stockItemId)
  if (!pending) {
    pending = fetch(`${API_BASE}/inventory/batches?stock_item_id=${stockItemId}`, { headers: authHeaders(token) })
      .then(r => (r.ok ? r.json() : [])).catch(() => [])
    batchCache.set(stockItemId, pending)
  }
  return pending
}

const select = 'h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs dark:border-slate-700 dark:bg-slate-900'

export function ItemExtras({ token, item, entry, godowns, units, onChange }: {
  token: string | null
  item: { stock_item_id: number; unit_id?: number | null; alt_unit_id?: number | null; alt_unit_conversion?: number | string | null } | undefined
  entry: { stock_item_id: string; godown_id?: string; batch_id?: string; quantity?: string }
  godowns: { godown_id: number; name: string }[]
  units: { unit_id: number; symbol?: string; name?: string }[]
  onChange: (patch: { godown_id?: string; batch_id?: string }) => void
}) {
  const [batches, setBatches] = useState<{ item: string; list: Batch[] }>({ item: '', list: [] })

  useEffect(() => {
    if (!token || !entry.stock_item_id) return
    let current = true
    loadBatches(token, entry.stock_item_id).then(list => { if (current) setBatches({ item: entry.stock_item_id, list }) })
    return () => { current = false }
  }, [token, entry.stock_item_id])

  if (!item || !entry.stock_item_id) return null
  const list = batches.item === entry.stock_item_id ? batches.list : []
  const unitName = (id?: number | null) => units.find(u => u.unit_id === id)?.symbol || units.find(u => u.unit_id === id)?.name || ''
  const conversion = Number(item.alt_unit_conversion || 0)
  const qty = Number(entry.quantity || 0)
  const showAlt = !!item.alt_unit_id && conversion > 0
  if (list.length === 0 && godowns.length <= 1 && !showAlt) return null

  return (
    <div className="flex flex-wrap items-center gap-2 pt-1.5 text-xs text-slate-600 dark:text-slate-300">
      {list.length > 0 && (
        <label className="flex items-center gap-1.5">Batch
          <select className={select} value={entry.batch_id || ''} onChange={e => onChange({ batch_id: e.target.value })} aria-label="Batch">
            <option value="">Choose a batch</option>
            {list.map(b => (
              <option key={b.batch_id} value={b.batch_id}>
                {b.batch_number} · {Number(b.quantity_available).toLocaleString('en-IN')} left{b.expiry_date ? ` · exp ${b.expiry_date}` : ''}
              </option>
            ))}
          </select>
        </label>
      )}
      {godowns.length > 1 && (
        <label className="flex items-center gap-1.5">Godown
          <select className={select} value={entry.godown_id || ''} onChange={e => onChange({ godown_id: e.target.value })} aria-label="Godown">
            {/* Empty means Tally's default "Main Location"; don't list it twice when a godown has that name */}
            {!godowns.some(g => g.name.trim().toLowerCase() === 'main location') && <option value="">Main Location</option>}
            {godowns.some(g => g.name.trim().toLowerCase() === 'main location') && <option value="">Choose a godown</option>}
            {godowns.map(g => <option key={g.godown_id} value={g.godown_id}>{g.name}</option>)}
          </select>
        </label>
      )}
      {showAlt && (
        <span>
          = {(qty / conversion).toLocaleString('en-IN', { maximumFractionDigits: 3 })} {unitName(item.alt_unit_id)}
          <span className="text-slate-400"> (1 {unitName(item.alt_unit_id)} = {conversion} {unitName(item.unit_id)})</span>
        </span>
      )}
    </div>
  )
}
