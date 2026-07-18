import jsPDF from 'jspdf'

export interface VoucherHeader {
  voucherType?: string | null
  voucherNumber?: string | null
  date?: string | null
  referenceNumber?: string | null
  partyName?: string | null
}

export interface AccountEntry {
  ledger?: string | null
  amount?: string | null
}

export interface InventoryEntry {
  item?: string | null
  quantity?: string | null
  rate?: string | null
  amount?: string | null
  discountAmount?: string | null
  gstRate?: string | null
  gstHsnCode?: string | null
  uom?: string | null
}

export interface PartyLedger {
  mailingName?: string | null
  mailingAddress?: string | null
  gstn?: string | null
  mailingState?: string | null
  mobile?: string | null
}

interface TableRow {
  type: 'item' | 'subtotal' | 'ledger'
  sl?: number
  description: string
  hsn?: string
  gstRate?: string
  quantity?: string
  rateInclTax?: string
  rate?: string
  per?: string
  disc?: string
  amount: string
}

const stateCodes: Record<string, string> = {
  'jammu & kashmir': '01',
  'jammu and kashmir': '01',
  'himachal pradesh': '02',
  'punjab': '03',
  'chandigarh': '04',
  'uttarakhand': '05',
  'haryana': '06',
  'delhi': '07',
  'rajasthan': '08',
  'uttar pradesh': '09',
  'bihar': '10',
  'sikkim': '11',
  'arunachal pradesh': '12',
  'assam': '13',
  'west bengal': '19',
  'jharkhand': '20',
  'odisha': '21',
  'chhattisgarh': '22',
  'madhya pradesh': '23',
  'gujarat': '24',
  'daman & diu': '25',
  'daman and diu': '25',
  'dadra & nagar haveli': '26',
  'dadra and nagar haveli': '26',
  'maharashtra': '27',
  'andhra pradesh': '37',
  'karnataka': '29',
  'goa': '30',
  'lakshadweep': '31',
  'kerala': '32',
  'tamil nadu': '33',
  'puducherry': '34',
  'telangana': '36',
  'ladakh': '38',
}

const getStateCode = (stateName?: string | null) => {
  if (!stateName) return ''
  const key = stateName.trim().toLowerCase()
  return stateCodes[key] || ''
}

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: '2-digit'
  }).replace(/ /g, '-')
}

function numberToWords(num: number): string {
  const a = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
    'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'
  ]
  const b = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']

  function convertHelper(n: number): string {
    if (n < 20) return a[n]
    const digit = n % 10
    if (n < 100) return b[Math.floor(n / 10)] + (digit ? ' ' + a[digit] : '')
    const hundredDigit = Math.floor(n / 100)
    const remainder = n % 100
    return a[hundredDigit] + ' Hundred' + (remainder ? ' ' + convertHelper(remainder) : '')
  }

  const cleanNum = Math.abs(num)
  const mainPart = Math.floor(cleanNum)
  const paisePart = Math.round((cleanNum - mainPart) * 100)

  function getMainWords(n: number): string {
    if (n === 0) return 'Zero'
    let words = ''
    if (n >= 10000000) {
      words += convertHelper(Math.floor(n / 10000000)) + ' Crore '
      n %= 10000000
    }
    if (n >= 100000) {
      words += convertHelper(Math.floor(n / 100000)) + ' Lakh '
      n %= 100000
    }
    if (n >= 1000) {
      words += convertHelper(Math.floor(n / 1000)) + ' Thousand '
      n %= 1000
    }
    if (n > 0) {
      words += convertHelper(n)
    }
    return words.trim()
  }

  const mainWords = getMainWords(mainPart)
  let paiseWords = ''
  if (paisePart > 0) {
    paiseWords = ' and ' + convertHelper(paisePart) + ' paise'
  }

  return 'INR ' + mainWords + paiseWords + ' Only'
}

