'use client'

import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import {
  Landmark,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  RefreshCw,
  Search,
  Filter,
  FileSpreadsheet,
  Check,
  X,
  History,
  TrendingUp,
  TrendingDown,
  Layers,
  ChevronRight,
  Info,
  Sparkles,
  Link2,
  Unlink,
  Eye,
  EyeOff,
  Lock,
  FileText,
  Shield,
  Ban,
  CreditCard,
  ArrowLeftRight,
  Building2,
  HelpCircle,
  CheckSquare,
  Square,
  Tag,
  Undo2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  LayoutList,
  LayoutGrid,
  SlidersHorizontal,
  Table,
  ExternalLink,
  Calendar
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import VoucherDetailModal, { BankTxContext } from '@/components/VoucherDetailModal'

export const REVIEW_CATEGORIES = [
  {
    id: 'not_specific',
    label: 'Not Specific to This Account',
    description: 'Personal drawing by proprietor, third-party funds, or non-business entry',
    badgeColor: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20',
  },
  {
    id: 'bank_charges',
    label: 'Bank Charges / Fee / GST',
    description: 'SMS alert charges, debit card annual fee, cheque return penalty (to be booked later)',
    badgeColor: 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20',
  },
  {
    id: 'interest',
    label: 'Bank Interest Received',
    description: 'Quarterly savings interest or auto-sweep FD credit (to be booked later)',
    badgeColor: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20',
  },
  {
    id: 'internal_transfer',
    label: 'Internal Transfer / Contra',
    description: 'Transfer between own company bank accounts or linked subsidiary account',
    badgeColor: 'bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20',
  },
  {
    id: 'other_account',
    label: 'Belongs to Another Account',
    description: 'Entry belonging to another ledger or mistaken account deposit',
    badgeColor: 'bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20',
  },
  {
    id: 'under_investigation',
    label: 'Under Investigation / Unknown',
    description: 'Unidentified NEFT/RTGS sender, pending bank confirmation',
    badgeColor: 'bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20',
  },
]

interface BankLedger {
  ledger_id: number
  name: string
  group_name: string
  is_bank_account: boolean
  bank_account_no?: string
  bank_ifsc?: string
  closing_balance: number
  statement_count: number
}

interface Statement {
  statement_id: number
  filename: string
  bank_ledger_id: number
  bank_name: string
  statement_from: string
  statement_to: string
  opening_balance: number
  closing_balance: number
  total_transactions: number
  reconciled_transactions: number
  unmatched_transactions: number
  reviewed_transactions?: number
  reconciled_pct: number
  status: string
  created_at: string
  created_by?: string
}

interface BRSDetails {
  statement_id: number
  bank_name: string
  statement_balance: number
  books_balance: number
  uncredited_deposits: number
  unpresented_cheques: number
  variance: number
  is_reconciled: boolean
  total_transactions: number
  reconciled_count: number
  suggested_count: number
  unmatched_count: number
  reviewed_count?: number
  pending_review_count?: number
  reconciled_pct: number
}

interface StatementTransaction {
  transaction_id: number
  statement_id: number
  transaction_date: string
  description: string
  reference_no?: string
  cheque_no?: string
  transaction_type: 'DEBIT' | 'CREDIT'
  amount: number
  running_balance?: number
  matched_status: 'unmatched' | 'suggested' | 'matched'
  review_status?: string
  review_notes?: string
  reviewed_by?: string
  reviewed_at?: string
  raw_data?: any
  match_type?: string
  matched_at?: string
  matched_by?: string
  match_notes?: string
  voucher?: {
    voucher_id: number
    voucher_number: string
    voucher_type: string
    date: string
    narration?: string
    party_name?: string
  }
}

interface UnmatchedBookEntry {
  voucher_id: number
  voucher_number: string
  voucher_type: string
  date: string
  party_name: string
  amount: number
  instrument_number?: string
  narration?: string
}

export default function BankReconciliationPage() {
  const { user, token } = useAuth()
  const router = useRouter()

  // State
  const [bankLedgers, setBankLedgers] = useState<BankLedger[]>([])
  const [selectedLedgerId, setSelectedLedgerId] = useState<number | null>(null)
  const [statements, setStatements] = useState<Statement[]>([])
  const [dateBounds, setDateBounds] = useState<{
    min_date: string | null
    max_date: string | null
    total_transactions: number
    total_statements: number
  } | null>(null)
  const [datePreset, setDatePreset] = useState<'all' | 'this_month' | 'last_30' | 'last_90' | 'current_fy' | 'custom'>('all')
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')
  const [brs, setBrs] = useState<BRSDetails | null>(null)
  const [transactions, setTransactions] = useState<StatementTransaction[]>([])
  const [unmatchedBooks, setUnmatchedBooks] = useState<UnmatchedBookEntry[]>([])

  const [loading, setLoading] = useState(true)
  const [loadingTransactions, setLoadingTransactions] = useState(false)
  const [activeTab, setActiveTab] = useState<'suggested' | 'unmatched_bank' | 'reviewed' | 'unmatched_books' | 'matched' | 'statements'>('suggested')
  const [searchQuery, setSearchQuery] = useState('')

  // Date Range Helper for Standard Presets
  const computeDateRange = (preset: 'all' | 'this_month' | 'last_30' | 'last_90' | 'current_fy'): { from: string; to: string } => {
    const today = new Date()
    const formatYMD = (d: Date) => {
      const year = d.getFullYear()
      const month = String(d.getMonth() + 1).padStart(2, '0')
      const day = String(d.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    if (preset === 'all') {
      return { from: '', to: '' }
    } else if (preset === 'this_month') {
      const start = new Date(today.getFullYear(), today.getMonth(), 1)
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0)
      return { from: formatYMD(start), to: formatYMD(end) }
    } else if (preset === 'last_30') {
      const start = new Date(today)
      start.setDate(today.getDate() - 30)
      return { from: formatYMD(start), to: formatYMD(today) }
    } else if (preset === 'last_90') {
      const start = new Date(today)
      start.setDate(today.getDate() - 90)
      return { from: formatYMD(start), to: formatYMD(today) }
    } else if (preset === 'current_fy') {
      const currentMonth = today.getMonth()
      const fyStartYear = currentMonth >= 3 ? today.getFullYear() : today.getFullYear() - 1
      return { from: `${fyStartYear}-04-01`, to: `${fyStartYear + 1}-03-31` }
    }
    return { from: '', to: '' }
  }

  const handlePresetChange = (preset: 'all' | 'this_month' | 'last_30' | 'last_90' | 'current_fy') => {
    setDatePreset(preset)
    const range = computeDateRange(preset)
    setDateFrom(range.from)
    setDateTo(range.to)
  }

  // Upload Modal State
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadPassword, setUploadPassword] = useState<string>('')
  const [showPassword, setShowPassword] = useState(false)
  const [uploadOpeningBal, setUploadOpeningBal] = useState<string>('')
  const [uploadClosingBal, setUploadClosingBal] = useState<string>('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null)

  // Voucher Detail Modal State (View Receipt / Voucher on the same page)
  const [modalVoucherId, setModalVoucherId] = useState<number | null>(null)
  const [modalBankTx, setModalBankTx] = useState<BankTxContext | null>(null)
  const [isVoucherModalOpen, setIsVoucherModalOpen] = useState(false)

  const handleOpenVoucherModal = (voucherId: number, bankContext?: BankTxContext | null) => {
    setModalVoucherId(voucherId)
    setModalBankTx(bankContext || null)
    setIsVoucherModalOpen(true)
  }

  // Manual Matching Modal
  const [matchingTx, setMatchingTx] = useState<StatementTransaction | null>(null)
  const [selectedBookVoucherId, setSelectedBookVoucherId] = useState<number | null>(null)
  const [isSubmittingMatch, setIsSubmittingMatch] = useState(false)

  // Admin Review / Classification Modal State
  const [reviewingTx, setReviewingTx] = useState<StatementTransaction | null>(null)
  const [reviewStatus, setReviewStatus] = useState<string>('not_specific')
  const [reviewNotes, setReviewNotes] = useState<string>('')
  const [submittingReview, setSubmittingReview] = useState<boolean>(false)
  const [showReviewModal, setShowReviewModal] = useState<boolean>(false)

  // Batch review selection
  const [selectedTxIds, setSelectedTxIds] = useState<number[]>([])
  const [showBatchReviewModal, setShowBatchReviewModal] = useState<boolean>(false)
  const [selectedSuggestedIds, setSelectedSuggestedIds] = useState<number[]>([])
  const [isBatchApproving, setIsBatchApproving] = useState<boolean>(false)

  // View mode: 'table' (default) or 'cards'
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table')

  // Sorting & Filtering state
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'CREDIT' | 'DEBIT'>('ALL')
  const [sortField, setSortField] = useState<'date' | 'amount' | 'type' | 'ref' | 'description'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Fetch Bank Ledgers on mount
  const fetchBankLedgers = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/bank-recon/bank-ledgers`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error('Failed to load bank ledgers')
      const data = await res.json()
      setBankLedgers(data)
      if (data.length > 0 && !selectedLedgerId) {
        const pnb = data.find((l: any) => 
          l.name.toLowerCase().includes('punjab national bank') || 
          l.name.toLowerCase().includes('pnb')
        )
        const defaultLedger = pnb || data.find((l: any) => !l.name.toLowerCase().includes('cash')) || data[0]
        setSelectedLedgerId(defaultLedger.ledger_id)
      }
    } catch (err: any) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [token, selectedLedgerId])

  useEffect(() => {
    fetchBankLedgers()
  }, [fetchBankLedgers])

  // Fetch Date Bounds across all statements for the bank ledger
  const fetchDateBounds = useCallback(async (ledgerId: number) => {
    if (!token) return null
    try {
      const res = await fetch(`${API_BASE}/bank-recon/date-bounds?bank_ledger_id=${ledgerId}`, {
        headers: authHeaders(token)
      })
      if (!res.ok) return null
      const data = await res.json()
      setDateBounds(data)
      return data
    } catch (err) {
      console.error('Failed to load date bounds:', err)
      return null
    }
  }, [token])

  // Fetch Statements for selected ledger (retained for batch history audit)
  const fetchStatements = useCallback(async () => {
    if (!token || !selectedLedgerId) return
    try {
      const res = await fetch(`${API_BASE}/bank-recon/statements?bank_ledger_id=${selectedLedgerId}`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error('Failed to load statements')
      const data = await res.json()
      setStatements(data)
    } catch (err) {
      console.error(err)
    }
  }, [token, selectedLedgerId])

  // Fetch Unified BRS, Transactions, and Unmatched Books by Ledger and Date Period
  const fetchStatementData = useCallback(async () => {
    if (!token || !selectedLedgerId) return
    setLoadingTransactions(true)
    try {
      const params = new URLSearchParams()
      params.append('bank_ledger_id', selectedLedgerId.toString())
      if (dateFrom) params.append('from_date', dateFrom)
      if (dateTo) params.append('to_date', dateTo)

      const [brsRes, txRes, booksRes] = await Promise.all([
        fetch(`${API_BASE}/bank-recon/summary?${params.toString()}`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/bank-recon/transactions?${params.toString()}&status=all`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/bank-recon/unmatched-books?${params.toString()}`, { headers: authHeaders(token) }),
      ])

      if (brsRes.ok) setBrs(await brsRes.json())
      if (txRes.ok) setTransactions(await txRes.json())
      if (booksRes.ok) setUnmatchedBooks(await booksRes.json())
    } catch (err) {
      console.error('Failed to load reconciliation data:', err)
    } finally {
      setLoadingTransactions(false)
    }
  }, [token, selectedLedgerId, dateFrom, dateTo])

  useEffect(() => {
    if (selectedLedgerId) {
      fetchStatements()
      fetchDateBounds(selectedLedgerId)
    }
  }, [selectedLedgerId, fetchStatements, fetchDateBounds])

  useEffect(() => {
    if (selectedLedgerId) {
      fetchStatementData()
    }
  }, [selectedLedgerId, dateFrom, dateTo, fetchStatementData])

  // Handle Statement File Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile || !selectedLedgerId) {
      setUploadError('Please select a statement file.')
      return
    }

    setIsUploading(true)
    setUploadError(null)
    setUploadSuccess(null)

    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('bank_ledger_id', selectedLedgerId.toString())
    if (uploadPassword) formData.append('password', uploadPassword)
    if (uploadOpeningBal) formData.append('opening_balance', uploadOpeningBal)
    if (uploadClosingBal) formData.append('closing_balance', uploadClosingBal)

    try {
      const res = await fetch(`${API_BASE}/bank-recon/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')
      }

      const result = await res.json()
      const msg = result.message || `✓ Statement imported successfully! Auto-matched ${result.exact_matches} exact entries, ${result.suggested_matches} suggested entries.`
      setUploadSuccess(msg)
      if (result.is_duplicate_file) {
        toast.info(msg)
      } else if (result.duplicate_rows_skipped > 0) {
        toast.success(msg)
      } else {
        toast.success(`✓ Statement imported! Auto-matched ${result.exact_matches} exact entries.`)
      }

      setTimeout(() => {
        setShowUploadModal(false)
        setUploadFile(null)
        setUploadPassword('')
        setUploadOpeningBal('')
        setUploadClosingBal('')
        setUploadSuccess(null)
      }, 1500)

      await fetchStatements()
      if (selectedLedgerId) {
        await fetchDateBounds(selectedLedgerId)
      }
      await fetchStatementData()
    } catch (err: any) {
      setUploadError(err.message)
    } finally {
      setIsUploading(false)
    }
  }

  // Handle Accept Match
  const handleConfirmMatch = async (transactionId: number, voucherId: number) => {
    setIsSubmittingMatch(true)
    try {
      const formData = new FormData()
      formData.append('transaction_id', transactionId.toString())
      formData.append('voucher_id', voucherId.toString())

      const res = await fetch(`${API_BASE}/bank-recon/match`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      })
      if (!res.ok) throw new Error('Match operation failed')
      await fetchStatementData()
      setMatchingTx(null)
      setSelectedBookVoucherId(null)
    } catch (err: any) {
      alert(err.message)
    } finally {
      setIsSubmittingMatch(false)
    }
  }

  // Handle Undo Match
  const handleUnmatch = async (transactionId: number) => {
    if (!confirm('Revert this match back to unmatched state?')) return
    try {
      const formData = new FormData()
      formData.append('transaction_id', transactionId.toString())

      const res = await fetch(`${API_BASE}/bank-recon/unmatch`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      })
      if (!res.ok) throw new Error('Unmatch failed')
      await fetchStatementData()
    } catch (err: any) {
      alert(err.message)
    }
  }

  // Handle 1-Click Accept All Suggested
  const handleBatchAcceptSuggested = async () => {
    if (!selectedLedgerId) return
    const periodMsg = dateFrom && dateTo
      ? `period ${formatDate(dateFrom)} to ${formatDate(dateTo)}`
      : 'all imported statement batches'
    if (!confirm(`Accept all high-confidence suggested matches for ${periodMsg}?`)) return

    try {
      const formData = new FormData()
      formData.append('bank_ledger_id', selectedLedgerId.toString())

      const res = await fetch(`${API_BASE}/bank-recon/batch-match-suggested`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      })
      if (!res.ok) throw new Error('Batch match failed')
      const result = await res.json()
      toast.success(`✓ Successfully approved ${result.accepted_count} suggested matches!`)
      await fetchStatementData()
      if (selectedLedgerId) await fetchDateBounds(selectedLedgerId)
    } catch (err: any) {
      toast.error(err.message)
    }
  }

  // Handle Approve Selected Suggested Matches
  const handleApproveSelectedSuggested = async () => {
    if (selectedSuggestedIds.length === 0) return
    setIsBatchApproving(true)
    try {
      const candidates = suggestedTransactions.filter(
        t => selectedSuggestedIds.includes(t.transaction_id) && t.voucher
      )
      for (const t of candidates) {
        const formData = new FormData()
        formData.append('transaction_id', t.transaction_id.toString())
        formData.append('voucher_id', t.voucher!.voucher_id.toString())
        await fetch(`${API_BASE}/bank-recon/match`, {
          method: 'POST',
          headers: authHeaders(token),
          body: formData,
        })
      }
      toast.success(`Successfully approved ${candidates.length} suggested matches!`)
      setSelectedSuggestedIds([])
      await fetchStatementData()
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve selected matches')
    } finally {
      setIsBatchApproving(false)
    }
  }

  // Column header sort toggle
  const handleSort = (field: 'date' | 'amount' | 'type' | 'ref' | 'description') => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder(field === 'amount' || field === 'date' ? 'desc' : 'asc')
    }
  }

  // Open Review / Classification Modal
  const handleOpenReviewModal = (tx: StatementTransaction) => {
    setReviewingTx(tx)
    setReviewStatus(tx.review_status && tx.review_status !== 'pending_review' ? tx.review_status : 'not_specific')
    setReviewNotes(tx.review_notes || '')
    setShowReviewModal(true)
  }

  // Handle Save Review Status
  const handleSaveReview = async (customStatus?: string) => {
    if (!reviewingTx) return
    const statusToSave = customStatus || reviewStatus
    setSubmittingReview(true)
    try {
      const formData = new FormData()
      formData.append('transaction_id', reviewingTx.transaction_id.toString())
      formData.append('review_status', statusToSave)
      if (reviewNotes.trim()) {
        formData.append('review_notes', reviewNotes.trim())
      }

      const res = await fetch(`${API_BASE}/bank-recon/review-status`, {
        method: 'POST',
        headers: authHeaders(token),
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to update review status')
      }
      toast.success(
        statusToSave === 'pending_review'
          ? 'Transaction reset to pending review queue'
          : 'Transaction audit classification saved successfully'
      )
      setShowReviewModal(false)
      setReviewingTx(null)
      await fetchStatementData()
    } catch (err: any) {
      toast.error(err.message || 'Error updating review status')
    } finally {
      setSubmittingReview(false)
    }
  }

  // Handle Revert from Reviewed back to Pending Review
  const handleRevertToPending = async (transactionId: number) => {
    try {
      const formData = new FormData()
      formData.append('transaction_id', transactionId.toString())
      formData.append('review_status', 'pending_review')

      const res = await fetch(`${API_BASE}/bank-recon/review-status`, {
        method: 'POST',
        headers: authHeaders(token),
        body: formData,
      })
      if (!res.ok) throw new Error('Failed to reset review status')
      toast.success('Reverted back to unmatched pending review')
      await fetchStatementData()
    } catch (err: any) {
      toast.error(err.message || 'Failed to revert transaction')
    }
  }

  // Handle Batch Save Review
  const handleBatchSaveReview = async () => {
    if (selectedTxIds.length === 0) return
    setSubmittingReview(true)
    try {
      const formData = new FormData()
      formData.append('transaction_ids', selectedTxIds.join(','))
      formData.append('review_status', reviewStatus)
      if (reviewNotes.trim()) {
        formData.append('review_notes', reviewNotes.trim())
      }

      const res = await fetch(`${API_BASE}/bank-recon/batch-review`, {
        method: 'POST',
        headers: authHeaders(token),
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to batch update review status')
      }
      toast.success(`Successfully classified ${selectedTxIds.length} transactions!`)
      setShowBatchReviewModal(false)
      setSelectedTxIds([])
      await fetchStatementData()
    } catch (err: any) {
      toast.error(err.message || 'Failed to batch classify transactions')
    } finally {
      setSubmittingReview(false)
    }
  }

  // Active bank details
  const activeBank = useMemo(() => {
    return bankLedgers.find(l => l.ledger_id === selectedLedgerId)
  }, [bankLedgers, selectedLedgerId])

  // Category subsets
  const pendingTransactions = useMemo(() => {
    return transactions.filter(t => t.matched_status === 'unmatched' && (!t.review_status || t.review_status === 'pending_review'))
  }, [transactions])

  const reviewedTransactions = useMemo(() => {
    return transactions.filter(t => t.matched_status !== 'matched' && t.review_status && t.review_status !== 'pending_review')
  }, [transactions])

  const matchedTransactions = useMemo(() => {
    return transactions.filter(t => t.matched_status === 'matched')
  }, [transactions])

  const suggestedTransactions = useMemo(() => {
    return transactions.filter(t => t.matched_status === 'suggested')
  }, [transactions])

  // Counts for the active tab before type filter
  const currentTabBaseList = useMemo(() => {
    if (activeTab === 'suggested') return suggestedTransactions
    if (activeTab === 'unmatched_bank') return pendingTransactions
    if (activeTab === 'reviewed') return reviewedTransactions
    if (activeTab === 'matched') return matchedTransactions
    return []
  }, [activeTab, suggestedTransactions, pendingTransactions, reviewedTransactions, matchedTransactions])

  const tabCounts = useMemo(() => {
    const credits = currentTabBaseList.filter(t => t.transaction_type === 'CREDIT').length
    const debits = currentTabBaseList.filter(t => t.transaction_type === 'DEBIT').length
    return {
      all: currentTabBaseList.length,
      credits,
      debits,
    }
  }, [currentTabBaseList])

  // Filtered and Sorted transactions for active tab
  const tabTransactions = useMemo(() => {
    let list = [...currentTabBaseList]

    // Type filter
    if (typeFilter !== 'ALL') {
      list = list.filter(t => t.transaction_type === typeFilter)
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(t =>
        t.description.toLowerCase().includes(q) ||
        (t.reference_no && t.reference_no.toLowerCase().includes(q)) ||
        (t.cheque_no && t.cheque_no.toLowerCase().includes(q)) ||
        (t.review_notes && t.review_notes.toLowerCase().includes(q)) ||
        (t.voucher && t.voucher.voucher_number.toLowerCase().includes(q)) ||
        (t.voucher && t.voucher.party_name && t.voucher.party_name.toLowerCase().includes(q)) ||
        t.amount.toString().includes(q)
      )
    }

    // Sorting
    list.sort((a, b) => {
      let cmp = 0
      if (sortField === 'date') {
        const da = new Date(a.transaction_date).getTime()
        const db = new Date(b.transaction_date).getTime()
        cmp = da - db
      } else if (sortField === 'amount') {
        cmp = Number(a.amount) - Number(b.amount)
      } else if (sortField === 'type') {
        cmp = a.transaction_type.localeCompare(b.transaction_type)
      } else if (sortField === 'ref') {
        const ra = (a.reference_no || a.cheque_no || '').toLowerCase()
        const rb = (b.reference_no || b.cheque_no || '').toLowerCase()
        cmp = ra.localeCompare(rb)
      } else if (sortField === 'description') {
        cmp = a.description.localeCompare(b.description)
      }
      return sortOrder === 'asc' ? cmp : -cmp
    })

    return list
  }, [currentTabBaseList, typeFilter, searchQuery, sortField, sortOrder])

  // Filtered and Sorted unmatched books
  const filteredUnmatchedBooks = useMemo(() => {
    let list = [...unmatchedBooks]
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(b =>
        b.party_name.toLowerCase().includes(q) ||
        b.voucher_number.toLowerCase().includes(q) ||
        b.voucher_type.toLowerCase().includes(q) ||
        (b.instrument_number && b.instrument_number.toLowerCase().includes(q)) ||
        (b.narration && b.narration.toLowerCase().includes(q)) ||
        b.amount.toString().includes(q)
      )
    }
    list.sort((a, b) => {
      let cmp = 0
      if (sortField === 'date') {
        cmp = new Date(a.date).getTime() - new Date(b.date).getTime()
      } else if (sortField === 'amount') {
        cmp = Number(a.amount) - Number(b.amount)
      } else {
        cmp = a.party_name.localeCompare(b.party_name)
      }
      return sortOrder === 'asc' ? cmp : -cmp
    })
    return list
  }, [unmatchedBooks, searchQuery, sortField, sortOrder])

  // Sortable column header renderer
  const renderSortHeader = (label: string, field: 'date' | 'amount' | 'type' | 'ref' | 'description', align: 'left' | 'right' | 'center' = 'left') => {
    const isActive = sortField === field
    return (
      <th
        onClick={() => handleSort(field)}
        className={cn(
          "px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer select-none transition-colors group",
          align === 'right' ? "text-right" : align === 'center' ? "text-center" : "text-left"
        )}
      >
        <div className={cn("inline-flex items-center gap-1.5", align === 'right' ? "justify-end" : align === 'center' ? "justify-center" : "justify-start")}>
          <span>{label}</span>
          {isActive ? (
            sortOrder === 'asc' ? (
              <ArrowUp className="h-3.5 w-3.5 text-primary" />
            ) : (
              <ArrowDown className="h-3.5 w-3.5 text-primary" />
            )
          ) : (
            <ArrowUpDown className="h-3 w-3 opacity-30 group-hover:opacity-100" />
          )}
        </div>
      </th>
    )
  }

  return (
    <div className="flex flex-col min-h-screen bg-background font-sans pb-28 sm:pb-20">
      {/* Top Banner & Bank Selector */}
      <div className="border-b border-border bg-card/70 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 sm:h-10 sm:w-10 rounded-2xl bg-primary/10 border border-primary/20 text-primary flex items-center justify-center shrink-0">
              <Landmark className="h-4.5 w-4.5 sm:h-5 sm:w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-sm sm:text-base font-bold tracking-tight text-foreground">
                  Bank Statement Reconciliation
                </h1>
                <span className="text-[9px] sm:text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  Automated BRS
                </span>
              </div>
              <p className="text-[11px] sm:text-[12px] text-muted-foreground line-clamp-1 sm:line-clamp-none">
                3-Way Intelligent Matching: Bank Statements ⟷ Tally Prime Vouchers ⟷ Collections
              </p>
            </div>
          </div>

          {/* Bank Ledger Selector & Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full md:w-auto">
            <div className="relative w-full sm:w-auto sm:min-w-[240px]">
              <select
                value={selectedLedgerId || ''}
                onChange={(e) => setSelectedLedgerId(Number(e.target.value))}
                className="w-full text-xs font-semibold px-3 py-2 bg-background border border-border rounded-xl text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 appearance-none cursor-pointer pr-8"
              >
                {bankLedgers.map(l => (
                  <option key={l.ledger_id} value={l.ledger_id}>
                    {l.name} {l.closing_balance ? `(${formatCurrency(l.closing_balance)})` : ''}
                  </option>
                ))}
              </select>
              <Landmark className="h-3.5 w-3.5 absolute right-3 top-3 text-muted-foreground pointer-events-none" />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={() => setShowUploadModal(true)}
                className="flex-1 sm:flex-initial justify-center px-3.5 py-2 rounded-xl text-xs font-bold bg-primary text-primary-foreground hover:opacity-90 transition-all flex items-center gap-1.5 shadow-sm active:scale-95 shrink-0"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Import Statement</span>
              </button>

              <button
                onClick={fetchStatementData}
                disabled={loadingTransactions}
                className="p-2 border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
                title="Refresh Reconciliation"
              >
                <RefreshCw className={cn("h-4 w-4", loadingTransactions && "animate-spin")} />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-4 sm:py-6 w-full space-y-4 sm:space-y-6">
        {/* Date-Specific Reconciliation Period Bar */}
        {(statements.length > 0 || transactions.length > 0 || (dateBounds && dateBounds.total_transactions > 0)) && (
          <div className="bg-card border border-border p-3 sm:p-4 rounded-2xl sm:rounded-3xl shadow-sm space-y-3 text-xs overflow-hidden">
            {/* Top row: Recon Period Badge & Horizontally Scrollable Presets */}
            <div className="flex items-center gap-2 w-full">
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-primary/10 text-primary rounded-xl text-xs font-bold shrink-0">
                <Calendar className="h-3.5 w-3.5" />
                <span className="whitespace-nowrap">Recon Period</span>
              </div>

              {/* Horizontal Scrollable Presets */}
              <div className="flex-1 overflow-x-auto scrollbar-none py-0.5 min-w-0">
                <div className="inline-flex items-center gap-1 bg-muted/60 p-1 rounded-xl border border-border text-xs font-semibold min-w-max">
                  <button
                    type="button"
                    onClick={() => handlePresetChange('all')}
                    className={cn(
                      "px-2.5 py-1 rounded-lg transition-all text-xs shrink-0 whitespace-nowrap",
                      datePreset === 'all'
                        ? "bg-card text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    All Dates
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetChange('this_month')}
                    className={cn(
                      "px-2.5 py-1 rounded-lg transition-all text-xs shrink-0 whitespace-nowrap",
                      datePreset === 'this_month'
                        ? "bg-card text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    This Month
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetChange('last_30')}
                    className={cn(
                      "px-2.5 py-1 rounded-lg transition-all text-xs shrink-0 whitespace-nowrap",
                      datePreset === 'last_30'
                        ? "bg-card text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Last 30 Days
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetChange('last_90')}
                    className={cn(
                      "px-2.5 py-1 rounded-lg transition-all text-xs shrink-0 whitespace-nowrap",
                      datePreset === 'last_90'
                        ? "bg-card text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Last 90 Days
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePresetChange('current_fy')}
                    className={cn(
                      "px-2.5 py-1 rounded-lg transition-all text-xs shrink-0 whitespace-nowrap",
                      datePreset === 'current_fy'
                        ? "bg-card text-foreground shadow-xs font-bold"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    Current FY
                  </button>
                </div>
              </div>
            </div>

            {/* Middle row: Responsive Date Pickers */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <div className="grid grid-cols-2 sm:flex sm:items-center gap-2 w-full sm:w-auto">
                <div className="flex items-center gap-1.5 bg-background border border-border rounded-xl px-2.5 py-1.5 focus-within:ring-1 focus-within:ring-primary min-w-0">
                  <span className="text-[11px] text-muted-foreground font-semibold shrink-0">From:</span>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => {
                      setDateFrom(e.target.value)
                      setDatePreset('custom')
                    }}
                    className="bg-transparent text-xs font-semibold text-foreground focus:outline-none w-full min-w-0"
                  />
                </div>
                <div className="flex items-center gap-1.5 bg-background border border-border rounded-xl px-2.5 py-1.5 focus-within:ring-1 focus-within:ring-primary min-w-0">
                  <span className="text-[11px] text-muted-foreground font-semibold shrink-0">To:</span>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => {
                      setDateTo(e.target.value)
                      setDatePreset('custom')
                    }}
                    className="bg-transparent text-xs font-semibold text-foreground focus:outline-none w-full min-w-0"
                  />
                </div>
                {(dateFrom || dateTo) && (
                  <button
                    type="button"
                    onClick={() => handlePresetChange('all')}
                    className="col-span-2 sm:col-auto p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground rounded-lg transition-colors flex items-center justify-center gap-1 text-xs border border-border/40 sm:border-0"
                    title="Clear date filter (show all dates)"
                  >
                    <X className="h-3.5 w-3.5" />
                    <span className="sm:hidden text-xs">Clear Date Filter</span>
                  </button>
                )}
              </div>

              {/* Transactions count badge (visible inline on desktop) */}
              {dateBounds && (dateBounds.total_transactions > 0 || dateBounds.total_statements > 0) && (
                <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground font-medium bg-muted/40 px-3 py-1.5 rounded-xl border border-border shrink-0">
                  <FileSpreadsheet className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span>
                    {dateBounds.total_transactions} Total Transactions
                    {dateBounds.total_statements > 1 ? ` (${dateBounds.total_statements} Batches Combined)` : ''}
                  </span>
                </div>
              )}
            </div>

            {/* Bottom Row on Mobile: Badge + Batch Approve button */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-border/50">
              {dateBounds && (dateBounds.total_transactions > 0 || dateBounds.total_statements > 0) && (
                <div className="flex sm:hidden items-center gap-1.5 text-[11px] text-muted-foreground font-medium bg-muted/40 px-2.5 py-1.5 rounded-xl border border-border w-fit">
                  <FileSpreadsheet className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span>
                    {dateBounds.total_transactions} Total Transactions
                    {dateBounds.total_statements > 1 ? ` (${dateBounds.total_statements} Batches)` : ''}
                  </span>
                </div>
              )}

              {brs && brs.suggested_count > 0 && (
                <button
                  type="button"
                  onClick={handleBatchAcceptSuggested}
                  className="w-full sm:w-auto justify-center px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-sm ml-auto"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Approve All Suggested ({brs.suggested_count})</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Bank Reconciliation Statement (BRS) Metric Header */}
        {brs ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4">
            {/* Card 1: Bank Statement Balance */}
            <div className="bg-card border border-border rounded-2xl sm:rounded-3xl p-3.5 sm:p-5 shadow-sm space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-muted-foreground truncate">Bank Statement</span>
                <Landmark className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-blue-500 shrink-0" />
              </div>
              <div className="text-base sm:text-2xl font-black text-foreground truncate">
                {formatCurrency(brs.statement_balance)}
              </div>
              <p className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
                Per statement
              </p>
            </div>

            {/* Card 2: Books Balance */}
            <div className="bg-card border border-border rounded-2xl sm:rounded-3xl p-3.5 sm:p-5 shadow-sm space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-muted-foreground truncate">Tally Books</span>
                <FileText className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-purple-500 shrink-0" />
              </div>
              <div className="text-base sm:text-2xl font-black text-foreground truncate">
                {formatCurrency(brs.books_balance)}
              </div>
              <p className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
                Ledger closing balance
              </p>
            </div>

            {/* Card 3: In-Transit Timing Differences */}
            <div className="bg-card border border-border rounded-2xl sm:rounded-3xl p-3.5 sm:p-5 shadow-sm space-y-1 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider text-muted-foreground truncate">In-Transit</span>
                <Clock className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-amber-500 shrink-0" />
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-3 text-xs pt-0.5 sm:pt-1 font-semibold">
                <span className="text-emerald-600 dark:text-emerald-400 text-[10px] sm:text-xs truncate">
                  +{formatCurrency(brs.uncredited_deposits)} Dep
                </span>
                <span className="text-rose-600 dark:text-rose-400 text-[10px] sm:text-xs truncate">
                  -{formatCurrency(brs.unpresented_cheques)} Chq
                </span>
              </div>
              <p className="text-[10px] sm:text-[11px] text-muted-foreground truncate">
                Timing differences
              </p>
            </div>

            {/* Card 4: Net Variance (The BRS Status Hero) */}
            <div className={cn(
              "border rounded-2xl sm:rounded-3xl p-3.5 sm:p-5 shadow-sm space-y-1 relative overflow-hidden transition-all",
              brs.is_reconciled
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-950 dark:text-emerald-100"
                : "bg-amber-500/10 border-amber-500/30 text-amber-950 dark:text-amber-100"
            )}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] sm:text-[11px] font-bold uppercase tracking-wider truncate">
                  {brs.is_reconciled ? "Balanced" : "Variance"}
                </span>
                {brs.is_reconciled ? (
                  <CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                ) : (
                  <AlertTriangle className="h-4 w-4 sm:h-5 sm:w-5 text-amber-600 dark:text-amber-400 shrink-0" />
                )}
              </div>
              <div className="text-base sm:text-2xl font-black truncate">
                {brs.is_reconciled ? "₹0.00" : formatCurrency(brs.variance)}
              </div>
              <div className="flex items-center justify-between text-[10px] sm:text-[11px] font-medium pt-0.5">
                <span className="truncate">{brs.reconciled_count}/{brs.total_transactions}</span>
                <span className="font-bold">{brs.reconciled_pct}%</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-card border border-border rounded-2xl sm:rounded-3xl p-6 sm:p-10 text-center space-y-3">
            <div className="h-12 w-12 rounded-2xl bg-muted/60 border border-border flex items-center justify-center mx-auto text-muted-foreground">
              <Landmark className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-sm font-bold text-foreground">No Bank Statements Found</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              Upload a bank statement Excel/CSV to automatically match Tally vouchers and generate Bank Reconciliation Statements (BRS).
            </p>
            <button
              onClick={() => setShowUploadModal(true)}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold inline-flex items-center gap-2 hover:opacity-90 shadow-sm"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Import Statement</span>
            </button>
          </div>
        )}

        {/* Tab Navigation & Search Bar */}
        {(statements.length > 0 || transactions.length > 0 || (dateBounds && dateBounds.total_transactions > 0)) && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none p-1 bg-muted/60 rounded-2xl border border-border text-xs font-semibold max-w-full">
                <button
                  onClick={() => setActiveTab('suggested')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'suggested' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                  <span>Suggested</span>
                  {brs && brs.suggested_count > 0 && (
                    <span className="px-1.5 py-0.2 bg-amber-500/20 text-amber-700 dark:text-amber-300 rounded-full text-[10px]">
                      {brs.suggested_count}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('unmatched_bank')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'unmatched_bank' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
                  <span>Pending Review</span>
                  {pendingTransactions.length > 0 && (
                    <span className="px-1.5 py-0.2 bg-rose-500/20 text-rose-700 dark:text-rose-300 rounded-full text-[10px]">
                      {pendingTransactions.length}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('reviewed')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'reviewed' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Shield className="h-3.5 w-3.5 text-blue-500" />
                  <span>Admin Reviewed</span>
                  {reviewedTransactions.length > 0 && (
                    <span className="px-1.5 py-0.2 bg-blue-500/20 text-blue-700 dark:text-blue-300 rounded-full text-[10px]">
                      {reviewedTransactions.length}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab('unmatched_books')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'unmatched_books' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <FileText className="h-3.5 w-3.5 text-purple-500" />
                  <span>In Books</span>
                  <span className="px-1.5 py-0.2 bg-purple-500/20 text-purple-700 dark:text-purple-300 rounded-full text-[10px]">
                    {unmatchedBooks.length}
                  </span>
                </button>

                <button
                  onClick={() => setActiveTab('matched')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'matched' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Reconciled ({matchedTransactions.length})</span>
                </button>

                <button
                  onClick={() => setActiveTab('statements')}
                  className={cn(
                    "px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shrink-0 whitespace-nowrap",
                    activeTab === 'statements' 
                      ? "bg-card text-foreground shadow-sm font-bold" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <History className="h-3.5 w-3.5 text-blue-500" />
                  <span>Batch History</span>
                </button>
              </div>
            </div>

            {/* Filter, Sort & View Control Toolbar */}
            {activeTab !== 'statements' && (
              <div className="flex flex-col gap-2.5 bg-muted/40 p-2.5 rounded-2xl border border-border/80">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  {/* Left: Type Filter Pills & Selection Action Bar */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {activeTab !== 'unmatched_books' ? (
                      <div className="flex items-center gap-1 bg-card border border-border p-1 rounded-xl shadow-2xs">
                        <button
                          onClick={() => setTypeFilter('ALL')}
                          className={cn(
                            "px-2.5 py-1 rounded-lg text-xs font-bold transition-all",
                            typeFilter === 'ALL'
                              ? "bg-primary text-primary-foreground shadow-xs"
                              : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          All ({tabCounts.all})
                        </button>
                        <button
                          onClick={() => setTypeFilter('CREDIT')}
                          className={cn(
                            "px-2.5 py-1 rounded-lg text-xs font-bold transition-all flex items-center gap-1",
                            typeFilter === 'CREDIT'
                              ? "bg-emerald-600 text-white shadow-xs"
                              : "text-muted-foreground hover:text-emerald-600"
                          )}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                          <span>Credits</span>
                          <span className="text-[10px] opacity-80 font-mono">({tabCounts.credits})</span>
                        </button>
                        <button
                          onClick={() => setTypeFilter('DEBIT')}
                          className={cn(
                            "px-2.5 py-1 rounded-lg text-xs font-bold transition-all flex items-center gap-1",
                            typeFilter === 'DEBIT'
                              ? "bg-rose-600 text-white shadow-xs"
                              : "text-muted-foreground hover:text-rose-600"
                          )}
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-rose-400"></span>
                          <span>Debits</span>
                          <span className="text-[10px] opacity-80 font-mono">({tabCounts.debits})</span>
                        </button>
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground font-medium px-2 py-1 flex items-center gap-2">
                        <FileText className="h-4 w-4 text-purple-500" />
                        <span>Showing <strong className="text-foreground">{filteredUnmatchedBooks.length}</strong> vouchers</span>
                      </div>
                    )}

                    {/* Tab-Specific Batch Action Buttons */}
                    {activeTab === 'suggested' && suggestedTransactions.length > 0 && selectedSuggestedIds.length > 0 && (
                      <button
                        onClick={handleApproveSelectedSuggested}
                        disabled={isBatchApproving}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50 animate-in fade-in"
                      >
                        <Check className="h-3.5 w-3.5" />
                        <span>{isBatchApproving ? 'Approving...' : `Approve (${selectedSuggestedIds.length})`}</span>
                      </button>
                    )}

                    {activeTab === 'unmatched_bank' && pendingTransactions.length > 0 && selectedTxIds.length > 0 && (
                      <button
                        onClick={() => {
                          setReviewStatus('not_specific')
                          setReviewNotes('')
                          setShowBatchReviewModal(true)
                        }}
                        className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-sm animate-in fade-in"
                      >
                        <Tag className="h-3.5 w-3.5" />
                        <span>Mark ({selectedTxIds.length})</span>
                      </button>
                    )}
                  </div>

                  {/* View Mode Toggle: Table vs Cards (on right, compact) */}
                  <div className="flex items-center bg-card border border-border p-0.5 rounded-xl shadow-2xs ml-auto">
                    <button
                      onClick={() => setViewMode('table')}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5",
                        viewMode === 'table' ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                      )}
                      title="Table View"
                    >
                      <Table className="h-3.5 w-3.5" />
                      <span className="text-[11px] hidden sm:inline">Table</span>
                    </button>
                    <button
                      onClick={() => setViewMode('cards')}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5",
                        viewMode === 'cards' ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                      )}
                      title="Cards View"
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                      <span className="text-[11px] hidden sm:inline">Cards</span>
                    </button>
                  </div>
                </div>

                {/* Search & Sort row: Full width Search on mobile + Sort */}
                <div className="flex items-center gap-2 w-full">
                  <div className="relative flex-1">
                    <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search narration, ref, cheque..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full text-xs pl-8 pr-7 py-1.5 bg-card border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 shadow-2xs"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>

                  <div className="relative shrink-0">
                    <select
                      value={`${sortField}-${sortOrder}`}
                      onChange={(e) => {
                        const [f, o] = e.target.value.split('-') as [any, 'asc' | 'desc']
                        setSortField(f)
                        setSortOrder(o)
                      }}
                      className="text-xs font-semibold pl-2.5 pr-7 py-1.5 bg-card border border-border rounded-xl text-foreground focus:outline-none cursor-pointer appearance-none shadow-2xs"
                    >
                      <option value="date-desc">Date: Newest</option>
                      <option value="date-asc">Date: Oldest</option>
                      <option value="amount-desc">Amount: High-Low</option>
                      <option value="amount-asc">Amount: Low-High</option>
                      <option value="type-asc">Type: Credit First</option>
                      <option value="type-desc">Type: Debit First</option>
                      <option value="description-asc">Narration: A-Z</option>
                      <option value="description-desc">Narration: Z-A</option>
                    </select>
                    <ArrowUpDown className="h-3 w-3 absolute right-2.5 top-2.5 text-muted-foreground pointer-events-none" />
                  </div>
                </div>
              </div>
            )}

            {/* TAB CONTENT */}

            {/* Tab 1: Suggested Matches */}
            {activeTab === 'suggested' && (
              <div className="space-y-3">
                {tabTransactions.length === 0 ? (
                  <div className="bg-card border border-border rounded-3xl p-10 text-center space-y-2">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                    <h4 className="text-sm font-bold text-foreground">No Suggested Matches Found</h4>
                    <p className="text-xs text-muted-foreground">
                      {typeFilter !== 'ALL' || searchQuery
                        ? 'No candidate matches match your current filter criteria.'
                        : 'All automatic high-confidence candidates have been approved or none were found. Check the Pending Review tab to manually link entries.'}
                    </p>
                  </div>
                ) : viewMode === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-xs">
                    <table className="w-full min-w-[760px] text-left text-xs border-collapse">
                      <thead className="bg-muted/60 border-b border-border text-muted-foreground select-none">
                        <tr>
                          <th className="w-10 px-3.5 py-3 text-center">
                            <button
                              onClick={() => {
                                if (selectedSuggestedIds.length === tabTransactions.length && tabTransactions.length > 0) {
                                  setSelectedSuggestedIds([])
                                } else {
                                  setSelectedSuggestedIds(tabTransactions.map(t => t.transaction_id))
                                }
                              }}
                              className="p-1 text-muted-foreground hover:text-primary transition-colors inline-flex items-center justify-center"
                              title={selectedSuggestedIds.length === tabTransactions.length ? "Deselect All" : "Select All"}
                            >
                              {selectedSuggestedIds.length === tabTransactions.length && tabTransactions.length > 0 ? (
                                <CheckSquare className="h-4 w-4 text-primary" />
                              ) : (
                                <Square className="h-4 w-4" />
                              )}
                            </button>
                          </th>
                          {renderSortHeader('Bank Date', 'date')}
                          {renderSortHeader('Type', 'type')}
                          {renderSortHeader('Amount', 'amount', 'right')}
                          {renderSortHeader('Chq / Ref', 'ref')}
                          {renderSortHeader('Bank Narration', 'description')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Candidate Book Voucher & Variance
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right w-28">
                            Action
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {tabTransactions.map(tx => {
                          const isSelected = selectedSuggestedIds.includes(tx.transaction_id)
                          return (
                            <tr 
                              key={tx.transaction_id}
                              className={cn(
                                "hover:bg-muted/40 transition-colors group",
                                isSelected && "bg-primary/5"
                              )}
                            >
                              <td className="px-3.5 py-3 text-center">
                                <button
                                  onClick={() => {
                                    setSelectedSuggestedIds(prev =>
                                      isSelected ? prev.filter(id => id !== tx.transaction_id) : [...prev, tx.transaction_id]
                                    )
                                  }}
                                  className="p-1 text-muted-foreground hover:text-primary transition-colors inline-flex items-center justify-center"
                                >
                                  {isSelected ? (
                                    <CheckSquare className="h-4 w-4 text-primary" />
                                  ) : (
                                    <Square className="h-4 w-4" />
                                  )}
                                </button>
                              </td>
                              <td className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap">
                                {formatDate(tx.transaction_date)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                <span className={cn(
                                  "text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md border",
                                  tx.transaction_type === 'CREDIT' 
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                                    : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                                )}>
                                  {tx.transaction_type}
                                </span>
                              </td>
                              <td className={cn(
                                "px-3.5 py-3 text-right font-black tabular-nums whitespace-nowrap",
                                tx.transaction_type === 'CREDIT' ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                              )}>
                                {tx.transaction_type === 'CREDIT' ? '+' : '-'}{formatCurrency(tx.amount)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                {tx.cheque_no ? (
                                  <span className="text-[11px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
                                    Chq: {tx.cheque_no}
                                  </span>
                                ) : tx.reference_no ? (
                                  <span className="text-[11px] font-mono font-medium text-foreground bg-muted px-2 py-0.5 rounded border border-border">
                                    {tx.reference_no}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground text-[11px] italic">—</span>
                                )}
                              </td>
                              <td className="px-3.5 py-3 max-w-xs sm:max-w-md">
                                <p className="text-xs text-foreground font-medium line-clamp-2 break-words break-all [overflow-wrap:anywhere] leading-relaxed" title={tx.description}>
                                  {tx.description}
                                </p>
                              </td>
                              <td className="px-3.5 py-3 max-w-sm">
                                {tx.voucher ? (
                                  <div className="space-y-1">
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      <button
                                        type="button"
                                        onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id, {
                                          transaction_id: tx.transaction_id,
                                          transaction_date: tx.transaction_date,
                                          transaction_type: tx.transaction_type,
                                          amount: tx.amount,
                                          description: tx.description,
                                          reference_no: tx.reference_no,
                                          cheque_no: tx.cheque_no,
                                          match_notes: tx.match_notes
                                        })}
                                        className="inline-flex items-center gap-1 group/v cursor-pointer text-left"
                                        title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                                      >
                                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 group-hover/v:bg-purple-500/20 group-hover/v:border-purple-500/40 transition-all flex items-center gap-1 cursor-pointer">
                                          <span>{tx.voucher.voucher_type} #{tx.voucher.voucher_number}</span>
                                          <Eye className="h-2.5 w-2.5 opacity-70 group-hover/v:opacity-100" />
                                        </span>
                                      </button>
                                      <span className="text-[11px] font-medium text-muted-foreground">
                                        {formatDate(tx.voucher.date)}
                                      </span>
                                    </div>
                                    {tx.voucher.narration && (
                                      <p className="text-[11px] text-muted-foreground break-words break-all [overflow-wrap:anywhere] max-w-xs">
                                        {tx.voucher.narration}
                                      </p>
                                    )}
                                    {tx.match_notes && (
                                      <button
                                        type="button"
                                        onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id, {
                                          transaction_id: tx.transaction_id,
                                          transaction_date: tx.transaction_date,
                                          transaction_type: tx.transaction_type,
                                          amount: tx.amount,
                                          description: tx.description,
                                          reference_no: tx.reference_no,
                                          cheque_no: tx.cheque_no,
                                          match_notes: tx.match_notes
                                        })}
                                        className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 dark:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 px-2 py-0.5 rounded border border-amber-500/20 hover:border-amber-500/40 transition-colors group/note cursor-pointer text-left"
                                        title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                                      >
                                        <Sparkles className="h-3 w-3 text-amber-500 shrink-0" />
                                        <span>{tx.match_notes}</span>
                                        <Eye className="h-2.5 w-2.5 opacity-60 group-hover/note:opacity-100 ml-0.5" />
                                      </button>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground italic">No candidate linked</span>
                                )}
                              </td>
                              <td className="px-3.5 py-3 text-right whitespace-nowrap">
                                {tx.voucher && (
                                  <div className="flex items-center justify-end gap-1.5">
                                    <button
                                      onClick={() => handleConfirmMatch(tx.transaction_id, tx.voucher!.voucher_id)}
                                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1 transition-colors shadow-2xs"
                                      title="Approve Match"
                                    >
                                      <Check className="h-3.5 w-3.5" />
                                      <span>Approve</span>
                                    </button>
                                    <button
                                      onClick={() => handleUnmatch(tx.transaction_id)}
                                      className="p-1.5 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-xl transition-colors"
                                      title="Dismiss Suggestion"
                                    >
                                      <X className="h-4 w-4" />
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  tabTransactions.map(tx => (
                    <div 
                      key={tx.transaction_id}
                      className="bg-card border border-amber-500/30 rounded-2xl p-4 shadow-sm space-y-3 hover:border-amber-500/60 transition-all"
                    >
                      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                        {/* Left: Statement Entry */}
                        <div className="flex-1 space-y-1 min-w-0 w-full">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-600 border border-blue-500/20 shrink-0">
                              Bank Statement
                            </span>
                            <span className="text-xs font-bold text-foreground shrink-0">
                              {formatDate(tx.transaction_date)}
                            </span>
                            <span className={cn(
                              "text-xs font-black px-2 py-0.5 rounded-md shrink-0",
                              tx.transaction_type === 'CREDIT' ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                            )}>
                              {tx.transaction_type}: {formatCurrency(tx.amount)}
                            </span>
                          </div>
                          <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                            {tx.description}
                          </p>
                          {tx.reference_no && (
                            <p className="text-[11px] text-muted-foreground break-words break-all">
                              Ref/UTR: <span className="font-mono text-foreground font-semibold">{tx.reference_no}</span>
                            </p>
                          )}
                        </div>

                        {/* Center: Match Badge */}
                        <div className="shrink-0 flex items-center justify-center">
                          <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 rounded-xl text-xs font-bold">
                            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                            <span>Suggested Match</span>
                          </div>
                        </div>

                        {/* Right: Candidate Book Voucher */}
                        {tx.voucher && (
                          <div className="flex-1 space-y-1 lg:text-right border-t lg:border-t-0 pt-3 lg:pt-0 border-border min-w-0 w-full">
                            <div className="flex items-center lg:justify-end gap-2 flex-wrap">
                              <button
                                type="button"
                                onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id, {
                                  transaction_id: tx.transaction_id,
                                  transaction_date: tx.transaction_date,
                                  transaction_type: tx.transaction_type,
                                  amount: tx.amount,
                                  description: tx.description,
                                  reference_no: tx.reference_no,
                                  cheque_no: tx.cheque_no,
                                  match_notes: tx.match_notes
                                })}
                                className="inline-flex items-center gap-1 group/v shrink-0 cursor-pointer"
                                title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                              >
                                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-600 border border-purple-500/20 group-hover/v:bg-purple-500/20 group-hover/v:border-purple-500/40 transition-all flex items-center gap-1 cursor-pointer">
                                  <span>{tx.voucher.voucher_type} #{tx.voucher.voucher_number}</span>
                                  <Eye className="h-2.5 w-2.5 opacity-70 group-hover/v:opacity-100" />
                                </span>
                              </button>
                              <span className="text-xs font-bold text-foreground shrink-0">
                                {formatDate(tx.voucher.date)}
                              </span>
                            </div>
                            <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                              {tx.voucher.narration || 'Book Voucher'}
                            </p>
                            <button
                              type="button"
                              onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id, {
                                transaction_id: tx.transaction_id,
                                transaction_date: tx.transaction_date,
                                transaction_type: tx.transaction_type,
                                amount: tx.amount,
                                description: tx.description,
                                reference_no: tx.reference_no,
                                cheque_no: tx.cheque_no,
                                match_notes: tx.match_notes
                              })}
                              className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors break-words break-all cursor-pointer text-left"
                              title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                            >
                              <span>{tx.match_notes}</span>
                              <Eye className="h-2.5 w-2.5 opacity-60 shrink-0" />
                            </button>
                          </div>
                        )}

                        {/* Approve Button */}
                        {tx.voucher && (
                          <div className="shrink-0 flex items-center gap-2">
                            <button
                              onClick={() => handleConfirmMatch(tx.transaction_id, tx.voucher!.voucher_id)}
                              className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors shadow-sm"
                            >
                              <Check className="h-3.5 w-3.5" />
                              <span>Approve</span>
                            </button>
                            <button
                              onClick={() => handleUnmatch(tx.transaction_id)}
                              className="p-1.5 text-muted-foreground hover:text-rose-600 rounded-lg"
                              title="Dismiss Suggestion"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab 2: Unmatched in Bank (Pending Review Queue) */}
            {activeTab === 'unmatched_bank' && (
              <div className="space-y-3">
                {/* Audit Policy Notice */}
                <div className="bg-muted/40 border border-border/80 rounded-2xl p-3 flex items-center gap-2 text-xs">
                  <Shield className="h-4 w-4 text-primary shrink-0" />
                  <span className="text-muted-foreground">
                    <strong className="text-foreground">Reconciliation Policy:</strong> Every bank transaction is saved here for audit. Link to an existing Tally voucher, or mark non-business / external entries as Admin Reviewed without creating new vouchers.
                  </span>
                </div>

                {tabTransactions.length === 0 ? (
                  <div className="bg-card border border-border rounded-3xl p-10 text-center space-y-2">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                    <h4 className="text-sm font-bold text-foreground">Zero Unmatched Bank Transactions</h4>
                    <p className="text-xs text-muted-foreground">
                      {typeFilter !== 'ALL' || searchQuery
                        ? 'No pending transactions match your filter criteria.'
                        : 'Every statement row has either been matched to a corresponding Tally voucher or classified by Admin.'}
                    </p>
                  </div>
                ) : viewMode === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-xs">
                    <table className="w-full min-w-[760px] text-left text-xs border-collapse">
                      <thead className="bg-muted/60 border-b border-border text-muted-foreground select-none">
                        <tr>
                          <th className="w-10 px-3.5 py-3 text-center">
                            <button
                              onClick={() => {
                                if (selectedTxIds.length === tabTransactions.length && tabTransactions.length > 0) {
                                  setSelectedTxIds([])
                                } else {
                                  setSelectedTxIds(tabTransactions.map(t => t.transaction_id))
                                }
                              }}
                              className="p-1 text-muted-foreground hover:text-primary transition-colors inline-flex items-center justify-center"
                              title={selectedTxIds.length === tabTransactions.length ? "Deselect All" : "Select All"}
                            >
                              {selectedTxIds.length === tabTransactions.length && tabTransactions.length > 0 ? (
                                <CheckSquare className="h-4 w-4 text-primary" />
                              ) : (
                                <Square className="h-4 w-4" />
                              )}
                            </button>
                          </th>
                          {renderSortHeader('Date', 'date')}
                          {renderSortHeader('Type', 'type')}
                          {renderSortHeader('Amount', 'amount', 'right')}
                          {renderSortHeader('Chq / Ref', 'ref')}
                          {renderSortHeader('Description & Balance', 'description')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Status
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right w-44">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {tabTransactions.map(tx => {
                          const isSelected = selectedTxIds.includes(tx.transaction_id)
                          return (
                            <tr
                              key={tx.transaction_id}
                              className={cn(
                                "hover:bg-muted/40 transition-colors group",
                                isSelected && "bg-primary/5"
                              )}
                            >
                              <td className="px-3.5 py-3 text-center">
                                <button
                                  onClick={() => {
                                    setSelectedTxIds(prev =>
                                      isSelected ? prev.filter(id => id !== tx.transaction_id) : [...prev, tx.transaction_id]
                                    )
                                  }}
                                  className="p-1 text-muted-foreground hover:text-primary transition-colors inline-flex items-center justify-center"
                                >
                                  {isSelected ? (
                                    <CheckSquare className="h-4 w-4 text-primary" />
                                  ) : (
                                    <Square className="h-4 w-4" />
                                  )}
                                </button>
                              </td>
                              <td className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap">
                                {formatDate(tx.transaction_date)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                <span className={cn(
                                  "text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md border",
                                  tx.transaction_type === 'CREDIT' 
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                                    : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                                )}>
                                  {tx.transaction_type}
                                </span>
                              </td>
                              <td className={cn(
                                "px-3.5 py-3 text-right font-black tabular-nums whitespace-nowrap",
                                tx.transaction_type === 'CREDIT' ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                              )}>
                                {tx.transaction_type === 'CREDIT' ? '+' : '-'}{formatCurrency(tx.amount)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                {tx.cheque_no ? (
                                  <span className="text-[11px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
                                    Chq: {tx.cheque_no}
                                  </span>
                                ) : tx.reference_no ? (
                                  <span className="text-[11px] font-mono font-medium text-foreground bg-muted px-2 py-0.5 rounded border border-border">
                                    {tx.reference_no}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground text-[11px] italic">—</span>
                                )}
                              </td>
                              <td className="px-3.5 py-3 max-w-sm sm:max-w-md">
                                <p className="text-xs text-foreground font-medium line-clamp-2 break-words break-all [overflow-wrap:anywhere] leading-relaxed" title={tx.description}>
                                  {tx.description}
                                </p>
                                {tx.running_balance !== null && tx.running_balance !== undefined && (
                                  <span className="text-[10px] text-muted-foreground font-mono mt-0.5 block">
                                    Running Balance: {formatCurrency(tx.running_balance)}
                                  </span>
                                )}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20">
                                  Pending Review
                                </span>
                              </td>
                              <td className="px-3.5 py-3 text-right whitespace-nowrap">
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => {
                                      setMatchingTx(tx)
                                      setSelectedBookVoucherId(null)
                                    }}
                                    className="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground border border-primary/20 transition-all flex items-center gap-1 shadow-2xs"
                                    title="Link to an existing voucher in Tally"
                                  >
                                    <Link2 className="h-3.5 w-3.5" />
                                    <span>Link</span>
                                  </button>
                                  <button
                                    onClick={() => handleOpenReviewModal(tx)}
                                    className="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500 hover:text-white border border-amber-500/20 transition-all flex items-center gap-1 shadow-2xs"
                                    title="Mark as Non-Specific, Bank Charges, or Personal without creating vouchers"
                                  >
                                    <Shield className="h-3.5 w-3.5" />
                                    <span>Review</span>
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  tabTransactions.map(tx => {
                    const isSelected = selectedTxIds.includes(tx.transaction_id)
                    return (
                      <div 
                        key={tx.transaction_id}
                        className={cn(
                          "bg-card border rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all",
                          isSelected ? "border-primary bg-primary/5" : "border-border hover:border-border/80"
                        )}
                      >
                        <div className="flex items-start gap-3 min-w-0 flex-1 w-full">
                          <button
                            onClick={() => {
                              setSelectedTxIds(prev => 
                                isSelected ? prev.filter(id => id !== tx.transaction_id) : [...prev, tx.transaction_id]
                              )
                            }}
                            className="mt-0.5 p-1 text-muted-foreground hover:text-primary transition-colors shrink-0"
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4 text-primary" />
                            ) : (
                              <Square className="h-4 w-4" />
                            )}
                          </button>

                          <div className="space-y-1.5 min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-bold text-foreground shrink-0">{formatDate(tx.transaction_date)}</span>
                              <span className={cn(
                                "text-xs font-black px-2 py-0.5 rounded-md shrink-0",
                                tx.transaction_type === 'CREDIT' ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                              )}>
                                {tx.transaction_type}: {formatCurrency(tx.amount)}
                              </span>
                              {tx.cheque_no && (
                                <span className="text-[10px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded shrink-0">
                                  Chq: {tx.cheque_no}
                                </span>
                              )}
                              {tx.reference_no && !tx.cheque_no && (
                                <span className="text-[11px] font-mono font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded shrink-0">
                                  Ref: {tx.reference_no}
                                </span>
                              )}
                              {tx.running_balance !== null && tx.running_balance !== undefined && (
                                <span className="text-[10px] text-muted-foreground bg-muted/60 px-1.5 py-0.5 rounded shrink-0">
                                  Bal: {formatCurrency(tx.running_balance)}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                              {tx.description}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0 self-start sm:self-center pt-1 sm:pt-0">
                          <button
                            onClick={() => {
                              setMatchingTx(tx)
                              setSelectedBookVoucherId(null)
                            }}
                            className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground border border-primary/20 transition-all flex items-center gap-1.5 shadow-2xs"
                            title="Link to an existing voucher in Tally"
                          >
                            <Link2 className="h-3.5 w-3.5" />
                            <span>Link to Voucher</span>
                          </button>

                          <button
                            onClick={() => handleOpenReviewModal(tx)}
                            className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500 hover:text-white border border-amber-500/20 transition-all flex items-center gap-1.5 shadow-2xs"
                            title="Mark as Non-Specific, Bank Charges, or Personal without creating vouchers"
                          >
                            <Shield className="h-3.5 w-3.5" />
                            <span>Mark as Reviewed</span>
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}

            {/* Tab: Admin Reviewed (Non-Specific / Excluded Queue) */}
            {activeTab === 'reviewed' && (
              <div className="space-y-3">
                <div className="bg-blue-500/5 border border-blue-500/20 rounded-2xl p-3 flex items-center gap-2 text-xs text-blue-900 dark:text-blue-100">
                  <Shield className="h-4 w-4 text-blue-600 shrink-0" />
                  <span>
                    These bank transactions were verified by Admin as non-specific, personal drawings, bank fees, or external entries. They remain permanently preserved in the reconciliation database for 100% audit integrity without altering Tally vouchers.
                  </span>
                </div>

                {tabTransactions.length === 0 ? (
                  <div className="bg-card border border-border rounded-3xl p-10 text-center space-y-2">
                    <Shield className="h-8 w-8 text-blue-500 mx-auto opacity-70" />
                    <h4 className="text-sm font-bold text-foreground">No Admin Reviewed Entries</h4>
                    <p className="text-xs text-muted-foreground">
                      {typeFilter !== 'ALL' || searchQuery
                        ? 'No reviewed entries match your filter criteria.'
                        : 'Transactions you mark as "Not Specific to this account", "Bank Charges", or "Personal Drawings" in the Pending Review tab will appear here.'}
                    </p>
                  </div>
                ) : viewMode === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-xs">
                    <table className="w-full min-w-[760px] text-left text-xs border-collapse">
                      <thead className="bg-muted/60 border-b border-border text-muted-foreground select-none">
                        <tr>
                          {renderSortHeader('Date', 'date')}
                          {renderSortHeader('Type', 'type')}
                          {renderSortHeader('Amount', 'amount', 'right')}
                          {renderSortHeader('Chq / Ref', 'ref')}
                          {renderSortHeader('Bank Narration', 'description')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Classification
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Audit Remarks & Reviewer
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right w-28">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {tabTransactions.map(tx => {
                          const cat = REVIEW_CATEGORIES.find(c => c.id === tx.review_status) || REVIEW_CATEGORIES[0]
                          return (
                            <tr key={tx.transaction_id} className="hover:bg-muted/40 transition-colors group">
                              <td className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap">
                                {formatDate(tx.transaction_date)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                <span className={cn(
                                  "text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md border",
                                  tx.transaction_type === 'CREDIT' 
                                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                                    : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                                )}>
                                  {tx.transaction_type}
                                </span>
                              </td>
                              <td className={cn(
                                "px-3.5 py-3 text-right font-black tabular-nums whitespace-nowrap",
                                tx.transaction_type === 'CREDIT' ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                              )}>
                                {tx.transaction_type === 'CREDIT' ? '+' : '-'}{formatCurrency(tx.amount)}
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                {tx.cheque_no ? (
                                  <span className="text-[11px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
                                    Chq: {tx.cheque_no}
                                  </span>
                                ) : tx.reference_no ? (
                                  <span className="text-[11px] font-mono font-medium text-foreground bg-muted px-2 py-0.5 rounded border border-border">
                                    {tx.reference_no}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground text-[11px] italic">—</span>
                                )}
                              </td>
                              <td className="px-3.5 py-3 max-w-xs sm:max-w-md">
                                <p className="text-xs text-foreground font-medium line-clamp-2 break-words break-all [overflow-wrap:anywhere] leading-relaxed" title={tx.description}>
                                  {tx.description}
                                </p>
                              </td>
                              <td className="px-3.5 py-3 whitespace-nowrap">
                                <span className={cn("text-[10px] font-bold px-2.5 py-1 rounded-md border inline-block", cat.badgeColor)}>
                                  {cat.label}
                                </span>
                              </td>
                              <td className="px-3.5 py-3 max-w-xs">
                                <div className="space-y-0.5">
                                  {tx.review_notes && (
                                    <p className="italic text-xs text-foreground font-medium line-clamp-2 break-words break-all [overflow-wrap:anywhere]">
                                      "{tx.review_notes}"
                                    </p>
                                  )}
                                  <p className="text-[10px] text-muted-foreground">
                                    {tx.reviewed_by && <span>By <strong className="text-foreground">{tx.reviewed_by}</strong> </span>}
                                    {tx.reviewed_at && <span>on {formatDate(tx.reviewed_at)}</span>}
                                  </p>
                                </div>
                              </td>
                              <td className="px-3.5 py-3 text-right whitespace-nowrap">
                                <div className="flex items-center justify-end gap-1">
                                  <button
                                    onClick={() => handleOpenReviewModal(tx)}
                                    className="px-2 py-1 rounded-lg text-xs font-bold border border-border bg-card hover:bg-muted/50 transition-all flex items-center gap-1"
                                    title="Edit classification or remarks"
                                  >
                                    <Tag className="h-3 w-3 text-muted-foreground" />
                                    <span>Edit</span>
                                  </button>
                                  <button
                                    onClick={() => handleRevertToPending(tx.transaction_id)}
                                    className="p-1 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-lg transition-colors"
                                    title="Revert back to Unmatched Pending Review"
                                  >
                                    <Undo2 className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  tabTransactions.map(tx => {
                    const cat = REVIEW_CATEGORIES.find(c => c.id === tx.review_status) || REVIEW_CATEGORIES[0]
                    return (
                      <div 
                        key={tx.transaction_id}
                        className="bg-card border border-border rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-border/80 transition-all"
                      >
                        <div className="space-y-1.5 min-w-0 flex-1 w-full">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-foreground shrink-0">{formatDate(tx.transaction_date)}</span>
                            <span className={cn(
                              "text-xs font-black px-2 py-0.5 rounded-md shrink-0",
                              tx.transaction_type === 'CREDIT' ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                            )}>
                              {tx.transaction_type}: {formatCurrency(tx.amount)}
                            </span>
                            <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-md border shrink-0", cat.badgeColor)}>
                              {cat.label}
                            </span>
                            {tx.cheque_no && (
                              <span className="text-[10px] font-mono font-medium text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded shrink-0">
                                Chq: {tx.cheque_no}
                              </span>
                            )}
                            {tx.reference_no && !tx.cheque_no && (
                              <span className="text-[10px] font-mono font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded shrink-0">
                                Ref: {tx.reference_no}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                            {tx.description}
                          </p>
                          <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
                            {tx.review_notes && (
                              <span className="italic font-medium text-foreground bg-muted/60 px-2 py-0.5 rounded border border-border/60 break-words break-all">
                                "{tx.review_notes}"
                              </span>
                            )}
                            {tx.reviewed_by && (
                              <span>Reviewed by <strong className="text-foreground">{tx.reviewed_by}</strong></span>
                            )}
                            {tx.reviewed_at && (
                              <span>on {formatDate(tx.reviewed_at)}</span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                          <button
                            onClick={() => handleOpenReviewModal(tx)}
                            className="px-3 py-1.5 rounded-xl text-xs font-bold border border-border bg-card hover:bg-muted/50 transition-all flex items-center gap-1.5"
                            title="Edit classification or remarks"
                          >
                            <Tag className="h-3.5 w-3.5 text-muted-foreground" />
                            <span>Edit Note</span>
                          </button>
                          <button
                            onClick={() => handleRevertToPending(tx.transaction_id)}
                            className="p-2 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-xl transition-colors"
                            title="Revert back to Unmatched Pending Review"
                          >
                            <Undo2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}

            {/* Tab 3: Unmatched in Books */}
            {activeTab === 'unmatched_books' && (
              <div className="space-y-3">
                {filteredUnmatchedBooks.length === 0 ? (
                  <div className="bg-card border border-border rounded-3xl p-10 text-center space-y-2">
                    <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
                    <h4 className="text-sm font-bold text-foreground">No Unmatched Book Entries</h4>
                    <p className="text-xs text-muted-foreground">
                      {searchQuery ? 'No vouchers match your search term.' : 'All Tally vouchers for this bank ledger in this period have cleared the statement.'}
                    </p>
                  </div>
                ) : viewMode === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-xs">
                    <table className="w-full min-w-[760px] text-left text-xs border-collapse">
                      <thead className="bg-muted/60 border-b border-border text-muted-foreground select-none">
                        <tr>
                          {renderSortHeader('Voucher Date', 'date')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Voucher # & Type
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Party Name
                          </th>
                          {renderSortHeader('Amount', 'amount', 'right')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Cheque / Inst #
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Narration
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {filteredUnmatchedBooks.map(b => (
                          <tr key={b.voucher_id} className="hover:bg-muted/40 transition-colors group">
                            <td className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap">
                              {formatDate(b.date)}
                            </td>
                            <td className="px-3.5 py-3 whitespace-nowrap">
                              <button
                                type="button"
                                onClick={() => handleOpenVoucherModal(b.voucher_id)}
                                className="inline-flex items-center gap-1 group/v cursor-pointer text-left"
                                title={`View ${b.voucher_type} #${b.voucher_number} on this page`}
                              >
                                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 group-hover/v:bg-purple-500/20 group-hover/v:border-purple-500/40 transition-all flex items-center gap-1 cursor-pointer">
                                  <span>{b.voucher_type} #{b.voucher_number}</span>
                                  <Eye className="h-2.5 w-2.5 opacity-70 group-hover/v:opacity-100" />
                                </span>
                              </button>
                            </td>
                            <td className="px-3.5 py-3 font-bold text-foreground break-words break-all [overflow-wrap:anywhere]">
                              {b.party_name}
                            </td>
                            <td className="px-3.5 py-3 text-right font-black tabular-nums whitespace-nowrap text-foreground">
                              {formatCurrency(b.amount)}
                            </td>
                            <td className="px-3.5 py-3 font-mono text-muted-foreground whitespace-nowrap">
                              {b.instrument_number || '—'}
                            </td>
                            <td className="px-3.5 py-3 max-w-xs text-muted-foreground break-words break-all [overflow-wrap:anywhere]" title={b.narration}>
                              {b.narration || '—'}
                            </td>
                            <td className="px-3.5 py-3 text-right whitespace-nowrap">
                              <span className="text-[10px] font-semibold text-amber-600 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                                Unpresented / In-Transit
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  filteredUnmatchedBooks.map(b => (
                    <div 
                      key={b.voucher_id}
                      className="bg-card border border-border rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="space-y-1 min-w-0 flex-1 w-full">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-foreground shrink-0">{formatDate(b.date)}</span>
                          <button
                            type="button"
                            onClick={() => handleOpenVoucherModal(b.voucher_id)}
                            className="inline-flex items-center gap-1 group/v shrink-0 cursor-pointer"
                            title={`View ${b.voucher_type} #${b.voucher_number} on this page`}
                          >
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-500/10 text-purple-600 border border-purple-500/20 group-hover/v:bg-purple-500/20 group-hover/v:border-purple-500/40 transition-all flex items-center gap-1 cursor-pointer">
                              <span>{b.voucher_type} #{b.voucher_number}</span>
                              <Eye className="h-2.5 w-2.5 opacity-70 group-hover/v:opacity-100" />
                            </span>
                          </button>
                          <span className="text-xs font-black text-foreground shrink-0">
                            {formatCurrency(b.amount)}
                          </span>
                          {b.instrument_number && (
                            <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                              Chq: {b.instrument_number}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                          Party: <span className="font-bold">{b.party_name}</span>
                        </p>
                        {b.narration && (
                          <p className="text-[11px] text-muted-foreground italic break-words break-all [overflow-wrap:anywhere] leading-relaxed">
                            {b.narration}
                          </p>
                        )}
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        <span className="text-[11px] font-semibold text-amber-600 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                          Unpresented / In-Transit
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab 4: Reconciled History */}
            {activeTab === 'matched' && (
              <div className="space-y-3">
                {tabTransactions.length === 0 ? (
                  <div className="bg-card border border-border rounded-3xl p-10 text-center space-y-2">
                    <Clock className="h-8 w-8 text-muted-foreground mx-auto" />
                    <h4 className="text-sm font-bold text-foreground">No Matched Entries Found</h4>
                    <p className="text-xs text-muted-foreground">
                      {typeFilter !== 'ALL' || searchQuery ? 'No reconciled entries match your filter criteria.' : 'Matched entries will appear here with an undo option.'}
                    </p>
                  </div>
                ) : viewMode === 'table' ? (
                  <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-xs">
                    <table className="w-full min-w-[760px] text-left text-xs border-collapse">
                      <thead className="bg-muted/60 border-b border-border text-muted-foreground select-none">
                        <tr>
                          {renderSortHeader('Bank Date', 'date')}
                          {renderSortHeader('Type', 'type')}
                          {renderSortHeader('Amount', 'amount', 'right')}
                          {renderSortHeader('Chq / Ref', 'ref')}
                          {renderSortHeader('Bank Narration', 'description')}
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Linked Book Voucher
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Match Details & Notes
                          </th>
                          <th className="px-3.5 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right w-20">
                            Unlink
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {tabTransactions.map(tx => (
                          <tr key={tx.transaction_id} className="hover:bg-muted/40 transition-colors group">
                            <td className="px-3.5 py-3 font-semibold text-foreground whitespace-nowrap">
                              {formatDate(tx.transaction_date)}
                            </td>
                            <td className="px-3.5 py-3 whitespace-nowrap">
                              <span className={cn(
                                "text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md border",
                                tx.transaction_type === 'CREDIT' 
                                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                                  : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                              )}>
                                {tx.transaction_type}
                              </span>
                            </td>
                            <td className={cn(
                              "px-3.5 py-3 text-right font-black tabular-nums whitespace-nowrap",
                              tx.transaction_type === 'CREDIT' ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                            )}>
                              {tx.transaction_type === 'CREDIT' ? '+' : '-'}{formatCurrency(tx.amount)}
                            </td>
                            <td className="px-3.5 py-3 whitespace-nowrap">
                              {tx.cheque_no ? (
                                <span className="text-[11px] font-mono font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
                                  Chq: {tx.cheque_no}
                                </span>
                              ) : tx.reference_no ? (
                                <span className="text-[11px] font-mono font-medium text-foreground bg-muted px-2 py-0.5 rounded border border-border">
                                  {tx.reference_no}
                                </span>
                              ) : (
                                <span className="text-muted-foreground text-[11px] italic">—</span>
                              )}
                            </td>
                            <td className="px-3.5 py-3 max-w-xs sm:max-w-md">
                              <p className="text-xs text-foreground font-medium line-clamp-2 break-words break-all [overflow-wrap:anywhere] leading-relaxed" title={tx.description}>
                                {tx.description}
                              </p>
                            </td>
                            <td className="px-3.5 py-3 max-w-xs">
                              {tx.voucher ? (
                                <div className="space-y-0.5">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <button
                                      type="button"
                                      onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id)}
                                      className="inline-flex items-center gap-1 group/v shrink-0 cursor-pointer"
                                      title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                                    >
                                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 group-hover/v:bg-emerald-500/20 group-hover/v:border-emerald-500/40 transition-all flex items-center gap-1 cursor-pointer">
                                        <span>{tx.voucher.voucher_type} #{tx.voucher.voucher_number}</span>
                                        <Eye className="h-2.5 w-2.5 opacity-70 group-hover/v:opacity-100" />
                                      </span>
                                    </button>
                                    <span className="text-[11px] font-medium text-muted-foreground shrink-0">
                                      {formatDate(tx.voucher.date)}
                                    </span>
                                  </div>
                                  {tx.voucher.narration && (
                                    <p className="text-[11px] text-muted-foreground break-words break-all [overflow-wrap:anywhere]">
                                      {tx.voucher.narration}
                                    </p>
                                  )}
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground italic">Linked</span>
                              )}
                            </td>
                            <td className="px-3.5 py-3 text-[11px] text-muted-foreground">
                              <p className="break-words break-all">{tx.match_notes || `Matched on ${formatDate(tx.matched_at || '')}`}</p>
                              {tx.matched_by && <p className="text-[10px]">by <strong className="text-foreground">{tx.matched_by}</strong></p>}
                            </td>
                            <td className="px-3.5 py-3 text-right whitespace-nowrap">
                              <button
                                onClick={() => handleUnmatch(tx.transaction_id)}
                                className="p-1.5 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-xl transition-colors"
                                title="Unmatch / Revert"
                              >
                                <Unlink className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  tabTransactions.map(tx => (
                    <div 
                      key={tx.transaction_id}
                      className="bg-card border border-emerald-500/20 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="space-y-1 min-w-0 flex-1 w-full">
                        <div className="flex items-center gap-2 flex-wrap">
                          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                          <span className="text-xs font-bold text-foreground shrink-0">{formatDate(tx.transaction_date)}</span>
                          <span className={cn(
                            "text-xs font-bold px-2 py-0.5 rounded shrink-0",
                            tx.transaction_type === 'CREDIT' ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                          )}>
                            {tx.transaction_type}: {formatCurrency(tx.amount)}
                          </span>
                          {tx.voucher && (
                            <button
                              type="button"
                              onClick={() => handleOpenVoucherModal(tx.voucher!.voucher_id)}
                              className="text-xs font-semibold text-foreground hover:underline inline-flex items-center gap-1 group/v shrink-0 cursor-pointer"
                              title={`View ${tx.voucher.voucher_type} #${tx.voucher.voucher_number} on this page`}
                            >
                              <span>Matched with {tx.voucher.voucher_type} #{tx.voucher.voucher_number}</span>
                              <Eye className="h-3 w-3 opacity-60 group-hover/v:opacity-100" />
                            </button>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground break-words break-all [overflow-wrap:anywhere] leading-relaxed">{tx.description}</p>
                        <p className="text-[11px] text-muted-foreground break-words break-all">
                          {tx.match_notes || `Matched on ${formatDate(tx.matched_at || '')}`}
                          {tx.matched_by && ` by ${tx.matched_by}`}
                        </p>
                      </div>

                      <button
                        onClick={() => handleUnmatch(tx.transaction_id)}
                        className="p-2 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-xl transition-colors shrink-0"
                        title="Unmatch / Revert"
                      >
                        <Unlink className="h-4 w-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Tab 5: Statements Batches */}
            {activeTab === 'statements' && (
              <div className="space-y-3">
                {statements.map(s => {
                  const isCurrentFilter = dateFrom === s.statement_from && dateTo === s.statement_to
                  return (
                    <div 
                      key={s.statement_id}
                      className={cn(
                        "bg-card border rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all",
                        isCurrentFilter ? "border-primary ring-1 ring-primary/30" : "border-border hover:border-border/80"
                      )}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <FileSpreadsheet className="h-4 w-4 text-primary shrink-0" />
                          <span className="text-sm font-bold text-foreground">{s.filename}</span>
                          <span className={cn(
                            "text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full",
                            s.reconciled_pct === 100 
                              ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                              : "bg-amber-500/10 text-amber-600 border border-amber-500/20"
                          )}>
                            {s.reconciled_pct}% Reconciled
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Period: {formatDate(s.statement_from)} to {formatDate(s.statement_to)} • {s.total_transactions} Total Transactions
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <span className="text-xs font-bold text-foreground block">{formatCurrency(s.closing_balance)}</span>
                          <span className="text-[10px] text-muted-foreground">Closing Balance</span>
                        </div>
                        <button
                          onClick={() => {
                            setDateFrom(s.statement_from)
                            setDateTo(s.statement_to)
                            setDatePreset('custom')
                            setActiveTab('suggested')
                            toast.info(`Filtered to ${formatDate(s.statement_from)} – ${formatDate(s.statement_to)}`)
                          }}
                          className={cn(
                            "px-3 py-1.5 text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5",
                            isCurrentFilter
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted hover:bg-muted/80 text-foreground"
                          )}
                        >
                          <Calendar className="h-3 w-3" />
                          <span>{isCurrentFilter ? 'Active Period' : 'Filter by this Period'}</span>
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Statement Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-2xl sm:rounded-3xl max-w-lg w-full p-4 sm:p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-primary" />
                <h3 className="text-sm font-bold text-foreground">Import Bank Statement</h3>
              </div>
              <button 
                onClick={() => setShowUploadModal(false)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              {uploadError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 rounded-xl text-xs font-medium">
                  {uploadError}
                </div>
              )}
              {uploadSuccess && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 rounded-xl text-xs font-medium">
                  {uploadSuccess}
                </div>
              )}

              <div>
                <label className="text-xs font-bold text-foreground block mb-1">Target Bank Ledger</label>
                <select
                  value={selectedLedgerId || ''}
                  onChange={(e) => setSelectedLedgerId(Number(e.target.value))}
                  className="w-full text-xs font-semibold px-3 py-2 bg-background border border-border rounded-xl text-foreground focus:outline-none"
                >
                  {bankLedgers.map(l => (
                    <option key={l.ledger_id} value={l.ledger_id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-bold text-foreground block mb-1">Statement File (Excel .xlsx / .xls or CSV)</label>
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv,.txt,.tsv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-xs file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-primary file:text-primary-foreground hover:file:opacity-90 cursor-pointer bg-background border border-border rounded-xl p-2"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  Supports Punjab National Bank (PNB), HDFC, ICICI, SBI, Axis, Kotak exports in native Excel (.xlsx) or CSV format.
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Lock className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>Statement Password (If Encrypted)</span>
                  </label>
                  <span className="text-[10px] text-muted-foreground font-semibold uppercase tracking-wider">Optional</span>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="e.g. DOB (DDMMYYYY), PAN, or Account digits"
                    value={uploadPassword}
                    onChange={(e) => setUploadPassword(e.target.value)}
                    className="w-full text-xs px-3 py-2 pr-9 bg-background border border-border rounded-xl text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer p-0.5"
                    title={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Enter password if your downloaded bank statement is password-protected. The system will decrypt and import it securely.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-foreground block mb-1">Opening Balance (Optional)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="₹ 0.00"
                    value={uploadOpeningBal}
                    onChange={(e) => setUploadOpeningBal(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-background border border-border rounded-xl text-foreground"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold text-foreground block mb-1">Closing Balance (Optional)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="₹ 0.00"
                    value={uploadClosingBal}
                    onChange={(e) => setUploadClosingBal(e.target.value)}
                    className="w-full text-xs px-3 py-2 bg-background border border-border rounded-xl text-foreground"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !uploadFile}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isUploading ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                  <span>{isUploading ? 'Parsing & Matching...' : 'Upload & Reconcile'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Link Modal */}
      {matchingTx && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
              <div className="min-w-0 flex-1 pr-2">
                <h3 className="text-sm font-bold text-foreground">Link Statement Entry to Book Voucher</h3>
                <p className="text-xs text-muted-foreground">
                  Statement Line: {formatDate(matchingTx.transaction_date)} • {matchingTx.transaction_type}: {formatCurrency(matchingTx.amount)}
                </p>
                <p className="text-xs text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed mt-1">
                  {matchingTx.description}
                </p>
              </div>
              <button 
                onClick={() => setMatchingTx(null)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                Available Book Entries for this Bank
              </p>
              {unmatchedBooks.length === 0 ? (
                <p className="text-xs text-muted-foreground py-6 text-center">No unmatched book vouchers found in this period.</p>
              ) : (
                unmatchedBooks.map(b => (
                  <div
                    key={b.voucher_id}
                    onClick={() => setSelectedBookVoucherId(b.voucher_id)}
                    className={cn(
                      "p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-center justify-between gap-3",
                      selectedBookVoucherId === b.voucher_id
                        ? "bg-primary/10 border-primary text-foreground font-medium"
                        : "bg-muted/40 border-border hover:bg-muted/70 text-foreground"
                    )}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{b.voucher_type} #{b.voucher_number}</span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleOpenVoucherModal(b.voucher_id)
                          }}
                          className="p-1 rounded-md hover:bg-background/80 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                          title={`Preview ${b.voucher_type} #${b.voucher_number} on this page`}
                        >
                          <Eye className="h-3 w-3" />
                        </button>
                        <span className="text-muted-foreground">({formatDate(b.date)})</span>
                      </div>
                      <p className="text-muted-foreground">{b.party_name}</p>
                    </div>
                    <div className="text-right">
                      <span className="font-black text-sm block">{formatCurrency(b.amount)}</span>
                      {b.amount === matchingTx.amount && (
                        <span className="text-[10px] text-emerald-600 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">Exact ₹ Match</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-border shrink-0">
              <button
                type="button"
                onClick={() => setMatchingTx(null)}
                className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedBookVoucherId || isSubmittingMatch}
                onClick={() => selectedBookVoucherId && handleConfirmMatch(matchingTx.transaction_id, selectedBookVoucherId)}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
              >
                <Link2 className="h-3.5 w-3.5" />
                <span>Confirm Link</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Review / Classification Modal */}
      {showReviewModal && reviewingTx && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 flex items-center justify-center">
                  <Shield className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">Classify Bank Transaction</h3>
                  <p className="text-[11px] text-muted-foreground">Audit Record • No Voucher Created</p>
                </div>
              </div>
              <button 
                onClick={() => setShowReviewModal(false)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Transaction summary header */}
            <div className="bg-muted/40 p-3.5 rounded-2xl border border-border space-y-1 shrink-0 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-foreground">{formatDate(reviewingTx.transaction_date)}</span>
                <span className={cn(
                  "font-black px-2 py-0.5 rounded-md",
                  reviewingTx.transaction_type === 'CREDIT' ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                )}>
                  {reviewingTx.transaction_type}: {formatCurrency(reviewingTx.amount)}
                </span>
              </div>
              <p className="text-foreground font-medium break-words break-all [overflow-wrap:anywhere] leading-relaxed">{reviewingTx.description}</p>
              {reviewingTx.cheque_no && (
                <p className="text-[11px] text-muted-foreground break-words break-all">Cheque No: <span className="font-mono text-foreground font-semibold">{reviewingTx.cheque_no}</span></p>
              )}
              {reviewingTx.reference_no && !reviewingTx.cheque_no && (
                <p className="text-[11px] text-muted-foreground break-words break-all">Ref / UTR: <span className="font-mono text-foreground font-semibold">{reviewingTx.reference_no}</span></p>
              )}
            </div>

            {/* Category selection */}
            <div className="space-y-2 flex-1 overflow-y-auto pr-1">
              <label className="text-xs font-bold text-foreground block">Select Audit Classification</label>
              <div className="space-y-2">
                {REVIEW_CATEGORIES.map(cat => (
                  <div
                    key={cat.id}
                    onClick={() => setReviewStatus(cat.id)}
                    className={cn(
                      "p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-start gap-3",
                      reviewStatus === cat.id
                        ? "bg-primary/10 border-primary text-foreground font-medium shadow-2xs"
                        : "bg-card border-border hover:bg-muted/40 text-foreground"
                    )}
                  >
                    <input
                      type="radio"
                      name="review_cat"
                      checked={reviewStatus === cat.id}
                      onChange={() => setReviewStatus(cat.id)}
                      className="mt-0.5 cursor-pointer accent-primary"
                    />
                    <div>
                      <span className="font-bold block text-foreground">{cat.label}</span>
                      <span className="text-[11px] text-muted-foreground">{cat.description}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Notes */}
              <div className="pt-2">
                <label className="text-xs font-bold text-foreground block mb-1">Audit Notes / Explanation (Optional)</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Proprietor personal drawing, to be booked separately..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  className="w-full text-xs p-2.5 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-border shrink-0">
              {reviewingTx.review_status && reviewingTx.review_status !== 'pending_review' ? (
                <button
                  type="button"
                  onClick={() => handleRevertToPending(reviewingTx.transaction_id)}
                  className="px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-500/10 rounded-xl font-semibold"
                >
                  Reset to Pending
                </button>
              ) : <div />}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowReviewModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={submittingReview}
                  onClick={() => handleSaveReview()}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
                >
                  {submittingReview ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                  <span>Save Classification</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Batch Review Modal */}
      {showBatchReviewModal && selectedTxIds.length > 0 && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 flex items-center justify-center">
                  <Tag className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-foreground">Batch Classify {selectedTxIds.length} Transactions</h3>
                  <p className="text-[11px] text-muted-foreground">Bulk classify selected non-matching bank entries</p>
                </div>
              </div>
              <button 
                onClick={() => setShowBatchReviewModal(false)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Category selection */}
            <div className="space-y-2 flex-1 overflow-y-auto pr-1">
              <label className="text-xs font-bold text-foreground block">Apply Audit Classification to All {selectedTxIds.length} Rows</label>
              <div className="space-y-2">
                {REVIEW_CATEGORIES.map(cat => (
                  <div
                    key={cat.id}
                    onClick={() => setReviewStatus(cat.id)}
                    className={cn(
                      "p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-start gap-3",
                      reviewStatus === cat.id
                        ? "bg-primary/10 border-primary text-foreground font-medium shadow-2xs"
                        : "bg-card border-border hover:bg-muted/40 text-foreground"
                    )}
                  >
                    <input
                      type="radio"
                      name="batch_review_cat"
                      checked={reviewStatus === cat.id}
                      onChange={() => setReviewStatus(cat.id)}
                      className="mt-0.5 cursor-pointer accent-primary"
                    />
                    <div>
                      <span className="font-bold block text-foreground">{cat.label}</span>
                      <span className="text-[11px] text-muted-foreground">{cat.description}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Notes */}
              <div className="pt-2">
                <label className="text-xs font-bold text-foreground block mb-1">Batch Note / Remark (Optional)</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Bank SMS / AMC recurring service charges..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  className="w-full text-xs p-2.5 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-border shrink-0">
              <button
                type="button"
                onClick={() => setShowBatchReviewModal(false)}
                className="px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submittingReview}
                onClick={handleBatchSaveReview}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 shadow-sm"
              >
                {submittingReview ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                <span>Apply to All ({selectedTxIds.length})</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Voucher / Receipt Detail Modal on the Same Page */}
      <VoucherDetailModal
        isOpen={isVoucherModalOpen}
        voucherId={modalVoucherId}
        token={token}
        onClose={() => {
          setIsVoucherModalOpen(false)
          setModalVoucherId(null)
          setModalBankTx(null)
        }}
        bankTx={modalBankTx}
        onApproveMatch={handleConfirmMatch}
        isApproving={isSubmittingMatch}
      />
    </div>
  )
}
