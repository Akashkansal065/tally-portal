import { API_BASE, authHeaders } from '@/lib/utils'

/* Voucher approval (maker-checker): vouchers matching a rule wait for the approving role before going to Tally. */

export interface ApprovalRule {
  rule_id: number
  voucher_type_id: number | null
  voucher_type: string
  min_amount: number
  approver_role_id: number
  approver_role: string | null
  is_active: boolean
}

export interface ApprovalItem {
  request_id: number
  status: 'Pending' | 'Approved' | 'Rejected'
  voucher_id: number
  voucher_number: string
  voucher_type: string | null
  voucher_date: string | null
  party: string | null
  amount: number
  requested_by: string | null
  requested_at: string | null
  acted_by: string | null
  acted_at: string | null
  note: string | null
  can_decide: boolean
  approver_role?: string | null
  can_resubmit?: boolean
}

async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/approvals${path}`, { ...init, headers: authHeaders(token) })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { const b = await res.json(); if (typeof b.detail === 'string') detail = b.detail } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getRules = (token: string) => call<ApprovalRule[]>(token, '/rules')
export const createRule = (token: string, body: { voucher_type_id: number | null; min_amount: number; approver_role_id: number }) =>
  call<ApprovalRule>(token, '/rules', { method: 'POST', body: JSON.stringify(body) })
export const removeRule = (token: string, id: number) => call<{ detail: string }>(token, `/rules/${id}`, { method: 'DELETE' })
export const getRequests = (token: string, scope: 'to_me' | 'mine' | 'all', status: 'Pending' | 'Rejected' | 'Approved' | 'all' = 'Pending') =>
  call<ApprovalItem[]>(token, `/requests?scope=${scope}&status=${status}`)
export const getSummary = (token: string) =>
  call<{ waiting_for_me: number; mine_pending: number; mine_rejected: number }>(token, '/summary')
export const getVoucherApproval = (token: string, voucherId: number) => call<ApprovalItem | null>(token, `/vouchers/${voucherId}`)
export const approve = (token: string, requestId: number, note = '') =>
  call<{ detail: string }>(token, `/requests/${requestId}/approve`, { method: 'POST', body: JSON.stringify({ note }) })
export const reject = (token: string, requestId: number, note: string) =>
  call<{ detail: string }>(token, `/requests/${requestId}/reject`, { method: 'POST', body: JSON.stringify({ note }) })
export const resubmit = (token: string, voucherId: number) =>
  call<{ detail: string; status: string }>(token, `/vouchers/${voucherId}/resubmit`, { method: 'POST' })