export async function generateVoucherPdf({
  voucherGuid,
  header,
  accounts,
  inventory,
  partyLedger,
  shouldDownload = true
}: {
  voucherGuid: string
  header: VoucherHeader
  accounts: AccountEntry[]
  inventory: InventoryEntry[]
  partyLedger: PartyLedger | null
  shouldDownload?: boolean
}) {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  })

  // Page parameters: A4 is 210 x 297 mm
  const xLeft = 10
  const width = 190
  const yTop = 15
  const yBottom = 287
  const pageHeight = 272 // inside borders

  // Calculate totals
  const totalQty = inventory.reduce((sum, item) => sum + Math.abs(parseFloat(item.quantity || '0')), 0)
  const uom = inventory[0]?.uom || 'PCS'
  const totalAmount = Math.abs(parseFloat(accounts.find(a => a.ledger === header.partyName)?.amount || '0'))

  // Group by HSN/SAC for Tax Analysis
  const groupItemsByHsn = () => {
    const groups: Record<string, { taxableValue: number; gstRate: number; cgstAmount: number; sgstAmount: number }> = {}
    
    // Find discount ledgers total to adjust taxable values proportionately
    const totalInvAmount = inventory.reduce((sum, item) => sum + Math.abs(parseFloat(item.amount || '0')), 0)
    const discountLedgersTotal = accounts
      .filter(acc => acc.ledger && acc.ledger.toUpperCase().includes('DISCOUNT'))
      .reduce((sum, acc) => sum + parseFloat(acc.amount || '0'), 0)
    const discountFactor = totalInvAmount > 0 ? (totalInvAmount + discountLedgersTotal) / totalInvAmount : 1

    inventory.forEach(item => {
      const hsn = item.gstHsnCode || 'N/A'
      const amount = Math.abs(parseFloat(item.amount || '0')) * discountFactor
      const gstRate = parseFloat(item.gstRate || '0')
      const cgstRate = gstRate / 2
      const sgstRate = gstRate / 2
      const cgstAmount = amount * (cgstRate / 100)
      const sgstAmount = amount * (sgstRate / 100)

      if (!groups[hsn]) {
        groups[hsn] = { taxableValue: 0, gstRate, cgstAmount: 0, sgstAmount: 0 }
      }
      groups[hsn].taxableValue += amount
      groups[hsn].cgstAmount += cgstAmount
      groups[hsn].sgstAmount += sgstAmount
    })
    return groups
  }

  const hsnGroups = groupItemsByHsn()
  const hsnRowsCount = Object.keys(hsnGroups).length
  const hsnTableHeight = 10 + hsnRowsCount * 6 + 8 // Header (2 rows=10) + data rows + total row
  // Total row (8) + amount words (13) + hsn table + gap (1) + tax words (9) + bank section (27) + declaration/signatory (22)
  const bottomSectionHeight = 8 + 13 + 1 + hsnTableHeight + 9 + 27 + 22

  // Collect all table rows:
  // 1. Items
  // 2. Subtotal (if taxes are present)
  // 3. Tax ledgers (CGST, SGST, IGST etc.)
  // 4. ROUND OFF
  const tableRows: TableRow[] = []
  inventory.forEach((item, idx) => {
    const rate = parseFloat(item.rate || '0')
    const gstRate = parseFloat(item.gstRate || '0')
    const rateInclTax = rate * (1 + gstRate / 100)
    const discPercent = parseFloat(item.discountAmount || '0')
    const amount = Math.abs(parseFloat(item.amount || '0'))

    tableRows.push({
      type: 'item',
      sl: idx + 1,
      description: item.item || '',
      hsn: item.gstHsnCode || '',
      gstRate: gstRate > 0 ? `${gstRate} %` : '',
      quantity: `${Math.abs(parseFloat(item.quantity || '0')).toLocaleString('en-IN', { maximumFractionDigits: 4 })} ${item.uom || ''}`,
      rateInclTax: rateInclTax > 0 ? rateInclTax.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '',
      rate: rate.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      per: item.uom || '',
      disc: discPercent > 0 ? `${discPercent}%` : '',
      amount: amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    })
  })

  // Check if we need subtotal & ledger rows
  const ledgerSplits = accounts.filter(acc => acc.ledger !== header.partyName && acc.ledger !== 'SALES AC')
  if (ledgerSplits.length > 0) {
    // Add Subtotal Row
    const subtotalAmount = inventory.reduce((sum, item) => sum + Math.abs(parseFloat(item.amount || '0')), 0)
    tableRows.push({
      type: 'subtotal',
      description: '',
      amount: subtotalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    })

    // Add Ledger Splits
    ledgerSplits.forEach(acc => {
      const ledgerName = acc.ledger || ''
      const isDiscount = ledgerName.toUpperCase().includes('DISCOUNT')
      const rawAmt = parseFloat(acc.amount || '0')

      if (isDiscount) {
        // Calculate total taxable value of inventory items
        const subtotalAmount = inventory.reduce((sum, item) => sum + Math.abs(parseFloat(item.amount || '0')), 0)
        const discRate = subtotalAmount > 0 ? Math.round((Math.abs(rawAmt) / subtotalAmount) * 100) : 0
        
        tableRows.push({
          type: 'ledger',
          description: `Less : ${ledgerName.toUpperCase()}`,
          rate: `(-)${discRate}`,
          per: `%`,
          amount: `(-)${Math.abs(rawAmt).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        })
      } else {
        const isRoundOff = ledgerName.toUpperCase().includes('ROUND')
        tableRows.push({
          type: 'ledger',
          description: ledgerName,
          amount: isRoundOff
            ? rawAmt.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            : Math.abs(rawAmt).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
        })
      }
    })
  }

  // We will perform pagination
  let currentPage = 1
  let rowIndex = 0
  let bottomSectionDrawn = false

  const drawPageLayout = (pageNumber: number) => {
    // Outer Page border
    doc.setLineWidth(0.15)
    doc.setDrawColor(0, 0, 0)
    doc.rect(xLeft, yTop, width, pageHeight)

    // Header Title
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    const titleText = pageNumber > 1 ? `Tax Invoice(Page ${pageNumber})` : 'Tax Invoice'
    doc.text(titleText, 105, yTop - 3, { align: 'center' })

    // (ORIGINAL FOR RECIPIENT)
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(8)
    doc.text('(ORIGINAL FOR RECIPIENT)', 200, yTop - 3, { align: 'right' })

    // Left Header: Sneh Distributors Details
    doc.setFontSize(11.5)
    doc.text('Sneh Distributors', 12, yTop + 6)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.text('43/7, Shastri Nagar, Meerut', 12, yTop + 11)
    doc.text('GSTIN/UIN: 09GAHPK5367P1ZR', 12, yTop + 16)
    doc.text('State Name : Uttar Pradesh, Code : 09', 12, yTop + 21)
    doc.text('Contact : +91-8384854172', 12, yTop + 26)
    doc.text('E-Mail : sneh.distributor@gmail.com', 12, yTop + 31)

    // Vertical divider at X = 105
    doc.line(105, yTop, 105, yTop + 75)

    // Right Header Details (Invoice No, Dates, etc.)
    // Row 1
    doc.setFontSize(8.5)
    doc.text('Invoice No.', 107, yTop + 5)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9.5)
    doc.text(header.voucherNumber || '', 107, yTop + 10)

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)
    doc.text('Dated', 154, yTop + 5)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9.5)
    doc.text(formatDate(header.date), 154, yTop + 10)
    doc.line(105, yTop + 12, 200, yTop + 12)

    // Row 2
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)
    doc.text('Delivery Note', 107, yTop + 16)
    doc.text('Other References', 154, yTop + 16)
    doc.line(105, yTop + 22, 200, yTop + 22)

    // Row 3
    doc.text('Reference No. & Date.', 107, yTop + 26)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9.5)
    doc.text(header.referenceNumber || '', 107, yTop + 30)

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)
    doc.text('Delivery Note Date', 154, yTop + 26)
    doc.line(105, yTop + 32, 200, yTop + 32)

    // Row 4
    doc.text('Dispatch Doc No.', 107, yTop + 36)
    doc.text('Dispatch Doc Date', 154, yTop + 36)
    doc.line(105, yTop + 42, 200, yTop + 42)

    // Row 5
    doc.text('Dispatched through', 107, yTop + 46)
    doc.text('Destination', 154, yTop + 46)
    doc.line(105, yTop + 52, 200, yTop + 52)

    // Row 6 (Terms of Delivery)
    doc.text('Terms of Delivery', 107, yTop + 56)

    // Inner vertical line on right side rows at X = 152.5
    doc.line(152.5, yTop, 152.5, yTop + 52)

    // Big Divider under upper block
    doc.line(10, yTop + 35, 105, yTop + 35) // separates Sneh details from Buyer

    // Buyer details (below line, Y = 50 to 90)
    let buyerY = yTop + 39
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.text('Buyer (Bill to)', 12, buyerY)

    buyerY += 4.5
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(10.5)
    const buyerName = partyLedger?.mailingName || header.partyName || ''
    doc.text(buyerName, 12, buyerY)

    buyerY += 4.5
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)
    doc.text('Adhar No :', 12, buyerY)

    buyerY += 4.5
    const address = partyLedger?.mailingAddress || ''
    const addressLines = doc.splitTextToSize(address, 90)
    addressLines.slice(0, 2).forEach((line: string) => {
      doc.text(line, 12, buyerY)
      buyerY += 4.5
    })

    doc.text(`GSTIN/UIN : ${partyLedger?.gstn || ''}`, 12, buyerY)
    buyerY += 4.5

    const stateName = partyLedger?.mailingState || ''
    const stateCode = getStateCode(stateName)
    doc.text(`State Name : ${stateName}${stateCode ? `, Code : ${stateCode}` : ''}`, 12, buyerY)
    buyerY += 4.5

    doc.text(`Contact : ${partyLedger?.mobile || ''}`, 12, buyerY)

    // Horizontal Line closing header block
    doc.line(10, yTop + 75, 200, yTop + 75)
  }

  const drawTableHeader = (y: number) => {
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)

    doc.text('Sl', 15, y + 4, { align: 'center' })
    doc.text('Description of Goods', 22, y + 6)
    doc.text('HSN/SAC', 84, y + 6, { align: 'center' })
    doc.text('GST', 99, y + 4, { align: 'center' })
    doc.text('Quantity', 121, y + 6, { align: 'right' })
    doc.text('Rate', 133, y + 4, { align: 'center' })
    doc.text('Rate', 159, y + 6, { align: 'right' })
    doc.text('per', 165, y + 6, { align: 'center' })
    doc.text('Disc. %', 180, y + 6, { align: 'right' })
    doc.text('Amount', 198, y + 6, { align: 'right' })

    doc.text('No.', 15, y + 8, { align: 'center' })
    doc.text('Rate', 99, y + 8, { align: 'center' })
    doc.text('(Incl. of Tax)', 133, y + 8, { align: 'center' })

    // Bottom Line of Header
    doc.line(10, y + 12, 200, y + 12)
  }

  const drawTableVerticalLines = (startY: number, endY: number) => {
    const xCoords = [10, 20, 75, 93, 105, 123, 143, 161, 169, 182, 200]
    xCoords.forEach(x => {
      doc.line(x, startY, x, endY)
    })
  }

  const drawTableRow = (row: TableRow, y: number) => {
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)

    if (row.type === 'item') {
      doc.text(String(row.sl || ''), 15, y + 4, { align: 'center' })
      
      // Wrap description
      const lines = doc.splitTextToSize(row.description || '', 53)
      doc.setFont('helvetica', 'bold')
      lines.forEach((line: string, i: number) => {
        doc.text(line, 22, y + 4 + i * 4)
      })
      doc.setFont('helvetica', 'normal')

      doc.text(row.hsn || '', 84, y + 4, { align: 'center' })
      doc.text(row.gstRate || '', 99, y + 4, { align: 'center' })
      doc.setFont('helvetica', 'bold')
      doc.text(row.quantity || '', 121, y + 4, { align: 'right' })
      doc.setFont('helvetica', 'normal')
      doc.text(row.rateInclTax || '', 141, y + 4, { align: 'right' })
      doc.text(row.rate || '', 159, y + 4, { align: 'right' })
      doc.text(row.per || '', 165, y + 4, { align: 'center' })
      doc.text(row.disc || '', 180, y + 4, { align: 'right' })
      doc.setFont('helvetica', 'bold')
      doc.text(row.amount || '', 198, y + 4, { align: 'right' })
    } else if (row.type === 'subtotal') {
      // Draw horizontal line
      doc.line(10, y, 200, y)
      doc.setFont('helvetica', 'bold')
      doc.text(row.amount || '', 198, y + 4.5, { align: 'right' })
    } else if (row.type === 'ledger') {
      doc.setFont('helvetica', 'bold')
      const isDiscount = row.description.toUpperCase().includes('LESS :')
      if (isDiscount) {
        doc.text(row.description || '', 74, y + 4.5, { align: 'right' })
        doc.text(row.rate || '', 159, y + 4.5, { align: 'right' })
        doc.text(row.per || '', 165, y + 4.5, { align: 'center' })
        doc.text(row.amount || '', 198, y + 4.5, { align: 'right' })
      } else {
        doc.text(row.description || '', 74, y + 4.5, { align: 'right' })
        doc.text(row.amount || '', 198, y + 4.5, { align: 'right' })
      }
    }
  }

  const drawBottomSection = (startY: number) => {
    // Line above total row
    doc.line(10, startY, 200, startY)

    // Total Row in items table
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(10.5)
    doc.text('Total', 74, startY + 5.5, { align: 'right' })
    doc.text(`${totalQty.toLocaleString('en-IN', { maximumFractionDigits: 4 })} ${uom}`, 121, startY + 5.5, { align: 'right' })
    doc.text(totalAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), 198, startY + 5.5, { align: 'right' })

    // Line below total row
    doc.line(10, startY + 8, 200, startY + 8)

    let nextY = startY + 12

    // Amount Chargeable in words
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.text('Amount Chargeable (in words)', 12, nextY)
    doc.setFont('helvetica', 'italic')
    doc.text('E. & O.E', 198, nextY, { align: 'right' })

    nextY += 4.5
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(10.5)
    const amountWords = numberToWords(totalAmount)
    doc.text(amountWords, 12, nextY)

    // Line below amount words
    nextY += 4.5
    doc.line(10, nextY, 200, nextY)

    // ======== HSN TAX ANALYSIS TABLE ========
    nextY += 1
    const hsnStartY = nextY
    const hsnSubHeaderY = hsnStartY + 5.5 // line between header row 1 and 2
    const hsnHeaderBottomY = hsnStartY + 10 // bottom of header

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)

    // Row 1 headers
    doc.text('HSN/SAC', 29, hsnStartY + 4, { align: 'center' })
    doc.text('Taxable', 63, hsnStartY + 4, { align: 'center' })
    doc.text('CGST', 97, hsnStartY + 4, { align: 'center' })
    doc.text('SGST/UTGST', 135, hsnStartY + 4, { align: 'center' })
    doc.text('Total', 177, hsnStartY + 4, { align: 'center' })

    // Row 2 headers
    doc.text('Value', 63, hsnStartY + 8, { align: 'center' })
    doc.text('Rate', 87, hsnStartY + 8, { align: 'center' })
    doc.text('Amount', 106, hsnStartY + 8, { align: 'center' })
    doc.text('Rate', 125, hsnStartY + 8, { align: 'center' })
    doc.text('Amount', 144, hsnStartY + 8, { align: 'center' })
    doc.text('Tax Amount', 177, hsnStartY + 8, { align: 'center' })

    // Table outer border
    doc.rect(10, hsnStartY, 190, hsnTableHeight)

    // Horizontal: sub-header line (only under CGST and SGST spans)
    doc.line(78, hsnSubHeaderY, 116, hsnSubHeaderY)
    doc.line(116, hsnSubHeaderY, 154, hsnSubHeaderY)
    // Horizontal: header bottom line
    doc.line(10, hsnHeaderBottomY, 200, hsnHeaderBottomY)

    // Vertical lines - FULL height (main column separators)
    const hsnFullCols = [10, 48, 78, 116, 154, 200]
    hsnFullCols.forEach(x => {
      doc.line(x, hsnStartY, x, hsnStartY + hsnTableHeight)
    })
    // Vertical lines - from SUB-HEADER down (Rate/Amount separators within CGST/SGST)
    const hsnSubCols = [96, 134]
    hsnSubCols.forEach(x => {
      doc.line(x, hsnSubHeaderY, x, hsnStartY + hsnTableHeight)
    })

    // HSN data rows
    let hsnRowY = hsnStartY + 14
    let totalTaxableValue = 0
    let totalCgstAmount = 0
    let totalSgstAmount = 0

    Object.entries(hsnGroups).forEach(([hsn, data]) => {
      doc.setFont('helvetica', 'normal')
      doc.text(hsn, 12, hsnRowY)
      doc.text(data.taxableValue.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 76, hsnRowY, { align: 'right' })
      doc.text(`${(data.gstRate / 2)}%`, 87, hsnRowY, { align: 'center' })
      doc.text(data.cgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 114, hsnRowY, { align: 'right' })
      doc.text(`${(data.gstRate / 2)}%`, 125, hsnRowY, { align: 'center' })
      doc.text(data.sgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 152, hsnRowY, { align: 'right' })
      const totalTax = data.cgstAmount + data.sgstAmount
      doc.text(totalTax.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, hsnRowY, { align: 'right' })

      totalTaxableValue += data.taxableValue
      totalCgstAmount += data.cgstAmount
      totalSgstAmount += data.sgstAmount
      hsnRowY += 6
    })

    // HSN Total row
    const hsnTotalLineY = hsnStartY + hsnTableHeight - 8
    doc.line(10, hsnTotalLineY, 200, hsnTotalLineY)
    const hsnTotalTextY = hsnStartY + hsnTableHeight - 3
    doc.setFont('helvetica', 'bold')
    doc.text('Total', 46, hsnTotalTextY, { align: 'right' })
    doc.text(totalTaxableValue.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 76, hsnTotalTextY, { align: 'right' })
    doc.text(totalCgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 114, hsnTotalTextY, { align: 'right' })
    doc.text(totalSgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 152, hsnTotalTextY, { align: 'right' })
    const grandTotalTax = totalCgstAmount + totalSgstAmount
    doc.text(grandTotalTax.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, hsnTotalTextY, { align: 'right' })

    nextY = hsnStartY + hsnTableHeight

    // ======== TAX AMOUNT IN WORDS (single line) ========
    nextY += 4
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    const taxWords = numberToWords(grandTotalTax)
    doc.text('Tax Amount (in words) :', 12, nextY)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9.5)
    doc.text(taxWords, 48, nextY)

    nextY += 5
    doc.line(10, nextY, 200, nextY)

    // ======== BOTTOM: Bank (center) then Declaration (left) / Signatory (right) ========
    const bottomStartY = nextY

    // Company's Bank Details heading (centered)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text("Company's Bank Details", 105, bottomStartY + 4, { align: 'center' })

    // Bank details
    const bLabelX = 80
    const bValX = 84
    const bY = bottomStartY + 9

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text('A/c Holder\'s Name', bLabelX, bY, { align: 'right' })
    doc.text(':', bLabelX + 2, bY)
    doc.setFont('helvetica', 'bold')
    doc.text('Sneh Distributors', bValX, bY)

    doc.setFont('helvetica', 'normal')
    doc.text('Bank Name', bLabelX, bY + 4, { align: 'right' })
    doc.text(':', bLabelX + 2, bY + 4)
    doc.setFont('helvetica', 'bold')
    doc.text('Punjab National Bank', bValX, bY + 4)

    doc.setFont('helvetica', 'normal')
    doc.text('A/c No.', bLabelX, bY + 8, { align: 'right' })
    doc.text(':', bLabelX + 2, bY + 8)
    doc.setFont('helvetica', 'bold')
    doc.text('4007002100062882', bValX, bY + 8)

    doc.setFont('helvetica', 'normal')
    doc.text('Branch & IFS Code', bLabelX, bY + 12, { align: 'right' })
    doc.text(':', bLabelX + 2, bY + 12)
    doc.setFont('helvetica', 'bold')
    doc.text('Jagriti Vihar & PUNB0400700', bValX, bY + 12)

    // Horizontal line below bank details
    const postBankY = bottomStartY + 24
    doc.line(10, postBankY, 200, postBankY)

    // LEFT: Declaration
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text('Declaration', 12, postBankY + 4)
    doc.line(12, postBankY + 4.5, 30, postBankY + 4.5)

    doc.setFontSize(8.5)
    const decText = 'We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.'
    const decLines = doc.splitTextToSize(decText, 90)
    decLines.forEach((line: string, idx: number) => {
      doc.text(line, 12, postBankY + 8 + idx * 3.5)
    })

    // RIGHT: Signatory
    doc.line(105, postBankY, 105, yBottom)

    doc.setFont('helvetica', 'italic')
    doc.setFontSize(10)
    doc.text('for Sneh Distributors', 152.5, postBankY + 5, { align: 'center' })

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9.5)
    doc.text('Authorised Signatory', 152.5, yBottom - 3, { align: 'center' })

    // Computer generated message
    doc.setFontSize(9.5)
    doc.text('This is a Computer Generated Invoice', 105, yBottom + 4.5, { align: 'center' })
  }

  while (!bottomSectionDrawn) {
    drawPageLayout(currentPage)
    drawTableHeader(90)

    let y = 102
    const remainingRows = tableRows.slice(rowIndex)
    const remainingHeights = remainingRows.map(row => {
      if (row.type === 'item') {
        const lines = doc.splitTextToSize(row.description || '', 53).length
        return 5 + (lines - 1) * 4
      }
      return 6
    })

    const remainingHeight = remainingHeights.reduce((a, b) => a + b, 0)
    const fitsOnCurrentPage = (remainingHeight + bottomSectionHeight <= 170)

    if (fitsOnCurrentPage) {
      for (let i = 0; i < remainingRows.length; i++) {
        const row = remainingRows[i]
        drawTableRow(row, y)
        y += remainingHeights[i]
      }

      const bottomSectionY = 287 - bottomSectionHeight
      drawTableVerticalLines(102, bottomSectionY)
      drawBottomSection(bottomSectionY)
      bottomSectionDrawn = true
    } else {
      // print as many rows as fit on Page
      let printedOnPage = 0
      let tempY = 102
      for (let i = 0; i < remainingRows.length; i++) {
        const h = remainingHeights[i]
        const fits = (tempY + h <= 265)
        const isLastRow = (i === remainingRows.length - 1)
        
        if (fits && (!isLastRow || fitsOnCurrentPage)) {
          drawTableRow(remainingRows[i], tempY)
          tempY += h
          printedOnPage++
        } else {
          break
        }
      }

      if (printedOnPage === 0 && remainingRows.length > 0) {
        drawTableRow(remainingRows[0], tempY)
        tempY += remainingHeights[0]
        printedOnPage = 1
      }

      // vertical lines
      drawTableVerticalLines(102, 270)
      doc.line(10, 270, 200, 270)

      // continued message
      doc.setFont('helvetica', 'italic')
      doc.setFontSize(8.5)
      doc.text(`continued to page number ${currentPage + 1}`, 198, 275, { align: 'right' })
      doc.text('This is a Computer Generated Invoice', 105, yBottom + 4.5, { align: 'center' })

      rowIndex += printedOnPage
      currentPage++
      doc.addPage()
    }
  }

  // Save document
  if (shouldDownload) {
    doc.save(`Invoice_${header.voucherNumber ? header.voucherNumber.replace(/[\/\\?%*:|"<>\s]/g, '_') : 'voucher'}.pdf`)
  }

  return doc
}
