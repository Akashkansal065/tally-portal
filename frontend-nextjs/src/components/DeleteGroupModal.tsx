'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BookOpen, CheckCircle2, FolderTree, Loader2, RefreshCw, Trash2, X, XCircle } from 'lucide-react'
import { API_BASE, authHeaders, cn } from '@/lib/utils'

interface PlanItem {
  kind: 'group' | 'ledger' | 'item'
  name: string
  parent: string | null
  in_app: boolean
  in_tally: boolean
  is_root: boolean
  can_delete: boolean
  reason: string | null
}

interface DeletePlan {
  group_id: number
  group_name: string
  items: PlanItem[]
  blocker_count: number
  undeletable_count: number
  can_delete_all: boolean
  tally_checked: boolean
  tally_message: string | null
}

interface Outcome {
  message: string
  deleted: { kind: string; name: string }[]
  failed: { kind: string; name: string; reason: string }[]
}

interface DeleteGroupModalProps {
  group: { group_id: number; name: string } | null
  token: string
  onClose: () => void
  /** Called whenever something was deleted, including a delete that stopped part way. */
  onChanged: () => void
  /** API path of the group collection; the stock groups page passes its own. */
  apiPath?: string
  /** What the things inside the group are called: ledgers in account groups, stock items in stock groups. */
  memberLabel?: string
  title?: string
}

const where = (item: PlanItem) =>
  item.in_app && item.in_tally ? 'MyTally + Tally' : item.in_tally ? 'Tally only' : 'MyTally only'

/**
 * Deleting a group: shows every sub-group and ledger (or stock item) that stands in the way, in MyTally and in Tally,
 * says which of them can never be deleted and why, and offers to delete the rest together with the group.
 */
