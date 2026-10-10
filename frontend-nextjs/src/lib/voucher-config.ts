// Which entry settings mean something for a voucher type. The settings belong to the app's own voucher
// form; Tally keeps its entry settings outside the company data, so none of them go to Tally.

export type VoucherConfigKey =
  | 'use_cr_dr'
  | 'show_ledger_current_balance'
  | 'warn_negative_cash'
  | 'provide_supplier_ref'
  | 'use_vch_no_as_bill_ref'
  | 'warn_negative_stock'

export type VoucherConfigSwitch = { key: VoucherConfigKey; label: string; description: string }

const INVOICE_TYPES = ['sales', 'purchase', 'credit note', 'debit note', 'delivery note', 'receipt note', 'sales order', 'purchase order']
const NO_LEDGER_TYPES = ['stock journal', 'physical stock', 'attendance', 'payroll']

export function voucherKind(parentType: string) {
  const t = (parentType || '').toLowerCase()
  const isOrder = t.includes('order')
  const isInvoice = INVOICE_TYPES.some(n => t.includes(n))
  const isAccounting = !isInvoice && !NO_LEDGER_TYPES.some(n => t.includes(n))
  return {
    isInvoice,
    isAccounting,
    // The supplier's own invoice number and date are asked for
    isPurchaseSide: t.includes('purchase') || t.includes('receipt note'),
    // The voucher raises a bill on the customer
    raisesSalesBill: t.includes('sales') && !isOrder,
    // Stock leaves the godown when the voucher is saved
    stockLeaves: (t.includes('sales') && !isOrder) || t.includes('delivery note') || t.includes('debit note'),
    // An invoice that is paid out of cash when the party is a cash ledger
    cashLeavesOnInvoice: (t.includes('purchase') && !isOrder) || t.includes('credit note'),
  }
}

export function voucherConfigSwitches(parentType: string): VoucherConfigSwitch[] {
  const k = voucherKind(parentType)
  const list: VoucherConfigSwitch[] = []
  if (k.isAccounting) {
    list.push({ key: 'use_cr_dr', label: 'Use Cr/Dr instead of To/By', description: 'Label the entry rows Dr and Cr rather than By and To' })
  }
  if (k.isAccounting || k.isInvoice) {
    list.push({ key: 'show_ledger_current_balance', label: 'Show current balance of ledgers', description: 'Show each ledger\'s balance next to its name when picking a ledger' })
  }
  if (k.isAccounting || k.cashLeavesOnInvoice) {
    list.push({ key: 'warn_negative_cash', label: 'Warn on negative cash balance', description: 'Warn before saving when the voucher would take a cash ledger below zero' })
  }
  if (k.isPurchaseSide) {
    list.push({ key: 'provide_supplier_ref', label: 'Provide supplier invoice no. and date', description: 'Ask for the supplier\'s own invoice number and its date' })
  }
  if (k.raisesSalesBill) {
    list.push({ key: 'use_vch_no_as_bill_ref', label: 'Use voucher no. as bill reference', description: 'Name the customer\'s bill after the voucher number; when off, after the reference number if one is given. Applies to new vouchers' })
  }
  if (k.stockLeaves) {
    list.push({ key: 'warn_negative_stock', label: 'Warn on negative stock', description: 'Warn before saving when an item\'s quantity is more than the stock in hand' })
  }
  return list
}
