import jsPDF from 'jspdf'
import { saveOrSharePdf } from './capacitor-pdf'
import { isNativePlatform } from './capacitor'

/* One customer's pending bills as an "Outstanding Vouchers Report" PDF, laid out like LiveKeeping's. */

export interface PendingBill {
  voucher_id?: number | null
  bill_reference: string
  bill_date: string
  due_date?: string | null
  outstanding_amount: number
  days_overdue: number
}

export interface OutstandingPdfOptions {
  company: { name: string; address?: string | null; gstin?: string | null }
  party: { name: string; address?: string | null; gstin?: string | null }
  bills: PendingBill[]
  total: number
  overdue: number
  /** Which bills are listed, e.g. "All" or "Overdue"; shown next to the overdue line */
  label?: string
}

const amount = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const shortDate = (iso?: string | null) => {
  if (!iso) return '—'
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`)
  return isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' })
}

export function outstandingFileName(partyName: string): string {
  return `${partyName.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40)}-Outstanding_Vouchers.pdf`
}

export function buildOutstandingPdf({ company, party, bills, total, overdue, label = 'All' }: OutstandingPdfOptions): jsPDF {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const left = 12, right = 198, bottom = 285
  // Vch. Date | Ref. No. | Pending Amount | Due Date | Overdue by days
  const cols = [left, 40, 88, 130, 158, right]
  const rowH = 6

  const header = () => {
    let y = 14
    doc.setTextColor(0, 0, 0)
    doc.setFont('helvetica', 'bold').setFontSize(15)
    doc.text(company.name || '', 105, y, { align: 'center' })
    doc.setFont('helvetica', 'normal').setFontSize(9)
    if (company.address) { y += 5; doc.text(company.address, 105, y, { align: 'center', maxWidth: 180 }) }
    if (company.gstin) { y += 5; doc.setFontSize(10).text(`GST: ${company.gstin}`, 105, y, { align: 'center' }) }
    y += 6
    doc.setFont('helvetica', 'bold').setFontSize(10).text('Outstanding Vouchers Report', 105, y, { align: 'center' })
    return y + 8
  }

  const field = (y: number, name: string, value: string) => {
    doc.setFont('helvetica', 'bold').setFontSize(9).text(name, left, y)
    const x = left + doc.getTextWidth(name) + 1.5   // measured in bold, before switching fonts
    doc.setFont('helvetica', 'normal').text(value, x, y, { maxWidth: right - x })
  }

  const tableHead = (y: number) => {
    doc.setFont('helvetica', 'bold').setFontSize(9)
    doc.rect(left, y, right - left, rowH)
    const labels = ['Vch. Date', 'Ref. No.', 'Pending Amount', 'Due Date', 'Overdue by days']
    labels.forEach((l, i) => {
      if (i === 2) doc.text(l, cols[i + 1] - 1.5, y + 4.2, { align: 'right' })
      else doc.text(l, cols[i] + 1.5, y + 4.2)
    })
    cols.slice(1, -1).forEach(x => doc.line(x, y, x, y + rowH))
    return y + rowH
  }

  const row = (y: number, cells: string[], bold = false) => {
    doc.setFont('helvetica', bold ? 'bold' : 'normal').setFontSize(9)
    doc.rect(left, y, right - left, rowH)
    cells.forEach((c, i) => {
      if (!c) return
      if (i === 2) doc.text(c, cols[i + 1] - 1.5, y + 4.2, { align: 'right' })
      else doc.text(doc.splitTextToSize(c, cols[i + 1] - cols[i] - 3)[0], cols[i] + 1.5, y + 4.2)
    })
    cols.slice(1, -1).forEach(x => doc.line(x, y, x, y + rowH))
    return y + rowH
  }

  let y = header()
  field(y, 'Date:', shortDate(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })))
  y += 5.5; field(y, 'Party Name:', party.name)
  if (party.address) { y += 5.5; field(y, 'Party Address:', party.address) }
  if (party.gstin) { y += 5.5; field(y, 'Party GSTIN:', party.gstin) }
  y += 5.5; field(y, 'Total Receivables Amount:', amount(total))
  y += 5.5; field(y, `Overdue (${label === 'All' ? 'All days' : label}):`, amount(overdue))
  y += 10
  y = tableHead(y)

  for (const b of bills) {
    if (y + rowH > bottom) {
      doc.addPage()
      y = tableHead(header())
    }
    y = row(y, [
      shortDate(b.bill_date),
      b.bill_reference,
      `${amount(b.outstanding_amount)} Dr.`,
      shortDate(b.due_date),
      b.days_overdue > 0 ? String(b.days_overdue) : 'Not due',
    ])
  }
  if (y + rowH > bottom) { doc.addPage(); y = tableHead(header()) }
  row(y, ['', 'Total', `${amount(bills.reduce((s, b) => s + b.outstanding_amount, 0))} Dr.`, '', ''], true)
  return doc
}

/** Open the PDF to read in a new tab on the web; in the app, hand it to the share sheet (save, print, WhatsApp). */
export function viewPdf(doc: jsPDF, filename: string) {
  if (isNativePlatform()) { saveOrSharePdf(doc, filename); return }
  const url = doc.output('bloburl') as unknown as string
  // Not 'noopener': with it window.open always returns null and every view would turn into a download
  const opened = window.open(url, '_blank')
  if (!opened) doc.save(filename)
}
