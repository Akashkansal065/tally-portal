'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { X, Search, ChevronDown, Plus, Trash2, Calendar, FileText, IndianRupee, Loader2, AlertCircle, FolderPlus, PackagePlus, Box, Zap, Landmark, CreditCard, QrCode, Percent, ShieldCheck, Info, Settings2 } from 'lucide-react'
import { cn, formatCurrency } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { toast } from 'sonner'
import VoucherConfigurationModal, { VoucherConfiguration } from './VoucherConfigurationModal'

export type VoucherFormModalProps = {
  isOpen: boolean
  onClose: () => void
  onSave: (data: any, voucherId?: number | null) => Promise<void>
  isSaving: boolean
  ledgers: any[]
  voucherTypes: any[]
  editVoucher?: any | null
  onLedgerCreated?: (newLedger: any) => void
  onItemCreated?: (newItem: any) => void
}

export default function VoucherFormModal({
  isOpen,
  onClose,
  onSave,
  isSaving,
  ledgers,
  voucherTypes,
  editVoucher,
  onLedgerCreated,
  onItemCreated
}: VoucherFormModalProps) {
  const { token } = useAuth()
  // 1. Basic Form States
  const [selectedType, setSelectedType] = useState<any>(null)
  const [voucherDate, setVoucherDate] = useState(new Date().toISOString().slice(0, 10))
  const [refNumber, setRefNumber] = useState('')
  const [narration, setNarration] = useState('')
  const [status, setStatus] = useState('confirmed')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [showRefInfo, setShowRefInfo] = useState(false)
  
  // Voucher F12 Configuration States
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false)
  const [voucherConfig, setVoucherConfig] = useState<VoucherConfiguration | null>(null)

  // Fetch F12 Configuration when voucher type is selected
  useEffect(() => {
    if (selectedType?.voucher_type_id && token) {
      fetch(`${API_BASE}/voucher-type/${selectedType.voucher_type_id}/configuration`, {
        headers: authHeaders(token),
      })
        .then(r => r.json())
        .then(data => {
          if (data && !data.detail) {
            setVoucherConfig(data)
          }
        })
        .catch(console.error)
    }
  }, [selectedType?.voucher_type_id, token])

  const handleSaveConfig = async (updated: VoucherConfiguration) => {
    if (!selectedType?.voucher_type_id || !token) return
    const res = await fetch(`${API_BASE}/voucher-type/${selectedType.voucher_type_id}/configuration`, {
      method: 'PUT',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updated),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to save configuration')
    }
    const saved = await res.json()
    setVoucherConfig(saved)
  }
  
  // 2. Ledgers State & Sync
  const [localLedgers, setLocalLedgers] = useState<any[]>(ledgers || [])

  useEffect(() => {
    const list = ledgers || []
    setLocalLedgers(list)
    if (editVoucher && list.length > 0) {
      if (editVoucher.party_ledger_id) {
        setPartyLedgerId(String(editVoucher.party_ledger_id))
      } else if (editVoucher.party_name) {
        const match = list.find(l => (l.name || '').trim().toLowerCase() === (editVoucher.party_name || '').trim().toLowerCase())
        if (match) setPartyLedgerId(String(match.ledger_id))
      }
    }
  }, [ledgers, editVoucher])

  // 3. Accounting View States
  const [entries, setEntries] = useState([
    { id: 1, ledger_id: '', type: 'Debit', amount: '', cost_center_id: '', bank_allocations: [] as any[] },
    { id: 2, ledger_id: '', type: 'Credit', amount: '', cost_center_id: '', bank_allocations: [] as any[] }
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
  const [uomsList, setUomsList] = useState<any[]>([])
  const [stockGroupsList, setStockGroupsList] = useState<any[]>([])

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

  const wasOpenRef = React.useRef(false)

  // 8. Quick Stock Item Creation Sub-Modal States
  const [isQuickItemOpen, setIsQuickItemOpen] = useState(false)
  const [quickItemTarget, setQuickItemTarget] = useState<{ type: 'inventory' | 'source' | 'dest', id?: number | 'new' } | null>(null)
  const [quickItemName, setQuickItemName] = useState('')
  const [quickItemUnitId, setQuickItemUnitId] = useState<string>('')
  const [quickItemStockGroupId, setQuickItemStockGroupId] = useState<string>('')
  const [quickItemHsn, setQuickItemHsn] = useState('')
  const [quickItemGstRate, setQuickItemGstRate] = useState('18')
  const [quickItemSellingPrice, setQuickItemSellingPrice] = useState('')
  const [quickItemCostPrice, setQuickItemCostPrice] = useState('')
  const [quickItemOpeningQty, setQuickItemOpeningQty] = useState('')
  const [quickItemOpeningRate, setQuickItemOpeningRate] = useState('')
  const [isCreatingItem, setIsCreatingItem] = useState(false)
  const [quickItemError, setQuickItemError] = useState<string | null>(null)

  // 9. Quick Unit of Measure (UOM) Sub-Modal States
  const [isQuickUnitOpen, setIsQuickUnitOpen] = useState(false)
  const [quickUnitType, setQuickUnitType] = useState<'simple' | 'compound'>('simple')
  const [quickUnitSymbol, setQuickUnitSymbol] = useState('')
  const [quickUnitFormalName, setQuickUnitFormalName] = useState('')
  const [quickUnitDecimalPlaces, setQuickUnitDecimalPlaces] = useState('0')
  const [quickCompoundFirstUnitId, setQuickCompoundFirstUnitId] = useState('')
  const [quickCompoundConversion, setQuickCompoundConversion] = useState('6')
  const [quickCompoundSecondUnitId, setQuickCompoundSecondUnitId] = useState('')
  const [isCreatingUnit, setIsCreatingUnit] = useState(false)
  const [quickUnitError, setQuickUnitError] = useState<string | null>(null)

  // 10. Interactive Banking Allocations Modal States
  const [isBankingModalOpen, setIsBankingModalOpen] = useState(false)
  const [activeBankingEntryId, setActiveBankingEntryId] = useState<number | null>(null)
  const [bankingTxType, setBankingTxType] = useState('Cheque')
  const [bankingVpa, setBankingVpa] = useState('')
  const [bankingInstNumber, setBankingInstNumber] = useState('')
  const [bankingInstDate, setBankingInstDate] = useState(new Date().toISOString().slice(0, 10))
  const [bankingChequeCrossing, setBankingChequeCrossing] = useState('A/c Payee')
  const [bankingTransferMode, setBankingTransferMode] = useState('NEFT')
  const [bankingBankName, setBankingBankName] = useState('')
  const [bankingAccountNumber, setBankingAccountNumber] = useState('')
  const [bankingIfsc, setBankingIfsc] = useState('')
  const [bankingFavouring, setBankingFavouring] = useState('')

  const isBankLedger = (ledgerId: string | number) => {
    if (!ledgerId) return false
    const led = localLedgers.find(l => String(l.ledger_id) === String(ledgerId))
    if (!led) return false
    const grp = groupsList.find(g => g.group_id === led.group_id)
    const grpName = (grp?.name || '').toLowerCase()
    const ledName = (led?.name || '').toLowerCase()
    return grpName.includes('bank') || ledName.includes('bank')
  }

  const openBankingModal = (entryId: number) => {
    setActiveBankingEntryId(entryId)
    const entry = entries.find(e => e.id === entryId)
    const existing = entry?.bank_allocations?.[0]
    if (existing) {
      setBankingTxType(existing.transaction_type || 'Cheque')
      setBankingVpa(existing.virtual_payment_address || '')
      setBankingInstNumber(existing.instrument_number || '')
      setBankingInstDate(existing.instrument_date || voucherDate)
      setBankingChequeCrossing(existing.cheque_cross_comment || 'A/c Payee')
      setBankingTransferMode(existing.transfer_mode || 'NEFT')
      setBankingBankName(existing.bank_name || '')
      setBankingAccountNumber(existing.account_number || '')
      setBankingIfsc(existing.ifs_code || '')
      setBankingFavouring(existing.payment_favouring || '')
    } else {
      setBankingTxType('Cheque')
      setBankingVpa('')
      setBankingInstNumber('')
      setBankingInstDate(voucherDate)
      setBankingChequeCrossing('A/c Payee')
      setBankingTransferMode('NEFT')
      setBankingBankName('')
      setBankingAccountNumber('')
      setBankingIfsc('')
      setBankingFavouring('')
    }
    setIsBankingModalOpen(true)
  }

  const saveBankingAllocation = () => {
    if (activeBankingEntryId === null) return
    setEntries(entries.map(x => {
      if (x.id === activeBankingEntryId) {
        return {
          ...x,
          bank_allocations: [{
            transaction_type: bankingTxType,
            virtual_payment_address: bankingTxType === 'UPI' ? bankingVpa : undefined,
            instrument_number: bankingInstNumber || undefined,
            instrument_date: bankingInstDate || undefined,
            cheque_cross_comment: (bankingTxType === 'Cheque' || bankingTxType === 'Cheque/DD') ? bankingChequeCrossing : undefined,
            transfer_mode: bankingTxType === 'Inter Bank Transfer' ? bankingTransferMode : undefined,
            bank_name: bankingBankName || undefined,
            account_number: bankingAccountNumber || undefined,
            ifs_code: bankingIfsc || undefined,
            payment_favouring: bankingFavouring || undefined,
            amount: parseFloat(x.amount || '0')
          }]
        }
      }
      return x
    }))
    setIsBankingModalOpen(false)
    toast.success('Banking details updated for entry row')
  }

  const calculateItemAmount = (qty: string, rate: string, disc: string) => {
    const q = parseFloat(qty || '0')
    const r = parseFloat(rate || '0')
    const d = parseFloat(disc || '0')
    const gross = q * r
    const discountAmt = gross * (d / 100)
    return Math.max(0, gross - discountAmt).toFixed(2)
  }

  // 10. Derived Sorted Lists (A-Z)
  const sortedLedgers = useMemo(() => {
    return [...localLedgers].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [localLedgers])

  const sortedGroups = useMemo(() => {
    return [...groupsList].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [groupsList])

  const sortedStockItems = useMemo(() => {
    return [...stockItems].sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [stockItems])

  const sortedStockGroups = useMemo(() => {
    return [...stockGroupsList]
      .filter(g => (g.name || '').trim().toLowerCase() !== 'primary')
      .sort((a, b) => (a.name || '').localeCompare(b.name || '', undefined, { sensitivity: 'base' }))
  }, [stockGroupsList])

  const sortedUoms = useMemo(() => {
    return [...uomsList]
      .filter(u => (u.symbol || '').trim().toLowerCase() !== 'not applicable')
      .sort((a, b) => (a.symbol || '').localeCompare(b.symbol || '', undefined, { sensitivity: 'base' }))
  }, [uomsList])

  const simpleUoms = useMemo(() => {
    return sortedUoms.filter(u => u.is_simple_unit !== false)
  }, [sortedUoms])

  const activeVoucherTypes = useMemo(() => {
    return voucherTypes.filter(t => t.is_active !== false)
  }, [voucherTypes])

  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      wasOpenRef.current = true

      if (editVoucher) {
        // Edit / Alter mode: Prepopulate from existing voucher
        const vtype = voucherTypes.find(t => 
          t.voucher_type_id === editVoucher.voucher_type_id || 
          (t.name || '').toLowerCase() === (editVoucher.voucher_type || editVoucher.voucher_type_name || '').toLowerCase()
        )
        setSelectedType(vtype || (activeVoucherTypes.length > 0 ? activeVoucherTypes[0] : null))
        setVoucherDate(
          editVoucher.date || editVoucher.voucher_date
            ? String(editVoucher.date || editVoucher.voucher_date).slice(0, 10)
            : new Date().toISOString().slice(0, 10)
        )
        setRefNumber(editVoucher.reference_number || '')
        setNarration(editVoucher.narration || '')
        setStatus(editVoucher.status || 'confirmed')
        setValidationError(null)
        setPartyLedgerId(editVoucher.party_ledger_id ? String(editVoucher.party_ledger_id) : '')
        setOriginalVoucherId(editVoucher.original_voucher_id ? String(editVoucher.original_voucher_id) : '')

        // Accounting Entries
        const rawEntries = editVoucher.entries || editVoucher.accounts || []
        if (rawEntries.length > 0) {
          setEntries(rawEntries.map((e: any, idx: number) => {
            const dr = parseFloat(e.debit_amount || (e.entry_type === 'Debit' ? e.amount : '0') || '0')
            const cr = parseFloat(e.credit_amount || (e.entry_type === 'Credit' ? e.amount : '0') || '0')
            const isDr = dr > 0 || e.entry_type === 'Debit'
            return {
              id: idx + 1,
              ledger_id: String(e.ledger_id || ''),
              type: isDr ? 'Debit' : 'Credit',
              amount: String(isDr ? (dr || e.amount || '') : (cr || e.amount || '')),
              cost_center_id: e.cost_center_id ? String(e.cost_center_id) : '',
              bank_allocations: e.bank_allocations || []
            }
          }))
          setNextId(rawEntries.length + 1)
        } else {
          setEntries([
            { id: 1, ledger_id: '', type: 'Debit', amount: '', cost_center_id: '', bank_allocations: [] },
            { id: 2, ledger_id: '', type: 'Credit', amount: '', cost_center_id: '', bank_allocations: [] }
          ])
          setNextId(3)
        }

        // Inventory Entries
        const rawInv = editVoucher.inventory_entries || editVoucher.inventory || []
        if (rawInv.length > 0) {
          setInventoryEntries(rawInv.map((inv: any, idx: number) => ({
            id: idx + 1,
            stock_item_id: String(inv.stock_item_id || ''),
            quantity: String(inv.quantity || '1'),
            rate: String(inv.rate || ''),
            discount_percent: String(inv.discount_percent || '0'),
            amount: String(inv.amount || '0.00')
          })))
          setNextInvId(rawInv.length + 1)
        } else {
          setInventoryEntries([
            { id: 1, stock_item_id: '', quantity: '1', rate: '', discount_percent: '0', amount: '0.00' }
          ])
          setNextInvId(2)
        }
      } else {
        // Create mode
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
          { id: 1, ledger_id: '', type: 'Debit', amount: '', cost_center_id: '', bank_allocations: [] },
          { id: 2, ledger_id: '', type: 'Credit', amount: '', cost_center_id: '', bank_allocations: [] }
        ])
        setNextId(3)
        setInventoryEntries([
          { id: 1, stock_item_id: '', quantity: '1', rate: '', discount_percent: '0', amount: '0.00' }
        ])
        setNextInvId(2)
        setSourceEntries([
          { id: 1, stock_item_id: '', godown_id: '', quantity: '1', rate: '', amount: '0.00' }
        ])
        setDestEntries([
          { id: 1, stock_item_id: '', godown_id: '', quantity: '1', rate: '', amount: '0.00' }
        ])
      }
      
      // Fetch items, godowns, groups, uoms, stock groups
      fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => {
          const items = Array.isArray(data) ? data : []
          setStockItems(items)
          if (editVoucher) {
            const rawInv = editVoucher.inventory_entries || editVoucher.inventory || []
            setInventoryEntries(prev => prev.map((e, idx) => {
              if ((!e.stock_item_id || e.stock_item_id === '') && rawInv[idx]) {
                const nameToMatch = rawInv[idx].item || rawInv[idx].stock_item_name
                const match = items.find(si => (si.name || '').trim().toLowerCase() === (nameToMatch || '').trim().toLowerCase())
                if (match) return { ...e, stock_item_id: String(match.stock_item_id) }
              }
              return e
            }))
          }
        })
        .catch(console.error)
      fetch(`${API_BASE}/inventory/godowns`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setGodowns(Array.isArray(data) ? data : []))
        .catch(console.error)
      fetch(`${API_BASE}/ledgers/groups`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setGroupsList(Array.isArray(data) ? data : []))
        .catch(console.error)
      fetch(`${API_BASE}/inventory/uoms`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setUomsList(Array.isArray(data) ? data : []))
        .catch(console.error)
      fetch(`${API_BASE}/inventory/groups`, { headers: authHeaders(token) })
        .then(r => r.json())
        .then(data => setStockGroupsList(Array.isArray(data) ? data : []))
        .catch(console.error)
    } else if (!isOpen) {
      wasOpenRef.current = false
    }
  }, [isOpen, token, editVoucher])

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

    setEntries([...entries, { id: nextId, ledger_id: '', type: newType, amount: autoAmount, cost_center_id: '', bank_allocations: [] }])
    setNextId(nextId + 1)
  }

  const removeEntry = (id: number) => {
    if (entries.length <= 2) {
      setEntries(entries.map(e => e.id === id ? { ...e, ledger_id: '', amount: '', cost_center_id: '', bank_allocations: [] } : e))
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
    setInventoryEntries([...inventoryEntries, { id: nextInvId, stock_item_id: '', quantity: '1', rate: '', discount_percent: '0', amount: '' }])
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

  // --- Inline Quick Stock Item Creation Logic ---
  const openQuickItemModal = (type: 'inventory' | 'source' | 'dest', id?: number | 'new') => {
    setQuickItemTarget({ type, id: id ?? 'new' })
    setQuickItemName('')
    setQuickItemHsn('')
    setQuickItemGstRate('18')
    setQuickItemSellingPrice('')
    setQuickItemCostPrice('')
    setQuickItemOpeningQty('')
    setQuickItemOpeningRate('')
    setQuickItemError(null)

    const defaultUom = uomsList.find(u => ['nos', 'pcs', 'unit', 'pkt'].includes((u.symbol || '').toLowerCase())) || uomsList[0]
    setQuickItemUnitId(defaultUom?.unit_id ? String(defaultUom.unit_id) : '')
    setQuickItemStockGroupId('')

    setIsQuickItemOpen(true)
  }

  const handleSaveQuickItem = async () => {
    setQuickItemError(null)
    if (!quickItemName.trim()) {
      setQuickItemError("Please enter an item name.")
      return
    }

    setIsCreatingItem(true)
    try {
      const payload: any = {
        name: quickItemName.trim(),
        unit_id: quickItemUnitId ? parseInt(quickItemUnitId) : undefined,
        stock_group_id: quickItemStockGroupId ? parseInt(quickItemStockGroupId) : undefined,
        hsn_code: quickItemHsn.trim() || undefined,
        gst_rate_percent: parseFloat(quickItemGstRate || '0'),
        standard_selling_price: quickItemSellingPrice ? parseFloat(quickItemSellingPrice) : undefined,
        standard_cost_price: quickItemCostPrice ? parseFloat(quickItemCostPrice) : undefined,
        opening_qty: parseFloat(quickItemOpeningQty || '0'),
        opening_rate: parseFloat(quickItemOpeningRate || '0'),
        is_active: true
      }

      const res = await fetch(`${API_BASE}/inventory/items`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(token)
        },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to create stock item')
      }

      const newItem = await res.json()

      // Update local stock items list
      setStockItems(prev => [...prev, newItem])
      if (onItemCreated) {
        onItemCreated(newItem)
      }

      // Auto-select in target row or append new row without overwriting populated rows
      if (quickItemTarget) {
        const rateToFill = isInvoiceView && parentType.toLowerCase() === 'sales'
          ? (newItem.standard_selling_price ? String(newItem.standard_selling_price) : '')
          : (newItem.standard_cost_price ? String(newItem.standard_cost_price) : (newItem.standard_selling_price ? String(newItem.standard_selling_price) : ''))

        if (quickItemTarget.type === 'inventory') {
          setInventoryEntries(prev => {
            const targetId = quickItemTarget.id
            // If a specific row ID was targeted and exists, update that specific row
            if (typeof targetId === 'number') {
              const rowExists = prev.some(x => x.id === targetId)
              if (rowExists) {
                return prev.map(x => {
                  if (x.id === targetId) {
                    const rate = rateToFill || x.rate || ''
                    const qty = x.quantity || '1'
                    const amount = rate ? (parseFloat(qty || '0') * parseFloat(rate || '0')).toFixed(2) : '0.00'
                    return { ...x, stock_item_id: String(newItem.stock_item_id), rate, quantity: qty, amount }
                  }
                  return x
                })
              }
            }

            // If header "+ Quick Create Item" was clicked or targetId is 'new':
            // Check if there is an unselected empty row
            const emptyIdx = prev.findIndex(x => !x.stock_item_id)
            if (emptyIdx !== -1) {
              return prev.map((x, idx) => {
                if (idx === emptyIdx) {
                  const rate = rateToFill || x.rate || ''
                  const qty = x.quantity || '1'
                  const amount = rate ? (parseFloat(qty || '0') * parseFloat(rate || '0')).toFixed(2) : '0.00'
                  return { ...x, stock_item_id: String(newItem.stock_item_id), rate, quantity: qty, amount }
                }
                return x
              })
            }

            // Otherwise, append a brand new row with the newly created item!
            const nextId = prev.length > 0 ? Math.max(...prev.map(x => x.id)) + 1 : 1
            const rate = rateToFill || ''
            const qty = '1'
            const amount = rate ? (parseFloat(qty) * parseFloat(rate)).toFixed(2) : '0.00'
            return [
              ...prev,
              { id: nextId, stock_item_id: String(newItem.stock_item_id), quantity: qty, rate, amount }
            ]
          })
        } else if (quickItemTarget.type === 'source') {
          setSourceEntries(prev => {
            const targetId = quickItemTarget.id
            if (typeof targetId === 'number' && prev.some(x => x.id === targetId)) {
              return prev.map(x => x.id === targetId ? { ...x, stock_item_id: String(newItem.stock_item_id) } : x)
            }
            const emptyIdx = prev.findIndex(x => !x.stock_item_id)
            if (emptyIdx !== -1) {
              return prev.map((x, idx) => idx === emptyIdx ? { ...x, stock_item_id: String(newItem.stock_item_id) } : x)
            }
            const nextId = prev.length > 0 ? Math.max(...prev.map(x => x.id)) + 1 : 1
            return [...prev, { id: nextId, stock_item_id: String(newItem.stock_item_id), godown_id: '', quantity: '1', rate: '', amount: '0.00' }]
          })
        } else if (quickItemTarget.type === 'dest') {
          setDestEntries(prev => {
            const targetId = quickItemTarget.id
            if (typeof targetId === 'number' && prev.some(x => x.id === targetId)) {
              return prev.map(x => x.id === targetId ? { ...x, stock_item_id: String(newItem.stock_item_id) } : x)
            }
            const emptyIdx = prev.findIndex(x => !x.stock_item_id)
            if (emptyIdx !== -1) {
              return prev.map((x, idx) => idx === emptyIdx ? { ...x, stock_item_id: String(newItem.stock_item_id) } : x)
            }
            const nextId = prev.length > 0 ? Math.max(...prev.map(x => x.id)) + 1 : 1
            return [...prev, { id: nextId, stock_item_id: String(newItem.stock_item_id), godown_id: '', quantity: '1', rate: '', amount: '0.00' }]
          })
        }
      }

      toast.success(`Stock item "${newItem.name}" registered & synced with Tally!`)
      setIsQuickItemOpen(false)
    } catch (e: any) {
      setQuickItemError(e.message || "Failed to create stock item")
    } finally {
      setIsCreatingItem(false)
    }
  }

  // --- Inline Quick Unit of Measure (UOM) Creation Logic ---
  const openQuickUnitModal = () => {
    setQuickUnitType('simple')
    setQuickUnitSymbol('')
    setQuickUnitFormalName('')
    setQuickUnitDecimalPlaces('0')

    const firstUom = simpleUoms.find(u => ['set', 'box', 'pkt', 'doz'].includes((u.symbol || '').toLowerCase())) || simpleUoms[0]
    const secondUom = simpleUoms.find(u => ['nos', 'pcs', 'unit', 'gm', 'kg'].includes((u.symbol || '').toLowerCase()) && u.unit_id !== firstUom?.unit_id) || simpleUoms[1] || simpleUoms[0]

    setQuickCompoundFirstUnitId(firstUom?.unit_id ? String(firstUom.unit_id) : '')
    setQuickCompoundConversion('6')
    setQuickCompoundSecondUnitId(secondUom?.unit_id ? String(secondUom.unit_id) : '')
    setQuickUnitError(null)
    setIsQuickUnitOpen(true)
  }

  const handleSaveQuickUnit = async () => {
    setQuickUnitError(null)
    setIsCreatingUnit(true)
    try {
      let payload: any = {}

      if (quickUnitType === 'simple') {
        if (!quickUnitSymbol.trim()) {
          setQuickUnitError("Please enter a unit symbol (e.g. PCS, BOX, SET).")
          setIsCreatingUnit(false)
          return
        }
        payload = {
          symbol: quickUnitSymbol.trim(),
          name: quickUnitSymbol.trim(),
          original_name: quickUnitFormalName.trim() || undefined,
          decimal_places: parseInt(quickUnitDecimalPlaces || '0'),
          is_simple_unit: true
        }
      } else {
        if (!quickCompoundFirstUnitId || !quickCompoundSecondUnitId || !quickCompoundConversion) {
          setQuickUnitError("Please select both units and enter a conversion quantity (e.g. 6 or 4).")
          setIsCreatingUnit(false)
          return
        }
        const conv = parseFloat(quickCompoundConversion)
        if (isNaN(conv) || conv <= 0) {
          setQuickUnitError("Conversion quantity must be a positive number (e.g. 6 or 4).")
          setIsCreatingUnit(false)
          return
        }
        if (quickCompoundFirstUnitId === quickCompoundSecondUnitId) {
          setQuickUnitError("First unit and second unit cannot be the same.")
          setIsCreatingUnit(false)
          return
        }
        payload = {
          is_simple_unit: false,
          base_unit_id: parseInt(quickCompoundFirstUnitId),
          conversion_factor: conv,
          additional_unit_id: parseInt(quickCompoundSecondUnitId),
          decimal_places: 0
        }
      }

      const res = await fetch(`${API_BASE}/inventory/uoms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(token)
        },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to create unit of measure')
      }

      const newUom = await res.json()

      // Update local UOMs list
      setUomsList(prev => [...prev, newUom])

      // Auto-select in the quick stock item form
      setQuickItemUnitId(String(newUom.unit_id))

      toast.success(`Unit "${newUom.symbol || newUom.name}" registered & synced with Tally!`)
      setIsQuickUnitOpen(false)
    } catch (e: any) {
      setQuickUnitError(e.message || "Failed to create unit")
    } finally {
      setIsCreatingUnit(false)
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
        credit_amount: e.type === 'Credit' ? parseFloat(e.amount) : 0,
        cost_center_id: e.cost_center_id ? parseInt(e.cost_center_id) : null,
        bank_allocations: e.bank_allocations && e.bank_allocations.length > 0 ? e.bank_allocations : undefined
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

      const invPayload = validInv.map(e => {
        const qty = parseFloat(e.quantity || '0')
        const rate = parseFloat(e.rate || '0')
        const disc = parseFloat(e.discount_percent || '0')
        const gross = qty * rate
        const discAmt = gross * (disc / 100)
        return {
          stock_item_id: parseInt(e.stock_item_id),
          quantity: qty,
          rate: rate,
          amount: parseFloat(e.amount || (gross - discAmt).toFixed(2)),
          discount_percent: disc,
          discount_amount: discAmt
        }
      })
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
    
    onSave(payload, editVoucher?.voucher_id || null)
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl border border-slate-200 dark:border-slate-800 relative overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">
              {editVoucher ? `Alter Voucher #${editVoucher.voucher_number || editVoucher.voucher_id}` : 'Create Voucher'}
            </h2>
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
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsConfigModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 border border-emerald-200 dark:border-emerald-500/30 rounded-lg transition-all shadow-sm cursor-pointer"
              title="Configure Voucher Settings"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>Configuration</span>
            </button>
            <button onClick={onClose} className="p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"><X className="w-5 h-5" /></button>
          </div>
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
            <div className="relative">
              <div className="flex items-center gap-1.5 mb-1">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Reference No.</label>
                <div className="relative inline-block">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowRefInfo(prev => !prev)
                    }}
                    className={cn(
                      "p-1 rounded-md transition-colors cursor-pointer flex items-center justify-center",
                      showRefInfo 
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" 
                        : "text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                    )}
                    title="Click for Reference No. details"
                  >
                    <Info className="w-4 h-4" />
                  </button>

                  {/* Popover / Dropdown below the icon */}
                  {showRefInfo && (
                    <div 
                      className="absolute right-0 top-full mt-2 w-80 p-4 bg-slate-900 text-white rounded-xl shadow-2xl border border-slate-700 z-50 animate-in fade-in zoom-in-95 duration-150"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
                        <span className="font-bold text-xs text-emerald-400 flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5" /> What is Reference No.?
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowRefInfo(false)}
                          className="text-slate-400 hover:text-white p-0.5"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="space-y-2.5 text-[11px] text-slate-300 leading-relaxed">
                        <p>
                          <strong className="text-white">Purchase Vouchers:</strong> Enter the <span className="text-emerald-400 font-semibold">Supplier's Tax Invoice No.</span> for GSTR-2B ITC matching & vendor bill-by-bill tracking.
                        </p>
                        <p>
                          <strong className="text-white">Sales Invoices:</strong> Enter the <span className="text-emerald-400 font-semibold">Buyer's PO No.</span> or Challan No. (prints under "Buyer's Order No.").
                        </p>
                        <p>
                          <strong className="text-white">Receipts / Payments:</strong> Enter the <span className="text-emerald-400 font-semibold">Bank UTR or Cheque No.</span> for bank reconciliation (BRS).
                        </p>
                      </div>
                      <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
                        <span>Syncs to Tally as &lt;REFERENCE&gt;</span>
                        <button
                          type="button"
                          onClick={() => setShowRefInfo(false)}
                          className="text-emerald-400 font-bold hover:underline cursor-pointer"
                        >
                          Got it
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <input 
                type="text" 
                className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium" 
                placeholder={
                  parentType.toLowerCase() === 'purchase'
                    ? "Supplier Bill No. (e.g. INV-892)"
                    : parentType.toLowerCase() === 'sales'
                    ? "Buyer PO No. (e.g. PO-2026-01)"
                    : "Ref / UTR / Cheque No."
                }
                value={refNumber} 
                onChange={e => setRefNumber(e.target.value)} 
              />
              <p className="text-[10px] text-slate-400 mt-1">
                {parentType.toLowerCase() === 'purchase'
                  ? "Vendor's original invoice number for GSTR-2B ITC claiming"
                  : parentType.toLowerCase() === 'sales'
                  ? "Customer's PO / Order reference number"
                  : "External transaction / bank UTR reference"}
              </p>
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
              
              {/* Column Headers */}
              <div className="flex gap-3 items-center text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider px-1">
                <div className="w-24">Type ({voucherConfig?.use_cr_dr === false ? 'By/To' : 'Dr/Cr'})</div>
                <div className="flex-1">Particulars / Ledger Account</div>
                <div className="w-44 text-right pr-4">Amount (₹)</div>
                <div className="w-8"></div>
              </div>

              {entries.map((e, idx) => (
                <div key={e.id} className="space-y-1">
                  <div className="flex gap-3 items-center">
                    <select 
                      className="w-24 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold bg-white dark:bg-slate-900" 
                      value={e.type} 
                      onChange={evt => {
                        setValidationError(null)
                        setEntries(entries.map(x => x.id === e.id ? { ...x, type: evt.target.value } : x))
                      }}
                    >
                      <option value="Debit">{voucherConfig?.use_cr_dr === false ? 'By' : 'Dr'}</option>
                      <option value="Credit">{voucherConfig?.use_cr_dr === false ? 'To' : 'Cr'}</option>
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

                  {/* Bank Allocation Trigger for Bank Ledgers */}
                  {isBankLedger(e.ledger_id) && (
                    <div className="flex items-center gap-2 pl-28 pt-0.5">
                      <button
                        type="button"
                        onClick={() => openBankingModal(e.id)}
                        className={cn(
                          "text-xs px-2.5 py-1 rounded-lg font-semibold flex items-center gap-1.5 transition-all border cursor-pointer",
                          e.bank_allocations && e.bank_allocations.length > 0
                            ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700 shadow-xs"
                            : "bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-700 border-dashed hover:bg-blue-100 dark:hover:bg-blue-900/40"
                        )}
                      >
                        <Landmark className="w-3.5 h-3.5" />
                        {e.bank_allocations && e.bank_allocations.length > 0 ? (
                          <span>Banking: <strong>{e.bank_allocations[0].transaction_type}</strong> ({e.bank_allocations[0].virtual_payment_address || e.bank_allocations[0].instrument_number || e.bank_allocations[0].transfer_mode || 'Configured'}) - Click to Edit</span>
                        ) : (
                          <span>+ Add Banking Allocations (UPI / Cheque / NEFT)</span>
                        )}
                      </button>
                    </div>
                  )}
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
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-800 dark:text-slate-200">Inventory Items</h3>
                <button 
                  type="button" 
                  onClick={() => openQuickItemModal('inventory', 'new')} 
                  className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <PackagePlus className="w-3.5 h-3.5" /> + Quick Create Item
                </button>
              </div>

              {/* Column Headers */}
              <div className="flex gap-3 items-center text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider px-1">
                <div className="flex-1">Item Description / Stock Item</div>
                <div className="w-20 text-center">Qty</div>
                <div className="w-24 text-right pr-2">Rate (₹)</div>
                <div className="w-20 text-center">Disc %</div>
                <div className="w-28 text-right pr-4">Amount (₹)</div>
                <div className="w-8"></div>
              </div>

              {inventoryEntries.map((e, idx) => (
                <div key={e.id} className="flex gap-3 items-center">
                  <div className="flex-1 flex gap-2">
                    <select 
                      className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                      value={e.stock_item_id} 
                      onChange={evt => {
                        if (evt.target.value === '__create_new__') {
                          openQuickItemModal('inventory', e.id)
                        } else {
                          const chosenItem = stockItems.find(si => String(si.stock_item_id) === evt.target.value)
                          const rateToFill = isInvoiceView && parentType.toLowerCase() === 'sales'
                            ? (chosenItem?.standard_selling_price ? String(chosenItem.standard_selling_price) : e.rate)
                            : (chosenItem?.standard_cost_price ? String(chosenItem.standard_cost_price) : (chosenItem?.standard_selling_price ? String(chosenItem.standard_selling_price) : e.rate))
                          const qty = e.quantity || '1'
                          const amount = calculateItemAmount(qty, rateToFill, e.discount_percent || '0')
                          setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value, rate: rateToFill, quantity: qty, amount } : x))
                        }
                      }}
                    >
                      <option value="">Select Item...</option>
                      <option value="__create_new__" className="font-bold text-emerald-600 dark:text-emerald-400">+ Create New Item (Syncs to Tally)...</option>
                      {sortedStockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}
                    </select>

                    <button 
                      type="button" 
                      onClick={() => openQuickItemModal('inventory', e.id)} 
                      title="Create New Stock Item"
                      className="px-2.5 h-10 bg-slate-100 dark:bg-slate-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 hover:text-emerald-600 text-slate-500 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold flex items-center gap-1 shrink-0 transition-colors"
                    >
                      <Plus className="w-3.5 h-3.5" /> New
                    </button>
                  </div>

                  <input 
                    type="number" 
                    className="w-20 h-10 px-2.5 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" 
                    placeholder="Qty" 
                    value={e.quantity} 
                    onChange={evt => {
                      const qty = evt.target.value
                      const amount = calculateItemAmount(qty, e.rate, e.discount_percent || '0')
                      setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, quantity: qty, amount } : x))
                    }} 
                  />
                  <input 
                    type="number" 
                    className="w-24 h-10 px-2.5 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" 
                    placeholder="Rate" 
                    value={e.rate} 
                    onChange={evt => {
                      const rate = evt.target.value
                      const amount = calculateItemAmount(e.quantity, rate, e.discount_percent || '0')
                      setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, rate, amount } : x))
                    }} 
                  />
                  <div className="relative w-20">
                    <input 
                      type="number" 
                      step="any"
                      min="0"
                      max="100"
                      className="w-full h-10 pl-2.5 pr-6 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                      placeholder="Disc" 
                      value={e.discount_percent || ''} 
                      onChange={evt => {
                        const disc = evt.target.value
                        const amount = calculateItemAmount(e.quantity, e.rate, disc)
                        setInventoryEntries(inventoryEntries.map(x => x.id === e.id ? { ...x, discount_percent: disc, amount } : x))
                      }} 
                    />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400 pointer-events-none">%</span>
                  </div>
                  <input type="number" className="w-28 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-slate-50 dark:bg-slate-800 font-semibold" placeholder="Amount" value={e.amount} readOnly />
                  <button onClick={() => removeInventoryEntry(e.id)} className="p-2 text-slate-400 hover:text-rose-500 rounded-lg transition-colors"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
              <button onClick={addInventoryEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline cursor-pointer"><Plus className="w-4 h-4" /> Add Item</button>
            </div>
          )}

          {isStockJournal && (
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-800 dark:text-slate-200">Source (Consumption)</h3>
                  <button 
                    type="button" 
                    onClick={() => openQuickItemModal('source', 'new')} 
                    className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Quick Item
                  </button>
                </div>
                {/* Source Column Header */}
                <div className="flex gap-2 items-center text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider px-1">
                  <div className="flex-1">Source Item</div>
                  <div className="w-20 text-center">Qty</div>
                </div>
                {sourceEntries.map((e, idx) => (
                  <div key={e.id} className="flex gap-2 items-center">
                    <select 
                      className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                      value={e.stock_item_id} 
                      onChange={evt => {
                        if (evt.target.value === '__create_new__') {
                          openQuickItemModal('source', e.id)
                        } else {
                          setSourceEntries(sourceEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value } : x))
                        }
                      }}
                    >
                      <option value="">Item...</option>
                      <option value="__create_new__" className="font-bold text-emerald-600">+ Create Item...</option>
                      {sortedStockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}
                    </select>
                    <input type="number" className="w-20 h-10 px-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Qty" value={e.quantity} onChange={evt => setSourceEntries(sourceEntries.map(x => x.id === e.id ? { ...x, quantity: evt.target.value } : x))} />
                  </div>
                ))}
                <button onClick={addSourceEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline cursor-pointer"><Plus className="w-4 h-4" /> Add Source</button>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-slate-800 dark:text-slate-200">Destination (Production)</h3>
                  <button 
                    type="button" 
                    onClick={() => openQuickItemModal('dest', 'new')} 
                    className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Quick Item
                  </button>
                </div>
                {/* Destination Column Header */}
                <div className="flex gap-2 items-center text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider px-1">
                  <div className="flex-1">Destination Item</div>
                  <div className="w-20 text-center">Qty</div>
                </div>
                {destEntries.map((e, idx) => (
                  <div key={e.id} className="flex gap-2 items-center">
                    <select 
                      className="flex-1 h-10 px-3 border border-slate-200 dark:border-slate-700 rounded-lg text-sm bg-white dark:bg-slate-900" 
                      value={e.stock_item_id} 
                      onChange={evt => {
                        if (evt.target.value === '__create_new__') {
                          openQuickItemModal('dest', e.id)
                        } else {
                          setDestEntries(destEntries.map(x => x.id === e.id ? { ...x, stock_item_id: evt.target.value } : x))
                        }
                      }}
                    >
                      <option value="">Item...</option>
                      <option value="__create_new__" className="font-bold text-emerald-600">+ Create Item...</option>
                      {sortedStockItems.map(si => <option key={si.stock_item_id} value={si.stock_item_id}>{si.name}</option>)}
                    </select>
                    <input type="number" className="w-20 h-10 px-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm" placeholder="Qty" value={e.quantity} onChange={evt => setDestEntries(destEntries.map(x => x.id === e.id ? { ...x, quantity: evt.target.value } : x))} />
                  </div>
                ))}
                <button onClick={addDestEntry} className="inline-flex items-center gap-1.5 text-emerald-600 text-sm font-semibold hover:underline cursor-pointer"><Plus className="w-4 h-4" /> Add Destination</button>
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
              {editVoucher ? 'Save Changes (Sync to Tally)' : 'Save Voucher'}
            </button>
          </div>
        </div>

        {/* --- Quick Create Ledger Sub-Modal Overlay --- */}
        {isQuickLedgerOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
              
              {/* Quick Modal Header */}
              <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/40">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-lg">
                    <FolderPlus className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Quick Create Ledger</h3>
                    <p className="text-[11px] text-slate-400">Creates ledger & auto-syncs with Tally</p>
                  </div>
                </div>
                <button 
                  type="button" 
                  onClick={() => setIsQuickLedgerOpen(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Quick Modal Body */}
              <div className="p-5 space-y-4">
                {quickLedgerError && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 text-xs rounded-xl flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{quickLedgerError}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Ledger Name *</label>
                  <input 
                    type="text" 
                    autoFocus
                    placeholder="e.g. Acme Corp / Office Supplies" 
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

        {/* --- Quick Create Stock Item Sub-Modal Overlay --- */}
        {isQuickItemOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="bg-white dark:bg-slate-900 w-full max-w-lg rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
              
              {/* Quick Modal Header */}
              <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/40">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-lg">
                    <PackagePlus className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Quick Create Stock Item</h3>
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                        <Zap className="w-3 h-3" /> Real-time Tally Sync
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">Registers item and pushes directly to Tally Prime</p>
                  </div>
                </div>
                <button 
                  type="button" 
                  onClick={() => setIsQuickItemOpen(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Quick Modal Body */}
              <div className="p-5 space-y-3.5 max-h-[70vh] overflow-y-auto">
                {quickItemError && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 text-xs rounded-xl flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{quickItemError}</span>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Item Name *</label>
                  <input 
                    type="text" 
                    autoFocus
                    placeholder="e.g. Wireless Mouse X1 / 4K Gaming Monitor" 
                    className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                    value={quickItemName}
                    onChange={e => setQuickItemName(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center justify-between mb-1.5 gap-1">
                      <label className="text-xs font-bold text-slate-700 dark:text-slate-300 truncate">Base Unit (UOM) *</label>
                      <button 
                        type="button" 
                        onClick={openQuickUnitModal}
                        className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-0.5 shrink-0 cursor-pointer"
                      >
                        <Plus className="w-3 h-3" /> New
                      </button>
                    </div>
                    <select 
                      className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemUnitId}
                      onChange={e => {
                        if (e.target.value === '__create_new_unit__') {
                          openQuickUnitModal()
                        } else {
                          setQuickItemUnitId(e.target.value)
                        }
                      }}
                    >
                      <option value="">Select Unit...</option>
                      <option value="__create_new_unit__" className="font-bold text-emerald-600 dark:text-emerald-400">+ Create New Unit...</option>
                      {sortedUoms.map(u => (
                        <option key={u.unit_id} value={u.unit_id}>
                          {u.symbol} {u.original_name ? `(${u.original_name})` : (u.name && u.name !== u.symbol ? `(${u.name})` : '')}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">Stock Group</label>
                    <select 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium truncate"
                      value={quickItemStockGroupId}
                      onChange={e => setQuickItemStockGroupId(e.target.value)}
                    >
                      <option value="">Primary</option>
                      {sortedStockGroups.map(g => (
                        <option key={g.stock_group_id} value={g.stock_group_id}>{g.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">HSN / SAC Code</label>
                    <input 
                      type="text" 
                      placeholder="e.g. 84716060" 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemHsn}
                      onChange={e => setQuickItemHsn(e.target.value)}
                    />
                  </div>

                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">GST Rate %</label>
                    <select 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold truncate"
                      value={quickItemGstRate}
                      onChange={e => setQuickItemGstRate(e.target.value)}
                    >
                      <option value="0">0% (Nil / Exempt)</option>
                      <option value="5">5%</option>
                      <option value="12">12%</option>
                      <option value="18">18% (Standard GST)</option>
                      <option value="28">28%</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">Selling Rate (₹)</label>
                    <input 
                      type="number" 
                      placeholder="0.00" 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemSellingPrice}
                      onChange={e => setQuickItemSellingPrice(e.target.value)}
                    />
                  </div>

                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">Purchase / Cost Rate (₹)</label>
                    <input 
                      type="number" 
                      placeholder="0.00" 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemCostPrice}
                      onChange={e => setQuickItemCostPrice(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-1 border-t border-slate-100 dark:border-slate-800">
                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">Opening Qty</label>
                    <input 
                      type="number" 
                      placeholder="0" 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemOpeningQty}
                      onChange={e => setQuickItemOpeningQty(e.target.value)}
                    />
                  </div>

                  <div className="min-w-0">
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5 truncate">Opening Rate (₹)</label>
                    <input 
                      type="number" 
                      placeholder="0.00" 
                      className="w-full min-w-0 h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                      value={quickItemOpeningRate}
                      onChange={e => setQuickItemOpeningRate(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {/* Quick Modal Footer */}
              <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex justify-end gap-2">
                <button 
                  type="button" 
                  onClick={() => setIsQuickItemOpen(false)} 
                  className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg"
                >
                  Cancel
                </button>
                <button 
                  type="button" 
                  onClick={handleSaveQuickItem} 
                  disabled={isCreatingItem}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow flex items-center gap-1.5 cursor-pointer"
                >
                  {isCreatingItem && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save & Select
                </button>
              </div>

            </div>
          </div>
        )}

        {/* --- Quick Create Unit of Measure (UOM) Sub-Modal Overlay --- */}
        {isQuickUnitOpen && (
          <div className="fixed inset-0 z-70 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
              
              {/* Quick Unit Header */}
              <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/40">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 rounded-xl">
                    <Box className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100">Create Unit of Measure</h3>
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                        <Zap className="w-2.5 h-2.5" /> Real-time Tally
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400">Registers unit and pushes directly to Tally Prime</p>
                  </div>
                </div>
                <button 
                  type="button" 
                  onClick={() => setIsQuickUnitOpen(false)}
                  className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Unit Type Tab Selector */}
              <div className="px-4 pt-3.5 pb-1">
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl gap-1">
                  <button
                    type="button"
                    onClick={() => setQuickUnitType('simple')}
                    className={cn(
                      "flex-1 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer",
                      quickUnitType === 'simple' 
                        ? "bg-white dark:bg-slate-900 shadow-xs text-slate-800 dark:text-slate-100" 
                        : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    )}
                  >
                    Simple Unit (e.g. PCS, SET, KG)
                  </button>
                  <button
                    type="button"
                    onClick={() => setQuickUnitType('compound')}
                    className={cn(
                      "flex-1 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer",
                      quickUnitType === 'compound' 
                        ? "bg-white dark:bg-slate-900 shadow-xs text-emerald-600 dark:text-emerald-400" 
                        : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    )}
                  >
                    Compound Unit (e.g. SET of 6)
                  </button>
                </div>
              </div>

              {/* Quick Unit Body */}
              <div className="p-4 space-y-3.5">
                {quickUnitError && (
                  <div className="p-2.5 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 text-xs rounded-xl flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{quickUnitError}</span>
                  </div>
                )}

                {quickUnitType === 'simple' ? (
                  <>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Unit Symbol *</label>
                      <input 
                        type="text" 
                        autoFocus
                        placeholder="e.g. PCS, BOX, MTR, LTR, SET, BAG" 
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-bold"
                        value={quickUnitSymbol}
                        onChange={e => {
                          const val = e.target.value
                          setQuickUnitSymbol(val)
                          const formalMap: Record<string, string> = {
                            PCS: 'Pieces',
                            BOX: 'Boxes',
                            MTR: 'Meters',
                            LTR: 'Litres',
                            SET: 'Sets',
                            BAG: 'Bags',
                            DOZ: 'Dozens',
                            ROLL: 'Rolls',
                            KG: 'Kilograms',
                            GM: 'Grams',
                            PKT: 'Packets',
                            NOS: 'Numbers'
                          }
                          const upper = val.trim().toUpperCase()
                          if (formalMap[upper]) {
                            setQuickUnitFormalName(formalMap[upper])
                          }
                        }}
                      />
                      {/* Quick Preset Chips */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {['PCS', 'BOX', 'MTR', 'LTR', 'SET', 'BAG', 'DOZ', 'ROLL'].map(preset => (
                          <button
                            key={preset}
                            type="button"
                            onClick={() => {
                              setQuickUnitSymbol(preset)
                              const formalMap: Record<string, string> = {
                                PCS: 'Pieces',
                                BOX: 'Boxes',
                                MTR: 'Meters',
                                LTR: 'Litres',
                                SET: 'Sets',
                                BAG: 'Bags',
                                DOZ: 'Dozens',
                                ROLL: 'Rolls',
                                KG: 'Kilograms',
                                GM: 'Grams',
                                PKT: 'Packets',
                                NOS: 'Numbers'
                              }
                              setQuickUnitFormalName(formalMap[preset] || preset)
                            }}
                            className="px-1.5 py-0.5 text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 hover:text-emerald-600 text-slate-600 dark:text-slate-300 rounded border border-slate-200 dark:border-slate-700 cursor-pointer"
                          >
                            +{preset}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Formal Name</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Pieces, Boxes, Meters, Sets" 
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium"
                        value={quickUnitFormalName}
                        onChange={e => setQuickUnitFormalName(e.target.value)}
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Decimal Places</label>
                      <select 
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                        value={quickUnitDecimalPlaces}
                        onChange={e => setQuickUnitDecimalPlaces(e.target.value)}
                      >
                        <option value="0">0 (Countable e.g. PCS, BOX, SET)</option>
                        <option value="1">1</option>
                        <option value="2">2 (Standard Weight/Length e.g. 1.25)</option>
                        <option value="3">3 (Precision e.g. 1.250)</option>
                        <option value="4">4</option>
                      </select>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">First Unit</label>
                        <select
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                          value={quickCompoundFirstUnitId}
                          onChange={e => setQuickCompoundFirstUnitId(e.target.value)}
                        >
                          {simpleUoms.map(u => (
                            <option key={u.unit_id} value={u.unit_id}>{u.symbol} {u.original_name ? `(${u.original_name})` : ''}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Sub Unit</label>
                        <select
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                          value={quickCompoundSecondUnitId}
                          onChange={e => setQuickCompoundSecondUnitId(e.target.value)}
                        >
                          {simpleUoms.map(u => (
                            <option key={u.unit_id} value={u.unit_id}>{u.symbol} {u.original_name ? `(${u.original_name})` : ''}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Contains Quantity / Units</label>
                      <input 
                        type="number" 
                        min="1"
                        step="any"
                        placeholder="Enter quantity e.g. 6 or 4" 
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-bold"
                        value={quickCompoundConversion}
                        onChange={e => setQuickCompoundConversion(e.target.value)}
                      />
                      {/* Popular Quick Conversion Chips */}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {['2', '4', '6', '8', '10', '12', '24', '50', '100'].map(val => (
                          <button
                            key={val}
                            type="button"
                            onClick={() => setQuickCompoundConversion(val)}
                            className={cn(
                              "px-2.5 py-1 text-xs font-bold rounded-lg border transition-all cursor-pointer",
                              quickCompoundConversion === val 
                                ? "bg-emerald-600 text-white border-emerald-600 shadow-xs" 
                                : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-emerald-500"
                            )}
                          >
                            {val}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Live Preview Box */}
                    <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl">
                      <div className="text-[10px] font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider mb-0.5">Live Unit Preview</div>
                      <div className="text-sm font-black text-emerald-950 dark:text-emerald-100">
                        {simpleUoms.find(u => String(u.unit_id) === String(quickCompoundFirstUnitId))?.symbol || 'SET'} of {quickCompoundConversion || '6'} {simpleUoms.find(u => String(u.unit_id) === String(quickCompoundSecondUnitId))?.symbol || 'nos'}
                      </div>
                      <div className="text-[11px] text-emerald-600 dark:text-emerald-400 mt-0.5">
                        1 {simpleUoms.find(u => String(u.unit_id) === String(quickCompoundFirstUnitId))?.symbol || 'SET'} = {quickCompoundConversion || '6'} {simpleUoms.find(u => String(u.unit_id) === String(quickCompoundSecondUnitId))?.symbol || 'nos'}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Quick Unit Footer */}
              <div className="p-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex justify-end gap-2">
                <button 
                  type="button" 
                  onClick={() => setIsQuickUnitOpen(false)} 
                  className="px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg"
                >
                  Cancel
                </button>
                <button 
                  type="button" 
                  onClick={handleSaveQuickUnit} 
                  disabled={isCreatingUnit}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold rounded-lg shadow flex items-center gap-1.5 cursor-pointer"
                >
                  {isCreatingUnit && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Save & Select Unit
                </button>
              </div>

            </div>
          </div>
        )}

        {/* 11. Interactive Banking Allocations Sub-Modal */}
        {isBankingModalOpen && (
          <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-in fade-in duration-200">
            <div className="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-lg shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col">
              
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                    <Landmark className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">Banking Allocations</h3>
                    <p className="text-[11px] text-slate-500">Configures official Tally banking & e-transfer tags</p>
                  </div>
                </div>
                <button 
                  type="button" 
                  onClick={() => setIsBankingModalOpen(false)} 
                  className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body */}
              <div className="p-4 space-y-4 max-h-[75vh] overflow-y-auto">
                
                {/* Transaction Mode Selector */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">Transaction Type</label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { id: 'Cheque', label: 'Cheque / DD', icon: CreditCard },
                      { id: 'UPI', label: 'UPI / QR', icon: QrCode },
                      { id: 'Inter Bank Transfer', label: 'NEFT / RTGS', icon: Landmark }
                    ].map(t => {
                      const Icon = t.icon
                      const isSel = bankingTxType === t.id
                      return (
                        <button
                          key={t.id}
                          type="button"
                          onClick={() => setBankingTxType(t.id)}
                          className={cn(
                            "px-2.5 py-2 rounded-xl text-xs font-bold flex flex-col items-center gap-1 transition-all border cursor-pointer",
                            isSel 
                              ? "bg-blue-600 text-white border-blue-600 shadow-sm" 
                              : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400"
                          )}
                        >
                          <Icon className="w-4 h-4" />
                          <span>{t.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* UPI Fields */}
                {bankingTxType === 'UPI' && (
                  <div className="space-y-3 p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/60 rounded-xl">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                        Virtual Payment Address (UPI VPA / ID)
                      </label>
                      <input 
                        type="text" 
                        placeholder="e.g. partyname@okaxis or 9876543210@upi"
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                        value={bankingVpa}
                        onChange={e => setBankingVpa(e.target.value)}
                      />
                      {/* Popular UPI Handles */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {['@okaxis', '@okhdfcbank', '@okicici', '@paytm', '@ybl', '@upi'].map(h => (
                          <button
                            key={h}
                            type="button"
                            onClick={() => {
                              const base = bankingVpa.includes('@') ? bankingVpa.split('@')[0] : bankingVpa
                              setBankingVpa(base ? `${base}${h}` : h)
                            }}
                            className="px-2 py-0.5 text-[10px] font-bold rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-blue-500 cursor-pointer"
                          >
                            {h}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                        UPI Reference / UTR Number (Optional)
                      </label>
                      <input 
                        type="text" 
                        placeholder="12-digit UTR e.g. 523184920194"
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
                        value={bankingInstNumber}
                        onChange={e => setBankingInstNumber(e.target.value)}
                      />
                    </div>
                  </div>
                )}

                {/* Cheque / DD Fields */}
                {bankingTxType === 'Cheque' && (
                  <div className="space-y-3 p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/60 rounded-xl">
                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Cheque Number
                        </label>
                        <input 
                          type="text" 
                          placeholder="6-digit e.g. 104523"
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                          value={bankingInstNumber}
                          onChange={e => setBankingInstNumber(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Cheque Date
                        </label>
                        <input 
                          type="date" 
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
                          value={bankingInstDate}
                          onChange={e => setBankingInstDate(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Cheque Crossing
                        </label>
                        <select 
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                          value={bankingChequeCrossing}
                          onChange={e => setBankingChequeCrossing(e.target.value)}
                        >
                          <option value="A/c Payee">A/c Payee</option>
                          <option value="Account Payee Only">Account Payee Only</option>
                          <option value="Not Negotiable">Not Negotiable</option>
                          <option value="None">None (Bearer)</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Payment Favouring
                        </label>
                        <input 
                          type="text" 
                          placeholder="Party / Payee Name"
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
                          value={bankingFavouring}
                          onChange={e => setBankingFavouring(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* NEFT / RTGS Transfer Fields */}
                {bankingTxType === 'Inter Bank Transfer' && (
                  <div className="space-y-3 p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/60 rounded-xl">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">Transfer Mode</label>
                      <div className="flex gap-2">
                        {['NEFT', 'RTGS', 'IMPS'].map(mode => (
                          <button
                            key={mode}
                            type="button"
                            onClick={() => setBankingTransferMode(mode)}
                            className={cn(
                              "flex-1 py-1.5 rounded-lg text-xs font-bold border transition-all cursor-pointer",
                              bankingTransferMode === mode 
                                ? "bg-blue-600 text-white border-blue-600" 
                                : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                            )}
                          >
                            {mode}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2.5">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          Beneficiary Bank
                        </label>
                        <input 
                          type="text" 
                          placeholder="e.g. HDFC Bank"
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm"
                          value={bankingBankName}
                          onChange={e => setBankingBankName(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                          IFSC Code
                        </label>
                        <input 
                          type="text" 
                          placeholder="e.g. HDFC0001234"
                          className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm uppercase"
                          value={bankingIfsc}
                          onChange={e => setBankingIfsc(e.target.value.toUpperCase())}
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                        Beneficiary Account Number
                      </label>
                      <input 
                        type="text" 
                        placeholder="Bank Account Number"
                        className="w-full h-10 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-semibold"
                        value={bankingAccountNumber}
                        onChange={e => setBankingAccountNumber(e.target.value)}
                      />
                    </div>
                  </div>
                )}

              </div>

              {/* Footer */}
              <div className="p-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex justify-end gap-2">
                <button 
                  type="button" 
                  onClick={() => setIsBankingModalOpen(false)} 
                  className="px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button 
                  type="button" 
                  onClick={saveBankingAllocation} 
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow flex items-center gap-1.5 cursor-pointer"
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Save Banking Details
                </button>
              </div>

            </div>
          </div>
        )}

        {/* 11. Voucher F12 Configuration Modal */}
        <VoucherConfigurationModal
          isOpen={isConfigModalOpen}
          onClose={() => setIsConfigModalOpen(false)}
          voucherType={selectedType}
          initialConfig={voucherConfig}
          onSaveConfig={handleSaveConfig}
        />

      </div>
    </div>
  )
}
