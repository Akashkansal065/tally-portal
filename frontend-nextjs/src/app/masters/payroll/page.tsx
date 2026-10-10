'use client'

import { confirmInCompany } from '@/lib/current-company'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Edit2, Trash2, Info, X, Loader2, Users, Wallet, CalendarCheck } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'

type Tab = 'employees' | 'pay-heads' | 'attendance-types'

const ATTENDANCE_KINDS = ['Attendance / Leave with Pay', 'Leave without Pay', 'Production', 'User Defined Calendar Type']
const PAY_HEAD_TYPES = ['Earnings for Employees', 'Deductions from Employees', "Employees' Statutory Deductions", "Employer's Statutory Contributions",
  "Employer's Other Charges", 'Bonus', 'Gratuity', 'Loans and Advances', 'Reimbursements to Employees']
const SIMPLE_CALCULATIONS = ['As User Defined Value', 'Flat Rate']

const inputCls = 'w-full h-10 px-3 bg-background border border-border rounded-lg text-sm'
const labelCls = 'block text-xs font-semibold text-muted-foreground mb-1'

// What Tally said about the change that was just saved
function reportOutcome(saved: any, what: string) {
  if (saved?.tally_status === 'SUCCESS') toast.success(`${what} saved and sent to Tally`)
  else if (saved?.tally_status) toast.warning(`${what} saved here. Tally could not be reached, so it will be sent when Tally is back.`)
  else toast.success(`${what} saved`)
}

