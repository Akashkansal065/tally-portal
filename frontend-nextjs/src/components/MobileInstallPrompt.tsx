'use client'

import { useState, useEffect, useRef } from 'react'
import { Share, PlusSquare, X, Smartphone, CheckCircle, Download } from 'lucide-react'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export function MobileInstallPrompt() {
  const [platform, setPlatform] = useState<'ios' | 'android' | null>(null)
  const [showPrompt, setShowPrompt] = useState(false)
  const [showIosModal, setShowIosModal] = useState(false)
  const deferredPromptRef = useRef<BeforeInstallPromptEvent | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return

    // Check if already in standalone app mode
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true

    if (isStandalone) return

    // Check if dismissed recently (within 7 days)
    const dismissedAt = localStorage.getItem('mytally_install_prompt_dismissed')
    const isRecentlyDismissed =
      dismissedAt && Date.now() - Number(dismissedAt) < 7 * 24 * 60 * 60 * 1000

    if (isRecentlyDismissed) return

    const ua = window.navigator.userAgent
    const isIos = /iPhone|iPad|iPod/.test(ua)
    const isAndroid = /Android/i.test(ua)

    if (isIos) {
      setPlatform('ios')
      const timer = setTimeout(() => setShowPrompt(true), 2500)
      return () => clearTimeout(timer)
    }

    // Android & Chrome beforeinstallprompt event
    const handleBeforeInstall = (e: Event) => {
      e.preventDefault()
      deferredPromptRef.current = e as BeforeInstallPromptEvent
      setPlatform(isAndroid ? 'android' : 'android')
      setShowPrompt(true)
    }

    const handleAppInstalled = () => {
      setShowPrompt(false)
      deferredPromptRef.current = null
      try {
        localStorage.setItem('mytally_install_prompt_dismissed', Date.now().toString())
      } catch (e) {}
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstall)
    window.addEventListener('appinstalled', handleAppInstalled)

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall)
      window.removeEventListener('appinstalled', handleAppInstalled)
    }
  }, [])

  const handleInstallClick = async () => {
    if (platform === 'ios') {
      setShowIosModal(true)
      return
    }

    // Android / Desktop Chrome PWA Install
    if (deferredPromptRef.current) {
      try {
        await deferredPromptRef.current.prompt()
        const choice = await deferredPromptRef.current.userChoice
        if (choice.outcome === 'accepted') {
          setShowPrompt(false)
        }
        deferredPromptRef.current = null
      } catch (e) {
        console.error('Install prompt error', e)
      }
    }
  }

  const handleDismiss = () => {
    setShowPrompt(false)
    setShowIosModal(false)
    try {
      localStorage.setItem('mytally_install_prompt_dismissed', Date.now().toString())
    } catch (e) {}
  }

  if (!showPrompt || !platform) return null

  return (
    <>
      {/* Floating Bottom Toast Prompt for both Android & iOS */}
      <div
        className="fixed z-40 left-3 right-3 sm:left-auto sm:right-4 sm:w-96 bg-card border border-emerald-500/40 rounded-2xl p-3.5 shadow-2xl animate-in slide-in-from-bottom-5 duration-300 backdrop-blur-md bg-card/95 text-foreground"
        style={{ bottom: 'calc(4.75rem + env(safe-area-inset-bottom, 0px))' }}
      >
        <div className="flex items-start gap-3">
          <img
            src="/icon-192.png"
            alt="MyTally App Icon"
            className="w-10 h-10 rounded-xl shadow-sm border border-border shrink-0"
          />
          <div className="flex-1 min-w-0">
            <h4 className="font-extrabold text-xs text-foreground flex items-center gap-1.5">
              <span>{platform === 'ios' ? 'Open MyTally as iOS App' : 'Install MyTally Android App'}</span>
            </h4>
            <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">
              {platform === 'ios'
                ? 'Run full-screen without Safari bars and launch directly from Home Screen.'
                : 'Install native standalone app on your device for instant launch & full-screen view.'}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <button
                onClick={handleInstallClick}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[11px] rounded-lg transition-colors cursor-pointer shadow-xs flex items-center gap-1.5"
              >
                {platform === 'ios' ? (
                  <>
                    <Smartphone className="w-3.5 h-3.5" />
                    <span>How to Install</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Install App</span>
                  </>
                )}
              </button>
              <button
                onClick={handleDismiss}
                className="px-2 py-1 text-muted-foreground hover:text-foreground text-[11px] font-medium transition-colors cursor-pointer"
              >
                Not now
              </button>
            </div>
          </div>
          <button
            onClick={handleDismiss}
            className="p-1 text-muted-foreground hover:text-foreground rounded-lg transition-colors cursor-pointer"
            aria-label="Dismiss prompt"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* iOS Step-by-Step Instructions Modal */}
      {showIosModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-3 animate-in fade-in duration-200">
          <div
            className="bg-card border border-border rounded-3xl max-w-sm w-full p-5 space-y-4 shadow-2xl text-foreground relative animate-in zoom-in-95 duration-200"
            style={{ paddingBottom: 'calc(1.25rem + env(safe-area-inset-bottom, 0px))' }}
          >
            <button
              onClick={() => setShowIosModal(false)}
              className="absolute top-4 right-4 p-1.5 text-muted-foreground hover:text-foreground rounded-full hover:bg-muted transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 border-b border-border pb-3">
              <div className="p-2.5 rounded-2xl bg-emerald-500/10 text-emerald-600">
                <Smartphone className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-foreground">Install on iPhone / iPad</h3>
                <p className="text-[11px] text-muted-foreground">3 simple steps to open like a native app</p>
              </div>
            </div>

            <ol className="space-y-3 text-xs">
              <li className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/60">
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white font-black text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  1
                </span>
                <div className="space-y-0.5">
                  <p className="font-bold text-foreground flex items-center gap-1.5">
                    Tap the Share icon <Share className="w-3.5 h-3.5 text-blue-500 inline" />
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Located in the Safari toolbar at the bottom of your iPhone screen.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/60">
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white font-black text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  2
                </span>
                <div className="space-y-0.5">
                  <p className="font-bold text-foreground flex items-center gap-1.5">
                    Select &quot;Add to Home Screen&quot; <PlusSquare className="w-3.5 h-3.5 text-foreground inline" />
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Scroll down in the share sheet options and tap <strong>Add to Home Screen</strong>.
                  </p>
                </div>
              </li>

              <li className="flex items-start gap-3 p-2.5 rounded-xl bg-muted/40 border border-border/60">
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white font-black text-[10px] flex items-center justify-center shrink-0 mt-0.5">
                  3
                </span>
                <div className="space-y-0.5">
                  <p className="font-bold text-foreground flex items-center gap-1.5">
                    Tap &quot;Add&quot; in Top Right <CheckCircle className="w-3.5 h-3.5 text-emerald-500 inline" />
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    MyTally will be placed on your home screen and will open full-screen like a native app.
                  </p>
                </div>
              </li>
            </ol>

            <button
              onClick={handleDismiss}
              className="w-full py-2.5 bg-primary text-primary-foreground font-bold text-xs rounded-xl hover:bg-primary/90 transition-all cursor-pointer shadow-xs"
            >
              Got it, thanks!
            </button>
          </div>
        </div>
      )}
    </>
  )
}
