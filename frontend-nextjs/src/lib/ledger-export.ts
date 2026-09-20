import jsPDF from 'jspdf'
import { toTitleCase } from './utils'

export interface ExportTransaction {
  id: number
  date: string
  voucherType: string
  voucherNumber: string
  referenceNumber: string | null
  narration: string | null
  partyName?: string
  amount: string
}

export interface ExportLedgerInfo {
  ledger_id: number
  name: string
  alias_name?: string | null
  parent?: string
  gstn?: string | null
  pan_number?: string | null
  address?: string | null
  state?: string | null
  pincode?: string | null
  phone?: string | null
  mobile?: string | null
  email?: string | null
  opening_balance?: number
  opening_balance_type?: string
}

export interface ExportPeriodSummary {
  opBal: number
  opType: string
  totalDebit: number
  totalCredit: number
  clBal: number
  clType: string
}

export interface ExportCompanyInfo {
  name?: string | null
  address?: string | null
  city?: string | null
  state?: string | null
  gstin?: string | null
  phone?: string | null
  mobile?: string | null
  email?: string | null
}

export interface ExportOptions {
  ledgerInfo: ExportLedgerInfo
  transactions: ExportTransaction[]
  periodSummary: ExportPeriodSummary
  startDate: string
  endDate: string
  filterType: string // 'all' | 'sales' | 'purchase' | 'receipt' | custom
  company?: ExportCompanyInfo
  customerPhone?: string
  customerName?: string
}

const formatNumber = (val: string | number): string => {
  const parsed = typeof val === 'string' ? parseFloat(val) : val
  return isNaN(parsed) ? '0.00' : parsed.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatDateStr = (dateStr?: string | null): string => {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    })
  } catch {
    return dateStr
  }
}

const getFilterLabel = (filterType: string): string => {
  if (!filterType || filterType === 'all') return 'All Transactions'
  if (filterType.toLowerCase() === 'sales') return 'Sales Vouchers'
  if (filterType.toLowerCase() === 'purchase') return 'Purchase Vouchers'
  if (filterType.toLowerCase() === 'receipt') return 'Receipt Vouchers'
  if (filterType.toLowerCase() === 'payment') return 'Payment Vouchers'
  return `${toTitleCase(filterType)} Vouchers`
}

/**
 * 1. CSV EXPORT
 * Generates a properly escaped CSV file with metadata header, column headers,
 * transaction rows, running balances, and totals.
 */