export default function PayrollMastersPage() {
  const { user, token, can } = useAuth()
  const router = useRouter()
  const [tab, setTab] = useState<Tab>('employees')
  const [employees, setEmployees] = useState<any[]>([])
  const [payHeads, setPayHeads] = useState<any[]>([])
  const [attendanceTypes, setAttendanceTypes] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [groups, setGroups] = useState<any[]>([])
  const [units, setUnits] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<{ tab: Tab; row: any | null; asGroup?: boolean } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const get = async (path: string) => {
      const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders(token) })
      const data = res.ok ? await res.json() : []
      return Array.isArray(data) ? data : []
    }
    try {
      const [e, p, a, c, g, u] = await Promise.all([
        get('/payroll-masters/employees'), get('/payroll-masters/pay-heads'), get('/payroll-masters/attendance-types'),
        get('/masters/cost-categories'), get('/ledgers/groups'), get('/inventory/uoms'),
      ])
      setEmployees(e); setPayHeads(p); setAttendanceTypes(a); setCategories(c); setGroups(g); setUnits(u)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!can('payroll', 'read')) { router.replace('/'); return }
    load()
  }, [user, can, router, load])

  const remove = async (path: string, name: string) => {
    if (!confirmInCompany(`Delete ${name}? It will be deleted in Tally as well.`)) return
    const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', headers: authHeaders(token) })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) { toast.error(data.detail || 'Could not delete'); return }
    toast.success(data.tally_status === 'SUCCESS' || data.tally_status === 'ALREADY_ABSENT' ? `${name} deleted here and in Tally` : `${name} deleted here. Tally will be told when it is back.`)
    load()
  }

  const tabs: { id: Tab; label: string; icon: any; count: number }[] = [
    { id: 'employees', label: 'Employees', icon: Users, count: employees.length },
    { id: 'pay-heads', label: 'Pay heads', icon: Wallet, count: payHeads.length },
    { id: 'attendance-types', label: 'Attendance types', icon: CalendarCheck, count: attendanceTypes.length },
  ]
  const canCreate = can('payroll', 'create'), canUpdate = can('payroll', 'update'), canDelete = can('payroll', 'delete')

  const actions = (onEdit: () => void, onDelete: () => void) => (
    <div className="flex items-center justify-end gap-2">
      {canUpdate && <button onClick={onEdit} className="p-1.5 bg-primary/10 text-primary hover:bg-primary/20 rounded-md" title="Edit"><Edit2 className="w-4 h-4" /></button>}
      {canDelete && <button onClick={onDelete} className="p-1.5 bg-destructive/10 text-destructive hover:bg-destructive/20 rounded-md" title="Delete"><Trash2 className="w-4 h-4" /></button>}
    </div>
  )

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="max-w-6xl mx-auto space-y-5">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Payroll masters</h1>
            <p className="text-sm text-muted-foreground mt-1">Employees, pay heads and attendance types, kept in step with Tally.</p>
          </div>
          <div className="bg-blue-50/50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/50 rounded-lg p-3 text-sm text-blue-800 dark:text-blue-200 flex gap-3">
            <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
            <p>
              Anything saved here is sent to Tally straight away; if Tally refuses it, it is not saved here either.
              Employee categories are <a className="underline font-semibold" href="/masters/cost-categories">cost categories</a> and
              work units (hours, pieces) are ordinary <a className="underline font-semibold" href="/masters/units">units</a>, so those are managed on their own screens.
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex gap-1 bg-muted/50 p-1 rounded-lg overflow-x-auto max-w-full">
              {tabs.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-semibold whitespace-nowrap transition-colors ${tab === t.id ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                  <t.icon className="w-4 h-4" />{t.label}<span className="text-xs font-normal text-muted-foreground">{t.count}</span>
                </button>
              ))}
            </div>
            {canCreate && (
              <div className="flex gap-2">
                {tab === 'employees' && (
                  <button onClick={() => setEditing({ tab, row: null, asGroup: true })} className="px-3 py-2 border border-border hover:bg-muted rounded-lg text-sm font-semibold flex items-center gap-2">
                    <Plus className="w-4 h-4" />Group
                  </button>
                )}
                <button onClick={() => setEditing({ tab, row: null })} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm text-sm font-semibold flex items-center gap-2">
                  <Plus className="w-4 h-4" />{tab === 'employees' ? 'Employee' : tab === 'pay-heads' ? 'Pay head' : 'Attendance type'}
                </button>
              </div>
            )}
          </div>

          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground animate-pulse">Loading...</div>
            ) : tab === 'employees' ? (
              employees.length === 0 ? <div className="p-8 text-center text-muted-foreground">No employees yet.</div> : (
                <div className="overflow-x-auto"><table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-muted-foreground font-semibold border-b border-border"><tr>
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Group</th><th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Designation</th><th className="px-4 py-3">Joined</th><th className="px-4 py-3">Salary details</th><th className="px-4 py-3" />
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {employees.map(e => (
                      <tr key={e.cost_centre_id} className="hover:bg-muted/30">
                        <td className="px-4 py-3">
                          <div className="font-semibold">{e.name}</div>
                          <div className="text-xs text-muted-foreground">{e.is_employee_group ? 'Employee group' : e.employee_number ? `No. ${e.employee_number}` : ''}</div>
                        </td>
                        <td className="px-4 py-3">{e.parent_name || '-'}</td>
                        <td className="px-4 py-3">{e.category_name}</td>
                        <td className="px-4 py-3">{e.designation || '-'}</td>
                        <td className="px-4 py-3 whitespace-nowrap">{e.date_of_join || '-'}</td>
                        <td className="px-4 py-3 text-xs">{(e.salary_rates || []).map((r: any) => `${r.pay_head_name}${r.rate != null ? ` ₹${Number(r.rate).toLocaleString('en-IN')}` : ''}`).join(', ') || '-'}</td>
                        <td className="px-4 py-3">{actions(() => setEditing({ tab, row: e }), () => remove(`/payroll-masters/employees/${e.cost_centre_id}`, e.name))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )
            ) : tab === 'pay-heads' ? (
              payHeads.length === 0 ? <div className="p-8 text-center text-muted-foreground">No pay heads yet.</div> : (
                <div className="overflow-x-auto"><table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-muted-foreground font-semibold border-b border-border"><tr>
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Under</th><th className="px-4 py-3">Calculation</th><th className="px-4 py-3" />
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {payHeads.map(p => (
                      <tr key={p.pay_head_id} className="hover:bg-muted/30">
                        <td className="px-4 py-3 font-semibold">{p.name}</td>
                        <td className="px-4 py-3">{p.pay_head_type}</td>
                        <td className="px-4 py-3">{p.group_name || '-'}</td>
                        <td className="px-4 py-3">{p.calculation_type || <span className="text-muted-foreground">Set in Tally</span>}</td>
                        <td className="px-4 py-3">{actions(() => setEditing({ tab, row: p }), () => remove(`/payroll-masters/pay-heads/${p.pay_head_id}`, p.name))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )
            ) : (
              attendanceTypes.length === 0 ? <div className="p-8 text-center text-muted-foreground">No attendance types yet.</div> : (
                <div className="overflow-x-auto"><table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-muted-foreground font-semibold border-b border-border"><tr>
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Measured in</th><th className="px-4 py-3" />
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {attendanceTypes.map(a => (
                      <tr key={a.attendance_type_id} className="hover:bg-muted/30">
                        <td className="px-4 py-3 font-semibold">{a.name}</td>
                        <td className="px-4 py-3">{a.type_of_attendance}</td>
                        <td className="px-4 py-3">{a.type_of_attendance === 'Production' ? (a.unit_name || '-') : (a.period || 'Days')}</td>
                        <td className="px-4 py-3">{actions(() => setEditing({ tab, row: a }), () => remove(`/payroll-masters/attendance-types/${a.attendance_type_id}`, a.name))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              )
            )}
          </div>
        </div>
      </div>

      {editing && (
        <MasterForm
          editing={editing} token={token} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }}
          categories={categories} groups={groups} units={units} payHeads={payHeads}
          employeeGroups={employees.filter(e => e.is_employee_group)}
        />
      )}
    </div>
  )
}

function MasterForm({ editing, token, onClose, onSaved, categories, groups, units, payHeads, employeeGroups }: any) {
  const { tab, row } = editing as { tab: Tab; row: any | null }
  const isGroup = tab === 'employees' && (row ? row.is_employee_group : Boolean(editing.asGroup))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState<any>(() => {
    if (tab === 'attendance-types') return { name: row?.name || '', type_of_attendance: row?.type_of_attendance || ATTENDANCE_KINDS[0], period: row?.period || 'Days', unit_name: row?.unit_name || '' }
    if (tab === 'pay-heads') return { name: row?.name || '', pay_head_type: row ? (PAY_HEAD_TYPES.find(t => t.toLowerCase() === String(row.pay_head_type).toLowerCase()) || row.pay_head_type) : PAY_HEAD_TYPES[0],
      under_group_id: row?.under_group_id ? String(row.under_group_id) : '', payslip_name: row?.payslip_name || '', calculation_type: row?.calculation_type || SIMPLE_CALCULATIONS[0] }
    return { name: row?.name || '', category_id: row?.category_id ? String(row.category_id) : (categories[0] ? String(categories[0].category_id) : ''),
      parent_id: row?.parent_id ? String(row.parent_id) : '', employee_number: row?.employee_number || '', date_of_join: row?.date_of_join || '',
      designation: row?.designation || '', gender: row?.gender || '',
      salary_rates: (row?.salary_rates || []).map((r: any) => ({ effective_from: r.effective_from, pay_head_name: r.pay_head_name, rate: r.rate ?? '' })) }
  })
  const set = (patch: any) => setForm((f: any) => ({ ...f, ...patch }))
  const calculationLocked = tab === 'pay-heads' && row && !SIMPLE_CALCULATIONS.includes(row.calculation_type)
  const sortedGroups = useMemo(() => [...groups].sort((a: any, b: any) => (a.name || '').localeCompare(b.name || '')), [groups])
  const title = `${row ? 'Edit' : 'New'} ${tab === 'attendance-types' ? 'attendance type' : tab === 'pay-heads' ? 'pay head' : isGroup ? 'employee group' : 'employee'}`

  const save = async () => {
    setError('')
    if (!form.name.trim()) { setError('Enter a name.'); return }
    let path = `/payroll-masters/${tab}`, body: any
    if (tab === 'attendance-types') {
      if (form.type_of_attendance === 'Production' && !form.unit_name) { setError('Choose the unit this is measured in.'); return }
      body = { name: form.name, type_of_attendance: form.type_of_attendance, period: form.period, unit_name: form.unit_name || null }
      if (row) path += `/${row.attendance_type_id}`
    } else if (tab === 'pay-heads') {
      if (!form.under_group_id) { setError('Choose the account group this pay head comes under.'); return }
      body = { name: form.name, pay_head_type: form.pay_head_type, under_group_id: parseInt(form.under_group_id), payslip_name: form.payslip_name || null, calculation_type: form.calculation_type }
      if (row) path += `/${row.pay_head_id}`
    } else {
      if (!form.category_id) { setError('Choose an employee category.'); return }
      const rates = isGroup ? [] : form.salary_rates.filter((r: any) => r.pay_head_name)
      if (rates.some((r: any) => !r.effective_from)) { setError('Each salary line needs the date it applies from.'); return }
      body = { name: form.name, category_id: parseInt(form.category_id), parent_id: form.parent_id ? parseInt(form.parent_id) : null, is_employee_group: isGroup,
        employee_number: form.employee_number || null, date_of_join: form.date_of_join || null, designation: form.designation || null, gender: form.gender || null,
        salary_rates: rates.map((r: any) => ({ effective_from: r.effective_from, pay_head_name: r.pay_head_name, rate: r.rate === '' ? null : Number(r.rate) })) }
      if (row) path += `/${row.cost_centre_id}`
    }
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}${path}`, { method: row ? 'PUT' : 'POST', headers: { ...authHeaders(token), 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) { setError(typeof data.detail === 'string' ? data.detail : 'Could not save.'); return }
      reportOutcome(data, form.name)
      onSaved()
    } catch (e: any) {
      setError(e.message || 'Could not save.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 p-0 sm:p-4" onClick={onClose}>
      <div className="w-full sm:max-w-xl max-h-[92vh] flex flex-col bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-lg font-bold capitalize">{title}</h2>
          <button onClick={onClose} className="p-1.5 text-muted-foreground hover:text-foreground rounded-md"><X className="w-5 h-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-600 rounded-lg text-sm font-medium">{error}</div>}
          <div>
            <label className={labelCls}>Name</label>
            <input className={inputCls} value={form.name} onChange={e => set({ name: e.target.value })} autoFocus />
          </div>

          {tab === 'attendance-types' && (<>
            <div>
              <label className={labelCls}>Type</label>
              <select className={inputCls} value={form.type_of_attendance} onChange={e => set({ type_of_attendance: e.target.value })}>
                {ATTENDANCE_KINDS.map(k => <option key={k}>{k}</option>)}
              </select>
            </div>
            {form.type_of_attendance === 'Production' ? (
              <div>
                <label className={labelCls}>Unit (work)</label>
                <select className={inputCls} value={form.unit_name} onChange={e => set({ unit_name: e.target.value })}>
                  <option value="">Select unit...</option>
                  {Array.from(new Set([...units.filter((u: any) => u.is_simple_unit !== false).map((u: any) => u.symbol || u.name), form.unit_name].filter(Boolean))).map((n: any) => <option key={n}>{n}</option>)}
                </select>
              </div>
            ) : <p className="text-xs text-muted-foreground">Counted in days.</p>}
          </>)}

          {tab === 'pay-heads' && (<>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Pay head type</label>
                <select className={inputCls} value={form.pay_head_type} onChange={e => set({ pay_head_type: e.target.value })}>
                  {Array.from(new Set([...PAY_HEAD_TYPES, form.pay_head_type])).map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Under (account group)</label>
                <select className={inputCls} value={form.under_group_id} onChange={e => set({ under_group_id: e.target.value })}>
                  <option value="">Select group...</option>
                  {sortedGroups.map((g: any) => <option key={g.group_id} value={g.group_id}>{g.name}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Name on payslip</label>
                <input className={inputCls} value={form.payslip_name} placeholder={form.name} onChange={e => set({ payslip_name: e.target.value })} />
              </div>
              <div>
                <label className={labelCls}>Calculation</label>
                {calculationLocked ? (
                  <div className="h-10 px-3 flex items-center border border-border rounded-lg text-sm bg-muted/40 text-muted-foreground">{row.calculation_type || 'Set in Tally'}</div>
                ) : (
                  <select className={inputCls} value={form.calculation_type} onChange={e => set({ calculation_type: e.target.value })}>
                    {SIMPLE_CALCULATIONS.map(c => <option key={c}>{c}</option>)}
                  </select>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              {calculationLocked ? 'This pay head\'s calculation is set up in Tally and is left as it is.' : 'Pay heads calculated on attendance, production or a formula are set up in Tally.'}
            </p>
          </>)}

          {tab === 'employees' && (<>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>Employee category</label>
                <select className={inputCls} value={form.category_id} onChange={e => set({ category_id: e.target.value })}>
                  {categories.map((c: any) => <option key={c.category_id} value={c.category_id}>{c.name}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Under group</label>
                <select className={inputCls} value={form.parent_id} onChange={e => set({ parent_id: e.target.value })}>
                  <option value="">Primary (no group)</option>
                  {employeeGroups.filter((g: any) => g.cost_centre_id !== row?.cost_centre_id).map((g: any) => <option key={g.cost_centre_id} value={g.cost_centre_id}>{g.name}</option>)}
                </select>
              </div>
              {!isGroup && (<>
                <div><label className={labelCls}>Employee number</label><input className={inputCls} value={form.employee_number} onChange={e => set({ employee_number: e.target.value })} /></div>
                <div><label className={labelCls}>Date of joining</label><input type="date" className={inputCls} value={form.date_of_join} onChange={e => set({ date_of_join: e.target.value })} /></div>
                <div><label className={labelCls}>Designation</label><input className={inputCls} value={form.designation} onChange={e => set({ designation: e.target.value })} /></div>
                <div>
                  <label className={labelCls}>Gender</label>
                  <select className={inputCls} value={form.gender} onChange={e => set({ gender: e.target.value })}>
                    <option value="">Not set</option><option>Male</option><option>Female</option>
                  </select>
                </div>
              </>)}
            </div>
            {!isGroup && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-bold">Salary details</label>
                  <button type="button" onClick={() => set({ salary_rates: [...form.salary_rates, { effective_from: form.salary_rates[0]?.effective_from || form.date_of_join || '', pay_head_name: '', rate: '' }] })}
                    className="text-xs font-semibold text-emerald-600 hover:underline flex items-center gap-1"><Plus className="w-3.5 h-3.5" />Add pay head</button>
                </div>
                {form.salary_rates.length === 0 && <p className="text-xs text-muted-foreground">No salary lines. Add the pay heads this employee is paid, with a rate where one applies.</p>}
                {form.salary_rates.map((r: any, i: number) => {
                  const patch = (p: any) => set({ salary_rates: form.salary_rates.map((x: any, j: number) => j === i ? { ...x, ...p } : x) })
                  return (
                    <div key={i} className="flex gap-2 items-center">
                      <input type="date" className={`${inputCls} w-36 shrink-0`} value={r.effective_from} onChange={e => patch({ effective_from: e.target.value })} title="Applies from" />
                      <select className={`${inputCls} flex-1 min-w-0`} value={r.pay_head_name} onChange={e => patch({ pay_head_name: e.target.value })}>
                        <option value="">Pay head...</option>
                        {Array.from(new Set([...payHeads.map((p: any) => p.name), r.pay_head_name].filter(Boolean))).map((n: any) => <option key={n}>{n}</option>)}
                      </select>
                      <input type="number" className={`${inputCls} w-24 shrink-0`} placeholder="Rate" value={r.rate} onChange={e => patch({ rate: e.target.value })} />
                      <button type="button" onClick={() => set({ salary_rates: form.salary_rates.filter((_: any, j: number) => j !== i) })} className="p-1.5 text-destructive hover:bg-destructive/10 rounded-md shrink-0"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  )
                })}
              </div>
            )}
          </>)}
        </div>
        <div className="flex gap-3 px-5 py-4 border-t border-border">
          <button onClick={onClose} className="flex-1 sm:flex-none px-4 py-2 border border-border rounded-lg text-sm font-semibold hover:bg-muted">Cancel</button>
          <button onClick={save} disabled={saving} className="flex-[2] sm:flex-none sm:ml-auto px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}Save
          </button>
        </div>
      </div>
    </div>
  )
}
