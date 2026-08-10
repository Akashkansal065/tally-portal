import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ChevronDown, Plus, Trash2 } from 'lucide-react'
import { InfoTip } from '@/components/ui/info-tip'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

interface VoucherTypePrefix {
  applicable_from: string;
  particulars: string;
}

interface VoucherTypeSuffix {
  applicable_from: string;
  particulars: string;
}

interface VoucherTypeRestart {
  applicable_from: string;
  starting_number: number;
  periodicity: string;
}

interface VoucherTypeClassGroup {
  group_name: string;
  is_included: boolean;
}

interface VoucherTypeClass {
  class_name: string;
  bank_alloc_for: string | null;
  default_ledger_name: string | null;
  groups: VoucherTypeClassGroup[];
}

interface VoucherType {
  voucher_type_id?: number;
  name: string;
  parent_type: string | null;
  abbreviation: string | null;
  numbering_method: string;
  numbering_behavior: string | null;
  width_of_numerical_part: number;
  prefill_with_zero: boolean;
  show_unused_vch_nos: boolean;
  prevent_duplicates: boolean;
  is_active: boolean;
  is_system_defined?: boolean;
  
  // Extended fields
  use_effective_dates?: boolean;
  allow_zero_valued_transactions?: boolean;
  is_optional_by_default?: boolean;
  allow_narration_in_voucher?: boolean;
  provide_narrations_for_each_ledger?: boolean;
  print_voucher_after_saving?: boolean;
  whatsapp_voucher_after_saving?: boolean;
  enable_default_accounting_allocations?: boolean;
  track_additional_costs_for_purchases?: boolean;
  default_jurisdiction?: string | null;
  default_title_to_print?: string | null;
  
