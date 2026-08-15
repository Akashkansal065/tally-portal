'use client'

import React, { useState, useEffect } from 'react'
import { X, Settings2, Sliders, ShieldAlert, CheckCircle2, RotateCcw, Save, Loader2, Landmark, Receipt, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

export type VoucherConfiguration = {
  config_id?: number | null
  company_id?: number | null
  voucher_type_id: number
  use_cr_dr: boolean
  provide_supplier_ref: boolean
  warn_negative_cash: boolean
  preallocate_bills: boolean
  show_bill_wise_details: boolean
  show_bill_wise_multiple_lines: boolean
  show_list_of_bills: boolean
  show_final_bill_balances: boolean
  skip_date_field: boolean
  show_inventory_details: boolean
  show_ledger_current_balance: boolean
  warn_voucher_number_length: boolean
  enable_stripe_view: boolean
  provide_buyer_details: boolean
  provide_dispatch_order_export: boolean
  provide_order_details: boolean
  select_common_sales_ledger: boolean
  use_vch_no_as_bill_ref: boolean
  warn_negative_stock: boolean
  provide_trade_discount: boolean
  rate_inclusive_of_tax: boolean
  show_party_turnover: boolean
  use_default_bank_allocations: boolean
  auto_cheque_numbering: boolean
  select_cheque_range: boolean
  set_ledger_bank_allocations: boolean
  print_cheque_after_saving: boolean
  show_cheque_details_before_printing: boolean
  provide_cash_denominations: boolean
  use_default_pg_allocations: boolean
  set_ledger_pg_allocations: boolean
  provide_party_gst_details: boolean
  modify_gst_hsn_details: boolean
  send_eway_bill_details: boolean
}

export type VoucherConfigurationModalProps = {
  isOpen: boolean
  onClose: () => void
  voucherType: { voucher_type_id: number; name: string; parent_type?: string } | null
  initialConfig: VoucherConfiguration | null
  onSaveConfig: (updatedConfig: VoucherConfiguration) => Promise<void>
}

export default function VoucherConfigurationModal({
  isOpen,
  onClose,
  voucherType,
  initialConfig,
  onSaveConfig,
}: VoucherConfigurationModalProps) {
  const [config, setConfig] = useState<VoucherConfiguration>({
    voucher_type_id: voucherType?.voucher_type_id || 0,
    use_cr_dr: true,
    provide_supplier_ref: false,
    warn_negative_cash: true,
    preallocate_bills: false,
    show_bill_wise_details: true,
    show_bill_wise_multiple_lines: true,
    show_list_of_bills: true,
    show_final_bill_balances: true,
    skip_date_field: false,
    show_inventory_details: false,
    show_ledger_current_balance: true,
    warn_voucher_number_length: true,
    enable_stripe_view: false,
    provide_buyer_details: true,
    provide_dispatch_order_export: true,
    provide_order_details: true,
    select_common_sales_ledger: true,
    use_vch_no_as_bill_ref: true,
    warn_negative_stock: true,
    provide_trade_discount: false,
    rate_inclusive_of_tax: false,
    show_party_turnover: false,
    use_default_bank_allocations: false,
    auto_cheque_numbering: true,
    select_cheque_range: true,
    set_ledger_bank_allocations: false,
    print_cheque_after_saving: false,
    show_cheque_details_before_printing: true,
    provide_cash_denominations: false,
    use_default_pg_allocations: false,
    set_ledger_pg_allocations: false,
    provide_party_gst_details: false,
    modify_gst_hsn_details: false,
    send_eway_bill_details: true,
  })

  const [isSaving, setIsSaving] = useState(false)

  const parentTypeStr = (voucherType?.parent_type || voucherType?.name || '').toLowerCase()
  const isContra = parentTypeStr.includes('contra')
  const isReceipt = parentTypeStr.includes('receipt') && !parentTypeStr.includes('receipt note')
  const isSales = parentTypeStr.includes('sales') || parentTypeStr.includes('delivery note')
  const isPurchase = parentTypeStr.includes('purchase') || parentTypeStr.includes('receipt note')

  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig)
    } else if (voucherType) {
      const pType = (voucherType.parent_type || voucherType.name || '').toLowerCase()
      const isPur = pType.includes('purchase') || pType.includes('receipt note')
      const isSalesType = pType.includes('sales') || pType.includes('delivery note')
      const isPmtRcpt = pType.includes('payment') || pType.includes('receipt') || pType.includes('contra')
      const isContraType = pType.includes('contra')

      setConfig(prev => ({
        ...prev,
        voucher_type_id: voucherType.voucher_type_id,
        provide_supplier_ref: isPur,
        show_inventory_details: isSalesType || isPur,
        use_default_bank_allocations: isPmtRcpt || isPur,
        provide_cash_denominations: isContraType,
        provide_buyer_details: isSalesType || isPur,
        provide_dispatch_order_export: isSalesType || isPur,
        provide_order_details: isSalesType || isPur,
        use_vch_no_as_bill_ref: isSalesType,
        warn_negative_stock: isSalesType || isPur,
        send_eway_bill_details: isSalesType,
      }))
    }
  }, [initialConfig, voucherType, isOpen])

  if (!isOpen || !voucherType) return null

  const handleToggle = (key: keyof VoucherConfiguration) => {
    setConfig(prev => ({
      ...prev,
      [key]: !prev[key],
    }))
  }

  const handleSave = async () => {
    try {
      setIsSaving(true)
      await onSaveConfig(config)
      toast.success(`Configuration saved for ${voucherType.name}`)
      onClose()
    } catch (err: any) {
      toast.error(err?.message || 'Failed to save voucher configuration')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-slate-900/95 border border-emerald-500/25 rounded-2xl shadow-2xl shadow-emerald-950/40 overflow-hidden text-slate-100 font-sans">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm shadow-emerald-500/10">
              <Settings2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-white tracking-wide">Voucher Configuration</h2>
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {voucherType.name}
                </span>
              </div>
              <p className="text-xs text-slate-400">Configure entry parameters, behavioral prompts, and sub-allocations</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/80 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          
          {/* Section 1: General Details */}
          <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-4 space-y-3 shadow-inner shadow-black/20">
            <div className="flex items-center gap-2 pb-2 border-b border-emerald-500/20 text-emerald-400 font-semibold text-sm">
              <Sliders className="w-4 h-4" />
              <span>General Details</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              
              <ToggleRow
                label="Use Cr/Dr instead of To/By during voucher entry"
                description="Display rows as Debit/Credit rather than traditional To/By prefixes"
                checked={config.use_cr_dr}
                onChange={() => handleToggle('use_cr_dr')}
              />

              <ToggleRow
                label="Provide Supplier Inv/Ref No. and Date"
                description="Prompts for supplier invoice reference number and original invoice date"
                checked={config.provide_supplier_ref}
                onChange={() => handleToggle('provide_supplier_ref')}
              />

              <ToggleRow
                label="Warn on negative Cash Balance"
                description="Triggers validation alert when cash account balance drops below zero"
                checked={config.warn_negative_cash}
                onChange={() => handleToggle('warn_negative_cash')}
              />

              <ToggleRow
                label="Preallocate bills for Payment/Receipt/Journal"
                description="Automatically assigns unsettled bill balances using FIFO methodology"
                checked={config.preallocate_bills}
                onChange={() => handleToggle('preallocate_bills')}
              />

              <ToggleRow
                label="Show list of Bills for selection"
                description="Opens the pending bills table when adjusting Debtor/Creditor ledgers"
                checked={config.show_list_of_bills}
                onChange={() => handleToggle('show_list_of_bills')}
              />

              <ToggleRow
                label="Show Final Balances for each Bill"
                description="Calculates and shows the remaining post-settlement balance per invoice"
                checked={config.show_final_bill_balances}
                onChange={() => handleToggle('show_final_bill_balances')}
              />

              <ToggleRow
                label="Skip the Date field during voucher creation"
                description="Directs initial cursor focus directly into Party / Account selector"
                checked={config.skip_date_field}
                onChange={() => handleToggle('skip_date_field')}
              />

              <ToggleRow
                label="Show Inventory details"
                description="Enables item quantity and rate rows on Payment/Receipt/Journal vouchers"
                checked={config.show_inventory_details}
                onChange={() => handleToggle('show_inventory_details')}
              />

              <ToggleRow
                label="Show Current Balance of Ledgers"
                description="Displays live closing balance beneath ledger search selectors"
                checked={config.show_ledger_current_balance}
                onChange={() => handleToggle('show_ledger_current_balance')}
              />

              <ToggleRow
                label="Show Bill-wise Details in multiple lines"
                description="Allows multi-bill reference allocations for a single ledger entry line"
                checked={config.show_bill_wise_multiple_lines}
                onChange={() => handleToggle('show_bill_wise_multiple_lines')}
              />

              <ToggleRow
                label="Warn when Voucher No. exceeds 16 characters"
                description="Alerts user if numbering exceeds recommended Tally character limits"
                checked={config.warn_voucher_number_length}
                onChange={() => handleToggle('warn_voucher_number_length')}
              />

              {/* Sales & Purchase Specific Toggles */}
              {(isSales || isPurchase) && (
                <>
                  <ToggleRow
                    label={isPurchase ? "Provide Supplier details" : "Provide Buyer details"}
                    description={isPurchase 
                      ? "Prompts for Supplier Mailing Name, Address, GSTIN, and State in purchase header" 
                      : "Prompts for Consignee / Buyer Name, Address, GSTIN, and State in invoice header"}
                    checked={config.provide_buyer_details}
                    onChange={() => handleToggle('provide_buyer_details')}
                  />

                  <ToggleRow
                    label={isPurchase ? "Provide Receipt Note, Order, and Import details" : "Provide Dispatch, Order, and Export details"}
                    description={isPurchase 
                      ? "Enables Receipt Doc No, Despatched through, Destination, Order No, and Import details" 
                      : "Enables Dispatch Doc No, Despatched through, Destination, Order No, and Export details"}
                    checked={config.provide_dispatch_order_export}
                    onChange={() => handleToggle('provide_dispatch_order_export')}
                  />

                  <ToggleRow
                    label="Provide Order details"
                    description={isPurchase ? "Prompts for Purchase Order reference number and date" : "Prompts for Buyer's PO / Order reference number and date"}
                    checked={config.provide_order_details}
                    onChange={() => handleToggle('provide_order_details')}
                  />

                  <ToggleRow
                    label="Select common Ledger Account for Item Allocation"
                    description={isPurchase 
                      ? "Applies a single primary Purchase expense ledger across all inventory lines" 
                      : "Applies a single primary Sales/Income ledger across all inventory lines"}
                    checked={config.select_common_sales_ledger}
                    onChange={() => handleToggle('select_common_sales_ledger')}
                  />

                  {isSales && (
                    <ToggleRow
                      label="Use Voucher No. as Bill Reference for Bill Allocation"
                      description="Automatically creates a 'New Ref' bill allocation matching the invoice number"
                      checked={config.use_vch_no_as_bill_ref}
                      onChange={() => handleToggle('use_vch_no_as_bill_ref')}
                    />
                  )}

                  {isPurchase && (
                    <ToggleRow
                      label="Provide Supplier Invoice details"
                      description="Prompts for Supplier Invoice / Reference No. and Original Invoice Date at top of entry"
                      checked={config.provide_supplier_ref}
                      onChange={() => handleToggle('provide_supplier_ref')}
                    />
                  )}

                  <ToggleRow
                    label="Warn on negative Stock Balance"
                    description="Triggers immediate warning if item quantity exceeds available godown stock"
                    checked={config.warn_negative_stock}
                    onChange={() => handleToggle('warn_negative_stock')}
                  />

                  <ToggleRow
                    label="Provide Cash/Trade Discount"
                    description="Enables column for Line Item Trade Discount % calculation"
                    checked={config.provide_trade_discount}
                    onChange={() => handleToggle('provide_trade_discount')}
                  />

                  <ToggleRow
                    label="Show Turnover from selected Party A/c"
                    description={isPurchase 
                      ? "Displays cumulative financial year purchase turnover for chosen supplier" 
                      : "Displays cumulative financial year sales turnover for chosen customer"}
                    checked={config.show_party_turnover}
                    onChange={() => handleToggle('show_party_turnover')}
                  />
                </>
              )}

            </div>
          </div>

          {/* Section 2: Tax & Price Details (Sales / Invoice) */}
          {isSales && (
            <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-4 space-y-3 shadow-inner shadow-black/20">
              <div className="flex items-center gap-2 pb-2 border-b border-teal-500/20 text-teal-400 font-semibold text-sm">
                <Receipt className="w-4 h-4" />
                <span>Tax & Price Details</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                
                <ToggleRow
                  label="Provide Rate Inclusive of Tax for Stock Items"
                  description="Enables entering MRP/Inclusive selling rate and auto-calculates basic taxable rate"
                  checked={config.rate_inclusive_of_tax}
                  onChange={() => handleToggle('rate_inclusive_of_tax')}
                />

              </div>
            </div>
          )}

          {/* Section 3: Bank Details (Payment, Receipt, Contra, Purchase) */}
          {!isSales && (
            <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-4 space-y-3 shadow-inner shadow-black/20">
              <div className="flex items-center gap-2 pb-2 border-b border-cyan-500/20 text-cyan-400 font-semibold text-sm">
                <Landmark className="w-4 h-4" />
                <span>Bank Details</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                
                <ToggleRow
                  label="Use default Bank Allocations"
                  description="Auto-opens Banking transaction details drawer on bank accounts"
                  checked={config.use_default_bank_allocations}
                  onChange={() => handleToggle('use_default_bank_allocations')}
                />

                <ToggleRow
                  label="Set Ledger-wise Bank Allocations during creation"
                  description="Prompts for separate banking allocation per individual bank line"
                  checked={config.set_ledger_bank_allocations}
                  onChange={() => handleToggle('set_ledger_bank_allocations')}
                />

                {!isReceipt && (
                  <>
                    <ToggleRow
                      label="Use Auto Cheque Numbering"
                      description="Auto-increments and selects consecutive instrument numbers from company cheque book"
                      checked={config.auto_cheque_numbering}
                      onChange={() => handleToggle('auto_cheque_numbering')}
                    />

                    <ToggleRow
                      label="Select Cheque Range"
                      description="Prompts for registered Cheque Book range selection on Bank ledgers"
                      checked={config.select_cheque_range}
                      onChange={() => handleToggle('select_cheque_range')}
                    />

                    <ToggleRow
                      label="Print Cheque after saving Voucher"
                      description="Triggers the Cheque PDF printing dialog automatically on save"
                      checked={config.print_cheque_after_saving}
                      onChange={() => handleToggle('print_cheque_after_saving')}
                    />

                    <ToggleRow
                      label="Show Cheque details before printing"
                      description="Previews favouring name, date, and crossed amount prior to print"
                      checked={config.show_cheque_details_before_printing}
                      onChange={() => handleToggle('show_cheque_details_before_printing')}
                    />
                  </>
                )}

                {isContra && (
                  <ToggleRow
                    label="Provide Cash Denomination details"
                    description="Prompts for physical currency notes breakdown (2000, 500, 200, 100, etc.) on cash transfers"
                    checked={config.provide_cash_denominations}
                    onChange={() => handleToggle('provide_cash_denominations')}
                  />
                )}

              </div>
            </div>
          )}

          {/* Section 4: GST & Statutory Details */}
          {!isContra && (
            <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-4 space-y-3 shadow-inner shadow-black/20">
              <div className="flex items-center gap-2 pb-2 border-b border-emerald-500/20 text-emerald-400 font-semibold text-sm">
                <Receipt className="w-4 h-4" />
                <span>GST & Statutory Details</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                
                {isSales && (
                  <ToggleRow
                    label="Send e-Way Bill details after saving Voucher"
                    description="Prompts for e-Way Bill vehicle no, transporter ID, distance, and dispatch details on save"
                    checked={config.send_eway_bill_details}
                    onChange={() => handleToggle('send_eway_bill_details')}
                  />
                )}

                <ToggleRow
                  label="Provide Party details for GST"
                  description="Enables Buyer/Consignee/Supplier mailing name, state, and GSTIN override popup"
                  checked={config.provide_party_gst_details}
                  onChange={() => handleToggle('provide_party_gst_details')}
                />

                <ToggleRow
                  label="Modify GST & HSN/SAC related details"
                  description="Allows item-level or voucher-level tax classification modifications"
                  checked={config.modify_gst_hsn_details}
                  onChange={() => handleToggle('modify_gst_hsn_details')}
                />

              </div>
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800/80 bg-slate-950/70">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>Settings apply to all new vouchers of type <strong className="text-emerald-300">{voucherType.name}</strong></span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800 rounded-lg border border-slate-700/60 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              className="inline-flex items-center gap-2 px-5 py-2 text-xs font-bold text-slate-950 bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 rounded-lg shadow-lg shadow-emerald-500/25 transition-all disabled:opacity-50 active:scale-[0.98]"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 text-slate-950" />
                  <span>Save Configuration</span>
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  onChange: () => void
}) {
  return (
    <div
      onClick={onChange}
      className={`flex items-start justify-between p-3.5 rounded-xl border transition-all duration-150 cursor-pointer select-none group ${
        checked
          ? 'border-emerald-500/40 bg-emerald-500/[0.04] hover:bg-emerald-500/[0.08] hover:border-emerald-500/60 shadow-sm shadow-emerald-950/20'
          : 'border-slate-800/80 bg-slate-900/50 hover:bg-slate-800/50 hover:border-slate-700/80'
      }`}
    >
      <div className="space-y-0.5 pr-3">
        <div
          className={`text-xs font-semibold transition-colors ${
            checked ? 'text-emerald-200 group-hover:text-emerald-100' : 'text-slate-300 group-hover:text-white'
          }`}
        >
          {label}
        </div>
        <div className="text-[11px] text-slate-400 leading-relaxed">{description}</div>
      </div>
      <div className="pt-0.5 flex-shrink-0">
        <div
          className={`w-10 h-5 flex items-center rounded-full p-0.5 transition-all duration-200 ease-in-out ${
            checked ? 'bg-emerald-500 shadow-md shadow-emerald-500/30' : 'bg-slate-800 border border-slate-700/60'
          }`}
        >
          <div
            className={`w-4 h-4 rounded-full shadow-sm transform transition-transform duration-200 ease-in-out ${
              checked ? 'translate-x-5 bg-slate-950' : 'translate-x-0 bg-slate-400'
            }`}
          />
        </div>
      </div>
    </div>
  )
}
