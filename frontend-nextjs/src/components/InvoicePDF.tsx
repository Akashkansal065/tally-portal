'use client'

import React from 'react'
import { Printer, Download, Share2, Mail, CheckCircle2 } from 'lucide-react'
import { formatCurrency, formatDate } from '@/lib/utils'

export interface InvoiceItem {
  name: string
  qty: number
  rate: number
  amount: number
  gstPercent?: number
}

export interface InvoiceData {
  companyName: string
  companyAddress?: string
  companyGstin?: string
  companyPhone?: string
  companyEmail?: string
  invoiceNumber: string
  invoiceDate: string
  partyName: string
  partyAddress?: string
  partyGstin?: string
  items: InvoiceItem[]
  subtotal: number
  cgst: number
  sgst: number
  totalAmount: number
  narration?: string
}

interface InvoicePDFProps {
  data: InvoiceData
  onClose?: () => void
}

export default function InvoicePDF({ data, onClose }: InvoicePDFProps) {
  const handlePrint = () => {
    window.print()
  }

  const handleShareWhatsApp = () => {
    const text = `*TAX INVOICE*\n*Invoice No:* ${data.invoiceNumber}\n*Date:* ${formatDate(data.invoiceDate)}\n*Company:* ${data.companyName}\n*Customer:* ${data.partyName}\n*Total Amount:* ₹${data.totalAmount.toLocaleString('en-IN')}\n\nThank you for doing business with us!`
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`
    window.open(url, '_blank')
  }

  const handleShareEmail = () => {
    const subject = `Tax Invoice ${data.invoiceNumber} from ${data.companyName}`
    const body = `Dear ${data.partyName},\n\nPlease find attached details of Tax Invoice ${data.invoiceNumber} for ₹${data.totalAmount.toLocaleString('en-IN')}.\n\nRegards,\n${data.companyName}`
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  }

  return (
    <div className="bg-card text-card-foreground border border-border rounded-2xl p-6 shadow-2xl max-w-3xl mx-auto my-4 space-y-6">
      {/* Action Buttons Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4 print:hidden">
        <div className="flex items-center gap-2">
          <span className="text-xs font-black uppercase tracking-wider text-emerald-600 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20 flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5" /> GST Compliant Tax Invoice
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrint}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-muted hover:bg-muted/80 text-xs font-bold transition-all cursor-pointer"
          >
            <Printer className="h-4 w-4" /> Print / Download
          </button>
          <button
            onClick={handleShareWhatsApp}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all cursor-pointer"
          >
            <Share2 className="h-4 w-4" /> WhatsApp
          </button>
          <button
            onClick={handleShareEmail}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all cursor-pointer"
          >
            <Mail className="h-4 w-4" /> Email
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-xl border border-border text-xs font-bold hover:bg-muted transition-all cursor-pointer"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {/* Printable Invoice Container */}
      <div className="printable-invoice p-4 border border-border/60 rounded-xl space-y-6 bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        {/* Header: Company Info vs Tax Invoice Title */}
        <div className="flex justify-between items-start border-b border-slate-200 dark:border-slate-800 pb-4">
          <div>
            <h1 className="text-xl font-extrabold text-slate-900 dark:text-white uppercase tracking-tight">{data.companyName}</h1>
            {data.companyAddress && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">{data.companyAddress}</p>}
            {data.companyGstin && <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-1">GSTIN: {data.companyGstin}</p>}
            {data.companyPhone && <p className="text-xs text-slate-500 dark:text-slate-400">Phone: {data.companyPhone}</p>}
          </div>
          <div className="text-right">
            <h2 className="text-lg font-black text-emerald-600 uppercase tracking-widest">TAX INVOICE</h2>
            <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-1">Invoice #: {data.invoiceNumber}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Date: {formatDate(data.invoiceDate)}</p>
          </div>
        </div>

        {/* Billed To Details */}
        <div className="bg-slate-50 dark:bg-slate-900 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800">
          <p className="text-[10px] uppercase font-extrabold tracking-wider text-slate-400">Billed To Customer</p>
          <p className="text-sm font-black text-slate-900 dark:text-white mt-0.5">{data.partyName}</p>
          {data.partyAddress && <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">{data.partyAddress}</p>}
          {data.partyGstin && <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-0.5">GSTIN: {data.partyGstin}</p>}
        </div>

        {/* Itemized Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-200 dark:border-slate-800 text-slate-500 uppercase tracking-wider text-[10px]">
                <th className="py-2 px-1">#</th>
                <th className="py-2 px-2">Item Description</th>
                <th className="py-2 px-2 text-right">Qty</th>
                <th className="py-2 px-2 text-right">Rate</th>
                <th className="py-2 px-2 text-right">Taxable Amt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.items.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50">
                  <td className="py-2.5 px-1 font-medium">{idx + 1}</td>
                  <td className="py-2.5 px-2 font-bold">{item.name}</td>
                  <td className="py-2.5 px-2 text-right font-medium">{item.qty}</td>
                  <td className="py-2.5 px-2 text-right font-medium">₹{item.rate.toLocaleString('en-IN')}</td>
                  <td className="py-2.5 px-2 text-right font-bold">₹{item.amount.toLocaleString('en-IN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Summary Footer Totals */}
        <div className="flex flex-col sm:flex-row justify-between items-start gap-4 border-t border-slate-200 dark:border-slate-800 pt-4">
          <div className="text-xs text-slate-500 space-y-1">
            {data.narration && <p><span className="font-bold text-slate-700 dark:text-slate-300">Narration:</span> {data.narration}</p>}
            <p className="text-[10px] italic">This is a computer-generated Tax Invoice synced with Tally Prime.</p>
          </div>
          <div className="w-full sm:w-64 space-y-1.5 text-xs">
            <div className="flex justify-between text-slate-600 dark:text-slate-400">
              <span>Subtotal</span>
              <span className="font-bold">₹{data.subtotal.toLocaleString('en-IN')}</span>
            </div>
            {data.cgst > 0 && (
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>CGST (9%)</span>
                <span className="font-bold">₹{data.cgst.toLocaleString('en-IN')}</span>
              </div>
            )}
            {data.sgst > 0 && (
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>SGST (9%)</span>
                <span className="font-bold">₹{data.sgst.toLocaleString('en-IN')}</span>
              </div>
            )}
            <div className="flex justify-between text-sm font-black text-slate-900 dark:text-white border-t border-slate-200 dark:border-slate-800 pt-1.5">
              <span>Total Invoice Amount</span>
              <span className="text-emerald-600">₹{data.totalAmount.toLocaleString('en-IN')}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