export function exportLedgerToCsv({
  ledgerInfo,
  transactions,
  periodSummary,
  startDate,
  endDate,
  filterType,
  company,
  customerName
}: ExportOptions): void {
  const companyName = company?.name || 'Sneh Distributors'
  const partyName = customerName || ledgerInfo.name || 'Customer'
  const filterLabel = getFilterLabel(filterType)

  const rows: string[][] = []

  // Meta info
  rows.push([`"${companyName}"`])
  rows.push([`"STATEMENT OF ACCOUNT"`])
  rows.push([`"Customer / Ledger:"`, `"${partyName}"`])
  if (ledgerInfo.gstn) rows.push([`"GSTIN:"`, `"${ledgerInfo.gstn}"`])
  if (ledgerInfo.mobile || ledgerInfo.phone) rows.push([`"Contact:"`, `"${ledgerInfo.mobile || ledgerInfo.phone}"`])
  rows.push([`"Period:"`, `"${formatDateStr(startDate)} to ${formatDateStr(endDate)}"`])
  rows.push([`"Filter Applied:"`, `"${filterLabel}"`])
  rows.push([`"Opening Balance:"`, `"${formatNumber(periodSummary.opBal)} ${periodSummary.opType}"`])
  rows.push([])

  // Column Headers
  rows.push([
    '"Date"',
    '"Voucher Type"',
    '"Voucher No"',
    '"Ref / Invoice"',
    '"Narration"',
    '"Debit (Dr)"',
    '"Credit (Cr)"',
    '"Running Balance"'
  ])

  // Calculate Running Balance
  let runningNet = periodSummary.opType === 'Dr' ? -periodSummary.opBal : periodSummary.opBal // negative = Dr, positive = Cr
  let totalDebits = 0
  let totalCredits = 0

  transactions.forEach(txn => {
    const amt = parseFloat(txn.amount || '0')
    const isDebit = amt < 0
    const isCredit = amt > 0
    const absAmt = Math.abs(amt)

    if (isDebit) {
      runningNet -= absAmt
      totalDebits += absAmt
    } else {
      runningNet += absAmt
      totalCredits += absAmt
    }

    const curBalType = Math.abs(runningNet) < 0.005 ? 'Dr' : runningNet < 0 ? 'Dr' : 'Cr'
    const curBalFormatted = `${formatNumber(Math.abs(runningNet))} ${curBalType}`

    const cleanNarration = (txn.narration || '').replace(/"/g, '""').replace(/\r?\n/g, ' ')

    rows.push([
      `"${formatDateStr(txn.date)}"`,
      `"${txn.voucherType || ''}"`,
      `"${txn.voucherNumber || ''}"`,
      `"${txn.referenceNumber || ''}"`,
      `"${cleanNarration}"`,
      `"${isDebit ? formatNumber(absAmt) : ''}"`,
      `"${isCredit ? formatNumber(absAmt) : ''}"`,
      `"${curBalFormatted}"`
    ])
  })

  // Summary Totals
  rows.push([])
  rows.push([
    '"TOTALS"',
    '""',
    '""',
    '""',
    `"Total Transactions: ${transactions.length}"`,
    `"${formatNumber(totalDebits)} Dr"`,
    `"${formatNumber(totalCredits)} Cr"`,
    '""'
  ])

  const finalBal = Math.abs(runningNet)
  const finalBalType = Math.abs(runningNet) < 0.005 ? 'Dr' : runningNet < 0 ? 'Dr' : 'Cr'
  rows.push([
    '"CLOSING BALANCE"',
    '""',
    '""',
    '""',
    '""',
    '""',
    '""',
    `"${formatNumber(finalBal)} ${finalBalType}"`
  ])

  // Build CSV content with UTF-8 BOM
  const csvContent = '\uFEFF' + rows.map(r => r.join(',')).join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const cleanParty = partyName.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 30)
  const cleanFilter = filterType.replace(/[^a-zA-Z0-9_-]/g, '_')
  const fileName = `${cleanParty}_Statement_${cleanFilter}_${startDate || 'all'}_to_${endDate || 'all'}.csv`

  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', fileName)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 2. PDF EXPORT
 * Builds a professional multi-page A4 document with corporate header,
 * summary cards, formatted transaction ledger, and automatic pagination.
 */
export function exportLedgerToPdf({
  ledgerInfo,
  transactions,
  periodSummary,
  startDate,
  endDate,
  filterType,
  company,
  customerName
}: ExportOptions): void {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  })

  const companyName = company?.name || 'Sneh Distributors'
  const partyName = customerName || ledgerInfo.name || 'Customer'
  const filterLabel = getFilterLabel(filterType)

  // Layout bounds
  const xLeft = 12
  const xRight = 198
  const width = xRight - xLeft // 186 mm
  const yMax = 278 // Bottom limit before page break

  let currentPage = 1

  // Helper: Draw Header on each page
  const drawPageHeader = (isFirstPage: boolean) => {
    let y = 12

    if (isFirstPage) {
      // Company Info Header
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(15)
      doc.setTextColor(15, 23, 42) // Slate 900
      doc.text(companyName.toUpperCase(), xLeft, y)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(8)
      doc.setTextColor(100, 116, 139) // Slate 500
      const compAddressParts = [company?.address, company?.city, company?.state].filter(Boolean)
      if (compAddressParts.length > 0) {
        y += 4
        doc.text(compAddressParts.join(', '), xLeft, y)
      }
      if (company?.gstin || company?.phone) {
        y += 3.5
        const taxContact = [
          company?.gstin ? `GSTIN: ${company.gstin}` : '',
          company?.phone ? `Phone: ${company.phone}` : ''
        ].filter(Boolean).join(' | ')
        doc.text(taxContact, xLeft, y)
      }

      // Title Bar
      y += 6
      doc.setDrawColor(226, 232, 240) // Slate 200
      doc.line(xLeft, y, xRight, y)

      y += 5
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(12)
      doc.setTextColor(5, 150, 105) // Emerald 600
      doc.text('STATEMENT OF ACCOUNT', xLeft, y)

      // Sub-badge for Filter
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.setTextColor(71, 85, 105)
      doc.text(`[ ${filterLabel.toUpperCase()} ]`, xRight, y, { align: 'right' })

      // Customer & Period 2-Column Details Box
      y += 4
      doc.setFillColor(248, 250, 252) // Slate 50
      doc.roundedRect(xLeft, y, width, 22, 2, 2, 'F')
      doc.setDrawColor(226, 232, 240)
      doc.roundedRect(xLeft, y, width, 22, 2, 2, 'D')

      // Left column: Customer Details
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(9.5)
      doc.setTextColor(15, 23, 42)
      doc.text(toTitleCase(partyName), xLeft + 3, y + 5)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.5)
      doc.setTextColor(71, 85, 105)
      const partyAddr = [ledgerInfo.address, ledgerInfo.state, ledgerInfo.pincode].filter(Boolean).join(', ')
      doc.text(partyAddr ? partyAddr.slice(0, 75) : 'No address recorded', xLeft + 3, y + 9)
      doc.text(
        `GSTIN: ${ledgerInfo.gstn || 'Unregistered'}  |  Mobile: ${ledgerInfo.mobile || ledgerInfo.phone || 'N/A'}`,
        xLeft + 3,
        y + 13
      )
      if (ledgerInfo.parent) {
        doc.text(`Group: ${ledgerInfo.parent}`, xLeft + 3, y + 17)
      }

      // Right column: Statement Period
      const rightColX = xLeft + width - 3
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8)
      doc.setTextColor(100, 116, 139)
      doc.text('STATEMENT PERIOD', rightColX, y + 5, { align: 'right' })

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.setTextColor(15, 23, 42)
      doc.text(`${formatDateStr(startDate)} to ${formatDateStr(endDate)}`, rightColX, y + 9, { align: 'right' })

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.5)
      doc.setTextColor(100, 116, 139)
      doc.text(`Generated: ${new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`, rightColX, y + 13, { align: 'right' })
      doc.text(`Total Records: ${transactions.length}`, rightColX, y + 17, { align: 'right' })

      // 4-Card Summary Strip
      y += 25
      const cardWidth = (width - 6) / 4
      const cardHeight = 13

      const summaryCards = [
        { label: 'OPENING BALANCE', value: `Rs. ${formatNumber(periodSummary.opBal)} ${periodSummary.opType}`, color: [15, 23, 42] },
        { label: 'TOTAL DEBIT (DR)', value: `Rs. ${formatNumber(periodSummary.totalDebit)} Dr`, color: [225, 29, 72] }, // Rose 600
        { label: 'TOTAL CREDIT (CR)', value: `Rs. ${formatNumber(periodSummary.totalCredit)} Cr`, color: [5, 150, 105] }, // Emerald 600
        { label: 'CLOSING BALANCE', value: `Rs. ${formatNumber(periodSummary.clBal)} ${periodSummary.clType}`, color: [15, 23, 42] }
      ]

      summaryCards.forEach((c, idx) => {
        const cx = xLeft + idx * (cardWidth + 2)
        doc.setFillColor(248, 250, 252)
        doc.roundedRect(cx, y, cardWidth, cardHeight, 1.5, 1.5, 'FD')

        doc.setFont('helvetica', 'bold')
        doc.setFontSize(6.5)
        doc.setTextColor(100, 116, 139)
        doc.text(c.label, cx + 2.5, y + 4)

        doc.setFont('helvetica', 'bold')
        doc.setFontSize(8.5)
        doc.setTextColor(c.color[0], c.color[1], c.color[2])
        doc.text(c.value, cx + 2.5, y + 9.5)
      })

      y += cardHeight + 4
    } else {
      // Repeat mini-header on subsequent pages
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.setTextColor(71, 85, 105)
      doc.text(`${companyName.toUpperCase()} — ${partyName.toUpperCase()} (${filterLabel})`, xLeft, y)
      doc.text(`Period: ${formatDateStr(startDate)} - ${formatDateStr(endDate)}`, xRight, y, { align: 'right' })
      y += 2
      doc.setDrawColor(226, 232, 240)
      doc.line(xLeft, y, xRight, y)
      y += 3
    }

    // Render Table Header
    doc.setFillColor(30, 41, 59) // Slate 800
    doc.rect(xLeft, y, width, 6.5, 'F')

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(7.5)
    doc.setTextColor(255, 255, 255)

    doc.text('Date', xLeft + 2, y + 4.5)
    doc.text('Type', xLeft + 22, y + 4.5)
    doc.text('Vch / Ref No', xLeft + 42, y + 4.5)
    doc.text('Narration', xLeft + 76, y + 4.5)
    doc.text('Debit (Dr)', xLeft + 138, y + 4.5, { align: 'right' })
    doc.text('Credit (Cr)', xLeft + 162, y + 4.5, { align: 'right' })
    doc.text('Balance', xRight - 2, y + 4.5, { align: 'right' })

    y += 6.5
    return y
  }

  // Draw Page Footer helper
  const drawPageFooter = (pageNo: number) => {
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(148, 163, 184)
    doc.text(
      `This is a computer generated statement from ${companyName}.`,
      xLeft,
      290
    )
    doc.text(
      `Page ${pageNo}`,
      xRight,
      290,
      { align: 'right' }
    )
  }

  let currentY = drawPageHeader(true)

  // Running balance tracker
  let runningNet = periodSummary.opType === 'Dr' ? -periodSummary.opBal : periodSummary.opBal
  let totalDebits = 0
  let totalCredits = 0

  if (transactions.length === 0) {
    currentY += 8
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(9)
    doc.setTextColor(148, 163, 184)
    doc.text('No transactions found with the selected filter and period.', width / 2 + xLeft, currentY, { align: 'center' })
    currentY += 10
  } else {
    transactions.forEach((txn, idx) => {
      const amt = parseFloat(txn.amount || '0')
      const isDebit = amt < 0
      const isCredit = amt > 0
      const absAmt = Math.abs(amt)

      if (isDebit) {
        runningNet -= absAmt
        totalDebits += absAmt
      } else {
        runningNet += absAmt
        totalCredits += absAmt
      }

      const curBalType = Math.abs(runningNet) < 0.005 ? 'Dr' : runningNet < 0 ? 'Dr' : 'Cr'
      const curBalFormatted = `Rs. ${formatNumber(Math.abs(runningNet))} ${curBalType}`

      // Split narration for text wrapping (column width ~52mm)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(6.8)
      const narrationText = txn.narration || '-'
      const splitNarration = doc.splitTextToSize(narrationText, 48)
      const rowHeight = Math.max(5.5, splitNarration.length * 3 + 2)

      // Check for Page Overflow
      if (currentY + rowHeight > yMax) {
        drawPageFooter(currentPage)
        doc.addPage()
        currentPage++
        currentY = drawPageHeader(false)
      }

      // Alternating row background
      if (idx % 2 === 1) {
        doc.setFillColor(248, 250, 252)
        doc.rect(xLeft, currentY, width, rowHeight, 'F')
      }

      // Bottom row border
      doc.setDrawColor(241, 245, 249)
      doc.line(xLeft, currentY + rowHeight, xRight, currentY + rowHeight)

      // Date
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.2)
      doc.setTextColor(51, 65, 85)
      doc.text(formatDateStr(txn.date), xLeft + 2, currentY + 3.8)

      // Voucher Type
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(6.8)
      if (txn.voucherType?.toLowerCase().includes('sale')) {
        doc.setTextColor(3, 105, 161) // Sky 700
      } else if (txn.voucherType?.toLowerCase().includes('receipt')) {
        doc.setTextColor(5, 150, 105) // Emerald 600
      } else if (txn.voucherType?.toLowerCase().includes('purchase')) {
        doc.setTextColor(217, 119, 6) // Amber 600
      } else {
        doc.setTextColor(71, 85, 105)
      }
      doc.text(txn.voucherType?.toUpperCase() || '-', xLeft + 22, currentY + 3.8)

      // Voucher No & Ref
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(6.8)
      doc.setTextColor(15, 23, 42)
      const vchNoText = txn.voucherNumber ? `#${txn.voucherNumber}` : ''
      const refText = txn.referenceNumber && txn.referenceNumber !== txn.voucherNumber ? ` (${txn.referenceNumber})` : ''
      doc.text(`${vchNoText}${refText}`.slice(0, 28), xLeft + 42, currentY + 3.8)

      // Narration
      doc.setFont('helvetica', 'italic')
      doc.setFontSize(6.2)
      doc.setTextColor(100, 116, 139)
      doc.text(splitNarration, xLeft + 76, currentY + 3.5)

      // Debit Amount
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(7.2)
      if (isDebit) {
        doc.setTextColor(225, 29, 72)
        doc.text(formatNumber(absAmt), xLeft + 138, currentY + 3.8, { align: 'right' })
      }

      // Credit Amount
      if (isCredit) {
        doc.setTextColor(5, 150, 105)
        doc.text(formatNumber(absAmt), xLeft + 162, currentY + 3.8, { align: 'right' })
      }

      // Running Balance
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(6.8)
      doc.setTextColor(15, 23, 42)
      doc.text(curBalFormatted, xRight - 2, currentY + 3.8, { align: 'right' })

      currentY += rowHeight
    })
  }

  // Check if Table Totals fits on current page
  if (currentY + 12 > yMax) {
    drawPageFooter(currentPage)
    doc.addPage()
    currentPage++
    currentY = drawPageHeader(false)
  }

  // Totals Row
  currentY += 1
  doc.setFillColor(241, 245, 249)
  doc.rect(xLeft, currentY, width, 7, 'F')
  doc.setDrawColor(203, 213, 225)
  doc.line(xLeft, currentY, xRight, currentY)
  doc.line(xLeft, currentY + 7, xRight, currentY + 7)

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(7.5)
  doc.setTextColor(15, 23, 42)
  doc.text(`TOTALS (${transactions.length} vouchers)`, xLeft + 2, currentY + 4.5)

  doc.setTextColor(225, 29, 72)
  doc.text(`${formatNumber(totalDebits)} Dr`, xLeft + 138, currentY + 4.5, { align: 'right' })

  doc.setTextColor(5, 150, 105)
  doc.text(`${formatNumber(totalCredits)} Cr`, xLeft + 162, currentY + 4.5, { align: 'right' })

  const finalBal = Math.abs(runningNet)
  const finalBalType = Math.abs(runningNet) < 0.005 ? 'Dr' : runningNet < 0 ? 'Dr' : 'Cr'
  doc.setTextColor(15, 23, 42)
  doc.text(`Rs. ${formatNumber(finalBal)} ${finalBalType}`, xRight - 2, currentY + 4.5, { align: 'right' })

  drawPageFooter(currentPage)

  // Trigger browser download
  const cleanParty = partyName.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 30)
  const cleanFilter = filterType.replace(/[^a-zA-Z0-9_-]/g, '_')
  const fileName = `${cleanParty}_Statement_${cleanFilter}_${startDate || 'all'}_to_${endDate || 'all'}.pdf`
  doc.save(fileName)
}

