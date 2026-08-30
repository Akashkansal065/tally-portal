'use client'

import { useEffect } from 'react'

export function DatePickerInitializer() {
  useEffect(() => {
    const handleGlobalClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (target && target.tagName === 'INPUT' && (target as HTMLInputElement).type === 'date') {
        try {
          if (typeof (target as HTMLInputElement).showPicker === 'function') {
            (target as HTMLInputElement).showPicker()
          }
        } catch (_) {}
      }
    }

    document.addEventListener('click', handleGlobalClick, true)
    return () => {
      document.removeEventListener('click', handleGlobalClick, true)
    }
  }, [])

  return null
}
