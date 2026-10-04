import { useCallback, useEffect, useState } from 'react'

/**
 * Runs `load` (memoize it with useCallback) whenever it changes or `reload()` is called, and tracks
 * loading/error without setting state synchronously inside the effect. Keeps the previous data
 * visible while a new request is in flight.
 */
export function useLoader<T>(load: () => Promise<T>) {
  const [nonce, setNonce] = useState(0)
  const [result, setResult] = useState<{ load: (() => Promise<T>) | null; nonce: number; data: T | null; error: string }>({
    load: null,
    nonce: -1,
    data: null,
    error: '',
  })

  useEffect(() => {
    let cancelled = false
    load().then(
      (data) => {
        if (!cancelled) setResult({ load, nonce, data, error: '' })
      },
      (err: unknown) => {
        if (!cancelled) {
          const error = err instanceof Error ? err.message : 'Could not load.'
          setResult((prev) => ({ load, nonce, data: prev.data, error }))
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [load, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  const loading = result.load !== load || result.nonce !== nonce
  return { data: result.data, error: result.error, loading, reload }
}
