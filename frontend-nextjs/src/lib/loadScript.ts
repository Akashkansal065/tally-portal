/**
 * loadScript.ts – Dynamically load external scripts on demand (e.g. Razorpay, Cashfree SDKs).
 */

const loadedScripts: Record<string, Promise<boolean>> = {}

export function loadScript(src: string): Promise<boolean> {
  if (typeof window === 'undefined') {
    return Promise.resolve(false)
  }

  if (src in loadedScripts) {
    return loadedScripts[src]
  }

  // Check if script tag is already in DOM
  const existingScript = document.querySelector(`script[src="${src}"]`)
  if (existingScript) {
    loadedScripts[src] = Promise.resolve(true)
    return loadedScripts[src]
  }

  loadedScripts[src] = new Promise<boolean>((resolve) => {
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.onload = () => resolve(true)
    script.onerror = () => {
      delete loadedScripts[src]
      resolve(false)
    }
    document.body.appendChild(script)
  })

  return loadedScripts[src]
}
