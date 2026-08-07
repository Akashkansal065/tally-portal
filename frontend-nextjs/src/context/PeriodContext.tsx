'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'

interface PeriodContextValue {
  startDate: string
  endDate: string
  setPeriod: (start: string, end: string) => void
  resetPeriod: () => void
}

const getCurrentFY = () => {
  const now = new Date()
  const yr = now.getFullYear()
  const m = now.getMonth() // 0-indexed (0=Jan, 3=Apr)
  const fyStart = m >= 3 ? yr : yr - 1
  return {
    start: `${fyStart}-04-01`,
    end: `${fyStart + 1}-03-31`
  }
}

const defaultFY = getCurrentFY()

const PeriodContext = createContext<PeriodContextValue>({
  startDate: defaultFY.start,
  endDate: defaultFY.end,
  setPeriod: () => {},
  resetPeriod: () => {},
})

export function PeriodProvider({ children }: { children: React.ReactNode }) {
  const [startDate, setStartDateState] = useState<string>(defaultFY.start)
  const [endDate, setEndDateState] = useState<string>(defaultFY.end)

  useEffect(() => {
    const savedStart = localStorage.getItem('mytally_period_start')
    const savedEnd = localStorage.getItem('mytally_period_end')
    if (savedStart) setStartDateState(savedStart)
    if (savedEnd) setEndDateState(savedEnd)
  }, [])

  const setPeriod = (start: string, end: string) => {
    const curr = getCurrentFY()
    const finalStart = start || curr.start
    const finalEnd = end || curr.end
    setStartDateState(finalStart)
    setEndDateState(finalEnd)
    localStorage.setItem('mytally_period_start', finalStart)
    localStorage.setItem('mytally_period_end', finalEnd)
  }

  const resetPeriod = () => {
    const curr = getCurrentFY()
    setStartDateState(curr.start)
    setEndDateState(curr.end)
    localStorage.setItem('mytally_period_start', curr.start)
    localStorage.setItem('mytally_period_end', curr.end)
  }

  return (
    <PeriodContext.Provider value={{ startDate, endDate, setPeriod, resetPeriod }}>
      {children}
    </PeriodContext.Provider>
  )
}

export const usePeriod = () => useContext(PeriodContext)
