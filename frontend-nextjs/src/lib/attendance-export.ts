import jsPDF from 'jspdf'
import { saveOrSharePdf } from './capacitor-pdf'

export interface MusterRollDay {
  day: number
  date: string
  weekday: string
  isSunday: boolean
  isPast: boolean
}

export interface EmployeeDayAttendance {
  status: 'P' | 'HD' | 'A' | 'WO' | '-'
  checkIn: string | null
  checkOut: string | null
  hours: number
  locationTag: string | null
  isAutoPunchOut: boolean
  photoUrl?: string | null
  approvalStatus?: 'approved' | 'pending' | 'rejected'
  isOutOfOffice?: boolean | null
  attendanceId?: number | null
  rejectionReason?: string | null
}

export interface EmployeeMusterRoll {
  userId: number
  username: string
  days: Record<string, EmployeeDayAttendance>
  summary: {
    totalPresent: number
    totalHalfDay: number
    totalAbsent: number
    totalWeekOff: number
    effectiveDays: number
    totalHours: number
    autoPunchOuts: number
  }
}

export interface CompanyMusterSummary {
  totalStaff: number
  workingDaysElapsed: number
  avgAttendancePct: number
  totalCompanyHours: number
}

export interface MusterRollPdfOptions {
  companyName: string
  monthName: string
  year: number
  days: MusterRollDay[]
  employees: EmployeeMusterRoll[]
  companySummary: CompanyMusterSummary
}

/**
 * Generates an executive A4 Landscape PDF Timesheet / Muster Roll.
 */