export default function DeleteGroupModal({
  group, token, onClose, onChanged, apiPath = '/ledgers/groups', memberLabel = 'ledger', title = 'Delete Group',
}: DeleteGroupModalProps) {
  const [plan, setPlan] = useState<DeletePlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState('')
  const [outcome, setOutcome] = useState<Outcome | null>(null)

  const fetchPlan = useCallback(async () => {
    if (!group) return
    try {
      const res = await fetch(`${API_BASE}${apiPath}/${group.group_id}/delete-preview`, { headers: authHeaders(token) })
      const data = await res.json()
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Could not check this group')
      setPlan(data)
    } catch (err) {
      setPlan(null)
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [group, token, apiPath])

  // The page mounts a fresh dialog per group, so the first check is all an effect has to do
  useEffect(() => {
    fetchPlan()
  }, [fetchPlan])

  const checkAgain = () => {
    setLoading(true)
    setError('')
    fetchPlan()
  }

  // Indent each item under its parent group
  const depthOf = useMemo(() => {
    const parents = new Map<string, string | null>()
    plan?.items.filter(i => i.kind === 'group').forEach(i => parents.set(i.name.toLowerCase(), i.parent))
    return (item: PlanItem) => {
      let depth = 0
      let parent = item.parent
      const seen = new Set<string>()
      while (parent && !seen.has(parent.toLowerCase())) {
        seen.add(parent.toLowerCase())
        depth += 1
        parent = parents.get(parent.toLowerCase()) ?? null
      }
      return depth
    }
  }, [plan])

  if (!group) return null

  const blockers = plan?.items.filter(i => !i.is_root) ?? []
  const subGroupCount = blockers.filter(i => i.kind === 'group').length
  const memberCount = blockers.length - subGroupCount
  const undeletable = blockers.filter(i => !i.can_delete)
  const root = plan?.items.find(i => i.is_root)
  const rootBlocked = !!root && !root.can_delete && undeletable.length === 0
  const canDelete = !!plan && plan.can_delete_all
  const needsConfirm = blockers.length > 0

  const handleDelete = async () => {
    if (!plan || deleting) return
    setDeleting(true)
    setError('')
    setOutcome(null)
    try {
      const res = await fetch(`${API_BASE}${apiPath}/${group.group_id}?cascade=${blockers.length > 0}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        onChanged()
        onClose()
        return
      }
      const detail = data.detail
      if (detail && typeof detail === 'object') {
        if (detail.deleted?.length) onChanged()
        setOutcome({ message: detail.message, deleted: detail.deleted ?? [], failed: detail.failed ?? [] })
        if (detail.plan) setPlan(detail.plan)
        setConfirmed(false)
      } else if (res.status === 404) {
        // Already deleted, by this request's first attempt or by someone else
        onChanged()
        onClose()
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to delete')
      }
    } catch (err) {
      setError(`${err instanceof Error ? err.message : String(err)}. Nothing is lost: check the list again and retry.`)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-card rounded-2xl w-full max-w-2xl shadow-2xl border border-border flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border bg-muted/20">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2.5 bg-rose-500/10 text-rose-600 rounded-xl">
              <Trash2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-xl font-black text-foreground tracking-tight">{title}</h2>
              <p className="text-sm text-muted-foreground mt-0.5 font-semibold truncate">{group.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={deleting}
            className="p-2 hover:bg-muted text-muted-foreground hover:text-foreground rounded-full transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-4">
          {loading && (
            <div className="flex items-center gap-3 text-sm text-muted-foreground py-8 justify-center">
              <Loader2 className="w-4 h-4 animate-spin" /> Checking MyTally and Tally for what this group contains...
            </div>
          )}

          {error && (
            <div className="flex gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-sm text-rose-600 font-semibold">
              <XCircle className="w-4 h-4 mt-0.5 shrink-0" /> <span>{error}</span>
            </div>
          )}

          {outcome && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-sm space-y-2">
              <div className="flex gap-3 font-bold text-amber-700">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" /> <span>{outcome.message}</span>
              </div>
              {outcome.deleted.length > 0 && (
                <p className="text-muted-foreground pl-7">Deleted: {outcome.deleted.map(d => d.name).join(', ')}</p>
              )}
              {outcome.failed.map(f => (
                <p key={`${f.kind}-${f.name}`} className="text-foreground pl-7">
                  <span className="font-bold">{f.name}</span>: {f.reason}
                </p>
              ))}
            </div>
          )}

          {plan && !loading && (
            <>
              {!plan.tally_checked && (
                <div className="flex gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-sm text-amber-700 font-semibold">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{plan.tally_message} Anything that exists only in Tally is not shown, and Tally may still refuse.</span>
                </div>
              )}

              {blockers.length === 0 ? (
                <p className="text-sm text-foreground">
                  {rootBlocked
                    ? root?.reason
                    : <>This group is empty. It will be deleted{plan.tally_checked ? ' in MyTally and in Tally' : ' in MyTally'}.</>}
                </p>
              ) : (
                <>
                  <p className="text-sm text-foreground">
                    This group cannot be deleted on its own because it contains{' '}
                    <span className="font-bold">
                      {[subGroupCount && `${subGroupCount} sub-group${subGroupCount === 1 ? '' : 's'}`,
                        memberCount && `${memberCount} ${memberLabel}${memberCount === 1 ? '' : 's'}`].filter(Boolean).join(' and ')}
                    </span>.
                    {undeletable.length > 0
                      ? <> {undeletable.length} of them cannot be deleted for the reasons shown, so nothing is deleted until those are resolved.</>
                      : <> They can all be deleted together with it.</>}
                  </p>

                  <div className="border border-border rounded-xl divide-y divide-border overflow-hidden">
                    {[...plan.items].reverse().map(item => (
                      <div
                        key={`${item.kind}-${item.name}`}
                        className={cn('flex items-start gap-3 px-4 py-2.5 text-sm', item.is_root && 'bg-muted/30')}
                        style={{ paddingLeft: `${16 + depthOf(item) * 20}px` }}
                      >
                        {item.kind === 'group'
                          ? <FolderTree className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
                          : <BookOpen className="w-4 h-4 mt-0.5 shrink-0 text-blue-600" />}
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <span className="font-bold text-foreground break-words">{item.name}</span>
                            <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                              {item.kind === 'group' ? (item.is_root ? 'This group' : 'Sub-group') : memberLabel} · {where(item)}
                            </span>
                          </div>
                          {!item.can_delete && item.reason && (
                            <p className="text-xs text-rose-600 font-semibold mt-0.5">{item.reason}</p>
                          )}
                        </div>
                        {item.can_delete
                          ? <span className="shrink-0 text-[11px] font-bold text-muted-foreground">{canDelete ? 'Will be deleted' : 'Can be deleted'}</span>
                          : <span className="shrink-0 text-[11px] font-bold text-rose-600">Cannot be deleted</span>}
                      </div>
                    ))}
                  </div>

                  {canDelete && (
                    <label className="flex items-start gap-3 text-sm text-foreground cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={confirmed}
                        onChange={e => setConfirmed(e.target.checked)}
                        disabled={deleting}
                        className="mt-0.5 w-4 h-4 accent-rose-600"
                      />
                      <span>
                        I understand that everything listed above will be permanently deleted
                        {plan.tally_checked ? ' in MyTally and in Tally' : ' in MyTally'}. This cannot be undone.
                      </span>
                    </label>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-6 border-t border-border bg-muted/20">
          <button
            onClick={checkAgain}
            disabled={loading || deleting}
            className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-muted-foreground hover:text-foreground rounded-xl hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} /> Check again
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              disabled={deleting}
              className="px-4 py-2 text-sm font-bold text-foreground rounded-xl hover:bg-muted transition-colors disabled:opacity-50"
            >
              {canDelete ? 'Cancel' : 'Close'}
            </button>
            {canDelete && (
              <button
                onClick={handleDelete}
                disabled={deleting || loading || (needsConfirm && !confirmed)}
                className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : needsConfirm ? <Trash2 className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
                {deleting ? 'Deleting...' : needsConfirm ? `Delete group and ${blockers.length} item${blockers.length === 1 ? '' : 's'}` : 'Delete group'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
