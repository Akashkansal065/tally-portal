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
  discount_percent?: number;
  discount_amount?: number;
  rate_unit_id?: number | null;
  godown_id?: number | null;
  batch_id?: number | null;
  is_deemed_positive?: boolean;
  flow_type?: 'source' | 'destination' | null;
}

export interface VoucherItem {
  entry_id?: number;
  ledger_id: number;
  ledger_name?: string;
  amount: number;
  entry_type: 'Debit' | 'Credit';
  cost_center_id?: number | null;
  bank_allocations?: BankAllocation[];
  bill_allocations?: BillAllocation[];
}

export interface Voucher {
  voucher_id: number;
  company_id: number;
  voucher_number: string;
  date: string;
  type: 'Contra' | 'Payment' | 'Receipt' | 'Journal' | 'Sales' | 'Purchase';
  narration?: string | null;
  party_ledger_id?: number | null;
  is_invoice?: boolean;
  total_amount?: number;
  items: VoucherItem[];
  inventory_entries?: InventoryEntry[];
}
