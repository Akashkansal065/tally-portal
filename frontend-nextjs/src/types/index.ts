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

export interface VoucherItem {
  ledger_id: number;
  ledger_name?: string;
  amount: number;
  entry_type: 'Debit' | 'Credit';
}

export interface Voucher {
  voucher_id: number;
  company_id: number;
  voucher_number: string;
  date: string;
  type: 'Contra' | 'Payment' | 'Receipt' | 'Journal' | 'Sales' | 'Purchase';
  narration?: string | null;
  items: VoucherItem[];
}
