import { useCallback, useSyncExternalStore } from 'react'

/**
 * True while the media query matches. Renders as `false` on the server, then updates in the browser.
 * Use it when a component must render differently on phones (e.g. put controls into a sheet), not for
 * styling, which CSS breakpoints handle.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [query],
  )
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false)
}

export const PHONE_QUERY = '(max-width: 767px)'
