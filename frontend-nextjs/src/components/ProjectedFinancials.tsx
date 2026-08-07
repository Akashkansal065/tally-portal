'use client'

import React, { useState, useEffect } from 'react'
import {
  FileText, Download, Sparkles, Plus, Trash2, Calendar, RefreshCw,
  Building2, TrendingUp, CheckCircle2, ChevronRight, Edit3, Lock, ShieldCheck
} from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import jsPDF from 'jspdf'

interface FixedAssetItem {
  id: string
  name: string
  cost: number
  deprRate: number // e.g. 15 for 15%
}

interface ExpenseItem {
  id: string
  name: string
  amount: number
}

interface YearData {
  yearLabel: string // e.g. "2026-27"
  yearEnd: string // e.g. "31ST MARCH, 2027"
  
  // Trading P&L
  sales: number
  openingStock: number
  purchases: number
  closingStock: number
  
  // Expenses
  expenses: ExpenseItem[]
  
  // Balance Sheet - Assets
  fixedAssets: FixedAssetItem[]
  sundryDebtors: number
  cashInHand: number
  balanceWithBanks: number
  gstCredit: number
  
  // Balance Sheet - Liabilities
  proprietorCapital: number
  unsecuredLoans: number
  creditorsForGoods: number
  expensesPayable: number
}

interface ProjectedFinancialsProps {
  companyName?: string
  initialData?: any
}