export function exportMusterRollToPdf({
  companyName,
  monthName,
  year,
  days,
  employees,
  companySummary,
}: MusterRollPdfOptions): void {
  // A4 Landscape: 297mm width x 210mm height
  const doc = new jsPDF({
    orientation: 'landscape',
    unit: 'mm',
    format: 'a4',
  })

  const pageWidth = 297
  const pageHeight = 210
  const marginX = 10
  const usableWidth = pageWidth - marginX * 2 // 277 mm

  let currentY = 12

  // 1. Header Banner
  doc.setFillColor(30, 58, 138) // Dark Navy Blue (#1E3A8A)
  doc.rect(marginX, currentY, usableWidth, 14, 'F')

  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.text(companyName.toUpperCase(), pageWidth / 2, currentY + 6, { align: 'center' })

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8.5)
  doc.text(
    `MONTHLY ATTENDANCE MUSTER ROLL — ${monthName.toUpperCase()} ${year} | STAFF: ${companySummary.totalStaff} | AVG ATTENDANCE: ${companySummary.avgAttendancePct}%`,
    pageWidth / 2,
    currentY + 11,
    { align: 'center' }
  )

  currentY += 18

  // 2. KPI Summary Bar
  doc.setFillColor(243, 244, 246) // Gray 100
  doc.roundedRect(marginX, currentY, usableWidth, 9, 1.5, 1.5, 'F')

  doc.setTextColor(31, 41, 55)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8)

  const kpis = [
    `Total Staff: ${companySummary.totalStaff}`,
    `Working Days: ${companySummary.workingDaysElapsed}`,
    `Avg Attendance: ${companySummary.avgAttendancePct}%`,
    `Total Hours Logged: ${companySummary.totalCompanyHours}h`,
    `Generated: ${new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}`,
  ]

  const kpiStep = usableWidth / kpis.length
  kpis.forEach((text, i) => {
    doc.text(text, marginX + i * kpiStep + kpiStep / 2, currentY + 6, { align: 'center' })
  })

  currentY += 13

  // 3. Grid Measurements
  const numDays = days.length
  const colNameWidth = 38
  const colUserIdWidth = 14
  const summaryColCount = 5 // P, HD, A, Eff, Hours
  const summaryColWidth = 11 // 11 * 5 = 55 mm
  const remainingWidth = usableWidth - colNameWidth - colUserIdWidth - (summaryColCount * summaryColWidth)
  const dayColWidth = Math.max(4.2, remainingWidth / numDays)

  const drawTableHeader = (y: number) => {
    doc.setFillColor(229, 231, 235) // Gray 200
    doc.rect(marginX, y, usableWidth, 7, 'F')

    doc.setTextColor(17, 24, 39)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(7)

    // Name & ID
    doc.text('Employee', marginX + 2, y + 4.8)
    doc.text('ID', marginX + colNameWidth + 2, y + 4.8)

    // Days
    let curX = marginX + colNameWidth + colUserIdWidth
    days.forEach((d) => {
      if (d.isSunday) {
        doc.setFillColor(209, 213, 219) // Sunday darker tint
        doc.rect(curX, y, dayColWidth, 7, 'F')
      }
      doc.text(String(d.day), curX + dayColWidth / 2, y + 3.2, { align: 'center' })
      doc.setFontSize(5.5)
      doc.text(d.weekday[0], curX + dayColWidth / 2, y + 5.8, { align: 'center' })
      doc.setFontSize(7)
      curX += dayColWidth
    })

    // Summary headers
    const sHeaders = ['P', 'HD', 'A', 'Eff', 'Hours']
    sHeaders.forEach((sh) => {
      doc.text(sh, curX + summaryColWidth / 2, y + 4.8, { align: 'center' })
      curX += summaryColWidth
    })
  }

  drawTableHeader(currentY)
  currentY += 7

  // 4. Employee Rows
  const rowHeight = 6
  const maxY = pageHeight - 12

  employees.forEach((emp, empIdx) => {
    if (currentY + rowHeight > maxY) {
      doc.addPage()
      currentY = 12
      drawTableHeader(currentY)
      currentY += 7
    }

    // Row alternating background
    if (empIdx % 2 === 1) {
      doc.setFillColor(249, 250, 251) // Gray 50
      doc.rect(marginX, currentY, usableWidth, rowHeight, 'F')
    }

    doc.setTextColor(31, 41, 55)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(6.5)

    // Name (truncated)
    const displayName = emp.username.length > 22 ? emp.username.slice(0, 21) + '…' : emp.username
    doc.text(displayName, marginX + 1.5, currentY + 4.2)
    doc.text(`#${emp.userId}`, marginX + colNameWidth + 1.5, currentY + 4.2)

    // Day Cells
    let curX = marginX + colNameWidth + colUserIdWidth
    days.forEach((d) => {
      const dayData = emp.days[String(d.day)]
      const status = dayData?.status || '-'

      if (status === 'P') {
        doc.setFillColor(220, 252, 231) // Green 100
        doc.rect(curX + 0.3, currentY + 0.8, dayColWidth - 0.6, rowHeight - 1.6, 'F')
        doc.setTextColor(22, 101, 52) // Green 800
        doc.setFont('helvetica', 'bold')
      } else if (status === 'HD') {
        doc.setFillColor(254, 243, 199) // Yellow 100
        doc.rect(curX + 0.3, currentY + 0.8, dayColWidth - 0.6, rowHeight - 1.6, 'F')
        doc.setTextColor(146, 64, 14) // Amber 800
        doc.setFont('helvetica', 'bold')
      } else if (status === 'A') {
        doc.setFillColor(254, 226, 226) // Red 100
        doc.rect(curX + 0.3, currentY + 0.8, dayColWidth - 0.6, rowHeight - 1.6, 'F')
        doc.setTextColor(153, 27, 27) // Red 800
        doc.setFont('helvetica', 'bold')
      } else if (status === 'WO') {
        doc.setTextColor(156, 163, 175) // Gray 400
        doc.setFont('helvetica', 'normal')
      } else {
        doc.setTextColor(209, 213, 219)
        doc.setFont('helvetica', 'normal')
      }

      doc.text(status, curX + dayColWidth / 2, currentY + 4.2, { align: 'center' })
      curX += dayColWidth
    })

    // Summary numbers
    doc.setTextColor(17, 24, 39)
    doc.setFont('helvetica', 'normal')

    const summ = emp.summary
    const summValues = [
      String(summ.totalPresent),
      String(summ.totalHalfDay),
      String(summ.totalAbsent),
      String(summ.effectiveDays),
      `${summ.totalHours}h`,
    ]

    summValues.forEach((val, i) => {
      if (i === 3) doc.setFont('helvetica', 'bold')
      else doc.setFont('helvetica', 'normal')
      doc.text(val, curX + summaryColWidth / 2, currentY + 4.2, { align: 'center' })
      curX += summaryColWidth
    })

    currentY += rowHeight
  })

  // Footer Legend
  const footerY = pageHeight - 8
  doc.setFontSize(6.5)
  doc.setTextColor(107, 114, 128)
  doc.setFont('helvetica', 'normal')
  doc.text(
    'Legend: [P] Full Day Present (>=7.5 hrs) | [HD] Half Day (4.0 - 7.5 hrs) | [A] Absent | [WO] Week Off (Sunday) | [-] Future Date',
    marginX,
    footerY
  )

  const filename = `Attendance_Muster_Roll_${monthName}_${year}.pdf`
  saveOrSharePdf(doc, filename)
}
