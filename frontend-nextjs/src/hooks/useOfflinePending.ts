'use client'

import { useEffect, useState } from 'react'
import { getOfflineQueue } from '@/lib/offline-storage'

/** How many items saved on this device are still waiting to upload (or failed to). Updates when the queue changes. */
export function useOfflinePending(): number {
  const [count, setCount] = useState(0)

  useEffect(() => {
    const update = () => {
      getOfflineQueue()
        .then(queue => setCount(queue.filter(i => i.status === 'pending' || i.status === 'failed').length))
        .catch(() => {})
    }
    update()
    window.addEventListener('mytally:offline-queue-changed', update)
    return () => window.removeEventListener('mytally:offline-queue-changed', update)
  }, [])

  return count
}
