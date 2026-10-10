'use client'

import React, { useState, useEffect } from 'react'
import { X, Settings2, Sliders, Save, Loader2, Info } from 'lucide-react'
import { voucherConfigSwitches } from '@/lib/voucher-config'
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

  const switches = voucherConfigSwitches(voucherType?.parent_type || voucherType?.name || '')

  useEffect(() => {
    if (initialConfig) {
      setConfig(initialConfig)
    } else if (voucherType) {
      setConfig(prev => ({ ...prev, voucher_type_id: voucherType.voucher_type_id }))
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
        <div className="flex items-center justify-between gap-2 px-4 sm:px-6 py-4 border-b border-slate-800/80 bg-slate-950/70">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 shrink-0 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm shadow-emerald-500/10">
              <Settings2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base sm:text-lg font-semibold text-white tracking-wide whitespace-nowrap">Voucher Configuration</h2>
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  {voucherType.name}
                </span>
              </div>
              <p className="text-xs text-slate-400">Entry settings for this app only</p>
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
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 custom-scrollbar">
          <div className="flex items-start gap-2 rounded-xl border border-slate-700/70 bg-slate-950/50 px-4 py-3 text-xs text-slate-300">
            <Info className="w-4 h-4 mt-0.5 shrink-0 text-emerald-400" />
            <span>These settings change how this app's voucher form behaves. They are not sent to Tally and are not read from it: Tally keeps its own entry settings (F12) on the Tally computer.</span>
          </div>

          {switches.length === 0 ? (
            <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-6 text-sm text-slate-400 text-center">
              There are no entry settings for {voucherType.name} vouchers.
            </div>
          ) : (
            <div className="rounded-xl border border-slate-800/90 bg-slate-950/40 p-4 space-y-3 shadow-inner shadow-black/20">
              <div className="flex items-center gap-2 pb-2 border-b border-emerald-500/20 text-emerald-400 font-semibold text-sm">
                <Sliders className="w-4 h-4" />
                <span>Entry Settings</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {switches.map(sw => (
                  <ToggleRow
                    key={sw.key}
                    label={sw.label}
                    description={sw.description}
                    checked={Boolean(config[sw.key])}
                    onChange={() => handleToggle(sw.key)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 sm:px-6 py-4 border-t border-slate-800/80 bg-slate-950/70">
          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400">
            <span>Applies to <strong className="text-emerald-300">{voucherType.name}</strong> vouchers in this app</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 sm:flex-none px-4 py-2.5 sm:py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800 rounded-lg border border-slate-700/60 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || switches.length === 0}
              className="flex-[2] sm:flex-none inline-flex items-center justify-center gap-2 px-5 py-2.5 sm:py-2 text-xs font-bold text-slate-950 bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 rounded-lg shadow-lg shadow-emerald-500/25 transition-all disabled:opacity-50 active:scale-[0.98]"
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
