'use client'

import { useState, useEffect } from 'react'
import { X, Sparkles, Building2, MapPin, CreditCard, UserCheck, AlertCircle } from 'lucide-react'
import { INDIAN_STATES, COUNTRY_LIST, parseGSTIN } from '@/lib/location-data'
import { API_BASE, authHeaders } from '@/lib/utils'
import { GST_REGISTRATION_TYPES } from '@/constants/gst'

export type AccountGroup = {
  group_id: number
  name: string
  nature?: string
  parent_group_id?: number | null
}

export type LedgerFormData = {
  ledger_id?: number
  name: string
  group_id: number
  opening_balance: string
  opening_balance_type: 'Dr' | 'Cr'
  gstin: string
  gst_registration_type?: string
  pan_number: string
  aadhar_number: string
  address: string
  state: string
  pincode: string
  country: string
  mobile: string
  phone: string
  email: string
  contact_person: string
  credit_limit: string
  credit_period_days: string
  is_billwise_on: boolean
  transporter_id?: string
  is_transporter?: boolean
  place_of_supply?: string
  is_other_territory_assessee?: boolean
  is_common_party?: boolean
  is_inventory_affected?: boolean
  is_cost_centres_on?: boolean
  notes?: string
}

type Props = {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  initialData?: LedgerFormData | null
  token: string | null
  defaultGroupType?: 'customer' | 'supplier' | 'all'
}