/**
 * 3. WHATSAPP STATEMENT MESSAGE GENERATOR
 * Formats a clean, professional WhatsApp text statement itemizing the
 * filtered transactions, opening balance, totals, and closing balance.
 */
export function generateWhatsAppStatementMessage({
  ledgerInfo,
  transactions,
  periodSummary,
  startDate,
  endDate,
  filterType,
  company,
  customerName
}: ExportOptions): string {
  const companyName = company?.name || 'Sneh Distributors'
  const partyName = customerName || ledgerInfo.name || 'Customer'
  const filterLabel = getFilterLabel(filterType)

  let text = `*STATEMENT OF ACCOUNT*\n`
  text += `*${companyName.toUpperCase()}*\n`
  text += `━━━━━━━━━━━━━━━━━━━━━\n`
  text += `👤 *Customer:* ${partyName}\n`
  if (ledgerInfo.gstn) text += `📋 *GSTIN:* ${ledgerInfo.gstn}\n`
  text += `📅 *Period:* ${formatDateStr(startDate)} to ${formatDateStr(endDate)}\n`
  text += `🔍 *Filter:* ${filterLabel}\n`
  text += `━━━━━━━━━━━━━━━━━━━━━\n`

  // Summary figures
  text += `*Opening Balance:* ₹${formatNumber(periodSummary.opBal)} ${periodSummary.opType}\n`
  text += `*Total Debit (Dr):* ₹${formatNumber(periodSummary.totalDebit)}\n`
  text += `*Total Credit (Cr):* ₹${formatNumber(periodSummary.totalCredit)}\n`
  text += `*Closing Balance:* ₹${formatNumber(periodSummary.clBal)} ${periodSummary.clType}\n`
  text += `━━━━━━━━━━━━━━━━━━━━━\n`

  // Itemized transactions (up to 15 to stay within WhatsApp link length limit)
  if (transactions.length > 0) {
    text += `*TRANSACTIONS (${transactions.length})*\n`
    const previewCount = Math.min(transactions.length, 15)
    for (let i = 0; i < previewCount; i++) {
      const t = transactions[i]
      const amt = parseFloat(t.amount || '0')
      const isDebit = amt < 0
      const tag = isDebit ? 'Dr' : 'Cr'
      const dt = formatDateStr(t.date)
      const num = t.voucherNumber ? `#${t.voucherNumber}` : ''
      const ref = t.referenceNumber && t.referenceNumber !== t.voucherNumber ? ` (Ref: ${t.referenceNumber})` : ''
      text += `• ${dt} | *${t.voucherType}* ${num}${ref}\n  ↳ ₹${formatNumber(Math.abs(amt))} ${tag}\n`
    }

    if (transactions.length > previewCount) {
      text += `_... and ${transactions.length - previewCount} more transactions in statement._\n`
    }
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
  } else {
    text += `_No transactions found for the selected filter/period._\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
  }

  text += `Please review and feel free to reach out for any clarifications.\nThank you for your valued business!`
  return text
}

/**
 * 4. OPEN WHATSAPP HELPER
 * Opens WhatsApp Web or app with the encoded message for a specific or empty phone.
 */
export function openWhatsAppWithStatement(phone: string | undefined | null, message: string): void {
  const cleanPhone = (phone || '').replace(/\D/g, '')
  let url = ''
  if (cleanPhone) {
    const formattedPhone = cleanPhone.length === 10 ? `91${cleanPhone}` : cleanPhone
    url = `https://wa.me/${formattedPhone}?text=${encodeURIComponent(message)}`
  } else {
    url = `https://wa.me/?text=${encodeURIComponent(message)}`
  }
  window.open(url, '_blank')
}
