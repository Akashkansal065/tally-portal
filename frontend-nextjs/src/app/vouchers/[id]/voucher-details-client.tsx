'use client'

import { useState, useMemo } from 'react'
import { cn, toTitleCase } from '@/lib/utils'
import { getProductDetails } from '@/lib/kgoc-mapping'

type Props = {
  header: any
  accounts: any[]
  inventory: any[]
  isInventoryVoucher: boolean
}

export default function VoucherDetailsClient({ header, accounts, inventory, isInventoryVoucher }: Props) {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('all') // all | items | accounts | discounted
  const [sortBy, setSortBy] = useState('default') // default | name-asc | name-desc | amount-desc | amount-asc | qty-desc | qty-asc

  // Filter and sort items list
  const processedInventory = useMemo(() => {
    let result = [...inventory]

    // 1. Filter out if "accounts-only" is selected
    if (filterType === 'accounts') return []

    // 2. Search query filter
    if (searchQuery.trim()) {
      const lower = searchQuery.toLowerCase()
      result = result.filter(item => (item.item || '').toLowerCase().includes(lower))
    }

    // 3. Discounted filter
    if (filterType === 'discounted') {
      result = result.filter(item => parseFloat(item.discountAmount || '0') > 0)
    }

    // 4. Sorting
    if (sortBy !== 'default') {
      const [key, direction] = sortBy.split('-')
      const mult = direction === 'asc' ? 1 : -1
      
      result.sort((a, b) => {
        if (key === 'name') {
          return (a.item || '').localeCompare(b.item || '') * mult
        }
        if (key === 'amount') {
          const valA = Math.abs(parseFloat(a.amount || '0'))
          const valB = Math.abs(parseFloat(b.amount || '0'))
          return (valA - valB) * mult
        }
        if (key === 'qty') {
          const valA = Math.abs(parseFloat(a.quantity || '0'))
          const valB = Math.abs(parseFloat(b.quantity || '0'))
          return (valA - valB) * mult
        }
        return 0
      })
    }

    return result
  }, [inventory, searchQuery, filterType, sortBy])

  // Filter accounts splits list
  const processedAccounts = useMemo(() => {
    let result = [...accounts]

    // 1. Filter out if "items-only" or "discounted-only" is selected
    if (filterType === 'items' || filterType === 'discounted') return []

    // 2. Search query filter
    if (searchQuery.trim()) {
      const lower = searchQuery.toLowerCase()
      result = result.filter(acc => (acc.ledger || '').toLowerCase().includes(lower))
    }

    return result
  }, [accounts, searchQuery, filterType])

  const formatNumber = (val: string | number) => {
    const parsed = typeof val === 'string' ? parseFloat(val) : val
    return isNaN(parsed) ? '' : parsed.toLocaleString('en-IN', { minimumFractionDigits: 2 })
  }

  const hasDiscountedItems = useMemo(() => {
    return inventory.some(item => parseFloat(item.discountAmount || '0') > 0)
  }, [inventory])

  return (
    <div className="space-y-4">
      {/* Search & Filters Bar */}
      <div className="bg-muted/40 p-3 flex flex-wrap gap-x-4 gap-y-2 items-center border rounded shadow-sm text-xs bg-card no-print">
        {/* Search Input */}
        <div className="flex-1 min-w-[200px] max-w-xs">
          <input
            type="text"
            placeholder="Search items or ledger splits..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-2 py-1 text-xs border border-border/50 rounded bg-background shadow-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-shadow"
          />
        </div>

        {/* Filter Type */}
        {isInventoryVoucher && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Show:</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-card border border-border rounded px-2 py-0.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
            >
              <option value="all">All Content</option>
              <option value="items">Items Only</option>
              <option value="accounts">Tax & Ledger Splits</option>
              {hasDiscountedItems && <option value="discounted">Discounted Items Only</option>}
            </select>
          </div>
        )}

        {/* Sort By (Only applicable if inventory items are visible) */}
        {isInventoryVoucher && filterType !== 'accounts' && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Sort Items:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-card border border-border rounded px-2 py-0.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer text-emerald-600 dark:text-emerald-400 font-bold"
            >
              <option value="default">Default Order</option>
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
              <option value="qty-desc">Qty (High-Low)</option>
              <option value="qty-asc">Qty (Low-High)</option>
              <option value="amount-desc">Value (High-Low)</option>
              <option value="amount-asc">Value (Low-High)</option>
            </select>
          </div>
        )}

        {/* Clear Filters Button */}
        {(searchQuery !== '' || filterType !== 'all' || sortBy !== 'default') && (
          <button
            onClick={() => {
              setSearchQuery('')
              setFilterType('all')
              setSortBy('default')
            }}
            className="text-[10px] text-red-600 dark:text-red-400 font-bold hover:underline ml-auto"
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Mobile Card Layout (hidden on Desktop) */}
      <div className="block md:hidden space-y-4">
        {/* Inventory Items */}
        {processedInventory.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-base font-bold uppercase tracking-wider text-muted-foreground font-mono">Items List</h3>
            {processedInventory.map((item, idx) => {
              const qty = Math.abs(parseFloat(item.quantity || '0'))
              const rate = parseFloat(item.rate || '0')
              const gstRate = parseFloat(item.gstRate || '0')
              const rateInclTax = rate * (1 + gstRate / 100)
              const discPercent = parseFloat(item.discountAmount || '0')
              const amt = Math.abs(parseFloat(item.amount || '0'))

              return (
                <div key={`mob-inv-${idx}`} className="p-4 bg-muted/20 border border-border rounded flex flex-col gap-3 shadow-sm font-sans">
                  {/* Item Name */}
                  <div className="mb-1">
                    <div className="font-extrabold text-base sm:text-lg text-foreground break-words leading-snug">
                      {toTitleCase(item.item)}
                    </div>
                    {(() => {
                      const details = getProductDetails(item.item, "");
                      if (details.subtitle === item.item && details.brand === "ITEM") return null;
                      return (
                        <div className="flex items-center gap-2 mt-1">
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-secondary text-secondary-foreground border border-border">
                            {details.brand}
                          </span>
                          <span className="text-[11px] text-muted-foreground font-medium">
                            {details.subtitle}
                          </span>
                        </div>
                      );
                    })()}
                  </div>
                  
                  {/* Metrics Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm mt-1">
                    {/* Qty & UOM */}
                    <div className="bg-card border border-border/50 p-2.5 rounded flex flex-col">
                      <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Qty</span>
                      <span className="font-extrabold font-mono text-foreground text-sm sm:text-base mt-0.5">{qty.toLocaleString('en-IN')} {item.uom}</span>
                    </div>

                    {/* HSN/SAC */}
                    {item.gstHsnCode && (
                      <div className="bg-card border border-border/50 p-2.5 rounded flex flex-col">
                        <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">HSN/SAC</span>
                        <span className="font-extrabold font-mono text-foreground text-sm sm:text-base mt-0.5">{item.gstHsnCode}</span>
                      </div>
                    )}

                    {/* Rate Incl Tax */}
                    <div className="bg-card border border-border/50 p-2.5 rounded flex flex-col">
                      <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Rate (Tax Incl)</span>
                      <span className="font-extrabold font-mono text-foreground text-sm sm:text-base mt-0.5">₹{rateInclTax.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>

                    {/* Rate (Base) */}
                    <div className="bg-card border border-border/50 p-2.5 rounded flex flex-col">
                      <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">Rate (Excl Tax)</span>
                      <span className="font-extrabold font-mono text-foreground text-sm sm:text-base mt-0.5">₹{rate.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>

                    {/* Discount */}
                    {discPercent > 0 && (
                      <div className="bg-rose-50/50 dark:bg-rose-950/10 border border-rose-200/40 p-2.5 rounded flex flex-col">
                        <span className="text-[10px] sm:text-[11px] font-bold text-rose-600 dark:text-rose-455 uppercase tracking-wider">Discount</span>
                        <span className="font-extrabold font-mono text-rose-700 dark:text-rose-350 text-sm sm:text-base mt-0.5">{discPercent}%</span>
                      </div>
                    )}
                  </div>

                  {/* Net Amount Row */}
                  <div className="flex justify-between items-center bg-card/45 border border-border/40 px-2.5 py-2 rounded mt-0.5">
                    <span className="text-xs sm:text-sm font-bold uppercase text-muted-foreground tracking-wider">Net Value:</span>
                    <span className="text-base sm:text-lg font-black font-mono text-emerald-600">₹{amt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Ledger Splits (GST, Round off, etc.) */}
        {processedAccounts.length > 0 && (
          <div className="space-y-2 mt-4">
            <h3 className="text-base font-bold uppercase tracking-wider text-muted-foreground font-mono">Accounts Split</h3>
            <div className="border border-border/50 rounded bg-card/30 divide-y divide-border/40 font-sans">
              {processedAccounts.map((acc, idx) => {
                const amt = parseFloat(acc.amount || '0')
                // Skip party ledger if items exist (to avoid double listing the total)
                if (isInventoryVoucher && acc.ledger === header.partyName) return null

                return (
                  <div key={`mob-acc-${idx}`} className="p-3 flex justify-between items-center text-base">
                    <span className="text-muted-foreground font-semibold">
                      <span className="text-foreground font-extrabold">
                        {amt < 0 ? 'Dr ' : 'To '}
                      </span>
                      {toTitleCase(acc.ledger)}
                    </span>
                    <span className="font-mono font-black text-foreground text-base sm:text-lg">
                      ₹{Math.abs(amt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Desktop Table View (hidden on Mobile) */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full border-t border-foreground">
          <thead>
            <tr className="border-b border-foreground text-left bg-muted/50">
              <th className="py-2 px-2">Particulars</th>
              {isInventoryVoucher && (
                <>
                  <th className="py-2 px-2 text-muted-foreground text-xs font-bold font-mono">HSN/SAC</th>
                  <th className="py-2 text-right px-2">Quantity</th>
                  <th className="py-2 text-right px-2">Rate(Incl of Tax)</th>
                  <th className="py-2 text-right px-2">per</th>
                  <th className="py-2 text-right px-2">Rate</th>
                  <th className="py-2 text-right px-2">Disc %</th>
                </>
              )}
              <th className="py-2 text-right px-2">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {/* Inventory Items (Stock) */}
            {processedInventory.map((item, idx) => {
              const rate = parseFloat(item.rate || '0')
              const gstRate = parseFloat(item.gstRate || '0')
              const rateInclTax = rate * (1 + gstRate / 100)
              const discPercent = parseFloat(item.discountAmount || '0')

              return (
                <tr key={`inv-${idx}`} className="align-top hover:bg-muted/30 transition-colors">
                  <td className="py-2 px-2">
                    <div className="font-semibold">{toTitleCase(item.item)}</div>
                    {(() => {
                      const details = getProductDetails(item.item, "");
                      if (details.subtitle === item.item && details.brand === "ITEM") return null;
                      return (
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider bg-secondary text-secondary-foreground border border-border">
                            {details.brand}
                          </span>
                          <span className="text-[10px] text-muted-foreground font-medium truncate max-w-[200px]">
                            {details.subtitle}
                          </span>
                        </div>
                      );
                    })()}
                  </td>
                  <td className="py-2 px-2 font-mono text-xs text-muted-foreground font-semibold">
                    {item.gstHsnCode || ''}
                  </td>
                  <td className="py-2 text-right px-2 font-mono">
                    {Math.abs(parseFloat(item.quantity || '0')).toLocaleString('en-IN', { maximumFractionDigits: 4 })}
                  </td>
                  <td className="py-2 text-right px-2 font-mono">
                    {rateInclTax > 0 ? rateInclTax.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ''}
                  </td>
                  <td className="py-2 text-right px-2 text-muted-foreground">{item.uom || ''}</td>
                  <td className="py-2 text-right px-2 font-mono">
                    {rate.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-2 text-right px-2 font-mono">
                    {discPercent > 0 ? `${discPercent}%` : ''}
                  </td>
                  <td className="py-2 text-right px-2 font-mono font-bold tabular-nums">
                    {Math.abs(parseFloat(item.amount || '0')).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              )
            })}

            {/* Ledger Splits (GST, Round off, etc.) */}
            {processedAccounts.map((acc, idx) => {
              const amt = parseFloat(acc.amount || '0')
              // Skip party ledger if items exist (to avoid double listing the total)
              if (isInventoryVoucher && acc.ledger === header.partyName) return null

              const ledgerName = acc.ledger || ''
              const isDiscount = ledgerName.toUpperCase().includes('DISCOUNT')

              if (isInventoryVoucher && isDiscount) {
                const totalInvAmount = processedInventory.reduce((sum, item) => sum + Math.abs(parseFloat(item.amount || '0')), 0)
                const discRate = totalInvAmount > 0 ? Math.round((Math.abs(amt) / totalInvAmount) * 100) : 0

                return (
                  <tr key={`acc-${idx}`} className="hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-2 italic text-muted-foreground font-semibold" colSpan={3}>
                      <span className="text-foreground not-italic font-bold">
                        Less :
                      </span>{' '}
                      {ledgerName.toUpperCase()}
                    </td>
                    <td className="py-2 text-center px-2 text-muted-foreground font-bold">
                      %
                    </td>
                    <td className="py-2 text-right px-2 font-mono text-foreground font-bold">
                      (-){discRate}
                    </td>
                    <td className="py-2 px-2"></td>
                    <td className="py-2 text-right px-2 font-mono tabular-nums font-bold text-foreground">
                      (-){Math.abs(amt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                )
              }

              const isRoundOff = ledgerName.toUpperCase().includes('ROUND')
              const formattedAmt = isRoundOff
                ? amt.toLocaleString('en-IN', { minimumFractionDigits: 2 })
                : Math.abs(amt).toLocaleString('en-IN', { minimumFractionDigits: 2 })

              return (
                <tr key={`acc-${idx}`} className="hover:bg-muted/30 transition-colors">
                  <td className="py-2 px-2 italic text-muted-foreground" colSpan={isInventoryVoucher ? 6 : 1}>
                    <span className="text-foreground not-italic font-medium">
                      {amt < 0 ? 'Dr ' : 'To '}
                    </span>
                    {toTitleCase(acc.ledger)}
                  </td>
                  <td className="py-2 text-right px-2 font-mono tabular-nums font-medium">
                    {formattedAmt}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
