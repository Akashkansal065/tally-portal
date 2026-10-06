'use client'

import { useEffect, useState } from 'react'
import { ClipboardCheck, Loader2, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { API_BASE, authHeaders } from '@/lib/utils'
import { createRule, getRules, removeRule, type ApprovalRule } from '@/lib/approvals'

const field = 'h-10 w-full rounded-xl border border-border bg-background px-3 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

/** Admin → Approvals: which vouchers must be approved, and by whom, before they go to Tally. */
export function ApprovalRulesPanel({ token }: { token: string | null }) {
  const [rules, setRules] = useState<ApprovalRule[] | null>(null)
  const [types, setTypes] = useState<{ voucher_type_id: number; name: string }[]>([])
  const [roles, setRoles] = useState<{ role_id: number; name: string }[]>([])
  const [reload, setReload] = useState(0)
  const [typeId, setTypeId] = useState('')
  const [minAmount, setMinAmount] = useState('0')
  const [roleId, setRoleId] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!token) return
    let current = true
    Promise.all([
      getRules(token),
      fetch(`${API_BASE}/vouchers/types`, { headers: authHeaders(token) }).then(r => (r.ok ? r.json() : [])),
      fetch(`${API_BASE}/admin/roles`, { headers: authHeaders(token) }).then(r => (r.ok ? r.json() : [])),
    ]).then(([r, t, ro]) => {
      if (!current) return
      setRules(r)
      setTypes(Array.isArray(t) ? t : [])
      setRoles(Array.isArray(ro) ? ro : [])
    }).catch(e => toast.error(e instanceof Error ? e.message : 'Could not load approval rules'))
    return () => { current = false }
  }, [token, reload])

  if (!token) return null
  const add = async () => {
    setSaving(true)
    try {
      await createRule(token, { voucher_type_id: typeId ? Number(typeId) : null, min_amount: Number(minAmount) || 0, approver_role_id: Number(roleId) })
      toast.success('Rule added')
      setReload(k => k + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not add the rule')
    } finally {
      setSaving(false)
    }
  }
  const remove = async (id: number) => {
    try {
      await removeRule(token, id)
      setReload(k => k + 1)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not remove the rule')
    }
  }

  return (
    <div className="space-y-4 font-sans">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <h2 className="flex items-center gap-1.5 text-sm font-extrabold uppercase tracking-wider"><ClipboardCheck className="h-4 w-4" /> Voucher approval</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Vouchers entered in MyTally that match a rule wait for someone in the approving role before they go to Tally. Admins, and people in the
          approving role, are never held back. The approvers are notified, and the person who entered it hears the decision.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h3 className="mb-2 text-sm font-bold">Rules</h3>
        {rules === null ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : rules.length === 0 ? (
          <p className="text-sm text-muted-foreground">No rules: every voucher goes straight to Tally.</p>
        ) : (
          <ul className="divide-y divide-border">
            {rules.map(r => (
              <li key={r.rule_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>
                  <span className="font-semibold">{r.voucher_type}</span>
                  {r.min_amount > 0 ? ` of ₹${r.min_amount.toLocaleString('en-IN')} or more` : ', any amount'}
                  <span className="text-muted-foreground"> → approved by {r.approver_role}</span>
                </span>
                <button type="button" onClick={() => remove(r.rule_id)} aria-label={`Remove the rule for ${r.voucher_type}`}
                  className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-xl text-rose-700 hover:bg-rose-500/10 dark:text-rose-400 cursor-pointer">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-border bg-card p-5">
        <h3 className="mb-3 text-sm font-bold">Add a rule</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm"><span className="mb-1 block font-semibold">Voucher type</span>
            <select value={typeId} onChange={e => setTypeId(e.target.value)} className={field}>
              <option value="">All voucher types</option>
              {types.map(t => <option key={t.voucher_type_id} value={t.voucher_type_id}>{t.name}</option>)}
            </select></label>
          <label className="text-sm"><span className="mb-1 block font-semibold">Amount at or over (₹)</span>
            <input type="number" inputMode="decimal" min={0} value={minAmount} onChange={e => setMinAmount(e.target.value)} className={field} />
            <span className="text-xs text-muted-foreground">0 = every voucher</span></label>
          <label className="text-sm"><span className="mb-1 block font-semibold">Approved by</span>
            <select value={roleId} onChange={e => setRoleId(e.target.value)} className={field}>
              <option value="">Choose a role</option>
              {roles.map(r => <option key={r.role_id} value={r.role_id}>{r.name}</option>)}
            </select></label>
        </div>
        <button type="button" onClick={add} disabled={saving || !roleId}
          className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Add rule
        </button>
      </section>
    </div>
  )
}
