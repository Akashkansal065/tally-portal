'use client'

/**
 * app/(console)/console/login/page.tsx – Operator Console Login Page.
 *
 * Implements:
 *   • Password authentication against platform_admins ONLY
 *   • WebAuthn / Passkey second-factor step (Face ID, Touch ID, Windows Hello, Security Key)
 *   • Clean error handling with constant failure messaging
 *   • Rate limit and lockout alert indicators
 */

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Fingerprint,
  Lock,
  Mail,
  ArrowRight,
  Loader2,
  AlertCircle,
  ShieldCheck,
} from 'lucide-react'
import { useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import { consoleApi, ConsoleApiError } from '@/console/api'

// Helper to convert base64url string to BufferSource
function base64urlToBuffer(base64url: string): BufferSource {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4)
  const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const buffer = new ArrayBuffer(rawData.length)
  const outputArray = new Uint8Array(buffer)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return buffer
}

// Helper to convert ArrayBuffer to base64url
function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export default function OperatorLoginPage() {
  const { login, completePasskeyLogin } = useConsoleAuth()
  const router = useRouter()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  // Passkey Second Step State
  const [isPasskeyStep, setIsPasskeyStep] = useState(false)
  const [mfaToken, setMfaToken] = useState('')
  const [passkeyLoading, setPasskeyLoading] = useState(false)
  const [passkeyError, setPasskeyError] = useState('')

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage('')
    setIsSubmitting(true)

    try {
      const res = await login(email, password)
      if (res.passkey_required && res.mfa_token) {
        setMfaToken(res.mfa_token)
        setIsPasskeyStep(true)
        // Auto trigger passkey prompt for seamless UX
        triggerPasskeyVerification(res.mfa_token)
      } else {
        router.push('/console')
      }
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        setErrorMessage(err.detail)
      } else {
        setErrorMessage('Failed to sign in. Please verify your connection.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const triggerPasskeyVerification = async (token: string) => {
    setPasskeyError('')
    setPasskeyLoading(true)

    try {
      if (!window.PublicKeyCredential) {
        throw new Error('Your browser does not support WebAuthn / Passkeys.')
      }

      // 1. Fetch authentication options from backend
      const { options, challenge_token } = await consoleApi.passkeyLoginOptions(token)

      // Decode challenge and allowCredentials IDs
      const rawOptions = options as Record<string, unknown>
      const rawCredentials = (rawOptions.allowCredentials as Array<Record<string, unknown>>) || []

      const publicKeyOptions: PublicKeyCredentialRequestOptions = {
        ...(options as unknown as PublicKeyCredentialRequestOptions),
        challenge: base64urlToBuffer(rawOptions.challenge as string),
        allowCredentials: rawCredentials.map((cred) => ({
          ...(cred as unknown as PublicKeyCredentialDescriptor),
          id: base64urlToBuffer(cred.id as string),
        })),
      }

      // 2. Prompt device authenticator (TouchID, FaceID, Windows Hello, YubiKey)
      const credential = (await navigator.credentials.get({
        publicKey: publicKeyOptions,
      })) as PublicKeyCredential

      if (!credential) {
        throw new Error('Passkey verification was cancelled.')
      }

      // 3. Serialize credential response for backend
      const assertionResponse = {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        response: {
          authenticatorData: bufferToBase64url(
            (credential.response as AuthenticatorAssertionResponse).authenticatorData
          ),
          clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
          signature: bufferToBase64url(
            (credential.response as AuthenticatorAssertionResponse).signature
          ),
          userHandle: (credential.response as AuthenticatorAssertionResponse).userHandle
            ? bufferToBase64url(
                (credential.response as AuthenticatorAssertionResponse).userHandle!
              )
            : null,
        },
      }

      // 4. Submit assertion to server
      await completePasskeyLogin(token, assertionResponse, challenge_token)
      router.push('/console')
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        setPasskeyError(err.detail)
      } else if (err instanceof Error) {
        setPasskeyError(err.message)
      } else {
        setPasskeyError('Passkey verification failed.')
      }
    } finally {
      setPasskeyLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-[radial-gradient(circle_at_top,_rgba(0,208,156,0.18),transparent_40%),linear-gradient(180deg,#f2faf7_0%,#edf7f2_30%,#f9fffc_100%)] relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,_rgba(10,185,129,0.08),transparent_35%)]" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#00b37a] via-[#00d09c] to-[#6ee7b7] shadow-xl shadow-[#00d09c]/25 mb-4 text-white text-2xl font-bold">
            G
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 flex items-center justify-center gap-2">
            MyTally <span className="text-xs px-2 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] uppercase tracking-wider font-semibold">Operator</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1.5 max-w-xs mx-auto">
            Platform Operator Console — Dedicated infrastructure & account administration
          </p>
        </div>

        {/* Card */}
        <div className="bg-white/90 backdrop-blur-xl border border-[#dfeee8] rounded-[28px] p-6 sm:p-8 shadow-[0_28px_70px_rgba(15,23,42,0.08)]">
          {!isPasskeyStep ? (
            /* ── Step 1: Email and Password ── */
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Operator Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-[#dfeee8] rounded-xl text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00d09c]/30 focus:border-[#00d09c] transition-all font-mono text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-[#dfeee8] rounded-xl text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00d09c]/30 focus:border-[#00d09c] transition-all font-mono"
                  />
                </div>
              </div>

              {errorMessage && (
                <div className="p-3 rounded-xl bg-[#fff1f2] border border-[#fecaca] text-[#d92d20] text-xs flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-[#00b37a] to-[#00d09c] hover:from-[#00a26d] hover:to-[#00bf8a] text-white font-medium text-xs shadow-lg shadow-[#00d09c]/25 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Verifying Credentials...</span>
                  </>
                ) : (
                  <>
                    <span>Continue</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          ) : (
            /* ── Step 2: Passkey Second Factor ── */
            <div className="text-center space-y-5">
              <div className="w-14 h-14 rounded-2xl bg-[#ebfff7] border border-[#b8f5dc] text-[#00a26d] flex items-center justify-center mx-auto">
                <Fingerprint className="w-7 h-7 animate-pulse" />
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-900">Touch ID or Security Key</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                  Verify your hardware biometric passkey or security key to complete sign-in.
                </p>
              </div>

              {passkeyError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2 text-left">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{passkeyError}</span>
                </div>
              )}

              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => triggerPasskeyVerification(mfaToken)}
                  disabled={passkeyLoading}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white font-medium text-xs shadow-lg shadow-[#00d09c]/25 transition-all disabled:opacity-50 cursor-pointer"
                >
                  {passkeyLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Waiting for Device...</span>
                    </>
                  ) : (
                    <>
                      <Fingerprint className="w-4 h-4" />
                      <span>Verify with Passkey</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setIsPasskeyStep(false)
                    setPassword('')
                  }}
                  className="w-full py-2 text-xs text-slate-500 hover:text-slate-800 transition-colors"
                >
                  Use different account
                </button>
              </div>
            </div>
          )}

          {/* Isolation Notice */}
          <div className="mt-6 pt-4 border-t border-[#e3f4ee] flex items-center justify-between text-[11px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-[#00a26d]" />
              Isolated Operator Store
            </span>
            <span>FastAPI • MyTally</span>
          </div>
        </div>

        {/* Security disclaimer footer */}
        <p className="text-center text-[11px] text-slate-500 mt-4 max-w-sm mx-auto">
          Notice: Customer tenant logins and ordinary user accounts are not permitted on this host.
        </p>
      </div>
    </div>
  )
}