export default function ProjectedFinancials({ companyName = 'M/S SNEH DISTRIBUTORS', initialData }: ProjectedFinancialsProps) {
  const [bussName, setBussName] = useState(companyName || 'M/S SNEH DISTRIBUTORS')
  const [startYear, setStartYear] = useState(2027)
  const [numYears, setNumYears] = useState(3) // 3 Years: 2027, 2028, 2029
  
  // Growth Rates (%)
  const [salesGrowth, setSalesGrowth] = useState(15)
  const [purchaseGrowth, setPurchaseGrowth] = useState(12)
  const [expenseGrowth, setExpenseGrowth] = useState(10)
  const [stockGrowth, setStockGrowth] = useState(10)
  
  const [activeYearIdx, setActiveYearIdx] = useState(0)
  const [isEditing, setIsEditing] = useState(true)
  const [yearsData, setYearsData] = useState<YearData[]>([])

  // Seed default base data matching the screenshot
  useEffect(() => {
    const defaultFixedAssets: FixedAssetItem[] = [
      { id: '1', name: 'FURNITURE & FIXTURE', cost: 48600, deprRate: 15 },
      { id: '2', name: 'Office Equipment', cost: 44800, deprRate: 15 },
      { id: '3', name: 'LAPTOP & printer', cost: 190000, deprRate: 15 },
    ]

    const defaultExpenses: ExpenseItem[] = [
      { id: 'e1', name: 'To Salary', amount: 330000 },
      { id: 'e2', name: 'To Printing & Stationery', amount: 9800 },
      { id: 'e3', name: 'To Postage & Telephone', amount: 1400 },
      { id: 'e4', name: 'To Electricity Charges', amount: 32400 },
      { id: 'e5', name: 'To Fees & Taxes', amount: 4000 },
      { id: 'e6', name: 'To Advertisement', amount: 7500 },
      { id: 'e7', name: 'To Sales Promotion', amount: 4500 },
      { id: 'e8', name: 'To Conveyance', amount: 54800 },
      { id: 'e9', name: 'To Telephone & Internet', amount: 9936 },
      { id: 'e10', name: 'To Bank Charges', amount: 1180 },
      { id: 'e11', name: 'To Misc. Exp.', amount: 11648 },
    ]

    // Base Year 1 (2027)
    const baseYear: YearData = {
      yearLabel: `FY ${startYear - 1}-${startYear.toString().slice(-2)}`,
      yearEnd: `31ST MARCH, ${startYear}`,
      sales: initialData?.total_sales || 15180500,
      openingStock: 1012600,
      purchases: initialData?.total_cogs || 19112680,
      closingStock: 6865700,
      expenses: defaultExpenses,
      fixedAssets: defaultFixedAssets,
      sundryDebtors: 1264536,
      cashInHand: 93058,
      balanceWithBanks: 77315,
      gstCredit: 343285,
      proprietorCapital: 8700684,
      unsecuredLoans: 0,
      creditorsForGoods: 174500,
      expensesPayable: 9600,
    }

    generateMultiYearProjections(baseYear, numYears, startYear, salesGrowth, purchaseGrowth, expenseGrowth, stockGrowth)
  }, [initialData, startYear])

  const generateMultiYearProjections = (
    baseYear: YearData,
    yearsCount: number,
    baseYearEnd: number,
    sGrowth: number,
    pGrowth: number,
    eGrowth: number,
    stkGrowth: number
  ) => {
    const list: YearData[] = []
    let prevYear: YearData = { ...baseYear }

    for (let i = 0; i < yearsCount; i++) {
      const yrEnd = baseYearEnd + i
      const yrLabel = `FY ${yrEnd - 1}-${yrEnd.toString().slice(-2)}`
      const yrEndStr = `31ST MARCH, ${yrEnd}`

      if (i === 0) {
        list.push({
          ...baseYear,
          yearLabel: yrLabel,
          yearEnd: yrEndStr,
        })
        prevYear = baseYear
      } else {
        const factorSales = 1 + sGrowth / 100
        const factorPurchases = 1 + pGrowth / 100
        const factorExpenses = 1 + eGrowth / 100
        const factorStock = 1 + stkGrowth / 100

        const newOpeningStock = prevYear.closingStock
        const newSales = Math.round(prevYear.sales * factorSales)
        const newPurchases = Math.round(prevYear.purchases * factorPurchases)
        const newClosingStock = Math.round(prevYear.closingStock * factorStock)

        // Projected Fixed Assets (WDV method: Cost becomes Previous Net WDV)
        const newFixedAssets = prevYear.fixedAssets.map(fa => {
          const prevDepr = Math.round((fa.cost * fa.deprRate) / 100)
          const newCostWDV = fa.cost - prevDepr
          return {
            ...fa,
            cost: newCostWDV > 0 ? newCostWDV : 0,
          }
        })

        // Projected Expenses
        const newExpenses = prevYear.expenses.map(exp => ({
          ...exp,
          amount: Math.round(exp.amount * factorExpenses),
        }))

        // Compute Year P&L to add Net Profit to Capital
        const grossProfit = newSales + newClosingStock - (newOpeningStock + newPurchases)
        const totalDepr = newFixedAssets.reduce((sum, fa) => sum + Math.round((fa.cost * fa.deprRate) / 100), 0)
        const totalOtherExp = newExpenses.reduce((sum, e) => sum + e.amount, 0)
        const netProfit = grossProfit - (totalOtherExp + totalDepr)

        const newCapital = prevYear.proprietorCapital + netProfit

        const newYear: YearData = {
          yearLabel: yrLabel,
          yearEnd: yrEndStr,
          sales: newSales,
          openingStock: newOpeningStock,
          purchases: newPurchases,
          closingStock: newClosingStock,
          expenses: newExpenses,
          fixedAssets: newFixedAssets,
          sundryDebtors: Math.round(prevYear.sundryDebtors * factorSales),
          cashInHand: Math.round(prevYear.cashInHand * 1.04),
          balanceWithBanks: Math.round(prevYear.balanceWithBanks * 1.2),
          gstCredit: Math.round(prevYear.gstCredit * 0.8),
          proprietorCapital: newCapital,
          unsecuredLoans: prevYear.unsecuredLoans,
          creditorsForGoods: Math.round(prevYear.creditorsForGoods * factorPurchases),
          expensesPayable: Math.round(prevYear.expensesPayable * factorExpenses),
        }

        list.push(newYear)
        prevYear = newYear
      }
    }

    setYearsData(list)
  }

  const handleApplyProjections = () => {
    if (yearsData.length === 0) return
    generateMultiYearProjections(yearsData[0], numYears, startYear, salesGrowth, purchaseGrowth, expenseGrowth, stockGrowth)
  }

  const updateYearField = (yearIdx: number, field: keyof YearData, val: any) => {
    const updated = [...yearsData]
    updated[yearIdx] = { ...updated[yearIdx], [field]: val }
    setYearsData(updated)
  }

  const updateExpense = (yearIdx: number, expId: string, amount: number) => {
    const updated = [...yearsData]
    const curYear = updated[yearIdx]
    const updatedExp = curYear.expenses.map(e => e.id === expId ? { ...e, amount } : e)
    updated[yearIdx] = { ...curYear, expenses: updatedExp }
    setYearsData(updated)
  }

  const updateFixedAsset = (yearIdx: number, faId: string, key: 'cost' | 'deprRate', val: number) => {
    const updated = [...yearsData]
    const curYear = updated[yearIdx]
    const updatedFA = curYear.fixedAssets.map(fa => fa.id === faId ? { ...fa, [key]: val } : fa)
    updated[yearIdx] = { ...curYear, fixedAssets: updatedFA }
    setYearsData(updated)
  }

  // Current Year Calculations
  const curData = yearsData[activeYearIdx] || yearsData[0]
  if (!curData) return null

  // P&L Calculations
  const grossProfit = curData.sales + curData.closingStock - (curData.openingStock + curData.purchases)
  const tradingTotal = curData.sales + curData.closingStock

  const totalDepreciation = curData.fixedAssets.reduce((sum, fa) => sum + Math.round((fa.cost * fa.deprRate) / 100), 0)
  const totalIndirectExpenses = curData.expenses.reduce((sum, e) => sum + e.amount, 0)
  const netProfit = grossProfit - (totalIndirectExpenses + totalDepreciation)

  // Balance Sheet Calculations
  const totalFixedAssetsNet = curData.fixedAssets.reduce((sum, fa) => {
    const depr = Math.round((fa.cost * fa.deprRate) / 100)
    return sum + (fa.cost - depr)
  }, 0)

  const totalCurrentAssets = curData.closingStock + curData.sundryDebtors + curData.cashInHand + curData.balanceWithBanks
  const totalLoansAdvances = curData.gstCredit
  const totalAssets = totalFixedAssetsNet + totalCurrentAssets + totalLoansAdvances

  const totalCurrentLiabilities = curData.creditorsForGoods + curData.expensesPayable
  const totalLiabilities = curData.proprietorCapital + curData.unsecuredLoans + totalCurrentLiabilities

  // Export PDF function matching exact screenshot layout
  const handleDownloadPdf = () => {
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    })

    yearsData.forEach((yd, idx) => {
      if (idx > 0) doc.addPage()

      // Computations for this year
      const gp = yd.sales + yd.closingStock - (yd.openingStock + yd.purchases)
      const tradingTot = yd.sales + yd.closingStock
      const deprTot = yd.fixedAssets.reduce((sum, fa) => sum + Math.round((fa.cost * fa.deprRate) / 100), 0)
      const indExpTot = yd.expenses.reduce((sum, e) => sum + e.amount, 0)
      const np = gp - (indExpTot + deprTot)

      const faNetTot = yd.fixedAssets.reduce((sum, fa) => sum + (fa.cost - Math.round((fa.cost * fa.deprRate) / 100)), 0)
      const currAssetsTot = yd.closingStock + yd.sundryDebtors + yd.cashInHand + yd.balanceWithBanks
      const bsAssetsTot = faNetTot + currAssetsTot + yd.gstCredit
      const bsLiabTot = yd.proprietorCapital + yd.unsecuredLoans + yd.creditorsForGoods + yd.expensesPayable

      // Page Header
      doc.setFont('times', 'bold')
      doc.setFontSize(11)
      doc.text(bussName.toUpperCase(), 105, 15, { align: 'center' })
      doc.text(`PROJECTED BALANCE SHEET AS AT ${yd.yearEnd}`, 105, 21, { align: 'center' })
      doc.line(70, 22.5, 140, 22.5) // Title underline

      // Balance Sheet Table Top Border
      let y = 30
      doc.setFontSize(9)
      doc.text('LIABILITIES', 12, y)
      doc.text('AMOUNT', 85, y, { align: 'right' })
      doc.text('ASSETS', 100, y)
      doc.text('AMOUNT', 198, y, { align: 'right' })
      doc.line(10, y + 2, 200, y + 2)

      y += 8
      doc.text("PROPRIETOR'S CAPITAL ACCOUNT", 12, y)
      doc.text(yd.proprietorCapital.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('FIXED ASSETS', 100, y)
      doc.text('-', 198, y, { align: 'right' })

      // Render Fixed Assets items on Assets side
      yd.fixedAssets.forEach((fa) => {
        const deprVal = Math.round((fa.cost * fa.deprRate) / 100)
        const netVal = fa.cost - deprVal
        y += 5
        doc.setFont('times', 'normal')
        doc.text(fa.name.toUpperCase(), 102, y)
        doc.text(fa.cost.toFixed(2), 160, y, { align: 'right' })
        
        y += 4
        doc.text(`LESS: DEPRECIATION`, 102, y)
        doc.text(deprVal.toFixed(2), 160, y, { align: 'right' })
        doc.text(netVal.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })
      })

      y += 6
      doc.setFont('times', 'bold')
      doc.text('UNSECURED LOANS', 12, y)
      if (yd.unsecuredLoans > 0) doc.text(yd.unsecuredLoans.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('CURRENT ASSETS, LOANS & ADVANCES', 100, y)

      y += 5
      doc.text('CURRENT LIABILITIES', 12, y)
      doc.text('(A) CURRENT ASSETS', 100, y)

      y += 5
      doc.setFont('times', 'normal')
      doc.text('Creditors for Goods', 12, y)
      doc.text(yd.creditorsForGoods.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('Closing Stock', 100, y)
      doc.text(yd.closingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 4
      doc.text('Expenses/ Amount Payable', 12, y)
      doc.text(yd.expensesPayable.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('(As certified by the Proprietor)', 100, y)

      y += 4
      doc.text('Sundry Debtors', 100, y)
      doc.text(yd.sundryDebtors.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 4
      doc.text('Cash in hand', 100, y)
      doc.text(yd.cashInHand.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 4
      doc.text('Balance with Banks', 100, y)
      doc.text(yd.balanceWithBanks.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 6
      doc.setFont('times', 'bold')
      doc.text('(B) LOANS & ADVANCES', 100, y)

      y += 4
      doc.setFont('times', 'normal')
      doc.text('GST Credit avilable', 100, y)
      doc.text(yd.gstCredit.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 12
      doc.setFont('times', 'bold')
      doc.text('TOTAL (RS.)', 25, y)
      doc.line(70, y - 4, 90, y - 4)
      doc.text(bsLiabTot.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })
      doc.line(70, y + 1.5, 90, y + 1.5)
      doc.line(70, y + 2.5, 90, y + 2.5)

      doc.text('TOTAL (RS.)', 120, y)
      doc.line(170, y - 4, 200, y - 4)
      doc.text(bsAssetsTot.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })
      doc.line(170, y + 1.5, 200, y + 1.5)
      doc.line(170, y + 2.5, 200, y + 2.5)

      // --- PAGE 2: PROFIT & LOSS ACCOUNT ---
      doc.addPage()
      doc.setFont('times', 'bold')
      doc.setFontSize(11)
      doc.text(bussName.toUpperCase(), 105, 15, { align: 'center' })
      doc.text(`PROJECTED PROFIT & LOSS ACCOUNT FOR THE YEAR ENDED ${yd.yearEnd}`, 105, 21, { align: 'center' })
      doc.line(55, 22.5, 155, 22.5)

      y = 30
      doc.setFontSize(9)
      doc.text('PARTICULARS', 12, y)
      doc.text('AMOUNT', 85, y, { align: 'right' })
      doc.text('PARTICULARS', 100, y)
      doc.text('AMOUNT', 198, y, { align: 'right' })
      doc.line(10, y + 2, 200, y + 2)

      // Trading Account Part
      y += 8
      doc.setFont('times', 'normal')
      doc.text('To Opening Stock', 12, y)
      doc.text(yd.openingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('By Sales', 100, y)
      doc.text(yd.sales.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 5
      doc.text('To Purchase', 12, y)
      doc.text(yd.purchases.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      doc.text('By Closing Stock', 100, y)
      doc.text(yd.closingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      y += 5
      doc.text('To Gross Profit Carried down', 12, y)
      doc.text(gp.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      y += 6
      doc.setFont('times', 'bold')
      doc.text('TOTAL (Rs.)', 25, y)
      doc.line(70, y - 4, 90, y - 4)
      doc.text(tradingTot.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })
      doc.line(70, y + 1.5, 90, y + 1.5)
      doc.line(70, y + 2.5, 90, y + 2.5)

      doc.text('TOTAL (Rs.)', 120, y)
      doc.line(170, y - 4, 200, y - 4)
      doc.text(tradingTot.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })
      doc.line(170, y + 1.5, 200, y + 1.5)
      doc.line(170, y + 2.5, 200, y + 2.5)

      // Indirect Expenses Part
      y += 10
      doc.setFont('times', 'normal')
      doc.text('By Gross Profit brought down', 100, y)
      doc.text(gp.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })

      yd.expenses.forEach((exp) => {
        doc.text(exp.name, 12, y)
        doc.text(exp.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })
        y += 4.5
      })

      doc.text('To Depreciation', 12, y)
      doc.text(deprTot.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      y += 4.5
      doc.text("To Net Profit transferred to Proprietor's Capital A/c", 12, y)
      doc.text(np.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })

      y += 7
      doc.setFont('times', 'bold')
      doc.text('TOTAL (Rs.)', 25, y)
      doc.line(70, y - 4, 90, y - 4)
      doc.text(gp.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 85, y, { align: 'right' })
      doc.line(70, y + 1.5, 90, y + 1.5)
      doc.line(70, y + 2.5, 90, y + 2.5)

      doc.text('TOTAL (Rs.)', 120, y)
      doc.line(170, y - 4, 200, y - 4)
      doc.text(gp.toLocaleString('en-IN', { minimumFractionDigits: 2 }), 198, y, { align: 'right' })
      doc.line(170, y + 1.5, 200, y + 1.5)
      doc.line(170, y + 2.5, 200, y + 2.5)
    })

    doc.save(`Projected_Financial_Statements_${bussName.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`)
  }

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <div className="bg-card border border-border rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-4">
          <div className="space-y-1">
            <h3 className="text-lg font-black tracking-tight text-foreground flex items-center gap-2">
              <FileText className="h-5 w-5 text-emerald-500" />
              <span>Projected Financial Statements & Bank PDF Generator</span>
            </h3>
            <p className="text-xs text-muted-foreground">
              Generate formal Projected Balance Sheet & P&L statements for Bank Loans & CMA Reports.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setIsEditing(!isEditing)}
              className="px-3 py-2 rounded-xl text-xs font-bold border border-border bg-muted/50 hover:bg-muted text-foreground flex items-center gap-1.5 cursor-pointer transition-all"
            >
              {isEditing ? <Lock className="h-3.5 w-3.5 text-amber-500" /> : <Edit3 className="h-3.5 w-3.5 text-emerald-500" />}
              <span>{isEditing ? 'Lock Values' : 'Edit All Fields'}</span>
            </button>
            <button
              onClick={handleDownloadPdf}
              className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white flex items-center gap-1.5 cursor-pointer shadow-sm transition-all"
            >
              <Download className="h-4 w-4" />
              <span>Download Bank PDF ({numYears} Years)</span>
            </button>
          </div>
        </div>

        {/* Global Settings & Growth Assumptions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <label className="font-extrabold uppercase text-[10px] text-muted-foreground block mb-1">Business Name</label>
            <input
              type="text"
              value={bussName}
              onChange={e => setBussName(e.target.value)}
              className="w-full bg-background border border-border rounded-xl px-3 py-2 font-bold text-foreground focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="font-extrabold uppercase text-[10px] text-muted-foreground block mb-1">Base Financial Year End</label>
            <select
              value={startYear}
              onChange={e => setStartYear(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-xl px-3 py-2 font-bold text-foreground focus:ring-2 focus:ring-emerald-500"
            >
              <option value={2026}>31st March, 2026</option>
              <option value={2027}>31st March, 2027</option>
              <option value={2028}>31st March, 2028</option>
            </select>
          </div>

          <div>
            <label className="font-extrabold uppercase text-[10px] text-muted-foreground block mb-1">Projection Duration</label>
            <select
              value={numYears}
              onChange={e => setNumYears(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-xl px-3 py-2 font-bold text-foreground focus:ring-2 focus:ring-emerald-500"
            >
              <option value={1}>1 Year (Single FY)</option>
              <option value={2}>2 Years Projection</option>
              <option value={3}>3 Years Projection (Standard Bank CMA)</option>
              <option value={5}>5 Years Projection</option>
            </select>
          </div>

          <div>
            <label className="font-extrabold uppercase text-[10px] text-muted-foreground block mb-1">Annual Sales Growth %</label>
            <input
              type="number"
              value={salesGrowth}
              onChange={e => setSalesGrowth(Number(e.target.value))}
              className="w-full bg-background border border-border rounded-xl px-3 py-2 font-bold text-foreground focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Growth Rate Modifiers & Re-Project Button */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 bg-muted/40 p-3 rounded-xl border border-border/60 text-xs">
          <div className="flex flex-wrap items-center gap-4 text-muted-foreground font-semibold">
            <span>Purchases Growth: <b className="text-foreground">{purchaseGrowth}%</b></span>
            <span>Expenses Growth: <b className="text-foreground">{expenseGrowth}%</b></span>
            <span>Closing Stock Growth: <b className="text-foreground">{stockGrowth}%</b></span>
          </div>
          <button
            onClick={handleApplyProjections}
            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-muted hover:bg-muted/80 text-foreground flex items-center gap-1 cursor-pointer transition-all border border-border"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            <span>Recalculate Multi-Year Projections</span>
          </button>
        </div>
      </div>

      {/* Year Selector Tabs */}
      <div className="flex gap-2 border-b border-border pb-2 overflow-x-auto no-scrollbar">
        {yearsData.map((yd, idx) => (
          <button
            key={idx}
            onClick={() => setActiveYearIdx(idx)}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-2 cursor-pointer ${
              activeYearIdx === idx
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            <Calendar className="h-3.5 w-3.5" />
            <span>{yd.yearEnd}</span>
          </button>
        ))}
      </div>

      {/* ACTIVE YEAR STATEMENT DISPLAY (MATCHING THE SCREENSHOT EXACTLY) */}
      <div className="bg-white dark:bg-zinc-950 border border-zinc-300 dark:border-zinc-800 rounded-2xl p-6 sm:p-8 space-y-8 font-serif text-zinc-900 dark:text-zinc-100 shadow-md">
        {/* Header Title */}
        <div className="text-center space-y-1">
          <h2 className="text-base font-extrabold uppercase tracking-wide">{bussName}</h2>
          <h3 className="text-sm font-bold uppercase underline underline-offset-4 tracking-wider">
            PROJECTED BALANCE SHEET AS AT {curData.yearEnd}
          </h3>
        </div>

        {/* Balance Sheet Grid (Two Column Layout) */}
        <div className="border-t-2 border-b-2 border-zinc-900 dark:border-zinc-100 py-3 text-xs">
          <div className="grid grid-cols-12 font-bold uppercase tracking-wider border-b border-zinc-300 dark:border-zinc-800 pb-2 mb-3">
            <div className="col-span-5">LIABILITIES</div>
            <div className="col-span-1 text-right">AMOUNT</div>
            <div className="col-span-5 pl-4">ASSETS</div>
            <div className="col-span-1 text-right">AMOUNT</div>
          </div>

          <div className="grid grid-cols-12 gap-x-2 gap-y-2 text-xs">
            {/* Left Side: Liabilities */}
            <div className="col-span-6 space-y-3 pr-2 border-r border-zinc-200 dark:border-zinc-800">
              <div>
                <div className="flex justify-between font-bold uppercase">
                  <span>PROPRIETOR'S CAPITAL ACCOUNT</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.proprietorCapital}
                      onChange={e => updateYearField(activeYearIdx, 'proprietorCapital', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.proprietorCapital.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
              </div>

              <div>
                <div className="flex justify-between font-bold uppercase">
                  <span>UNSECURED LOANS</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.unsecuredLoans}
                      onChange={e => updateYearField(activeYearIdx, 'unsecuredLoans', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.unsecuredLoans > 0 ? curData.unsecuredLoans.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '-'}</span>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <div className="font-bold uppercase">CURRENT LIABILITIES</div>
                <div className="flex justify-between pl-3">
                  <span>Creditors for Goods</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.creditorsForGoods}
                      onChange={e => updateYearField(activeYearIdx, 'creditorsForGoods', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.creditorsForGoods.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between pl-3">
                  <span>Expenses/ Amount Payable</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.expensesPayable}
                      onChange={e => updateYearField(activeYearIdx, 'expensesPayable', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.expensesPayable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
              </div>
            </div>

            {/* Right Side: Assets */}
            <div className="col-span-6 space-y-3 pl-2">
              <div>
                <div className="font-bold uppercase">FIXED ASSETS</div>
                {curData.fixedAssets.map((fa) => {
                  const deprVal = Math.round((fa.cost * fa.deprRate) / 100)
                  const netVal = fa.cost - deprVal
                  return (
                    <div key={fa.id} className="pl-3 space-y-0.5 text-[11px] my-1">
                      <div className="flex justify-between uppercase font-semibold">
                        <span>{fa.name}</span>
                        {isEditing ? (
                          <input
                            type="number"
                            value={fa.cost}
                            onChange={e => updateFixedAsset(activeYearIdx, fa.id, 'cost', Number(e.target.value))}
                            className="w-24 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono"
                          />
                        ) : (
                          <span>{fa.cost.toFixed(2)}</span>
                        )}
                      </div>
                      <div className="flex justify-between text-zinc-600 dark:text-zinc-400 pl-2">
                        <span>LESS: DEPRECIATION ({fa.deprRate}%)</span>
                        <span>{deprVal.toFixed(2)}</span>
                        <span className="font-bold text-zinc-900 dark:text-zinc-100">{netVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="space-y-1">
                <div className="font-bold uppercase">CURRENT ASSETS, LOANS & ADVANCES</div>
                <div className="font-semibold text-[11px] uppercase pl-2">(A) CURRENT ASSETS</div>
                <div className="flex justify-between pl-4">
                  <div>
                    <p>Closing Stock</p>
                    <p className="text-[10px] text-zinc-500 italic">(As certified by the Proprietor)</p>
                  </div>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.closingStock}
                      onChange={e => updateYearField(activeYearIdx, 'closingStock', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono text-xs h-6"
                    />
                  ) : (
                    <span>{curData.closingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between pl-4">
                  <span>Sundry Debtors</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.sundryDebtors}
                      onChange={e => updateYearField(activeYearIdx, 'sundryDebtors', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono text-xs h-6"
                    />
                  ) : (
                    <span>{curData.sundryDebtors.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between pl-4">
                  <span>Cash in hand</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.cashInHand}
                      onChange={e => updateYearField(activeYearIdx, 'cashInHand', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono text-xs h-6"
                    />
                  ) : (
                    <span>{curData.cashInHand.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between pl-4">
                  <span>Balance with Banks</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.balanceWithBanks}
                      onChange={e => updateYearField(activeYearIdx, 'balanceWithBanks', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono text-xs h-6"
                    />
                  ) : (
                    <span>{curData.balanceWithBanks.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>

                <div className="font-semibold text-[11px] uppercase pl-2 pt-1">(B) LOANS & ADVANCES</div>
                <div className="flex justify-between pl-4">
                  <span>GST Credit avilable</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.gstCredit}
                      onChange={e => updateYearField(activeYearIdx, 'gstCredit', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 dark:bg-zinc-900 border border-zinc-300 px-1 rounded font-mono text-xs h-6"
                    />
                  ) : (
                    <span>{curData.gstCredit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Balance Sheet Bottom Totals */}
          <div className="grid grid-cols-12 pt-4 border-t-2 border-zinc-900 dark:border-zinc-100 font-bold uppercase">
            <div className="col-span-4">TOTAL (RS.)</div>
            <div className="col-span-2 text-right text-sm underline underline-offset-4 decoration-double">
              {totalLiabilities.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
            <div className="col-span-4 pl-4">TOTAL (RS.)</div>
            <div className="col-span-2 text-right text-sm underline underline-offset-4 decoration-double">
              {totalAssets.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>
          </div>
        </div>

        {/* --- PROFIT & LOSS STATEMENT (PAGE 2) --- */}
        <div className="pt-8 border-t border-dashed border-zinc-300 dark:border-zinc-800 space-y-6">
          <div className="text-center space-y-1">
            <h2 className="text-base font-extrabold uppercase tracking-wide">{bussName}</h2>
            <h3 className="text-sm font-bold uppercase underline underline-offset-4 tracking-wider">
              PROJECTED PROFIT & LOSS ACCOUNT FOR THE YEAR ENDED {curData.yearEnd}
            </h3>
          </div>

          <div className="border-t-2 border-b-2 border-zinc-900 dark:border-zinc-100 py-3 text-xs space-y-4">
            <div className="grid grid-cols-12 font-bold uppercase tracking-wider border-b border-zinc-300 dark:border-zinc-800 pb-2">
              <div className="col-span-5">PARTICULARS</div>
              <div className="col-span-1 text-right">AMOUNT</div>
              <div className="col-span-5 pl-4">PARTICULARS</div>
              <div className="col-span-1 text-right">AMOUNT</div>
            </div>

            {/* Trading Section */}
            <div className="grid grid-cols-12 gap-x-2 text-xs">
              <div className="col-span-6 space-y-1 pr-2 border-r border-zinc-200 dark:border-zinc-800">
                <div className="flex justify-between">
                  <span>To Opening Stock</span>
                  <span>{curData.openingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span>To Purchase</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.purchases}
                      onChange={e => updateYearField(activeYearIdx, 'purchases', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 border border-zinc-300 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.purchases.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between font-bold">
                  <span>To Gross Profit Carried down</span>
                  <span>{grossProfit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>

              <div className="col-span-6 space-y-1 pl-2">
                <div className="flex justify-between">
                  <span>By Sales</span>
                  {isEditing ? (
                    <input
                      type="number"
                      value={curData.sales}
                      onChange={e => updateYearField(activeYearIdx, 'sales', Number(e.target.value))}
                      className="w-28 text-right bg-zinc-50 border border-zinc-300 px-1 rounded font-mono text-xs"
                    />
                  ) : (
                    <span>{curData.sales.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  )}
                </div>
                <div className="flex justify-between">
                  <span>By Closing Stock</span>
                  <span>{curData.closingStock.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-12 border-t border-b border-zinc-900 font-bold uppercase py-1">
              <div className="col-span-4">TOTAL (Rs.)</div>
              <div className="col-span-2 text-right underline underline-offset-4 decoration-double">
                {tradingTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div className="col-span-4 pl-4">TOTAL (Rs.)</div>
              <div className="col-span-2 text-right underline underline-offset-4 decoration-double">
                {tradingTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </div>

            {/* Indirect Expenses & Net Profit Section */}
            <div className="grid grid-cols-12 gap-x-2 text-xs">
              <div className="col-span-6 space-y-1.5 pr-2 border-r border-zinc-200 dark:border-zinc-800">
                {curData.expenses.map((exp) => (
                  <div key={exp.id} className="flex justify-between">
                    <span>{exp.name}</span>
                    {isEditing ? (
                      <input
                        type="number"
                        value={exp.amount}
                        onChange={e => updateExpense(activeYearIdx, exp.id, Number(e.target.value))}
                        className="w-24 text-right bg-zinc-50 border border-zinc-300 px-1 rounded font-mono text-xs"
                      />
                    ) : (
                      <span>{exp.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    )}
                  </div>
                ))}
                <div className="flex justify-between">
                  <span>To Depreciation</span>
                  <span>{totalDepreciation.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between font-bold pt-1 text-emerald-700 dark:text-emerald-400">
                  <span>To Net Profit transferred to Capital A/c</span>
                  <span>{netProfit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>

              <div className="col-span-6 space-y-1 pl-2">
                <div className="flex justify-between font-bold">
                  <span>By Gross Profit brought down</span>
                  <span>{grossProfit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-12 border-t-2 border-zinc-900 font-bold uppercase pt-2">
              <div className="col-span-4">TOTAL (Rs.)</div>
              <div className="col-span-2 text-right underline underline-offset-4 decoration-double">
                {grossProfit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div className="col-span-4 pl-4">TOTAL (Rs.)</div>
              <div className="col-span-2 text-right underline underline-offset-4 decoration-double">
                {grossProfit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