export default function LedgerFormModal({
  isOpen,
  onClose,
  onSuccess,
  initialData,
  token,
  defaultGroupType = 'customer'
}: Props) {
  const [activeFormTab, setActiveFormTab] = useState<'basic' | 'tax' | 'contact'>('basic')
  const [groups, setGroups] = useState<AccountGroup[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)

  const [formData, setFormData] = useState<LedgerFormData>({
    name: '',
    group_id: 0,
    opening_balance: '0.00',
    opening_balance_type: 'Dr',
    gstin: '',
    gst_registration_type: 'Unregistered/Consumer',
    pan_number: '',
    aadhar_number: '',
    address: '',
    state: 'Haryana',
    pincode: '',
    country: 'India',
    mobile: '',
    phone: '',
    email: '',
    contact_person: '',
    credit_limit: '',
    credit_period_days: '',
    is_billwise_on: true,
    transporter_id: '',
    is_transporter: false,
    place_of_supply: '',
    is_other_territory_assessee: false,
    is_common_party: false,
    is_inventory_affected: false,
    is_cost_centres_on: false,
    notes: ''
  })

  const [saving, setSaving] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [gstRegTypes, setGstRegTypes] = useState<string[]>([...GST_REGISTRATION_TYPES])
  const [transactionTypes, setTransactionTypes] = useState<string[]>([
    'e-Fund Transfer', 'UPI', 'Cheque', 'ECS', 'Card', 'ATM', 'Electronic Cheque', 'Electronic DD/PO', 'Others'
  ])

  const [provideBankDetails, setProvideBankDetails] = useState(false)
  const [bankDetail, setBankDetail] = useState({
    transaction_type: 'e-Fund Transfer',
    account_number: '',
    ifsc_code: '',
    bank_name: '',
    upi_id: '',
    account_holder_name: '',
    cross_using: 'A/c Payee',
    favouring_name: ''
  })

  // Fetch groups and DB GST / Bank registration types
  useEffect(() => {
    if (!isOpen || !token) return
    const fetchGroupsAndTypes = async () => {
      setGroupsLoading(true)
      try {
        const [groupsRes, typesRes, bankTypesRes] = await Promise.all([
          fetch(`${API_BASE}/ledgers/groups`, { headers: authHeaders(token || '') }),
          fetch(`${API_BASE}/ledgers/gst-registration-types`),
          fetch(`${API_BASE}/ledgers/bank-transaction-types`)
        ])
        if (groupsRes.ok) {
          const data = await groupsRes.json()
          setGroups(Array.isArray(data) ? data : [])
        }
        if (typesRes.ok) {
          const typesData = await typesRes.json()
          if (Array.isArray(typesData) && typesData.length > 0) {
            setGstRegTypes(typesData.map((item: any) => item.name))
          }
        }
        if (bankTypesRes.ok) {
          const bData = await bankTypesRes.json()
          if (Array.isArray(bData) && bData.length > 0) {
            setTransactionTypes(bData.map((item: any) => item.name))
          }
        }
      } catch (err) {
        console.error('Failed to load groups or types:', err)
      } finally {
        setGroupsLoading(false)
      }
    }
    fetchGroupsAndTypes()
  }, [isOpen, token])

  // Set default group when groups or initialData changes
  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || '',
        group_id: initialData.group_id || 0,
        opening_balance: initialData.opening_balance ? Math.abs(parseFloat(initialData.opening_balance)).toString() : '0.00',
        opening_balance_type: initialData.opening_balance_type || 'Dr',
        gstin: initialData.gstin || '',
        gst_registration_type: initialData.gst_registration_type || (initialData.gstin ? 'Regular' : 'Unregistered/Consumer'),
        pan_number: initialData.pan_number || '',
        aadhar_number: initialData.aadhar_number || '',
        address: initialData.address || '',
        state: initialData.state || 'Haryana',
        pincode: initialData.pincode || '',
        country: initialData.country || 'India',
        mobile: initialData.mobile || '',
        phone: initialData.phone || '',
        email: initialData.email || '',
        contact_person: initialData.contact_person || '',
        credit_limit: initialData.credit_limit || '',
        credit_period_days: initialData.credit_period_days || '',
        is_billwise_on: initialData.is_billwise_on ?? true,
        transporter_id: initialData.transporter_id || '',
        is_transporter: initialData.is_transporter ?? false,
        place_of_supply: initialData.place_of_supply || '',
        is_other_territory_assessee: initialData.is_other_territory_assessee ?? false,
        is_common_party: initialData.is_common_party ?? false,
        is_inventory_affected: initialData.is_inventory_affected ?? false,
        is_cost_centres_on: initialData.is_cost_centres_on ?? false,
        notes: initialData.notes || ''
      })

      const anyBank = (initialData as any).bank_details?.[0]
      if (anyBank) {
        setProvideBankDetails(true)
        setBankDetail({
          transaction_type: anyBank.transaction_type || 'e-Fund Transfer',
          account_number: anyBank.account_number || '',
          ifsc_code: anyBank.ifsc_code || '',
          bank_name: anyBank.bank_name || '',
          upi_id: anyBank.upi_id || '',
          account_holder_name: anyBank.account_holder_name || '',
          cross_using: anyBank.cross_using || 'A/c Payee',
          favouring_name: anyBank.favouring_name || ''
        })
      } else {
        setProvideBankDetails(false)
        setBankDetail({
          transaction_type: 'e-Fund Transfer',
          account_number: '',
          ifsc_code: '',
          bank_name: '',
          upi_id: '',
          account_holder_name: '',
          cross_using: 'A/c Payee',
          favouring_name: ''
        })
      }
    } else {
      // Find default group (Sundry Debtors for customer, Sundry Creditors for supplier)
      let defaultGrpId = 0
      if (groups.length > 0) {
        if (defaultGroupType === 'customer') {
          const debtors = groups.find(g => g.name.toLowerCase().includes('debtor'))
          if (debtors) defaultGrpId = debtors.group_id
        } else if (defaultGroupType === 'supplier') {
          const creditors = groups.find(g => g.name.toLowerCase().includes('creditor'))
          if (creditors) defaultGrpId = creditors.group_id
        }
        if (!defaultGrpId && groups[0]) {
          defaultGrpId = groups[0].group_id
        }
      }
      setFormData({
        name: '',
        group_id: defaultGrpId,
        opening_balance: '0.00',
        opening_balance_type: defaultGroupType === 'customer' ? 'Dr' : 'Cr',
        gstin: '',
        gst_registration_type: 'Unregistered/Consumer',
        pan_number: '',
        aadhar_number: '',
        address: '',
        state: 'Haryana',
        pincode: '',
        country: 'India',
        mobile: '',
        phone: '',
        email: '',
        contact_person: '',
        credit_limit: '',
        credit_period_days: '',
        is_billwise_on: true,
        transporter_id: '',
        is_transporter: false,
        place_of_supply: '',
        is_other_territory_assessee: false,
        is_common_party: false,
        is_inventory_affected: false,
        is_cost_centres_on: false,
        notes: ''
      })
      setProvideBankDetails(false)
      setBankDetail({
        transaction_type: 'e-Fund Transfer',
        account_number: '',
        ifsc_code: '',
        bank_name: '',
        upi_id: '',
        account_holder_name: '',
        cross_using: 'A/c Payee',
        favouring_name: ''
      })
    }
    setErrorMsg('')
  }, [initialData, isOpen, groups, defaultGroupType])

  // Handle GSTIN change with Auto-State & Auto-PAN extraction
  const handleGSTINChange = (val: string) => {
    const uppercaseVal = val.toUpperCase()
    const { stateName, panNumber } = parseGSTIN(uppercaseVal)

    setFormData(prev => ({
      ...prev,
      gstin: uppercaseVal,
      gst_registration_type: uppercaseVal.length > 0 && prev.gst_registration_type === 'Unregistered/Consumer' ? 'Regular' : prev.gst_registration_type,
      state: stateName || prev.state,
      place_of_supply: stateName || prev.place_of_supply || prev.state,
      pan_number: panNumber || prev.pan_number
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) {
      setErrorMsg('Ledger Name is required')
      setActiveFormTab('basic')
      return
    }
    if (!formData.group_id) {
      setErrorMsg('Please select a Parent Account Group')
      setActiveFormTab('basic')
      return
    }

    setSaving(true)
    setErrorMsg('')

    try {
      const isEdit = Boolean(initialData?.ledger_id)
      const url = isEdit
        ? `${API_BASE}/ledgers/${initialData?.ledger_id}`
        : `${API_BASE}/ledgers`
      const method = isEdit ? 'PUT' : 'POST'

      const payload = {
        name: formData.name.trim(),
        group_id: Number(formData.group_id),
        opening_balance: parseFloat(formData.opening_balance || '0'),
        opening_balance_type: formData.opening_balance_type,
        gstin: formData.gstin.trim() || null,
        gst_registration_type: formData.gst_registration_type || null,
        pan_number: formData.pan_number.trim() || null,
        aadhar_number: formData.aadhar_number.trim() || null,
        address: formData.address.trim() || null,
        state: formData.state || null,
        pincode: formData.pincode.trim() || null,
        country: formData.country || 'India',
        mobile: formData.mobile.trim() || null,
        phone: formData.phone.trim() || null,
        email: formData.email.trim() || null,
        contact_person: formData.contact_person.trim() || null,
        credit_limit: formData.credit_limit ? parseFloat(formData.credit_limit) : null,
        credit_period_days: formData.credit_period_days ? parseInt(formData.credit_period_days) : null,
        is_billwise_on: formData.is_billwise_on,
        transporter_id: formData.transporter_id?.trim() || null,
        is_transporter: formData.is_transporter || Boolean(formData.transporter_id?.trim()),
        place_of_supply: formData.place_of_supply || formData.state || null,
        is_other_territory_assessee: formData.is_other_territory_assessee ?? false,
        is_common_party: formData.is_common_party ?? false,
        is_inventory_affected: formData.is_inventory_affected ?? false,
        is_cost_centres_on: formData.is_cost_centres_on ?? false,
        notes: formData.notes?.trim() || null,
        bank_details: provideBankDetails && (bankDetail.account_number || bankDetail.upi_id || bankDetail.bank_name) ? [
          {
            transaction_type: bankDetail.transaction_type,
            account_number: bankDetail.account_number.trim() || null,
            ifsc_code: bankDetail.ifsc_code.trim() || null,
            bank_name: bankDetail.bank_name.trim() || null,
            upi_id: bankDetail.upi_id.trim() || null,
            account_holder_name: bankDetail.account_holder_name.trim() || null,
            is_default: true
          }
        ] : []
      }

      const res = await fetch(url, {
        method,
        headers: {
          ...authHeaders(token || ''),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Failed to save ledger')
      }

      onSuccess()
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Something went wrong while saving')
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card border border-border w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
              <Building2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-foreground">
                {initialData?.ledger_id ? 'Edit Ledger Master' : 'Create New Ledger'}
              </h2>
              <p className="text-[11px] text-muted-foreground font-medium">
                {initialData?.ledger_id ? 'Update Tally ledger parameters' : 'Add new customer, supplier, or account ledger'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation Header */}
        <div className="flex border-b border-border bg-background/50 px-4 pt-2 gap-2 text-xs">
          <button
            type="button"
            onClick={() => setActiveFormTab('basic')}
            className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-bold transition-all cursor-pointer ${
              activeFormTab === 'basic'
                ? 'border-emerald-500 text-emerald-600 bg-emerald-500/5 rounded-t-lg'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            Basic Info
          </button>
          <button
            type="button"
            onClick={() => setActiveFormTab('tax')}
            className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-bold transition-all cursor-pointer ${
              activeFormTab === 'tax'
                ? 'border-emerald-500 text-emerald-600 bg-emerald-500/5 rounded-t-lg'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <CreditCard className="w-3.5 h-3.5" />
            Tax & Credit
          </button>
          <button
            type="button"
            onClick={() => setActiveFormTab('contact')}
            className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-bold transition-all cursor-pointer ${
              activeFormTab === 'contact'
                ? 'border-emerald-500 text-emerald-600 bg-emerald-500/5 rounded-t-lg'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <MapPin className="w-3.5 h-3.5" />
            Location & Contact
          </button>
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-semibold">{errorMsg}</span>
          </div>
        )}

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* TAB 1: BASIC INFO */}
          {activeFormTab === 'basic' && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Ledger Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Apex Tech Solutions Pvt Ltd"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">
                  Parent Account Group <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  disabled={groupsLoading}
                  value={formData.group_id}
                  onChange={e => setFormData({ ...formData, group_id: Number(e.target.value) })}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                >
                  <option value={0}>Select Group...</option>
                  {groups.map(g => (
                    <option key={g.group_id} value={g.group_id}>
                      {g.name} {g.nature ? `(${g.nature})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-foreground mb-1">Opening Balance</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={formData.opening_balance}
                    onChange={e => setFormData({ ...formData, opening_balance: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Type</label>
                  <select
                    value={formData.opening_balance_type}
                    onChange={e => setFormData({ ...formData, opening_balance_type: e.target.value as 'Dr' | 'Cr' })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-bold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    <option value="Dr">Dr (Debit)</option>
                    <option value="Cr">Cr (Credit)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Credit Limit (₹)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 500000"
                    value={formData.credit_limit}
                    onChange={e => setFormData({ ...formData, credit_limit: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Credit Days</label>
                  <input
                    type="number"
                    placeholder="e.g. 45"
                    value={formData.credit_period_days}
                    onChange={e => setFormData({ ...formData, credit_period_days: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border space-y-2">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_billwise_on"
                    checked={formData.is_billwise_on}
                    onChange={e => setFormData({ ...formData, is_billwise_on: e.target.checked })}
                    className="rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                  />
                  <label htmlFor="is_billwise_on" className="text-xs font-bold text-foreground cursor-pointer">
                    Enable Bill-by-Bill Tracking
                  </label>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_inventory_affected"
                      checked={formData.is_inventory_affected || false}
                      onChange={e => setFormData({ ...formData, is_inventory_affected: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                    />
                    <label htmlFor="is_inventory_affected" className="text-xs text-foreground cursor-pointer">
                      Inventory Affected
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_cost_centres_on"
                      checked={formData.is_cost_centres_on || false}
                      onChange={e => setFormData({ ...formData, is_cost_centres_on: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                    />
                    <label htmlFor="is_cost_centres_on" className="text-xs text-foreground cursor-pointer">
                      Cost Centres On
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: TAX & STATUTORY */}
          {activeFormTab === 'tax' && (
            <div className="space-y-4">
              {/* Primary GST Registration */}
              <div className="space-y-3">
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-bold text-foreground">GST Registration Type</label>
                  <span className="text-[10px] text-muted-foreground font-medium">Statutory Tax Type</span>
                </div>
                <select
                  value={formData.gst_registration_type || 'Unregistered/Consumer'}
                  onChange={e => setFormData({ ...formData, gst_registration_type: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 font-semibold cursor-pointer"
                >
                  {gstRegTypes.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>

                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="text-xs font-bold text-foreground">GSTIN / UIN Number</label>
                    <span className="text-[10px] text-emerald-600 font-semibold">Auto-detects State & PAN</span>
                  </div>
                  <input
                    type="text"
                    maxLength={15}
                    placeholder="e.g. 07AAACA1234A1Z5"
                    value={formData.gstin}
                    onChange={e => handleGSTINChange(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500 uppercase"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-foreground mb-1">PAN / IT No.</label>
                    <input
                      type="text"
                      maxLength={10}
                      placeholder="e.g. AAACA1234A"
                      value={formData.pan_number || ''}
                      onChange={e => setFormData({ ...formData, pan_number: e.target.value.toUpperCase() })}
                      className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500 uppercase"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-foreground mb-1">Aadhaar Number</label>
                    <input
                      type="text"
                      maxLength={12}
                      placeholder="e.g. 123456789012"
                      value={formData.aadhar_number || ''}
                      onChange={e => setFormData({ ...formData, aadhar_number: e.target.value.replace(/\D/g, '') })}
                      className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    />
                  </div>
                </div>
              </div>

              {/* Tally Prime Style: Additional GST Details Card */}
              <div className="p-3.5 rounded-xl bg-muted/40 border border-border/80 space-y-3">
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-xs font-extrabold text-foreground">Additional GST Details</span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                    Tally Prime Format
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">
                    Place of Supply (for Outwards)
                  </label>
                  <select
                    value={formData.place_of_supply || formData.state || 'Haryana'}
                    onChange={e => setFormData({ ...formData, place_of_supply: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    {INDIAN_STATES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <label className="block text-xs font-bold text-foreground mb-1">Is Party a Transporter?</label>
                    <select
                      value={formData.is_transporter ? 'Yes' : 'No'}
                      onChange={e => {
                        const isYes = e.target.value === 'Yes'
                        setFormData(prev => ({
                          ...prev,
                          is_transporter: isYes,
                          transporter_id: isYes ? prev.transporter_id : ''
                        }))
                      }}
                      className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer font-bold"
                    >
                      <option value="No">No</option>
                      <option value="Yes">Yes</option>
                    </select>
                  </div>

                  {formData.is_transporter && (
                    <div className="animate-in fade-in slide-in-from-top-1 duration-200">
                      <label className="block text-xs font-bold text-emerald-700 dark:text-emerald-400 mb-1">
                        Transporter ID <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. 1234 or Transporter GSTIN"
                        value={formData.transporter_id || ''}
                        onChange={e => setFormData({ ...formData, transporter_id: e.target.value })}
                        className="w-full px-3 py-2 text-xs border border-emerald-500/40 rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      />
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/50">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_other_territory_assessee"
                      checked={formData.is_other_territory_assessee || false}
                      onChange={e => setFormData({ ...formData, is_other_territory_assessee: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                    />
                    <label htmlFor="is_other_territory_assessee" className="text-xs text-foreground cursor-pointer">
                      Other Territory Assessee
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_common_party"
                      checked={formData.is_common_party || false}
                      onChange={e => setFormData({ ...formData, is_common_party: e.target.checked })}
                      className="rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                    />
                    <label htmlFor="is_common_party" className="text-xs text-foreground cursor-pointer">
                      Common Party
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: LOCATION & CONTACT */}
          {activeFormTab === 'contact' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Contact Person</label>
                  <input
                    type="text"
                    placeholder="e.g. Mr. Vikram Malhotra"
                    value={formData.contact_person}
                    onChange={e => setFormData({ ...formData, contact_person: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Mobile Number</label>
                  <input
                    type="tel"
                    placeholder="e.g. 9810012345"
                    value={formData.mobile}
                    onChange={e => setFormData({ ...formData, mobile: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Phone (Landline)</label>
                  <input
                    type="tel"
                    placeholder="e.g. 0124-4567890"
                    value={formData.phone}
                    onChange={e => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Primary Email</label>
                  <input
                    type="email"
                    placeholder="accounts@apextech.com"
                    value={formData.email}
                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">Street Address</label>
                <textarea
                  rows={2}
                  placeholder="Plot No 78, Cyber City, Sector 18..."
                  value={formData.address}
                  onChange={e => setFormData({ ...formData, address: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 resize-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">State</label>
                  <select
                    value={formData.state}
                    onChange={e => setFormData({ ...formData, state: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    {INDIAN_STATES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Pincode</label>
                  <input
                    type="text"
                    maxLength={6}
                    placeholder="122002"
                    value={formData.pincode}
                    onChange={e => setFormData({ ...formData, pincode: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Country</label>
                  <select
                    value={formData.country}
                    onChange={e => setFormData({ ...formData, country: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                  >
                    {COUNTRY_LIST.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Tally Prime Style: Banking Details Card */}
              <div className="p-3.5 rounded-xl bg-muted/40 border border-border/80 space-y-3">
                <div className="flex items-center justify-between border-b border-border/60 pb-2">
                  <div className="flex items-center gap-1.5">
                    <CreditCard className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-xs font-extrabold text-foreground">Banking Details</span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                    Provide bank details
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-foreground mb-1">Provide bank details?</label>
                    <select
                      value={provideBankDetails ? 'Yes' : 'No'}
                      onChange={e => setProvideBankDetails(e.target.value === 'Yes')}
                      className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer font-bold"
                    >
                      <option value="No">No</option>
                      <option value="Yes">Yes</option>
                    </select>
                  </div>

                  {provideBankDetails && (
                    <div className="animate-in fade-in slide-in-from-top-1 duration-200">
                      <label className="block text-xs font-bold text-foreground mb-1">Transaction Type</label>
                      <select
                        value={bankDetail.transaction_type}
                        onChange={e => setBankDetail({ ...bankDetail, transaction_type: e.target.value })}
                        className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer font-semibold"
                      >
                        {transactionTypes.map(t => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>

                {provideBankDetails && (
                  <div className="space-y-3 pt-1 animate-in fade-in slide-in-from-top-1 duration-200">
                    {/* For Cheque / Electronic Cheque */}
                    {['Cheque', 'Electronic Cheque'].includes(bankDetail.transaction_type) && (
                      <div className="grid grid-cols-2 gap-3 p-2.5 rounded-lg bg-background/50 border border-border/60">
                        <div>
                          <label className="block text-xs font-bold text-foreground mb-1">Cross Using</label>
                          <input
                            type="text"
                            placeholder="A/c Payee"
                            value={bankDetail.cross_using || 'A/c Payee'}
                            onChange={e => setBankDetail({ ...bankDetail, cross_using: e.target.value })}
                            className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 font-semibold"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-bold text-foreground mb-1">Favouring Name</label>
                          <input
                            type="text"
                            placeholder={formData.name || 'Favouring Company / Person'}
                            value={bankDetail.favouring_name || ''}
                            onChange={e => setBankDetail({ ...bankDetail, favouring_name: e.target.value })}
                            className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        </div>
                      </div>
                    )}

                    {/* For UPI */}
                    {bankDetail.transaction_type === 'UPI' && (
                      <div className="space-y-2 p-2.5 rounded-lg bg-background/50 border border-border/60">
                        <div>
                          <label className="block text-xs font-bold text-emerald-700 dark:text-emerald-400 mb-1">
                            UPI ID (VPA) <span className="text-rose-500">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="e.g. 8979921514@upi or name@okaxis"
                            value={bankDetail.upi_id || ''}
                            onChange={e => setBankDetail({ ...bankDetail, upi_id: e.target.value })}
                            className="w-full px-3 py-2 text-xs border border-emerald-500/40 rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        </div>
                      </div>
                    )}

                    {/* Bank Name */}
                    <div>
                      <label className="block text-xs font-bold text-foreground mb-1">Bank Name</label>
                      <input
                        type="text"
                        placeholder="e.g. Punjab National Bank, HDFC Bank, State Bank of India..."
                        value={bankDetail.bank_name || ''}
                        onChange={e => setBankDetail({ ...bankDetail, bank_name: e.target.value })}
                        className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-foreground mb-1">A/c No.</label>
                        <input
                          type="text"
                          placeholder="e.g. 1232121211"
                          value={bankDetail.account_number || ''}
                          onChange={e => setBankDetail({ ...bankDetail, account_number: e.target.value })}
                          className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-foreground mb-1">IFS Code</label>
                        <input
                          type="text"
                          maxLength={11}
                          placeholder="e.g. PUNB0400700"
                          value={bankDetail.ifsc_code || ''}
                          onChange={e => setBankDetail({ ...bankDetail, ifsc_code: e.target.value.toUpperCase() })}
                          className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-emerald-500 uppercase"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">Internal Notes / Remarks</label>
                <textarea
                  rows={2}
                  placeholder="Special client terms, notes, or instructions..."
                  value={formData.notes || ''}
                  onChange={e => setFormData({ ...formData, notes: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-border rounded-xl bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 resize-none"
                />
              </div>
            </div>
          )}

          {/* Form Actions Footer */}
          <div className="pt-4 border-t border-border flex items-center justify-between gap-3">
            <div className="text-[11px] text-muted-foreground font-medium">
              {activeFormTab === 'basic' && 'Step 1 of 3: Basic Details'}
              {activeFormTab === 'tax' && 'Step 2 of 3: Tax & Credit Limits'}
              {activeFormTab === 'contact' && 'Step 3 of 3: Location & Contact Info'}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="px-4 py-2 border border-border rounded-xl text-xs font-bold text-foreground hover:bg-muted transition-all cursor-pointer"
              >
                Cancel
              </button>

              {activeFormTab !== 'contact' ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    if (activeFormTab === 'basic') setActiveFormTab('tax')
                    else if (activeFormTab === 'tax') setActiveFormTab('contact')
                  }}
                  className="px-4 py-2 bg-foreground text-background rounded-xl text-xs font-bold hover:opacity-90 transition-all cursor-pointer"
                >
                  Next &rarr;
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-extrabold shadow-md transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      {initialData?.ledger_id ? 'Update Ledger' : 'Save & Sync Ledger'}
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