  prefixes: VoucherTypePrefix[];
  suffixes: VoucherTypeSuffix[];
  restarts: VoucherTypeRestart[];
  classes: VoucherTypeClass[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  voucherTypeToEdit?: VoucherType | null;
  systemTypes: string[];
}

export default function VoucherTypeFormModal({ isOpen, onClose, onSuccess, voucherTypeToEdit, systemTypes }: Props) {
  const { token } = useAuth()
  const [activeTab, setActiveTab] = useState('general')
  const [selectedClassIndex, setSelectedClassIndex] = useState<number | null>(null)
  
  const defaultState: VoucherType = {
    name: '',
    parent_type: '',
    abbreviation: '',
    numbering_method: 'Automatic',
    numbering_behavior: 'Retain Original Voucher No.',
    width_of_numerical_part: 0,
    prefill_with_zero: false,
    show_unused_vch_nos: false,
    prevent_duplicates: false,
    is_active: true,
    use_effective_dates: false,
    allow_zero_valued_transactions: false,
    is_optional_by_default: false,
    allow_narration_in_voucher: true,
    provide_narrations_for_each_ledger: false,
    print_voucher_after_saving: false,
    whatsapp_voucher_after_saving: false,
    enable_default_accounting_allocations: false,
    track_additional_costs_for_purchases: false,
    default_jurisdiction: '',
    default_title_to_print: '',
    prefixes: [],
    suffixes: [],
    restarts: [],
    classes: []
  }

  const [formData, setFormData] = useState<VoucherType>(defaultState)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [accountGroups, setAccountGroups] = useState<{group_id: number; name: string}[]>([])
  const [ledgersList, setLedgersList] = useState<{ledger_id: number; name: string}[]>([])

  // Fetch groups and ledgers when modal opens
  useEffect(() => {
    if (isOpen && token) {
      fetch(`${API_BASE}/ledgers/groups`, { headers: authHeaders(token) })
        .then(r => r.json()).then(data => setAccountGroups(Array.isArray(data) ? data : []))
        .catch(() => setAccountGroups([]))
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
        .then(r => r.json()).then(data => setLedgersList(Array.isArray(data) ? data : []))
        .catch(() => setLedgersList([]))
    }
  }, [isOpen, token])

  useEffect(() => {
    if (voucherTypeToEdit) {
      setFormData({
        ...defaultState,
        ...voucherTypeToEdit,
        parent_type: voucherTypeToEdit.parent_type || '',
        abbreviation: voucherTypeToEdit.abbreviation || '',
        default_jurisdiction: voucherTypeToEdit.default_jurisdiction || '',
        default_title_to_print: voucherTypeToEdit.default_title_to_print || ''
      })
    } else {
      setFormData(defaultState)
    }
    setError('')
    setActiveTab('general')
    setSelectedClassIndex(null)
  }, [voucherTypeToEdit, isOpen])

  const handleChange = (field: keyof VoucherType, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    
    try {
      const url = voucherTypeToEdit ? `${API_BASE}/voucher-type/${voucherTypeToEdit.voucher_type_id}` : `${API_BASE}/voucher-type`
      const method = voucherTypeToEdit ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(formData)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save voucher type')
      }

      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const pType = formData.parent_type || '';
  const showAccountingAllocations = ['Contra', 'Payment', 'Receipt', 'Sales', 'Purchase', 'Credit Note', 'Debit Note'].includes(pType);
  const showTrackAdditionalCosts = ['Debit Note', 'Purchase'].includes(pType);
  const showDefaultJurisdiction = ['Credit Note', 'Sales'].includes(pType);
  const showDefaultTitle = ['Credit Note', 'Sales', 'Debit Note', 'Purchase'].includes(pType);

  const tabs = [
    { id: 'general', label: 'General' },
    { id: 'numbering', label: 'Numbering' },
    { id: 'classes', label: 'Classes & Defaults' },
    { id: 'printing', label: 'Printing' }
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] flex flex-col p-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle>{voucherTypeToEdit ? 'Edit Voucher Type' : 'Create Voucher Type'}</DialogTitle>
        </DialogHeader>

        <div className="flex border-b px-6 pt-2 space-x-4 bg-gray-50">
          {tabs.map(t => (
            <button
              key={t.id}
              type="button"
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${activeTab === t.id ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              onClick={() => setActiveTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error && <div className="mb-4 p-3 text-sm text-red-500 bg-red-50 rounded-md border border-red-200">{error}</div>}

          <form id="vt-form" onSubmit={handleSubmit} className="space-y-6">
            
            {/* GENERAL TAB */}
            {activeTab === 'general' && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2 col-span-2">
                    <Label className="flex items-center">Name *<InfoTip text="Unique name for this voucher type as it will appear in menus." /></Label>
                    <Input required value={formData.name} onChange={e => handleChange('name', e.target.value)} disabled={voucherTypeToEdit?.is_system_defined} />
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center">Parent Type<InfoTip text="The base voucher class this type inherits from (Payment, Receipt, etc.). Determines the underlying accounting behavior." /></Label>
                    <select className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm" value={formData.parent_type || "none"} onChange={e => handleChange('parent_type', e.target.value === "none" ? "" : e.target.value)} disabled={voucherTypeToEdit?.is_system_defined}>
                      <option value="none">None</option>
                      {systemTypes.map(st => <option key={st} value={st}>{st}</option>)}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label className="flex items-center">Abbreviation<InfoTip text="Short code shown in registers/reports next to voucher numbers. Purely cosmetic." /></Label>
                    <Input value={formData.abbreviation || ''} onChange={e => handleChange('abbreviation', e.target.value)} disabled={voucherTypeToEdit?.is_system_defined} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <div className="flex items-center space-x-2">
                    <Checkbox id="is_active" checked={formData.is_active} onCheckedChange={(c) => handleChange('is_active', !!c)} />
                    <Label htmlFor="is_active" className="flex items-center">Activate this Voucher Type<InfoTip text="If disabled, the voucher type exists in the DB but won't appear in transaction entry menus. Useful for retiring a type without deleting it." /></Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="use_effective_dates" checked={formData.use_effective_dates} onCheckedChange={(c) => handleChange('use_effective_dates', !!c)} />
                    <Label htmlFor="use_effective_dates" className="flex items-center">Use effective dates for vouchers<InfoTip text="Lets each voucher carry a separate 'effective date' distinct from the voucher date — used for post-dated cheques." /></Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="allow_zero_valued_transactions" checked={formData.allow_zero_valued_transactions} onCheckedChange={(c) => handleChange('allow_zero_valued_transactions', !!c)} />
                    <Label htmlFor="allow_zero_valued_transactions" className="flex items-center">Allow zero-valued transactions<InfoTip text="Permits saving a voucher where debit = credit = 0. Useful for narration-only or memo entries." /></Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="is_optional_by_default" checked={formData.is_optional_by_default} onCheckedChange={(c) => handleChange('is_optional_by_default', !!c)} />
                    <Label htmlFor="is_optional_by_default" className="flex items-center">Make optional by default<InfoTip text="Every new voucher of this type opens pre-marked 'Optional' — excluded from books until confirmed. Used for provisional/draft entries." /></Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="allow_narration_in_voucher" checked={formData.allow_narration_in_voucher} onCheckedChange={(c) => handleChange('allow_narration_in_voucher', !!c)} />
                    <Label htmlFor="allow_narration_in_voucher" className="flex items-center">Allow narration in voucher<InfoTip text="Enables a free-text narration box at the voucher level." /></Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="provide_narrations_for_each_ledger" checked={formData.provide_narrations_for_each_ledger} onCheckedChange={(c) => handleChange('provide_narrations_for_each_ledger', !!c)} />
                    <Label htmlFor="provide_narrations_for_each_ledger" className="flex items-center">Provide narrations for each ledger<InfoTip text="Enables a narration field per individual ledger line, not just one voucher-level note." /></Label>
                  </div>
                  {showTrackAdditionalCosts && (
                    <div className="flex items-center space-x-2">
                      <Checkbox id="track_additional_costs" checked={formData.track_additional_costs_for_purchases} onCheckedChange={(c) => handleChange('track_additional_costs_for_purchases', !!c)} />
                      <Label htmlFor="track_additional_costs" className="flex items-center">Track additional costs for purchases<InfoTip text="Lets you capture freight/insurance/other costs and allocate them to item cost." /></Label>
                    </div>
                  )}
                  {showAccountingAllocations && (
                    <div className="flex items-center space-x-2">
                      <Checkbox id="enable_default_allocations" checked={formData.enable_default_accounting_allocations} onCheckedChange={(c) => handleChange('enable_default_accounting_allocations', !!c)} />
                      <Label htmlFor="enable_default_allocations" className="flex items-center">Enable default accounting allocations<InfoTip text="Pre-configure standard ledger entries that auto-populate whenever this voucher type is used." /></Label>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* NUMBERING TAB */}
            {activeTab === 'numbering' && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="flex items-center">Method of Voucher Numbering<InfoTip text="Controls how voucher numbers are generated: Automatic (system increments), Manual (user types), Multi-User Auto (concurrent safety), or None." /></Label>
                    <select className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm" value={formData.numbering_method} onChange={e => handleChange('numbering_method', e.target.value)}>
                      <option value="Automatic">Automatic</option>
                      <option value="Automatic (Manual Override)">Automatic (Manual Override)</option>
                      <option value="Manual">Manual</option>
                      <option value="Multi-user Auto">Multi-user Auto</option>
                      <option value="None">None</option>
                    </select>
                  </div>
                  {formData.numbering_method.includes('Automatic') && (
                    <div className="space-y-2">
                      <Label className="flex items-center">Numbering behaviour on insertion/deletion<InfoTip text="'Renumber Vouchers' shifts all subsequent numbers to stay contiguous. 'Retain Original' keeps existing numbers fixed, gaps can appear." /></Label>
                      <select className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm" value={formData.numbering_behavior || 'Retain Original Voucher No.'} onChange={e => handleChange('numbering_behavior', e.target.value)}>
                        <option value="Retain Original Voucher No.">Retain Original Voucher No.</option>
                        <option value="Renumber Vouchers">Renumber Vouchers</option>
                      </select>
                    </div>
                  )}
                </div>

                {formData.numbering_method.includes('Automatic') && (
                  <>
                    <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                      <div className="flex items-center space-x-2">
                        <Checkbox id="prevent_duplicates" checked={formData.prevent_duplicates} onCheckedChange={(c) => handleChange('prevent_duplicates', !!c)} />
                        <Label htmlFor="prevent_duplicates" className="flex items-center">Prevent Duplicates<InfoTip text="Prevents two vouchers from having the same number within this voucher type." /></Label>
                      </div>
                      {formData.numbering_behavior === 'Retain Original Voucher No.' && (
                        <div className="flex items-center space-x-2">
                          <Checkbox id="show_unused" checked={formData.show_unused_vch_nos} onCheckedChange={(c) => handleChange('show_unused_vch_nos', !!c)} />
                          <Label htmlFor="show_unused" className="flex items-center">Show unused vch nos. in transactions<InfoTip text="When creating a new voucher, the system will offer any skipped/unused numbers from the gap, not just the next sequential one." /></Label>
                        </div>
                      )}
                      <div className="space-y-2">
                        <Label className="flex items-center">Width of Numerical Part<InfoTip text="Number of digits for the numerical portion. Used with 'Prefill with zero' to add leading zeros (e.g., width 4 → 0001)." /></Label>
                        <Input type="number" min="0" value={formData.width_of_numerical_part} onChange={e => handleChange('width_of_numerical_part', parseInt(e.target.value)||0)} />
                      </div>
                      <div className="flex items-center space-x-2 mt-8">
                        <Checkbox id="prefill_zero" checked={formData.prefill_with_zero} onCheckedChange={(c) => handleChange('prefill_with_zero', !!c)} />
                        <Label htmlFor="prefill_zero" className="flex items-center">Prefill with zero<InfoTip text="Pads the voucher number with leading zeros up to the specified width (e.g., 1 → 0001)." /></Label>
                      </div>
                    </div>

                    <div className="space-y-4 pt-4 border-t">
                      <h4 className="font-medium">Prefix Details</h4>
                      {formData.prefixes.map((p, idx) => (
                        <div key={idx} className="flex gap-2">
                          <Input type="date" value={p.applicable_from} onChange={e => { const n = [...formData.prefixes]; n[idx].applicable_from = e.target.value; handleChange('prefixes', n) }} />
                          <Input placeholder="Particulars" value={p.particulars} onChange={e => { const n = [...formData.prefixes]; n[idx].particulars = e.target.value; handleChange('prefixes', n) }} />
                          <Button type="button" variant="ghost" size="icon" onClick={() => handleChange('prefixes', formData.prefixes.filter((_, i) => i !== idx))}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                        </div>
                      ))}
                      <Button type="button" variant="outline" size="sm" onClick={() => handleChange('prefixes', [...formData.prefixes, { applicable_from: new Date().toISOString().split('T')[0], particulars: '' }])}>
                        <Plus className="h-4 w-4 mr-2" /> Add Prefix
                      </Button>
                    </div>

                    <div className="space-y-4 pt-4 border-t">
                      <h4 className="font-medium">Suffix Details</h4>
                      {formData.suffixes.map((s, idx) => (
                        <div key={idx} className="flex gap-2">
                          <Input type="date" value={s.applicable_from} onChange={e => { const n = [...formData.suffixes]; n[idx].applicable_from = e.target.value; handleChange('suffixes', n) }} />
                          <Input placeholder="Particulars" value={s.particulars} onChange={e => { const n = [...formData.suffixes]; n[idx].particulars = e.target.value; handleChange('suffixes', n) }} />
                          <Button type="button" variant="ghost" size="icon" onClick={() => handleChange('suffixes', formData.suffixes.filter((_, i) => i !== idx))}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                        </div>
                      ))}
                      <Button type="button" variant="outline" size="sm" onClick={() => handleChange('suffixes', [...formData.suffixes, { applicable_from: new Date().toISOString().split('T')[0], particulars: '' }])}>
                        <Plus className="h-4 w-4 mr-2" /> Add Suffix
                      </Button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* CLASSES & DEFAULTS TAB */}
            {activeTab === 'classes' && (
              <div className="space-y-6">
                <div className="flex justify-between items-center">
                  <Label>Voucher Classes</Label>
                  <Button type="button" size="sm" onClick={() => {
                    const newClass = { class_name: 'New Class', bank_alloc_for: null, default_ledger_name: null, groups: [] };
                    handleChange('classes', [...formData.classes, newClass]);
                    setSelectedClassIndex(formData.classes.length);
                  }}>
                    <Plus className="h-4 w-4 mr-2" /> Add Class
                  </Button>
                </div>
                
                {formData.classes.length === 0 && <p className="text-sm text-gray-500 italic">No classes defined.</p>}
                
                <div className="flex gap-4">
                  <div className="w-1/3 border rounded-md p-2 space-y-1 min-h-[200px]">
                    {formData.classes.map((cls, idx) => (
                      <div key={idx} className={`p-2 cursor-pointer rounded-md flex justify-between items-center ${selectedClassIndex === idx ? 'bg-primary/10 font-medium' : 'hover:bg-gray-100'}`} onClick={() => setSelectedClassIndex(idx)}>
                        <span className="text-sm truncate">{cls.class_name}</span>
                        <Button type="button" variant="ghost" size="sm" className="h-6 w-6 p-0 shrink-0" onClick={(e) => { e.stopPropagation(); handleChange('classes', formData.classes.filter((_, i) => i !== idx)); setSelectedClassIndex(null); }}>
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    ))}
                  </div>
                  
                  {selectedClassIndex !== null && formData.classes[selectedClassIndex] && (() => {
                    const cls = formData.classes[selectedClassIndex];
                    const excludedGroups = cls.groups.filter(g => !g.is_included);
                    const includedGroups = cls.groups.filter(g => g.is_included);
                    const usedGroupNames = cls.groups.map(g => g.group_name);
                    const availableGroups = accountGroups.filter(ag => !usedGroupNames.includes(ag.name));
                    
                    const addGroup = (groupName: string, isIncluded: boolean) => {
                      const n = [...formData.classes];
                      n[selectedClassIndex] = { ...n[selectedClassIndex], groups: [...n[selectedClassIndex].groups, { group_name: groupName, is_included: isIncluded }] };
                      handleChange('classes', n);
                    };
                    const removeGroup = (groupName: string) => {
                      const n = [...formData.classes];
                      n[selectedClassIndex] = { ...n[selectedClassIndex], groups: n[selectedClassIndex].groups.filter(g => g.group_name !== groupName) };
                      handleChange('classes', n);
                    };
                    
                    return (
                      <div className="w-2/3 border rounded-md p-4 space-y-4 overflow-y-auto max-h-[500px]">
                        <div className="space-y-2">
                          <Label>Class Name</Label>
                          <Input value={cls.class_name} onChange={e => {
                            const n = [...formData.classes];
                            n[selectedClassIndex].class_name = e.target.value;
                            handleChange('classes', n);
                          }} />
                        </div>
                        
                        <div className="space-y-2">
                          <Label>Bank Allocations For</Label>
                          <select className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm" value={cls.bank_alloc_for || ''} onChange={e => {
                            const n = [...formData.classes];
                            n[selectedClassIndex].bank_alloc_for = e.target.value || null;
                            handleChange('classes', n);
                          }}>
                            <option value="">None</option>
                            <option value="Employees">Employees</option>
                            <option value="Cost Centres">Cost Centres</option>
                            <option value="Both">Both</option>
                          </select>
                        </div>
                        
                        {/* Exclude / Include Groups */}
                        <div className="pt-2 border-t space-y-3">
                          <p className="text-xs text-gray-500 italic">Restrict which ledger groups this class can use</p>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                              <Label className="text-xs font-semibold">Exclude these Groups</Label>
                              <div className="border rounded-md p-2 min-h-[80px] space-y-1">
                                {excludedGroups.map(g => (
                                  <div key={g.group_name} className="flex justify-between items-center text-sm px-1 py-0.5 bg-red-50 rounded">
                                    <span>{g.group_name}</span>
                                    <button type="button" onClick={() => removeGroup(g.group_name)} className="text-red-500 hover:text-red-700 text-xs">✕</button>
                                  </div>
                                ))}
                              </div>
                              <select className="flex h-8 w-full rounded-md border border-input bg-transparent px-2 py-0.5 text-xs" value="" onChange={e => { if (e.target.value) addGroup(e.target.value, false); e.target.value = ''; }}>
                                <option value="">+ Add group to exclude...</option>
                                {availableGroups.map(ag => <option key={ag.group_id} value={ag.name}>{ag.name}</option>)}
                              </select>
                            </div>
                            <div className="space-y-2">
                              <Label className="text-xs font-semibold">Include these Groups</Label>
                              <div className="border rounded-md p-2 min-h-[80px] space-y-1">
                                {includedGroups.map(g => (
                                  <div key={g.group_name} className="flex justify-between items-center text-sm px-1 py-0.5 bg-green-50 rounded">
                                    <span>{g.group_name}</span>
                                    <button type="button" onClick={() => removeGroup(g.group_name)} className="text-red-500 hover:text-red-700 text-xs">✕</button>
                                  </div>
                                ))}
                              </div>
                              <select className="flex h-8 w-full rounded-md border border-input bg-transparent px-2 py-0.5 text-xs" value="" onChange={e => { if (e.target.value) addGroup(e.target.value, true); e.target.value = ''; }}>
                                <option value="">+ Add group to include...</option>
                                {availableGroups.map(ag => <option key={ag.group_id} value={ag.name}>{ag.name}</option>)}
                              </select>
                            </div>
                          </div>
                        </div>
                        
                        {/* Specific Ledger */}
                        <div className="pt-2 border-t space-y-2">
                          <Label>Specific Ledger for which this Class is created</Label>
                          <p className="text-xs text-gray-500 italic">e.g. Cash, or a Bank Account</p>
                          <select className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm" value={cls.default_ledger_name || ''} onChange={e => {
                            const n = [...formData.classes];
                            n[selectedClassIndex].default_ledger_name = e.target.value || null;
                            handleChange('classes', n);
                          }}>
                            <option value="">Not Applicable</option>
                            {ledgersList.map(l => <option key={l.ledger_id} value={l.name}>{l.name}</option>)}
                          </select>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            )}

            {/* PRINTING TAB */}
            {activeTab === 'printing' && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center space-x-2 col-span-2">
                    <Checkbox id="print_voucher_after_saving" checked={formData.print_voucher_after_saving} onCheckedChange={(c) => handleChange('print_voucher_after_saving', !!c)} />
                    <Label htmlFor="print_voucher_after_saving" className="flex items-center">Print voucher after saving<InfoTip text="Automatically opens the print dialog right after the voucher is saved." /></Label>
                  </div>
                  <div className="flex items-center space-x-2 col-span-2">
                    <Checkbox id="whatsapp_voucher" checked={formData.whatsapp_voucher_after_saving} onCheckedChange={(c) => handleChange('whatsapp_voucher_after_saving', !!c)} />
                    <Label htmlFor="whatsapp_voucher" className="flex items-center">WhatsApp voucher after saving<InfoTip text="Prompts to send the voucher (as PDF/image) via WhatsApp immediately after save." /></Label>
                  </div>
                  
                  {showDefaultJurisdiction && (
                    <div className="space-y-2">
                      <Label className="flex items-center">Default Jurisdiction<InfoTip text="Sets the default tax jurisdiction printed on the voucher." /></Label>
                      <Input value={formData.default_jurisdiction || ''} onChange={e => handleChange('default_jurisdiction', e.target.value)} />
                    </div>
                  )}
                  {showDefaultTitle && (
                    <div className="space-y-2">
                      <Label className="flex items-center">Default Title to Print<InfoTip text="Custom title that appears on the printed voucher instead of the default." /></Label>
                      <Input value={formData.default_title_to_print || ''} onChange={e => handleChange('default_title_to_print', e.target.value)} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </form>
        </div>

        <div className="px-6 py-4 border-t flex justify-end gap-2 bg-gray-50 rounded-b-lg">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="vt-form" disabled={submitting}>
            {submitting ? 'Saving...' : 'Save Configuration'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
