'use client'

import { useState } from 'react'
import { AlertTriangle, Trash2, X } from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { toast } from 'sonner'

type Props = {
  isOpen: boolean
  ledgerId: number | null
  ledgerName: string
  onClose: () => void
  onSuccess: () => void
  token: string | null
}

export default function DeleteLedgerModal({
  isOpen,
  ledgerId,
  ledgerName,
  onClose,
  onSuccess,
  token
}: Props) {
  const [deleting, setDeleting] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  if (!isOpen || !ledgerId) return null

  const handleDelete = async () => {
    setDeleting(true)
    setErrorMsg('')
    try {
      const res = await fetch(`${API_BASE}/ledgers/${ledgerId}`, {
        method: 'DELETE',
        headers: authHeaders(token || '')
      })

      const resData = await res.json()
      if (!res.ok) {
        throw new Error(resData.detail || 'Failed to delete ledger')
      }

      if (resData.tally_synced === false) {
        toast.warning(`⚠️ Deleted locally, but Tally Prime sync failed: ${resData.tally_message || 'Cannot be deleted in Tally Prime'}`)
      } else {
        toast.success('Ledger deleted and removed from Tally Prime ✅')
      }

      onSuccess()
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Error deleting ledger')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card border border-border w-full max-w-sm rounded-2xl shadow-2xl overflow-hidden p-5 space-y-4">
        <div className="flex items-start justify-between">
          <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-600">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-all cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div>
          <h3 className="text-base font-extrabold text-foreground">Delete Ledger Master?</h3>
          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            Are you sure you want to delete <span className="font-bold text-foreground">"{ledgerName}"</span>?
          </p>
          <p className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold mt-2 bg-amber-50 dark:bg-amber-950/40 p-2.5 rounded-xl border border-amber-200/50">
            ⚠️ Note: Tally Prime only permits deleting ledgers that have <strong>zero voucher entries</strong>.
          </p>
        </div>

        {errorMsg && (
          <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold">
            {errorMsg}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            className="px-4 py-2 border border-border rounded-xl text-xs font-bold text-foreground hover:bg-muted transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-extrabold shadow-md transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {deleting ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="w-3.5 h-3.5" />
                Confirm Delete
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
