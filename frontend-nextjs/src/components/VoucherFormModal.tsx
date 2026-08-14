'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { X, Search, ChevronDown, Plus, Trash2, Calendar, FileText, IndianRupee, Loader2, AlertCircle, FolderPlus } from 'lucide-react'
import { cn, formatCurrency } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { toast } from 'sonner'

export type VoucherFormModalProps = {
  isOpen: boolean
  onClose: () => void
  onSave: (data: any) => Promise<void>
  isSaving: boolean
  ledgers: any[]
  voucherTypes: any[]
  onLedgerCreated?: (newLedger: any) => void
}

export default function VoucherFormModal({
  isOpen,
  onClose,
  onSave,
  isSaving,
  ledgers,
  voucherTypes,
  onLedgerCreated
}: VoucherFormModalProps) {
  const { token } = useAuth()
  // 1. Basic Form States
  const [selectedType, setSelectedType] = useState<any>(null)
  const [voucherDate, setVoucherDate] = useState(new Date().toISOString().slice(0, 10))
  const [refNumber, setRefNumber] = useState('')
  const [narration, setNarration] = useState('')
  const [status, setStatus] = useState('confirmed')
  const [validationError, setValidationError] = useState<string | null>(null)
  
  // 2. Ledgers State & Sync
  const [localLedgers, setLocalLedgers] = useState<any[]>(ledgers || [])

  useEffect(() => {
    setLocalLedgers(ledgers || [])
  }, [ledgers])

  // 3. Accounting View States
  const [entries, setEntries] = useState([
    { id: 1, ledger_id: '', type: 'Debit', amount: '' },
    { id: 2, ledger_id: '', type: 'Credit', amount: '' }
  ])
  const [nextId, setNextId] = useState(3)
  
  // 4. Invoice View States
  const [partyLedgerId, setPartyLedgerId] = useState('')
  const [originalVoucherId, setOriginalVoucherId] = useState('')
  const [inventoryEntries, setInventoryEntries] = useState<any[]>([])
  const [nextInvId, setNextInvId] = useState(1)
  
  // 5. Stock Journal View States
  const [sourceEntries, setSourceEntries] = useState<any[]>([])
  const [destEntries, setDestEntries] = useState<any[]>([])
  
  // 6. Fetched Data States
  const [stockItems, setStockItems] = useState<any[]>([])
  const [godowns, setGodowns] = useState<any[]>([])

  // 7. Quick Ledger Creation Sub-Modal States
  const [isQuickLedgerOpen, setIsQuickLedgerOpen] = useState(false)
  const [quickLedgerTarget, setQuickLedgerTarget] = useState<'party' | number | null>(null)
  const [quickName, setQuickName] = useState('')
  const [quickGroupId, setQuickGroupId] = useState<string>('')
  const [quickOpeningBalance, setQuickOpeningBalance] = useState('')
  const [quickOpeningBalanceType, setQuickOpeningBalanceType] = useState<'Dr' | 'Cr'>('Dr')
  const [groupsList, setGroupsList] = useState<any[]>([])
  const [isCreatingLedger, setIsCreatingLedger] = useState(false)
  const [quickLedgerError, setQuickLedgerError] = useState<string | null>(null)

  // 8. Derived Sorted Lists (A-Z)
  const sortedLedgers = useMemo(() => {
    return [...localLedgers].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [localLedgers])

  const sortedGroups = useMemo(() => {
    return [...groupsList].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [groupsList])

  const sortedStockItems = useMemo(() => {
    return [...stockItems].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [stockItems])

  const activeVoucherTypes = useMemo(() => {
    return voucherTypes.filter(t => t.is_active !== false)
  }, [voucherTypes])

  useEffect(() => {
    if (isOpen) {
      const typeSales = activeVoucherTypes.find(t => t.name.toLowerCase() === 'sales')
      setSelectedType(typeSales || (activeVoucherTypes.length > 0 ? activeVoucherTypes[0] : null))
      setVoucherDate(new Date().toISOString().slice(0, 10))
      setRefNumber('')
      setNarration('')
      setStatus('confirmed')
      setValidationError(null)
      setPartyLedgerId('')
      setOriginalVoucherId('')
      setEntries([
        { id: 1, ledger_id: '', type: 'Debit', amount: '' },
        { id: 2, ledger_id: '', type: 'Credit', amount: '' }
      ])
      setInventoryEntries([])
      setSourceEntries([])
      setDestEntries([])
      
      // Fetch items, godowns, and groups
      fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setStockItems(Array.isArray(data) ? data : []))
        .catch(console.error)
      fetch(`${API_BASE}/inventory/godowns`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setGodowns(Array.isArray(data) ? data : []))
        .catch(console.error)
      fetch(`${API_BASE}/ledgers/groups`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setGroupsList(Array.isArray(data) ? data : []))
        .catch(console.error)
    }
  }, [isOpen, voucherTypes, token])

  const parentType = selectedType?.parent_type || selectedType?.name || ''
  const isInvoiceView = ['Sales', 'Purchase', 'Credit Note', 'Debit Note'].includes(parentType)
  const isStockJournal = parentType === 'Stock Journal'
  const isAccountingView = !isInvoiceView && !isStockJournal

  // Compute active non-empty accounting entries
  const activeEntries = useMemo(() => {
    return entries.filter(e => e.ledger_id || e.amount)
  }, [entries])

  const totals = useMemo(() => {
    const debits = activeEntries.filter(e => e.type === 'Debit').reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0)
    const credits = activeEntries.filter(e => e.type === 'Credit').reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0)
    return { 
      debits, 
      credits, 
      isBalanced: Math.abs(debits - credits) < 0.01 && debits > 0 
    }
  }, [activeEntries])

  // Helper to add entry row with smart default type
  const addEntry = () => {
    const lastType = entries[entries.length - 1]?.type || 'Debit'
    const newType = lastType === 'Debit' ? 'Credit' : 'Debit'
    
    // Calculate difference for auto-fill
    const diff = Math.abs(totals.debits - totals.credits)
    const autoAmount = diff > 0 ? diff.toFixed(2) : ''

    setEntries([...entries, { id: nextId, ledger_id: '', type: newType, amount: autoAmount }])
    setNextId(nextId + 1)
  }

  const removeEntry = (id: number) => {
    if (entries.length <= 2) {
      setEntries(entries.map(e => e.id === id ? { ...e, ledger_id: '', amount: '' } : e))
    } else {
      setEntries(entries.filter(e => e.id !== id))
    }
  }

  const handleAmountChange = (id: number, val: string) => {
    setValidationError(null)
    const updated = entries.map(e => {
      if (e.id === id) {
        return { ...e, amount: val }
      }
      return e
    })

    // Auto-suggest balance for single empty opposite row
    const numVal = parseFloat(val) || 0
    if (numVal > 0) {
      const changedItem = updated.find(e => e.id === id)
      const oppositeType = changedItem?.type === 'Debit' ? 'Credit' : 'Debit'
      const emptyOpposite = updated.find(e => e.type === oppositeType && (!e.amount || parseFloat(e.amount) === 0))
      if (emptyOpposite) {
        emptyOpposite.amount = val
      }
    }

    setEntries(updated)
  }
  
  const addInventoryEntry = () => {
    setInventoryEntries([...inventoryEntries, { id: nextInvId, stock_item_id: '', quantity: '', rate: '', amount: '' }])
    setNextInvId(nextInvId + 1)
  }

  const removeInventoryEntry = (id: number) => {
    setInventoryEntries(inventoryEntries.filter(e => e.id !== id))
  }

  const addSourceEntry = () => {
    setSourceEntries([...sourceEntries, { id: nextInvId, stock_item_id: '', quantity: '', rate: '', amount: '' }])
    setNextInvId(nextInvId + 1)
  }

  const addDestEntry = () => {
    setDestEntries([...destEntries, { id: nextInvId, stock_item_id: '', quantity: '', rate: '', amount: '' }])
    setNextInvId(nextInvId + 1)
  }

  // --- Inline Quick Ledger Creation Logic ---
  const openQuickLedgerModal = (target: 'party' | number) => {
    setQuickLedgerTarget(target)
    setQuickName('')
    setQuickLedgerError(null)
    
    // Smart default group selection based on target & voucher type
    if (target === 'party') {
      if (parentType.toLowerCase() === 'sales') {
        const debtorGrp = groupsList.find(g => g.name.toLowerCase().includes('sundry debtors'))
        setQuickGroupId(debtorGrp ? String(debtorGrp.group_id) : (groupsList[0]?.group_id ? String(groupsList[0].group_id) : ''))
      } else {
        const creditorGrp = groupsList.find(g => g.name.toLowerCase().includes('sundry creditors'))
        setQuickGroupId(creditorGrp ? String(creditorGrp.group_id) : (groupsList[0]?.group_id ? String(groupsList[0].group_id) : ''))
      }
    } else {
      setQuickGroupId(groupsList[0]?.group_id ? String(groupsList[0].group_id) : '')
    }
    
    setQuickOpeningBalance('')
    setQuickOpeningBalanceType('Dr')
    setIsQuickLedgerOpen(true)
  }

  const handleSaveQuickLedger = async () => {
    setQuickLedgerError(null)
    if (!quickName.trim()) {
      setQuickLedgerError("Please enter a ledger name.")
      return
    }
    if (!quickGroupId) {
      setQuickLedgerError("Please select an account group.")
      return
    }

    setIsCreatingLedger(true)
    try {
      const payload = {
        name: quickName.trim(),
        group_id: parseInt(quickGroupId),
        opening_balance: parseFloat(quickOpeningBalance || '0'),
        opening_balance_type: quickOpeningBalanceType
      }

      const res = await fetch(`${API_BASE}/ledgers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(token)
        },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to create ledger')
      }

      const newLedger = await res.json()
      
      // Update local ledgers list
      setLocalLedgers(prev => [...prev, newLedger])
      if (onLedgerCreated) {
        onLedgerCreated(newLedger)
      }

      // Auto select new ledger in the field that opened the quick modal
      if (quickLedgerTarget === 'party') {
        setPartyLedgerId(String(newLedger.ledger_id))
      } else if (typeof quickLedgerTarget === 'number') {
        setEntries(entries.map(e => e.id === quickLedgerTarget ? { ...e, ledger_id: String(newLedger.ledger_id) } : e))
      }

      toast.success(`Ledger "${newLedger.name}" created & selected!`)
      setIsQuickLedgerOpen(false)
    } catch (e: any) {
      setQuickLedgerError(e.message || "Failed to create ledger")
    } finally {
      setIsCreatingLedger(false)
    }
  }

  const handleSave = () => {
    setValidationError(null)
    if (!selectedType) {
      setValidationError("Please select a voucher type.")
      return
    }
    
    let payload: any = {
      voucher_type_id: selectedType.voucher_type_id,
      voucher_date: voucherDate,
      reference_number: refNumber,
      narration,
      status,
      entries: [],
      inventory_entries: []
    }
    
    if (isAccountingView) {
      const validRows = entries.filter(e => e.ledger_id.trim() !== '' || e.amount.trim() !== '')
      
      if (validRows.length === 0) {
        setValidationError("Please add at least one accounting entry.")
        return
      }

      for (const r of validRows) {
        if (!r.ledger_id) {
          setValidationError("Please select a ledger for all entry rows.")
          return
        }
        if (!r.amount || parseFloat(r.amount) <= 0) {
          setValidationError("Please enter a valid non-zero amount for all entries.")
          return
        }
      }

      const debits = validRows.filter(e => e.type === 'Debit').reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0)
      const credits = validRows.filter(e => e.type === 'Credit').reduce((sum, e) => sum + (parseFloat(e.amount) || 0), 0)

      if (Math.abs(debits - credits) >= 0.01) {
        setValidationError(`Accounting entries are unbalanced. Total Debits: ₹${debits.toFixed(2)} vs Total Credits: ₹${credits.toFixed(2)}. Difference: ₹${Math.abs(debits - credits).toFixed(2)}`)
        return
      }

      if (debits === 0) {
        setValidationError("Total voucher amount must be greater than zero.")
        return
      }

      payload.entries = validRows.map(e => ({
        ledger_id: parseInt(e.ledger_id),
        debit_amount: e.type === 'Debit' ? parseFloat(e.amount) : 0,
        credit_amount: e.type === 'Credit' ? parseFloat(e.amount) : 0
      }))
    } else if (isInvoiceView) {
      if (!partyLedgerId) {
        setValidationError("Please select a party ledger.")
        return
      }
      payload.party_ledger_id = parseInt(partyLedgerId)
      payload.is_invoice = true
      if (['Credit Note', 'Debit Note'].includes(parentType) && originalVoucherId) {
        payload.original_voucher_id = parseInt(originalVoucherId)
      }
      
      const validInv = inventoryEntries.filter(e => e.stock_item_id)
      if (validInv.length === 0) {
        setValidationError("Please select at least one inventory item.")
        return
      }

      const invPayload = validInv.map(e => ({
        stock_item_id: parseInt(e.stock_item_id),
        quantity: parseFloat(e.quantity || '0'),
        rate: parseFloat(e.rate || '0'),
        amount: parseFloat(e.amount || '0')
      }))
      payload.inventory_entries = invPayload
    } else if (isStockJournal) {
      const src = sourceEntries.filter(e => e.stock_item_id).map(e => ({
        stock_item_id: parseInt(e.stock_item_id),
        quantity: parseFloat(e.quantity || '0'),
        rate: parseFloat(e.rate || '0'),
        amount: parseFloat(e.amount || '0'),
        flow_type: 'source'
      }))
      const dst = destEntries.filter(e => e.stock_item_id).map(e => ({
        stock_item_id: parseInt(e.stock_item_id),
        quantity: parseFloat(e.quantity || '0'),
        rate: parseFloat(e.rate || '0'),
        amount: parseFloat(e.amount || '0'),
        flow_type: 'destination'
      }))
      if (src.length === 0 && dst.length === 0) {
        setValidationError("Please add at least one source or destination item in Stock Journal.")
        return
      }
      payload.inventory_entries = [...src, ...dst]
    }
    
    onSave(payload)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 dark:border-slate-800 relative overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Create Voucher</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-500">Status:</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  className="sr-only peer" 
                  checked={status === 'optional'} 
                  onChange={e => setStatus(e.target.checked ? 'optional' : 'confirmed')} 
                />
                <div className="w-11 h-6 bg-emerald-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
                <span className="ml-3 text-sm font-bold text-slate-700 dark:text-slate-300">
                  {status === 'optional' ? 'Optional (No Posting)' : 'Regular (Confirmed)'}
                </span>
              </label>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"><X className="w-5 h-5" /></button>
        </div>

        {/* Content */}
        <div className="p-6 flex-1 overflow-y-auto space-y-6">
          
          {/* Validation Alert Box */}
          {validationError && (
            <div className="flex items-center gap-3 p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 rounded-xl text-rose-700 dark:text-rose-300 text-sm font-medium animate-in fade-in slide-in-from-top-2">
              <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          <div className="grid grid-cols-3 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Voucher Type</label>
              <select 
                className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium" 
                value={selectedType?.voucher_type_id || ''} 
                onChange={e => {
                  setValidationError(null)
                  setSelectedType(activeVoucherTypes.find(t => t.voucher_type_id === parseInt(e.target.value)))
                }}
              >
                {activeVoucherTypes.map(t => <option key={t.voucher_type_id} value={t.voucher_type_id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Date</label>
              <input type="date" className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" value={voucherDate} onChange={e => setVoucherDate(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Reference No.</label>
              <input type="text" className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Ref No." value={refNumber} onChange={e => setRefNumber(e.target.value)} />
            </div>
          </div>

          {isInvoiceView && (
            <div className="grid grid-cols-2 gap-6 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Party Ledger</label>
                  <button 
                    type="button" 
                    onClick={() => openQuickLedgerModal('party')} 
                    className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" /> New Ledger
                  </button>
                </div>
                <div className="flex gap-2">
                  <select 
                    className="flex-1 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium" 
                    value={partyLedgerId} 
                    onChange={e => {
                      if (e.target.value === '__create_new__') {
                        openQuickLedgerModal('party')
                      } else {
                        setPartyLedgerId(e.target.value)
                      }
                    }}
                  >
                    <option value="">Select Party...</option>
                    <option value="__create_new__" className="font-bold text-emerald-600 dark:text-emerald-400">+ Create New Ledger...</option>
                    {sortedLedgers.map(l => (
                      <option key={l.ledger_id} value={l.ledger_id}>{l.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {['Credit Note', 'Debit Note'].includes(parentType) && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Against Original Invoice ID</label>
                  <input type="text" className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Voucher ID" value={originalVoucherId} onChange={e => setOriginalVoucherId(e.target.value)} />
                </div>
              )}
            </div>
          )}

          {isAccountingView && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-800 dark:text-slate-200">Accounting Entries</h3>
                <div className="flex items-center gap-4">
                  <button 
                    type="button" 
                    onClick={() => openQuickLedgerModal(entries[0]?.id || 1)} 
                    className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <FolderPlus className="w-3.5 h-3.5" /> + Quick Create Ledger
                  </button>
                  <span className="text-xs text-slate-400">Dr and Cr totals must balance</span>
                </div>
              </div>
              
              {entries.map((e, idx) => (
                <div key={e.id} className="flex gap-3 items-center">
                  <select 
                    className="w-24 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold bg-white dark:bg-slate-900" 
                    value={e.type} 
                    onChange={evt => {
                      setValidationError(null)
                      setEntries(entries.map(x => x.id === e.id ? { ...x, type: evt.target.value } : x))
                    }}
                  >
                    <option value="Debit">Dr</option>
                    <option value="Credit">Cr</option>
                  </select>
                  
                  <div className="flex-1 flex gap-2">
                    <select 
                      className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                      value={e.ledger_id} 
                      onChange={evt => {
                        setValidationError(null)
                        if (evt.target.value === '__create_new__') {
                          openQuickLedgerModal(e.id)
                        } else {
                          setEntries(entries.map(x => x.id === e.id ? { ...x, ledger_id: evt.target.value } : x))
                        }
                      }}
                    >
                      <option value="">Select Ledger...</option>
                      <option value="__create_new__" className="font-bold text-emerald-600 dark:text-emerald-400">+ Create New Ledger...</option>
                      {sortedLedgers.map(l => <option key={l.ledger_id} value={l.ledger_id}>{l.name}</option>)}
                    </select>
                    
                    <button 
                      type="button" 
                      onClick={() => openQuickLedgerModal(e.id)} 
                      title="Create New Ledger"
                      className="px-2.5 h-10 bg-slate-100 dark:bg-slate-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 hover:text-emerald-600 text-slate-500 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold flex items-center gap-1 shrink-0 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" /> New
                    </button>
                  </div>
                  
                  <div className="relative w-44">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400">₹</span>
                    <input 
                      type="number" 
                      className="w-full h-10 pl-7 pr-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold bg-white dark:bg-slate-900" 
                      placeholder="0.00" 
                      value={e.amount} 
                      onChange={evt => handleAmountChange(e.id, evt.target.value)} 
                    />
                  </div>

                  <button 
                    onClick={() => removeEntry(e.id)} 
                    title="Remove Entry"
                    className="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              
              <button 
                onClick={addEntry} 
                className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-sm font-semibold hover:underline cursor-pointer"
              >
                <Plus className="w-4 h-4" /> Add Entry Row
              </button>
            </div>
          )}

          {isInvoiceView && (
            <div className="space-y-4">
              <h3 className="font-bold text-slate-800 dark:text-slate-200">Inventory Items</h3>
              {inventoryEntries.map((e, idx) => (
                <div key={e.id} className="flex gap-3 items-center">
                  <select 
                    className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                    value={e.stock_item_id} 
                    onChange={evt => setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value } : x))}
                  >
                    <option value="">Select Item...</option>
                    {sortedStockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}
                  </select>
                  <input type="number" className="w-24 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Qty" value={e.quantity} onChange={evt => setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, quantity: evt.target.value, amount: (parseFloat(evt.target.value||'0') * parseFloat(x.rate||'0')).toFixed(2) } : x))} />
                  <input type="number" className="w-24 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Rate" value={e.rate} onChange={evt => setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, rate: evt.target.value, amount: (parseFloat(evt.target.value||'0') * parseFloat(x.quantity||'0')).toFixed(2) } : x))} />
                  <input type="number" className="w-32 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-slate-50 dark:bg-slate-800" placeholder="Amount" value={e.amount} readOnly />
                  <button onClick={() => removeInventoryEntry(e.id)} className="p-2 text-slate-400 hover:text-rose-500 rounded-lg"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
              <button onClick={addInventoryEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline"><Plus className="w-4 h-4" /> Add Item</button>
            </div>
          )}

          {isStockJournal && (
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <h3 className="font-bold text-slate-800 dark:text-slate-200">Source (Consumption)</h3>
                {sourceEntries.map((e, idx) => (
                  <div key={e.id} className="flex gap-2 items-center">
                    <select className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" value={e.stock_item_id} onChange={evt => setSourceEntries(sourceEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value } : x))}><option value="">Item...</option>{stockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}</select>
                    <input type="number" className="w-20 h-10 px-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Qty" value={e.quantity} onChange={evt => setSourceEntries(sourceEntries.map(x => x.id === e.id ? { ...x, quantity: evt.target.value } : x))} />
                  </div>
                ))}
                <button onClick={addSourceEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline"><Plus className="w-4 h-4" /> Add Source</button>
              </div>
              <div className="space-y-4">
                <h3 className="font-bold text-slate-800 dark:text-slate-200">Destination (Production)</h3>
                {destEntries.map((e, idx) => (
                  <div key={e.id} className="flex gap-2 items-center">
                    <select className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" value={e.stock_item_id} onChange={evt => setDestEntries(destEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value } : x))}><option value="">Item...</option>{stockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}</select>
                    <input type="number" className="w-20 h-10 px-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Qty" value={e.quantity} onChange={evt => setDestEntries(destEntries.map(x => x.id === e.id ? { ...x, quantity: evt.target.value } : x))} />
                  </div>
                ))}
                <button onClick={addDestEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline"><Plus className="w-4 h-4" /> Add Destination</button>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Narration</label>
            <textarea className="w-full p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm min-h-[80px]" placeholder="Being..." value={narration} onChange={e => setNarration(e.target.value)} />
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 rounded-b-2xl">
          {isAccountingView ? (
             <div className="text-sm font-medium text-slate-600 dark:text-slate-300 flex items-center gap-4">
               <span>Total Debits: <strong className="text-slate-900 dark:text-white">₹{totals.debits.toFixed(2)}</strong></span>
               <span>Total Credits: <strong className={cn(totals.isBalanced ? "text-slate-900 dark:text-white" : "text-rose-500 font-bold")}>₹{totals.credits.toFixed(2)}</strong></span>
               {!totals.isBalanced && (
                 <span className="text-xs bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 px-2 py-0.5 rounded font-bold">
                   Unbalanced (Diff: ₹{Math.abs(totals.debits - totals.credits).toFixed(2)})
                 </span>
               )}
             </div>
          ) : <div></div>}
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="px-5 py-2.5 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-colors">Cancel</button>
            <button 
              onClick={handleSave} 
              disabled={isSaving} 
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all flex items-center gap-2 cursor-pointer"
            >
              {isSaving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save Voucher
            </button>
          </div>
        </div>

        {/* --- Quick Create Ledger Sub-Modal Overlay --- */}
        {isQuickLedgerOpen && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-in fade-in duration-150">
            <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-md shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden">
              
              {/* Quick Modal Header */}
              <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <div className="flex items-center gap-2">
                  <FolderPlus className="w-5 h-5 text-emerald-600" />
                  <h3 className="font-bold text-slate-900 dark:text-white">Quick Create Ledger</h3>
                </div>
                <button onClick={() => setIsQuickLedgerOpen(false)} className="p-1.5 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg"><X className="w-4 h-4" /></button>
              </div>

              {/* Quick Modal Form Body */}
              <div className="p-5 space-y-4">
                {quickLedgerError && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs font-medium rounded-lg">
                    {quickLedgerError}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Ledger Name *</label>
                  <input 
                    type="text" 
                    autoFocus
                    placeholder="e.g. ICICI Bank, Ramesh Traders, Office Rent" 
                    className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                    value={quickName}
                    onChange={e => setQuickName(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Under Account Group *</label>
                  <select 
                    className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                    value={quickGroupId}
                    onChange={e => setQuickGroupId(e.target.value)}
                  >
                    <option value="">Select Group...</option>
                    {sortedGroups.map(g => (
                      <option key={g.group_id} value={g.group_id}>{g.name}</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Opening Balance</label>
                    <input 
                      type="number" 
                      placeholder="0.00" 
                      className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickOpeningBalance}
                      onChange={e => setQuickOpeningBalance(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Type</label>
                    <select 
                      className="w-full h-10 px-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-bold"
                      value={quickOpeningBalanceType}
                      onChange={e => setQuickOpeningBalanceType(e.target.value as 'Dr' | 'Cr')}
                    >
                      <option value="Dr">Dr</option>
                      <option value="Cr">Cr</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Quick Modal Footer */}
              <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex justify-end gap-2">
                <button 
                  type="button" 
                  onClick={() => setIsQuickLedgerOpen(false)} 
                  className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg"
                >
                  Cancel
                </button>
                <button 
                  type="button" 
                  onClick={handleSaveQuickLedger} 
                  disabled={isCreatingLedger}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow flex items-center gap-1.5 cursor-pointer"
                >
                  {isCreatingLedger && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save & Select
                </button>
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  )
}
