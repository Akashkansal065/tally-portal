import { API_BASE, authHeaders } from '@/lib/utils'

/* A sales voucher's e-invoice (IRN) and e-way bill, through the GST Suvidha Provider (Phase 4). Each sits behind
   its Admin → Integrations switch; Demo mode makes labelled, made-up numbers. */

export interface EdocRecord {
  environment: string
  demo: boolean
  irn: string | null
  ack_no: string | null
  ack_date: string | null
  irn_status: 'active' | 'cancelled' | null
  signed_qr: string | null
  eway_bill_no: string | null
  eway_bill_date: string | null
  ewb_valid_till: string | null
  ewb_status: 'active' | 'cancelled' | null
}

export interface VoucherEdocs {
  mode: 'demo' | 'live'
  is_b2b: boolean
  invoice_total: number
  einvoice: { switch_on: boolean; keys_ready: boolean; problems: string[] }
  eway_bill: { switch_on: boolean; keys_ready: boolean; problems: string[] }
  record: EdocRecord | null
  can_cancel_irn: boolean
  can_cancel_ewb: boolean
}

export interface TransportInput {
  vehicle_no: string
  distance_km: number
  transporter_id?: string
  transporter_name?: string
  mode?: 'road' | 'rail' | 'air' | 'ship'
}

export interface GstDocsSettings {
  mode: 'demo' | 'live'
  gsp_provider: string
  gsp_account_ready: boolean
  company_gstin: string | null
  einvoice_username: string | null
  has_einvoice_password: boolean
  eway_username: string | null
  has_eway_password: boolean
}

export const IRN_CANCEL_REASONS = [['1', 'Duplicate'], ['2', 'Data entry mistake'], ['3', 'Order cancelled'], ['4', 'Others']] as const
export const EWB_CANCEL_REASONS = [['1', 'Duplicate'], ['2', 'Order cancelled'], ['3', 'Data entry mistake'], ['4', 'Others']] as const
export const VEHICLE_REASONS = [['1', 'Breakdown'], ['2', 'Transhipment'], ['3', 'Others'], ['4', 'First time']] as const

/** Errors come back as a message, or { message, problems[] } when details must be fixed first. */
export class EdocError extends Error {
  problems: string[]
  constructor(message: string, problems: string[] = []) {
    super(message)
    this.problems = problems
  }
}

async function call<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/gst${path}`, { ...init, headers: authHeaders(token) })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    let problems: string[] = []
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail?.message) { message = body.detail.message; problems = body.detail.problems || [] }
    } catch {}
    throw new EdocError(message, problems)
  }
  return res.json() as Promise<T>
}

export const getVoucherEdocs = (token: string, voucherId: number) => call<VoucherEdocs>(token, `/edocs/${voucherId}`)
export const generateIrn = (token: string, voucherId: number) =>
  call<EdocRecord & { detail: string }>(token, `/einvoice/${voucherId}/generate`, { method: 'POST' })
export const cancelIrn = (token: string, voucherId: number, reason: string, remark = '') =>
  call<EdocRecord>(token, `/einvoice/${voucherId}/cancel`, { method: 'POST', body: JSON.stringify({ reason, remark }) })
export const generateEwaybill = (token: string, voucherId: number, t: TransportInput) =>
  call<EdocRecord>(token, `/ewaybill/${voucherId}/generate`, { method: 'POST', body: JSON.stringify(t) })
export const updateVehicle = (token: string, voucherId: number, body: { vehicle_no: string; reason: string; from_place: string; remark?: string }) =>
  call<EdocRecord>(token, `/ewaybill/${voucherId}/vehicle`, { method: 'POST', body: JSON.stringify(body) })
export const cancelEwaybill = (token: string, voucherId: number, reason: string, remark = '') =>
  call<EdocRecord>(token, `/ewaybill/${voucherId}/cancel`, { method: 'POST', body: JSON.stringify({ reason, remark }) })
export const getGstDocsSettings = (token: string) => call<GstDocsSettings>(token, '/einvoice/settings')
export const saveGstDocsSettings = (token: string, body: Partial<{
  mode: 'demo' | 'live'; einvoice_username: string; einvoice_password: string; eway_username: string; eway_password: string
}>) => call<GstDocsSettings>(token, '/einvoice/settings', { method: 'PUT', body: JSON.stringify(body) })
