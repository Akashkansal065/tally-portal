'use client'

import { useEffect } from 'react'

export function PwaRegister() {
  useEffect(() => {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').then(
          (reg) => {
            console.log('ServiceWorker registration successful with scope: ', reg.scope)
          },
          (err) => {
            console.log('ServiceWorker registration failed: ', err)
          }
        )
      })
    }
  }, [])

  return null
}
