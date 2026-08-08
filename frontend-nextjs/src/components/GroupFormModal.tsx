'use client'

import { useState, useEffect } from 'react'
import { X, Sparkles, Building2, AlertCircle, Plus, Trash2 } from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { cn } from '@/lib/utils'

export type AccountGroupTreeNode = {
  group_id: number
  name: string
  nature?: string
  alias_name?: string
  parent_group_id?: number | null
  children?: AccountGroupTreeNode[]
}

export type GroupGstDetail = {
  applicable_from: string
  hsn_sac_details: string
  hsn_sac: string
  gst_rate_details: string
  taxability_type: string
  gst_rate: number | ''
}

export type GroupFormData = {
  group_id?: number
  name: string
  parent_group_id: number | null
  nature: string
  alias_name?: string
  is_addable: boolean
  is_revenue: boolean
  is_deemed_positive: boolean
  affects_gross_profit: boolean
  is_subledger: boolean
  is_billwise_on: boolean
  used_for_calculation: boolean
  method_to_allocate: string
  gst_details: GroupGstDetail[]
}

type Props = {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  initialData?: GroupFormData | null
  token: string | null
  parentGroupId?: number | null
}

export default function GroupFormModal({
  isOpen,
  onClose,
  onSuccess,
  initialData,
  token,
  parentGroupId
}: Props) {
  const [groups, setGroups] = useState<any[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'general' | 'advanced' | 'statutory'>('general')

  const [formData, setFormData] = useState<GroupFormData>({
    name: '',
    parent_group_id: parentGroupId || null,
    nature: 'Asset',
    alias_name: '',
    is_addable: true,
    is_revenue: false,
    is_deemed_positive: false,
    affects_gross_profit: false,
    is_subledger: false,
    is_billwise_on: false,
    used_for_calculation: false,
    method_to_allocate: 'Not Applicable',
    gst_details: []
  })

  const [saving, setSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  // Flatten tree for dropdown
  const flattenGroups = (nodes: AccountGroupTreeNode[], level = 0): any[] => {
    let result: any[] = []
    for (const node of nodes) {
      result.push({ ...node, level })
      if (node.children && node.children.length > 0) {
        result = result.concat(flattenGroups(node.children, level + 1))
      }
    }
    return result
  }

  const fetchGroups = async () => {
    if (!token) return
    setGroupsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/ledgers/groups/tree`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setGroups(flattenGroups(data))
      }
    } catch (err) {
      console.error(err)
    } finally {
      setGroupsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchGroups()
      setActiveTab('general')
      if (initialData) {
        setFormData({
          ...initialData,
          gst_details: initialData.gst_details || [],
          method_to_allocate: initialData.method_to_allocate || 'Not Applicable'
        })
      } else {
        setFormData({
          name: '',
          parent_group_id: parentGroupId || null,
          nature: 'Asset',
          alias_name: '',
          is_addable: true,
          is_revenue: false,
          is_deemed_positive: false,
          affects_gross_profit: false,
          is_subledger: false,
          is_billwise_on: false,
          used_for_calculation: false,
          method_to_allocate: 'Not Applicable',
          gst_details: []
        })
      }
      setErrorMsg('')
    }
  }, [isOpen, initialData, parentGroupId])

  // Auto-inherit nature from parent
  useEffect(() => {
    if (formData.parent_group_id && groups.length > 0) {
      const parent = groups.find(g => g.group_id === formData.parent_group_id)
      if (parent && parent.nature) {
        setFormData(prev => ({ ...prev, nature: parent.nature }))
      }
    }
  }, [formData.parent_group_id, groups])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')
    
    if (!token) {
      setErrorMsg("Unauthorized")
      return
    }

    if (!formData.name.trim()) {
      setErrorMsg("Group Name is required")
      return
    }

    setSaving(true)
    try {
      const url = initialData?.group_id 
        ? `${API_BASE}/ledgers/groups/${initialData.group_id}`
        : `${API_BASE}/ledgers/groups`
        
      const method = initialData?.group_id ? 'PUT' : 'POST'
      
      const payload = { ...formData }

      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Failed to save group')
      }

      onSuccess()
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message)
    } finally {
      setSaving(false)
    }
  }

  const addGstRow = () => {
    setFormData(prev => ({
      ...prev,
      gst_details: [
        ...prev.gst_details,
        {
          applicable_from: new Date().toISOString().split('T')[0],
          hsn_sac_details: 'Specify Details Here',
          hsn_sac: '',
          gst_rate_details: 'Specify Details Here',
          taxability_type: 'Taxable',
          gst_rate: 0
        }
      ]
    }))
  }

  const updateGstRow = (index: number, field: keyof GroupGstDetail, value: any) => {
    const newRows = [...formData.gst_details]
    newRows[index] = { ...newRows[index], [field]: value }
    setFormData({ ...formData, gst_details: newRows })
  }

  const removeGstRow = (index: number) => {
    const newRows = [...formData.gst_details]
    newRows.splice(index, 1)
    setFormData({ ...formData, gst_details: newRows })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-card rounded-2xl w-full max-w-4xl shadow-2xl border border-border flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border bg-muted/20">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-emerald-500/10 text-emerald-600 rounded-xl">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-black text-foreground tracking-tight">
                {initialData ? 'Alter Group' : 'Group Creation'}
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5 font-semibold">
                Manage your chart of accounts grouping
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-muted text-muted-foreground hover:text-foreground rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex px-6 pt-4 gap-6 border-b border-border">
          <button
            onClick={() => setActiveTab('general')}
            className={cn("pb-3 text-sm font-bold border-b-2 transition-all", activeTab === 'general' ? "border-emerald-500 text-emerald-600" : "border-transparent text-muted-foreground hover:text-foreground")}
          >
            General Details
          </button>
          <button
            onClick={() => setActiveTab('advanced')}
            className={cn("pb-3 text-sm font-bold border-b-2 transition-all", activeTab === 'advanced' ? "border-emerald-500 text-emerald-600" : "border-transparent text-muted-foreground hover:text-foreground")}
          >
            Advanced Parameters
          </button>
          <button
            onClick={() => setActiveTab('statutory')}
            className={cn("pb-3 text-sm font-bold border-b-2 transition-all", activeTab === 'statutory' ? "border-emerald-500 text-emerald-600" : "border-transparent text-muted-foreground hover:text-foreground")}
          >
            Statutory & GST
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto">
          {errorMsg && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive shrink-0 mt-0.5" />
              <p className="text-destructive text-sm font-medium">{errorMsg}</p>
            </div>
          )}

          <form id="group-form" onSubmit={handleSubmit} className="space-y-8">
            
            {/* TAB: GENERAL */}
            <div className={cn("space-y-4", activeTab === 'general' ? "block" : "hidden")}>
              <h3 className="text-xs font-bold text-emerald-600 uppercase tracking-wider">Group Details</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div className="space-y-1.5 md:col-span-2">
                  <label className="text-xs font-bold text-muted-foreground">Name *</label>
                  <input
                    type="text"
                    required={activeTab === 'general'}
                    value={formData.name}
                    onChange={e => setFormData({...formData, name: e.target.value})}
                    className="w-full bg-background border border-input rounded-xl px-4 py-2.5 text-foreground text-sm font-semibold focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-muted-foreground/50"
                    placeholder="e.g. North Zone Debtors"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground">Alias (Optional)</label>
                  <input
                    type="text"
                    value={formData.alias_name || ''}
                    onChange={e => setFormData({...formData, alias_name: e.target.value})}
                    className="w-full bg-background border border-input rounded-xl px-4 py-2.5 text-foreground text-sm font-semibold focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all placeholder:text-muted-foreground/50"
                    placeholder="Short name or code"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground">Under (Parent Group)</label>
                  <select
                    value={formData.parent_group_id || ''}
                    onChange={e => setFormData({...formData, parent_group_id: e.target.value ? Number(e.target.value) : null})}
                    className="w-full bg-background border border-input rounded-xl px-4 py-2.5 text-foreground text-sm font-semibold focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all"
                    disabled={groupsLoading}
                  >
                    <option value="">Primary</option>
                    {groups.map(g => (
                      <option key={g.group_id} value={g.group_id} disabled={!g.is_addable}>
                        {'\u00A0'.repeat(g.level * 4)} {g.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground">Nature of Group</label>
                  <select
                    value={formData.nature}
                    onChange={e => setFormData({...formData, nature: e.target.value})}
                    disabled={!!formData.parent_group_id} 
                    className="w-full bg-background border border-input rounded-xl px-4 py-2.5 text-foreground text-sm font-semibold focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-all disabled:opacity-50 disabled:bg-muted"
                  >
                    <option value="Asset">Assets</option>
                    <option value="Liability">Liabilities</option>
                    <option value="Income">Income</option>
                    <option value="Expense">Expenses</option>
                  </select>
                </div>
              </div>
            </div>

            {/* TAB: ADVANCED */}
            <div className={cn("space-y-8", activeTab === 'advanced' ? "block" : "hidden")}>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <label className="flex items-center gap-3 p-4 rounded-xl border border-border bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.is_addable}
                    onChange={e => setFormData({...formData, is_addable: e.target.checked})}
                    className="w-4 h-4 rounded border-input bg-background text-emerald-600 focus:ring-emerald-500/20"
                  />
                  <div>
                    <div className="text-sm font-bold text-foreground">Can Add Sub-Groups</div>
                    <div className="text-[11px] text-muted-foreground">Allow items under this group</div>
                  </div>
                </label>
                
                <label className="flex items-center gap-3 p-4 rounded-xl border border-border bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.affects_gross_profit}
                    onChange={e => setFormData({...formData, affects_gross_profit: e.target.checked})}
                    className="w-4 h-4 rounded border-input bg-background text-emerald-600 focus:ring-emerald-500/20"
                  />
                  <div>
                    <div className="text-sm font-bold text-foreground">Affects Gross Profit</div>
                    <div className="text-[11px] text-muted-foreground">Used for Trading Account groups</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-4 rounded-xl border border-border bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.is_subledger}
                    onChange={e => setFormData({...formData, is_subledger: e.target.checked})}
                    className="w-4 h-4 rounded border-input bg-background text-emerald-600 focus:ring-emerald-500/20"
                  />
                  <div>
                    <div className="text-sm font-bold text-foreground">Behaves like a Sub-Ledger</div>
                    <div className="text-[11px] text-muted-foreground">Don't show sub-ledgers in reports</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-4 rounded-xl border border-border bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.is_billwise_on}
                    onChange={e => setFormData({...formData, is_billwise_on: e.target.checked})}
                    className="w-4 h-4 rounded border-input bg-background text-emerald-600 focus:ring-emerald-500/20"
                  />
                  <div>
                    <div className="text-sm font-bold text-foreground">Nett Debit/Credit Balances</div>
                    <div className="text-[11px] text-muted-foreground">Show net balances for reporting</div>
                  </div>
                </label>
                
                <label className="flex items-center gap-3 p-4 rounded-xl border border-border bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={formData.used_for_calculation}
                    onChange={e => setFormData({...formData, used_for_calculation: e.target.checked})}
                    className="w-4 h-4 rounded border-input bg-background text-emerald-600 focus:ring-emerald-500/20"
                  />
                  <div>
                    <div className="text-sm font-bold text-foreground">Used for Calculation</div>
                    <div className="text-[11px] text-muted-foreground">For taxes, discounts in invoices</div>
                  </div>
                </label>

                <div className="space-y-1.5 p-4 rounded-xl border border-border bg-muted/30">
                  <label className="text-sm font-bold text-foreground">Method to Allocate (Purchase Invoice)</label>
                  <select
                    value={formData.method_to_allocate}
                    onChange={e => setFormData({...formData, method_to_allocate: e.target.value})}
                    className="w-full bg-background border border-input rounded-xl px-4 py-2 mt-1 text-foreground text-sm font-semibold focus:outline-none focus:border-emerald-500 transition-all"
                  >
                    <option value="Not Applicable">Not Applicable</option>
                    <option value="Appropriate by Qty">Appropriate by Qty</option>
                    <option value="Appropriate by Value">Appropriate by Value</option>
                  </select>
                </div>
              </div>
            </div>

            {/* TAB: STATUTORY */}
            <div className={cn("space-y-4", activeTab === 'statutory' ? "block" : "hidden")}>
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-emerald-600 uppercase tracking-wider">Historical GST & HSN Details</h3>
                <button
                  type="button"
                  onClick={addGstRow}
                  className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 rounded-lg text-xs font-bold transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add GST Rate
                </button>
              </div>

              {formData.gst_details.length === 0 ? (
                <div className="p-8 border border-dashed border-border rounded-xl flex flex-col items-center justify-center text-center">
                  <p className="text-sm font-semibold text-muted-foreground">No statutory details specified.</p>
                  <p className="text-xs text-muted-foreground/70 mt-1">This group will inherit GST details from the Company.</p>
                </div>
              ) : (
                <div className="border border-border rounded-xl overflow-hidden overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-muted/30 text-xs text-muted-foreground uppercase">
                      <tr>
                        <th className="px-4 py-3 font-bold border-b border-border">Applicable From</th>
                        <th className="px-4 py-3 font-bold border-b border-border">HSN Details</th>
                        <th className="px-4 py-3 font-bold border-b border-border">HSN Code</th>
                        <th className="px-4 py-3 font-bold border-b border-border">GST Rate Details</th>
                        <th className="px-4 py-3 font-bold border-b border-border">Taxability</th>
                        <th className="px-4 py-3 font-bold border-b border-border">Rate %</th>
                        <th className="px-4 py-3 font-bold border-b border-border w-10"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {formData.gst_details.map((row, i) => (
                        <tr key={i} className="bg-background">
                          <td className="px-4 py-2">
                            <input
                              type="date"
                              required
                              value={row.applicable_from}
                              onChange={e => updateGstRow(i, 'applicable_from', e.target.value)}
                              className="w-full bg-transparent text-sm font-semibold focus:outline-none"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <select
                              value={row.hsn_sac_details}
                              onChange={e => updateGstRow(i, 'hsn_sac_details', e.target.value)}
                              className="w-full bg-transparent text-sm font-semibold focus:outline-none"
                            >
                              <option value="As per Company/Group">As per Company/Group</option>
                              <option value="Specify Details Here">Specify Details Here</option>
                              <option value="Specify in Voucher">Specify in Voucher</option>
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="text"
                              value={row.hsn_sac}
                              onChange={e => updateGstRow(i, 'hsn_sac', e.target.value)}
                              disabled={row.hsn_sac_details !== 'Specify Details Here'}
                              className="w-24 bg-transparent text-sm font-semibold focus:outline-none disabled:opacity-30"
                              placeholder="e.g. 9954"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <select
                              value={row.gst_rate_details}
                              onChange={e => updateGstRow(i, 'gst_rate_details', e.target.value)}
                              className="w-full bg-transparent text-sm font-semibold focus:outline-none"
                            >
                              <option value="As per Company/Group">As per Company/Group</option>
                              <option value="Specify Details Here">Specify Details Here</option>
                              <option value="Specify in Voucher">Specify in Voucher</option>
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            <select
                              value={row.taxability_type}
                              onChange={e => updateGstRow(i, 'taxability_type', e.target.value)}
                              disabled={row.gst_rate_details !== 'Specify Details Here'}
                              className="w-full bg-transparent text-sm font-semibold focus:outline-none disabled:opacity-30"
                            >
                              <option value="Unknown">Unknown</option>
                              <option value="Exempt">Exempt</option>
                              <option value="Nil Rated">Nil Rated</option>
                              <option value="Taxable">Taxable</option>
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="number"
                              value={row.gst_rate}
                              onChange={e => updateGstRow(i, 'gst_rate', e.target.value === '' ? '' : Number(e.target.value))}
                              disabled={row.gst_rate_details !== 'Specify Details Here' || row.taxability_type !== 'Taxable'}
                              className="w-16 bg-transparent text-sm font-semibold focus:outline-none disabled:opacity-30"
                              placeholder="0"
                            />
                          </td>
                          <td className="px-4 py-2 text-right">
                            <button
                              type="button"
                              onClick={() => removeGstRow(i)}
                              className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

          </form>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border bg-muted/20 flex justify-end gap-3 rounded-b-2xl">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 text-xs font-bold text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="group-form"
            disabled={saving}
            className="px-6 py-2.5 text-xs font-extrabold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl shadow-sm transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {saving ? 'Saving...' : 'Save Group'}
          </button>
        </div>
      </div>
    </div>
  )
}
