'use client'

/**
 * app/(console)/console/page.tsx – Platform Operator Console Overview & Phase 1 Dashboard.
 *
 * Displays:
 *   • Current operator identity, permissions & rank
 *   • Hardware Passkey management (register device, list passkeys)
 *   • Active session inspection and revocation
 *   • Roadmap phase access & system health
 */

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  Shield,
  KeyRound,
  Fingerprint,
  ShieldCheck,
  CreditCard,
  Laptop,
  Trash2,
  Plus,
  Loader2,
  CheckCircle2,
  UserPlus,
  Users,
} from 'lucide-react'
import { useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import {
  consoleApi,
  ConsoleApiError,
  PasskeyItem,
  SessionItem,
} from '@/console/api'

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

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export default function ConsoleOverviewPage() {
  const { operator, permissions } = useConsoleAuth()

  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [passkeys, setPasskeys] = useState<PasskeyItem[]>([])

  const [registeringPasskey, setRegisteringPasskey] = useState(false)
  const [passkeyNickname, setPasskeyNickname] = useState('Office Laptop')
  const [showAddPasskeyModal, setShowAddPasskeyModal] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  const loadData = async () => {
    const [sessList, credList] = await Promise.all([
      consoleApi.getSessions().catch(() => []),
      consoleApi.getPasskeys().catch(() => []),
    ])
    setSessions(sessList)
    setPasskeys(credList)
  }

  useEffect(() => {
    let mounted = true
    const fetchData = async () => {
      const [sessList, credList] = await Promise.all([
        consoleApi.getSessions().catch(() => []),
        consoleApi.getPasskeys().catch(() => []),
      ])
      if (mounted) {
        setSessions(sessList)
        setPasskeys(credList)
      }
    }
    fetchData()
    return () => {
      mounted = false
    }
  }, [])



  const handleRegisterPasskey = async () => {
    setActionError('')
    setActionSuccess('')
    setRegisteringPasskey(true)

    try {
      if (!window.PublicKeyCredential) {
        throw new Error('Your browser does not support WebAuthn passkeys.')
      }

      // 1. Get registration options
      const { options, challenge_token } = await consoleApi.passkeyRegisterOptions()
      const rawOptions = options as Record<string, unknown>
      const rawUser = rawOptions.user as Record<string, unknown>
      const rawExclude = (rawOptions.excludeCredentials as Array<Record<string, unknown>>) || []

      const publicKeyOptions: PublicKeyCredentialCreationOptions = {
        ...(options as unknown as PublicKeyCredentialCreationOptions),
        challenge: base64urlToBuffer(rawOptions.challenge as string),
        user: {
          ...(rawUser as unknown as PublicKeyCredentialUserEntity),
          id: base64urlToBuffer(rawUser.id as string),
        },
        excludeCredentials: rawExclude.map((cred) => ({
          ...(cred as unknown as PublicKeyCredentialDescriptor),
          id: base64urlToBuffer(cred.id as string),
        })),
      }

      // 2. Call authenticator
      const credential = (await navigator.credentials.create({
        publicKey: publicKeyOptions,
      })) as PublicKeyCredential

      if (!credential) {
        throw new Error('Passkey creation was cancelled.')
      }

      const attestationResponse = {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        response: {
          clientDataJSON: bufferToBase64url(
            (credential.response as AuthenticatorAttestationResponse).clientDataJSON
          ),
          attestationObject: bufferToBase64url(
            (credential.response as AuthenticatorAttestationResponse).attestationObject
          ),
        },
      }

      // 3. Verify on server
      await consoleApi.passkeyRegisterVerify(
        attestationResponse,
        challenge_token,
        passkeyNickname || 'My Device'
      )

      setActionSuccess('Passkey registered successfully.')
      setShowAddPasskeyModal(false)
      loadData()
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        setActionError(err.detail)
      } else if (err instanceof Error) {
        setActionError(err.message)
      } else {
        setActionError('Failed to register passkey.')
      }
    } finally {
      setRegisteringPasskey(false)
    }
  }

  const handleDeletePasskey = async (pk: number) => {
    if (!confirm('Are you sure you want to remove this passkey?')) return
    try {
      await consoleApi.deletePasskey(pk)
      loadData()
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        alert(err.detail)
      } else {
        alert('Failed to delete passkey.')
      }
    }
  }

  const handleRevokeSession = async (sid: number) => {
    if (!confirm('Revoke this session?')) return
    try {
      await consoleApi.revokeSession(sid)
      loadData()
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError) {
        alert(err.detail)
      } else {
        alert('Failed to revoke session.')
      }
    }
  }

  return (
    <div className="space-y-8">
      {/* ── Welcome Banner ── */}
      <div className="relative rounded-[28px] bg-gradient-to-r from-[#ebfff7] via-white to-[#f3faf7] border border-[#dfeee8] p-6 md:p-8 shadow-[0_18px_45px_rgba(15,23,42,0.04)] overflow-hidden">
        <div className="absolute inset-y-0 right-0 w-40 bg-[radial-gradient(circle_at_center,_rgba(0,208,156,0.12),transparent_70%)]" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] text-xs font-semibold flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00d09c] animate-pulse" />
                Active Session
              </span>
              <span className="text-xs text-slate-500 font-mono">Rank: {operator?.max_rank}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Welcome, {operator?.full_name}
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Signed in as <code className="text-[#00a26d] font-mono text-xs">{operator?.email}</code>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/console/roles?tab=admins"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-white text-xs font-semibold shadow-lg shadow-[#00d09c]/20 transition-all"
            >
              <UserPlus className="w-4 h-4" />
              Invite Operator
            </Link>
            <button
              onClick={() => setShowAddPasskeyModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium border border-[#dfeee8] transition-all shadow-sm"
            >
              <Fingerprint className="w-4 h-4 text-[#00a26d]" />
              Register Passkey
            </button>
            <Link
              href="/console/billing"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium border border-[#dfeee8] transition-all shadow-sm"
            >
              <CreditCard className="w-4 h-4 text-[#00a26d]" />
              Billing Console
            </Link>
          </div>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* ── Status Grid ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-500">Architecture</span>
            <div className="p-2 rounded-lg bg-[#ebfff7] text-[#00a26d]">
              <Shield className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold text-slate-900">Isolated Store</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Dedicated <code className="font-mono text-[#00a26d]">platform_*</code> tables
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-500">Authentication</span>
            <div className="p-2 rounded-lg bg-[#ebfff7] text-[#00a26d]">
              <Fingerprint className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold text-slate-900">
            {operator?.passkey_required ? 'Passkeys Active' : 'Password Only'}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {passkeys.length} biometric key{passkeys.length !== 1 ? 's' : ''} registered
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-500">Tokens & Cookies</span>
            <div className="p-2 rounded-lg bg-[#f3f6ff] text-[#4f46e5]">
              <KeyRound className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold text-slate-900">Rotating Family</div>
          <div className="text-[11px] text-slate-500 mt-1">
            10m JWT + HttpOnly refresh rotation
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-white border border-[#dfeee8] shadow-[0_10px_24px_rgba(15,23,42,0.03)] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-500">Effective Permissions</span>
            <div className="p-2 rounded-lg bg-[#fff7db] text-[#a16207]">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="text-lg font-bold text-slate-900">
            {permissions.size} Permission{permissions.size !== 1 ? 's' : ''}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Roles synchronized at startup
          </div>
        </div>
      </div>

      {/* ── Two Column: Passkeys & Active Sessions ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Hardware Passkeys */}
        <div className="rounded-2xl bg-white border border-[#dfeee8] p-6 space-y-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-[#ebfff7] text-[#00a26d]">
                <Fingerprint className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Registered Passkeys</h3>
                <p className="text-xs text-slate-500">Biometric devices & security keys for step-up</p>
              </div>
            </div>
            <button
              onClick={() => setShowAddPasskeyModal(true)}
              className="px-2.5 py-1.5 rounded-lg bg-[#ebfff7] hover:bg-[#ddf9ee] text-xs text-[#00a26d] transition-colors"
            >
              + Add
            </button>
          </div>

          <div className="space-y-2">
            {passkeys.length === 0 ? (
              <div className="p-6 rounded-xl border border-dashed border-[#dfeee8] text-center text-xs text-slate-500">
                No passkeys registered yet. Click &quot;Register Passkey&quot; to add this device.
              </div>
            ) : (
              passkeys.map((cred) => (
                <div
                  key={cred.credential_pk}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]"
                >
                  <div className="flex items-center gap-3">
                    <Laptop className="w-4 h-4 text-[#00a26d]" />
                    <div>
                      <div className="text-xs font-semibold text-slate-800">{cred.nickname}</div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        RP: {cred.rp_id} • Registered:{' '}
                        {new Date(cred.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeletePasskey(cred.credential_pk)}
                    className="p-1.5 text-slate-400 hover:text-[#d92d20] transition-colors"
                    title="Remove passkey"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Active Operator Sessions */}
        <div className="rounded-2xl bg-white border border-[#dfeee8] p-6 space-y-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-[#f3f6ff] text-[#4f46e5]">
                <Laptop className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Active Sessions</h3>
                <p className="text-xs text-slate-500">Open operator sessions across browsers</p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            {sessions.map((sess) => (
              <div
                key={sess.session_id}
                className="flex items-center justify-between p-3.5 rounded-xl bg-[#f9fffc] border border-[#e3f4ee]"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-800 font-mono">
                      {sess.ip_address || '127.0.0.1'}
                    </span>
                    {sess.is_current && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] font-semibold">
                        This Device
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate max-w-xs mt-0.5 font-mono">
                    {sess.user_agent || 'Operator Client'}
                  </div>
                </div>
                {!sess.is_current && (
                  <button
                    onClick={() => handleRevokeSession(sess.session_id)}
                    className="text-xs text-[#d92d20] hover:text-[#b42318] font-medium"
                  >
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Roadmap Progress ── */}
      <div className="rounded-2xl bg-white border border-[#dfeee8] p-6 space-y-4 shadow-[0_10px_24px_rgba(15,23,42,0.03)]">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Platform Implementation Architecture</h3>
          <p className="text-xs text-slate-500">All four architectural milestones are fully deployed and live</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-2">
          <div className="p-4 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] space-y-1.5 transition-all">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#00a26d]">Phase 1</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#dffdf0] text-[#00a26d] font-semibold">Live</span>
            </div>
            <div className="text-xs font-semibold text-slate-900">Schema & Authentication</div>
            <p className="text-[11px] text-slate-600">
              Isolated tables, rotating cookies, passkeys, rate limits & lockout defense.
            </p>
          </div>

          <Link
            href="/console/users"
            className="p-4 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] space-y-1.5 hover:border-[#00d09c] hover:shadow-sm transition-all group"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#00a26d]">Phase 2</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#dffdf0] text-[#00a26d] font-semibold group-hover:bg-[#00d09c] group-hover:text-white transition-colors">Live ↗</span>
            </div>
            <div className="text-xs font-semibold text-slate-900">User CRUD & Directory</div>
            <p className="text-[11px] text-slate-600">
              Key pagination, PII masking, account scoping, tenant user lifecycle operations.
            </p>
          </Link>

          <Link
            href="/console/roles"
            className="p-4 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] space-y-1.5 hover:border-[#00d09c] hover:shadow-sm transition-all group"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#00a26d]">Phase 3</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#dffdf0] text-[#00a26d] font-semibold group-hover:bg-[#00d09c] group-hover:text-white transition-colors">Live ↗</span>
            </div>
            <div className="text-xs font-semibold text-slate-900">Dynamic Roles & ABAC</div>
            <p className="text-[11px] text-slate-600">
              Strict hierarchy, self-elevation guards, operator management & permissions.
            </p>
          </Link>

          <Link
            href="/console/audit"
            className="p-4 rounded-xl bg-[#ebfff7] border border-[#b8f5dc] space-y-1.5 hover:border-[#00d09c] hover:shadow-sm transition-all group"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[#00a26d]">Phase 4</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#dffdf0] text-[#00a26d] font-semibold group-hover:bg-[#00d09c] group-hover:text-white transition-colors">Live ↗</span>
            </div>
            <div className="text-xs font-semibold text-slate-900">Audit & Compliance</div>
            <p className="text-[11px] text-slate-600">
              Tamper-evident hash chain, 2-person hard-delete anonymisation, audit logs.
            </p>
          </Link>
        </div>
      </div>

      {/* ── Modal: Register Passkey ── */}
      {showAddPasskeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/35 backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-sm rounded-2xl bg-white border border-[#dfeee8] p-6 space-y-4 shadow-[0_24px_70px_rgba(15,23,42,0.16)]">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-[#ebfff7] text-[#00a26d]">
                <Fingerprint className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Add Hardware Passkey</h3>
                <p className="text-xs text-slate-500">Touch ID, Face ID or USB security key</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Device Nickname
              </label>
              <input
                type="text"
                value={passkeyNickname}
                onChange={(e) => setPasskeyNickname(e.target.value)}
                placeholder="e.g. MacBook Pro, YubiKey 5"
                className="w-full px-3.5 py-2 rounded-xl bg-slate-50 border border-[#dfeee8] text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#00d09c]/30 text-xs"
              />
            </div>

            {actionError && (
              <div className="p-3 rounded-xl bg-[#fff1f2] border border-[#fecaca] text-[#d92d20] text-xs">
                {actionError}
              </div>
            )}

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddPasskeyModal(false)}
                className="flex-1 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-xs text-slate-700 font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRegisterPasskey}
                disabled={registeringPasskey}
                className="flex-1 py-2 rounded-xl bg-[#00d09c] hover:bg-[#00b98a] text-xs text-white font-medium flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {registeringPasskey ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Enrolling...</span>
                  </>
                ) : (
                  <span>Register</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
