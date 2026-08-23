export interface User {
  user_id: number;
  username: string;
  email: string;
  role_id: number;
  role_name?: string;
  is_active: boolean;
}

export interface Role {
  role_id: number;
  name: string;
  description: string;
}

export interface Module {
  module_id: number;
  code: string;
  name: string;
  description: string;
}

export interface Permission {
  permission_id: number;
  role_id: number;
  module_id: number;
  can_create: boolean;
  can_read: boolean;
  can_update: boolean;
  can_delete: boolean;
}

export interface AccountGroup {
  group_id: number;
  company_id: number;
  name: string;
  parent_group_id?: number | null;
  nature?: string | null;
  affects_gross_profit?: boolean;
}

export interface Ledger {
  ledger_id: number;
  company_id: number;
  name: string;
  group_id: number;
  opening_balance: number;
  is_active: boolean;
  ledger_type?: string | null;
  closing_balance?: number | null;
  credit_period_days?: number | null;
  tax_classification_name?: string | null;
  gstin?: string | null;
  state?: string | null;
  gst_registrations?: LedgerGstRegistration[];
  msme_details?: LedgerMsmeDetail[];
  addresses?: LedgerAddress[];
  lower_deductions?: LedgerTdsLowerDeduction[];
}

export interface StockItem {
  stock_item_id: number;
  company_id: number;
  name: string;
  stock_group_id?: number | null;
  stock_category_id?: number | null;
  unit_id: number;
  hsn_code?: string | null;
  gst_rate_percent?: number | null;
  opening_qty?: number | null;
  closing_qty?: number | null;
  closing_rate?: number | null;
  closing_value?: number | null;
  costing_method?: string | null;
  valuation_method?: string | null;
  gst_type_of_supply?: string | null;
  is_batch_wise?: boolean;
  is_perishable?: boolean;
  ignore_negative_stock?: boolean;
  is_active: boolean;
}

export interface BankAllocation {
  allocation_id?: number;
  entry_id?: number;
  instrument_date?: string | null;
  transaction_type: string;
  payment_favouring?: string | null;
  instrument_number?: string | null;
  amount: number;
  transfer_mode?: string | null;
  virtual_payment_address?: string | null;
  cheque_cross_comment?: string | null;
  bank_name?: string | null;
  account_number?: string | null;
  ifs_code?: string | null;
  is_connected_payment?: boolean;
}

export interface BillAllocation {
  allocation_id?: number;
  voucher_entry_id?: number;
  bill_id?: number | null;
  bill_reference?: string | null;
  allocation_type: string;
  amount: number;
}

export interface InventoryEntry {
  stock_entry_id?: number;
  stock_item_id: number;
  stock_item_name?: string;
  quantity: number;
  rate: number;
  amount: number;
  billed_qty?: number | null;
  actual_quantity?: number | null;
  discount_percent?: number;
  discount_amount?: number;
  rate_unit_id?: number | null;
  godown_id?: number | null;
  batch_id?: number | null;
  item_description?: string | null;
  is_deemed_positive?: boolean;
  flow_type?: 'source' | 'destination' | null;
}

export interface LedgerGstRegistration {
  id?: number;
  ledger_id?: number;
  gstin: string;
  state_name?: string | null;
  place_of_supply?: string | null;
  registration_type?: string;
  applicable_from?: string | null;
  is_default?: boolean;
}

export interface HsnDetail {
  id?: number;
  company_id?: number;
  stock_item_id?: number | null;
  ledger_id?: number | null;
  hsn_code: string;
  hsn_description?: string | null;
  source_type?: string;
  taxability?: string;
  igst_rate?: number;
  cgst_rate?: number;
  sgst_rate?: number;
  applicable_from?: string | null;
  is_rcm?: boolean;
}

export interface EwayBillDetail {
  id?: number;
  voucher_id?: number;
  bill_number?: string | null;
  bill_date?: string | null;
  valid_up_to?: string | null;
  distance_km?: number | null;
  transporter_id?: string | null;
  transporter_name?: string | null;
  doc_number?: string | null;
  doc_date?: string | null;
  vehicle_number?: string | null;
  vehicle_type?: string;
  transport_mode?: string;
  sub_type?: string;
  doc_type?: string;
  status?: string;
}

export interface LedgerMsmeDetail {
  id?: number;
  ledger_id?: number;
  enterprise_type?: string;
  udyam_reg_no?: string | null;
  applicable_from?: string | null;
  is_active?: boolean;
}

export interface LedgerAddress {
  id?: number;
  ledger_id?: number;
  address_name: string;
  mailing_name?: string | null;
  address?: string | null;
  state_name?: string | null;
  country_name?: string;
  pincode?: string | null;
  is_default?: boolean;
}

export interface LedgerTdsLowerDeduction {
  id?: number;
  ledger_id?: number;
  section_number: string;
  certificate_no: string;
  rate_of_deduction: number;
  applicable_from?: string | null;
  applicable_to?: string | null;
  threshold_limit?: number | null;
}

export interface CostCentreAllocation {
  id?: number;
  entry_id?: number;
  cost_centre_id: number;
  cost_centre_name?: string;
  amount: number;
  percentage?: number | null;
}

export interface VoucherItem {
  entry_id?: number;
  ledger_id: number;
  ledger_name?: string;
  amount: number;
  entry_type: 'Debit' | 'Credit';
  cost_center_id?: number | null;
  nature_of_transaction?: string | null;
  bank_allocations?: BankAllocation[];
  bill_allocations?: BillAllocation[];
  cost_centre_allocations?: CostCentreAllocation[];
}

export interface Voucher {
  voucher_id: number;
  company_id: number;
  voucher_number: string;
  date: string;
  effective_date?: string | null;
  reference_date?: string | null;
  place_of_supply?: string | null;
  buyer_name?: string | null;
  buyer_address?: string | null;
  consignee_name?: string | null;
  consignee_address?: string | null;
  order_reference?: string | null;
  despatch_doc_no?: string | null;
  is_post_dated?: boolean;
  
  // e-Invoice fields
  irn?: string | null;
  irn_ack_no?: string | null;
  irn_ack_date?: string | null;
  irn_qr_code?: string | null;
  irn_cancelled?: boolean;
  irn_cancel_date?: string | null;
  irn_cancel_reason?: string | null;
  irn_source?: string | null;
  
  type: 'Contra' | 'Payment' | 'Receipt' | 'Journal' | 'Sales' | 'Purchase';
  narration?: string | null;
  party_ledger_id?: number | null;
  is_invoice?: boolean;
  total_amount?: number;
  items: VoucherItem[];
  inventory_entries?: InventoryEntry[];
  eway_bills?: EwayBillDetail[];
}
