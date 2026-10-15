/**
 * console/api.ts – Dedicated API client for the MyTally Platform Operator Console.
 *
 * Rules (Plan Section 1.2):
 *   • All console requests target relative path /console-api/...
 *   • Never names the API host directly (Next.js rewrites to backend /platform/...)
 *   • Operates with HttpOnly cookies, double-submit CSRF tokens
 *   • Never imports from or shares state with the customer app
 */

export interface OperatorProfile {
  admin_id: number
  email: string
  full_name: string
  status: string
  last_login_at: string | null
  permissions: string[]
  max_rank: number
  pages: string[]
  passkey_required: boolean
  csrf_token?: string
}

export interface LoginResult {
  passkey_required: boolean
  mfa_token?: string
  admin_id?: number
  email?: string
  csrf_token?: string
}

export interface PasskeyItem {
  credential_pk: number
  nickname: string
  rp_id: string
  created_at: string
  last_used_at: string | null
}

export interface SessionItem {
  session_id: number
  ip_address: string
  user_agent: string
  created_at: string
  last_seen_at: string
  is_current: boolean
}

// ── Customer User Management (Phase 2) ──

export interface ConsoleUserItem {
  user_id: number
  account_id: number | null
  company_id: number
  company_name?: string | null
  role_id: number
  role_name?: string | null
  username: string
  email: string
  phone?: string | null
  designation?: string | null
  status: 'active' | 'suspended' | 'locked' | 'deleted' | string
  is_active: boolean
  email_verified_at?: string | null
  created_at?: string | null
  last_login?: string | null
  deleted_at?: string | null
  purged_at?: string | null
  version: number
}

export interface ConsoleUserListResponse {
  items: ConsoleUserItem[]
  next_cursor?: string | null
  has_more: boolean
  approx_count?: number | null
}

export interface ConsoleUserDetail {
  user_id: number
  account_id: number | null
  account_name?: string | null
  company_id: number
  company_name?: string | null
  role_id: number
  role_name?: string | null
  username: string
  email: string
  phone?: string | null
  alternate_phone?: string | null
  employee_code?: string | null
  designation?: string | null
  status: string
  suspended_at?: string | null
  suspended_reason?: string | null
  must_change_password: boolean
  temp_password_expires?: string | null
  is_active: boolean
  email_verified_at?: string | null
  created_at?: string | null
  last_login?: string | null
  deleted_at?: string | null
  deleted_by_admin_id?: number | null
  purge_after?: string | null
  purged_at?: string | null
  active_sessions_count: number
  version: number
}

// ── Two-Person Purge & Anonymisation (Phase 5) ──
export interface PurgeRequestItem {
  purge_request_id: number
  target_user_id: number
  target_account_id: number | null
  target_email: string
  target_username: string
  requested_by_admin_id: number
  requester_email?: string | null
  requested_at: string
  reason: string
  status: 'pending' | 'approved' | 'rejected' | string
  approved_by_admin_id?: number | null
  approver_email?: string | null
  approved_at?: string | null
  rejected_by_admin_id?: number | null
  rejecter_email?: string | null
  rejected_at?: string | null
  rejection_reason?: string | null
  can_approve: boolean
}

// ── Time-Boxed Operator Impersonation (Phase 5) ──
export interface ImpersonationSessionItem {
  impersonation_id: number
  admin_id: number
  admin_email: string
  target_user_id: number
  target_account_id: number
  reason: string
  duration_minutes: number
  is_write: boolean
  started_at: string
  expires_at: string
  terminated_at?: string | null
  is_active: boolean
}

export interface ImpersonationStartResponse {
  impersonation_id: number
  token: string
  session_token: string
  target_user_id: number
  target_username: string
  target_email: string
  expires_at: string
  write_access: boolean
  redirect_url: string
}

// ── Statutory Data Retention (Phase 5) ──
export interface RetentionPolicyItem {
  policy_id: number
  data_category: string
  title: string
  retention_period_days: number
  legal_basis: string
  action_on_expiry: string
  description?: string | null
  updated_at?: string | null
}

export interface UserQueryParams {
  cursor?: string
  limit?: number
  sort?: 'created_at' | 'last_login' | 'username'
  order?: 'asc' | 'desc'
  q?: string
  account_id?: number
  status?: string
  role_id?: number
  verified?: boolean
  created_from?: string
  created_to?: string
  include_deleted?: boolean
  include_approx_count?: boolean
}

export interface CreateUserPayload {
  account_id: number
  company_id: number
  role_id: number
  email: string
  username: string
  phone?: string
  designation?: string
  employee_code?: string
  generate_temp_password?: boolean
  verified_by_us?: boolean
  reason?: string
}

export interface UpdateUserPayload {
  username?: string
  phone?: string
  designation?: string
  employee_code?: string
  role_id?: number
  version?: number
  reason?: string
}

export interface PasswordResetResult {
  mode: 'temporary' | 'link'
  temp_password?: string | null
  expires_at?: string | null
  reset_link?: string | null
}

export interface CreateUserResult {
  user: ConsoleUserDetail
  temp_password?: string | null
}

export interface UserMetaLookups {
  accounts: Array<{ account_id: number; name: string; status: string }>
  companies: Array<{ company_id: number; name: string; account_id: number | null }>
  roles: Array<{ role_id: number; name: string; account_id: number | null }>
}

// ── RBAC Roles & Dynamic Permissions (Phase 3) ──

export interface PermissionCatalogueItem {
  permission_id: number
  code: string
  resource: string
  action: string
  description: string
  is_sensitive: boolean
}

export interface ConsoleRoleItem {
  role_id: number
  code: string
  name: string
  description?: string | null
  rank: number
  is_system: boolean
  version: number
  created_at?: string | null
  member_count: number
  permissions: string[]
}

export interface CreateRolePayload {
  code: string
  name: string
  description?: string
  rank: number
  permission_codes: string[]
  reason?: string
}

export interface UpdateRolePayload {
  name?: string
  description?: string
  rank?: number
  version?: number
  reason?: string
}

export interface SetRolePermissionsPayload {
  permission_codes: string[]
  version?: number
  reason?: string
}

// ── Platform Operator Management (Phase 3) ──

export interface AdminAssignedRole {
  role_id: number
  code: string
  name: string
  rank: number
  scope_account_ids?: number[] | null
  expires_at?: string | null
}

export interface ConsoleAdminItem {
  admin_id: number
  email: string
  full_name: string
  status: 'invited' | 'active' | 'suspended' | 'disabled' | string
  permission_version: number
  max_rank: number
  roles: AdminAssignedRole[]
  allowed_ip_cidrs?: string[] | null
  last_login_at?: string | null
  last_login_ip?: string | null
  created_at?: string | null
  active_sessions_count: number
  passkeys_count: number
  version: number
}

export interface ConsoleAdminDetail extends ConsoleAdminItem {
  effective_permissions: string[]
}

export interface CreateAdminPayload {
  email: string
  full_name: string
  password: string
  role_ids: number[]
  allowed_ip_cidrs?: string[]
  status?: 'active' | 'invited'
  reason?: string
}

export interface UpdateAdminPayload {
  full_name?: string
  status?: 'active' | 'suspended' | 'disabled'
  allowed_ip_cidrs?: string[]
  unlock?: boolean
  version?: number
  reason?: string
}

export interface AssignAdminRolesPayload {
  roles: Array<{
    role_id: number
    scope_account_ids?: number[]
    expires_at?: string
  }>
  version?: number
  reason?: string
}

export function formatApiErrorDetail(detail: unknown, fallback: string = 'API request failed'): string {
  if (typeof detail === 'string') {
    return detail.trim() || fallback
  }
  if (Array.isArray(detail)) {
    const formatted = detail
      .map((item: any) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc)
            ? item.loc.filter((p: any) => p !== 'body').join('.')
            : ''
          const msg = item.msg || item.message || JSON.stringify(item)
          return loc ? `${loc}: ${msg}` : msg
        }
        return String(item)
      })
      .filter(Boolean)
      .join(', ')
    return formatted || fallback
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as Record<string, any>
    return obj.message || obj.msg || obj.detail || JSON.stringify(detail) || fallback
  }
  return detail ? String(detail) : fallback
}

export class ConsoleApiError extends Error {
  status: number
  detail: string
  isStepUpRequired: boolean

  constructor(status: number, detail: unknown, isStepUpRequired: boolean = false) {
    const formatted = formatApiErrorDetail(detail, `API request failed with HTTP ${status}`)
    super(formatted)
    this.name = 'ConsoleApiError'
    this.status = status
    this.detail = formatted
    this.isStepUpRequired = isStepUpRequired
  }
}

let inMemoryCsrfToken: string | null = null

export function setConsoleCsrfToken(token: string | null | undefined): void {
  if (token) inMemoryCsrfToken = token
  else inMemoryCsrfToken = null
}

function getCsrfTokenFromCookie(): string | null {
  if (inMemoryCsrfToken) return inMemoryCsrfToken
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(/(?:^|;\s*)pa_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export async function consoleFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const url = `/console-api${cleanPath}`

  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')

  // Inject CSRF token on state-changing requests
  if (WRITE_METHODS.has(method)) {
    const csrf = getCsrfTokenFromCookie()
    if (csrf && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrf)
    }
    if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
      headers.set('Content-Type', 'application/json')
    }
  }

  const response = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: 'same-origin',
  })

  // Check for step-up required header or detail
  const stepUpHeader = response.headers.get('X-Step-Up')?.toLowerCase()
  const hasStepUpHeader = stepUpHeader === 'required' || stepUpHeader === 'true'

  if (!response.ok) {
    let errorDetail: unknown = response.statusText
    try {
      const errJson = await response.json()
      if (errJson && typeof errJson === 'object') {
        if ('detail' in errJson) {
          errorDetail = errJson.detail
        } else if ('message' in errJson || 'error' in errJson) {
          errorDetail = (errJson as any).message || (errJson as any).error
        }
      }
    } catch {
      // Non-JSON response
    }

    const detailString = formatApiErrorDetail(errorDetail, response.statusText)
    const isStepUp = hasStepUpHeader || detailString.toLowerCase().includes('step-up')

    // Auto-redirect to operator login if unauthenticated / session expired
    // CRITICAL: Do NOT redirect if this is a step-up challenge!
    if (
      response.status === 401 &&
      !isStepUp &&
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/console/login') &&
      !cleanPath.startsWith('/auth/login') &&
      !cleanPath.startsWith('/auth/refresh')
    ) {
      window.location.href = '/console/login'
    }

    throw new ConsoleApiError(response.status, detailString, isStepUp)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T
  }

  return response.json()
}

export const consoleApi = {
  // ── Auth ──
  async login(email: string, password: string): Promise<LoginResult> {
    const res = await consoleFetch<LoginResult>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    if (res.csrf_token) setConsoleCsrfToken(res.csrf_token)
    return res
  },

  async passkeyLoginOptions(mfaToken: string): Promise<{ options: Record<string, unknown>; challenge_token: string }> {
    return consoleFetch('/auth/passkey/login/options', {
      method: 'POST',
      body: JSON.stringify({ mfa_token: mfaToken }),
    })
  },

  async passkeyLoginVerify(
    mfaToken: string,
    assertionResponse: Record<string, unknown>,
    challengeToken: string
  ): Promise<{ status: string; admin_id: number; email: string }> {
    return consoleFetch('/auth/passkey/login/verify', {
      method: 'POST',
      body: JSON.stringify({
        mfa_token: mfaToken,
        assertion_response: assertionResponse,
        challenge_token: challengeToken,
      }),
    })
  },

  async passkeyRegisterOptions(): Promise<{ options: Record<string, unknown>; challenge_token: string }> {
    return consoleFetch('/auth/passkey/register/options', {
      method: 'POST',
    })
  },

  async passkeyRegisterVerify(
    attestationResponse: Record<string, unknown>,
    challengeToken: string,
    nickname: string
  ): Promise<{ status: string; credential_id: string; nickname: string }> {
    return consoleFetch('/auth/passkey/register/verify', {
      method: 'POST',
      body: JSON.stringify({
        attestation_response: attestationResponse,
        challenge_token: challengeToken,
        nickname,
      }),
    })
  },

  async getPasskeys(): Promise<PasskeyItem[]> {
    return consoleFetch<PasskeyItem[]>('/auth/passkey/credentials')
  },

  async deletePasskey(credentialPk: number): Promise<{ status: string }> {
    return consoleFetch(`/auth/passkey/credentials/${credentialPk}`, {
      method: 'DELETE',
    })
  },

  async stepUp(password: string): Promise<{ succeeded: boolean; mfa_at: string }> {
    return consoleFetch('/auth/step-up', {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
  },

  async refresh(): Promise<{ status: string }> {
    return consoleFetch('/auth/refresh', {
      method: 'POST',
    })
  },

  async logout(): Promise<{ status: string }> {
    setConsoleCsrfToken(null)
    return consoleFetch('/auth/logout', {
      method: 'POST',
    })
  },

  async logoutAll(): Promise<{ status: string }> {
    setConsoleCsrfToken(null)
    return consoleFetch('/auth/logout-all', {
      method: 'POST',
    })
  },

  async me(): Promise<OperatorProfile> {
    const res = await consoleFetch<OperatorProfile>('/auth/me')
    if (res.csrf_token) setConsoleCsrfToken(res.csrf_token)
    return res
  },

  async getSessions(): Promise<SessionItem[]> {
    return consoleFetch<SessionItem[]>('/auth/sessions')
  },

  async revokeSession(sessionId: number): Promise<{ status: string }> {
    return consoleFetch(`/auth/sessions/${sessionId}`, {
      method: 'DELETE',
    })
  },

  // ── Customer User Management (Phase 2) ──

  async listUsers(params?: UserQueryParams): Promise<ConsoleUserListResponse> {
    const qp = new URLSearchParams()
    if (params) {
      if (params.cursor) qp.set('cursor', params.cursor)
      if (params.limit) qp.set('limit', String(params.limit))
      if (params.sort) qp.set('sort', params.sort)
      if (params.order) qp.set('order', params.order)
      if (params.q) qp.set('q', params.q)
      if (params.account_id !== undefined && params.account_id !== null) qp.set('account_id', String(params.account_id))
      if (params.status) qp.set('status', params.status)
      if (params.role_id !== undefined && params.role_id !== null) qp.set('role_id', String(params.role_id))
      if (params.verified !== undefined) qp.set('verified', String(params.verified))
      if (params.include_deleted) qp.set('include_deleted', 'true')
      if (params.include_approx_count) qp.set('include_approx_count', 'true')
    }
    const queryStr = qp.toString()
    return consoleFetch<ConsoleUserListResponse>(`/users${queryStr ? `?${queryStr}` : ''}`)
  },

  async getUser(userId: number): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}`)
  },

  async getUserLookups(accountId?: number): Promise<UserMetaLookups> {
    const qp = accountId ? `?account_id=${accountId}` : ''
    return consoleFetch<UserMetaLookups>(`/users/meta/lookups${qp}`)
  },

  async createUser(payload: CreateUserPayload): Promise<CreateUserResult> {
    return consoleFetch<CreateUserResult>('/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async updateUser(userId: number, payload: UpdateUserPayload, version: number): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}`, {
      method: 'PATCH',
      headers: {
        'If-Match': `W/"${version}"`,
      },
      body: JSON.stringify({ ...payload, version }),
    })
  },

  async suspendUser(userId: number, reason: string): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}/suspend`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  async reinstateUser(userId: number, reason?: string): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}/reinstate`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason || '' }),
    })
  },

  async unlockUser(userId: number): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}/unlock`, {
      method: 'POST',
    })
  },

  async resetPassword(userId: number, mode: 'temporary' | 'link', reason?: string): Promise<PasswordResetResult> {
    return consoleFetch<PasswordResetResult>(`/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ mode, reason }),
    })
  },

  async revokeUserSessions(userId: number): Promise<{ revoked_sessions_count: number }> {
    return consoleFetch<{ revoked_sessions_count: number }>(`/users/${userId}/sessions/revoke`, {
      method: 'POST',
    })
  },

  async softDeleteUser(userId: number): Promise<{ status: string; purge_after: string }> {
    return consoleFetch<{ status: string; purge_after: string }>(`/users/${userId}`, {
      method: 'DELETE',
    })
  },

  async restoreUser(userId: number): Promise<ConsoleUserDetail> {
    return consoleFetch<ConsoleUserDetail>(`/users/${userId}/restore`, {
      method: 'POST',
    })
  },

  // ── Two-Person Purge Workflow (Phase 5) ──
  async createPurgeRequest(userId: number, reason: string): Promise<{ status: string; purge_request_id: number; message: string }> {
    return consoleFetch<{ status: string; purge_request_id: number; message: string }>(`/users/${userId}/purge-requests`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  async listPurgeRequests(status?: string): Promise<PurgeRequestItem[]> {
    return consoleFetch<PurgeRequestItem[]>(`/users/purge-requests${status ? `?status=${encodeURIComponent(status)}` : ''}`)
  },

  async approvePurgeRequest(requestId: number): Promise<{ status: string; message: string; target_user_id: number }> {
    return consoleFetch<{ status: string; message: string; target_user_id: number }>(`/users/purge-requests/${requestId}/approve`, {
      method: 'POST',
    })
  },

  async rejectPurgeRequest(requestId: number, reason: string): Promise<{ status: string; purge_request_id: number }> {
    return consoleFetch<{ status: string; purge_request_id: number }>(`/users/purge-requests/${requestId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  // ── Time-Boxed Operator Impersonation (Phase 5) ──
  async impersonateUser(
    userId: number,
    payload: { reason: string; minutes: number; write_access: boolean }
  ): Promise<ImpersonationStartResponse> {
    return consoleFetch<ImpersonationStartResponse>(`/users/${userId}/impersonate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async terminateImpersonation(impersonationId: number): Promise<{ status: string; impersonation_id: number }> {
    return consoleFetch<{ status: string; impersonation_id: number }>(`/users/impersonations/${impersonationId}`, {
      method: 'DELETE',
    })
  },

  async listActiveImpersonations(): Promise<ImpersonationSessionItem[]> {
    return consoleFetch<ImpersonationSessionItem[]>('/users/impersonations/active')
  },

  // ── Statutory Data Retention (Phase 5) ──
  async getRetentionPolicies(): Promise<RetentionPolicyItem[]> {
    return consoleFetch<RetentionPolicyItem[]>('/users/retention-policies')
  },

  // ── Roles & Dynamic Permissions (Phase 3) ──
  async listPermissions(): Promise<PermissionCatalogueItem[]> {
    return consoleFetch<PermissionCatalogueItem[]>('/permissions')
  },

  async listRoles(): Promise<ConsoleRoleItem[]> {
    return consoleFetch<ConsoleRoleItem[]>('/roles')
  },

  async getRole(roleId: number): Promise<ConsoleRoleItem> {
    return consoleFetch<ConsoleRoleItem>(`/roles/${roleId}`)
  },

  async createRole(payload: CreateRolePayload): Promise<ConsoleRoleItem> {
    return consoleFetch<ConsoleRoleItem>('/roles', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async updateRole(roleId: number, payload: UpdateRolePayload, version: number): Promise<ConsoleRoleItem> {
    return consoleFetch<ConsoleRoleItem>(`/roles/${roleId}`, {
      method: 'PATCH',
      headers: {
        'If-Match': `"${version}"`,
      },
      body: JSON.stringify({ ...payload, version }),
    })
  },

  async deleteRole(roleId: number): Promise<{ ok: boolean; status: string; role_id: number; code: string }> {
    return consoleFetch<{ ok: boolean; status: string; role_id: number; code: string }>(`/roles/${roleId}`, {
      method: 'DELETE',
    })
  },

  async setRolePermissions(roleId: number, permissionCodes: string[], version: number, reason?: string): Promise<ConsoleRoleItem> {
    return consoleFetch<ConsoleRoleItem>(`/roles/${roleId}/permissions`, {
      method: 'PUT',
      headers: {
        'If-Match': `"${version}"`,
      },
      body: JSON.stringify({ permission_codes: permissionCodes, version, reason }),
    })
  },

  // ── Platform Operators / Admins (Phase 3) ──
  async listAdmins(params?: { q?: string; status?: string; role_id?: number }): Promise<ConsoleAdminItem[]> {
    const searchParams = new URLSearchParams()
    if (params?.q) searchParams.set('q', params.q)
    if (params?.status) searchParams.set('status', params.status)
    if (params?.role_id) searchParams.set('role_id', String(params.role_id))
    const qs = searchParams.toString()
    return consoleFetch<ConsoleAdminItem[]>(`/admins${qs ? `?${qs}` : ''}`)
  },

  async getAdmin(adminId: number): Promise<ConsoleAdminDetail> {
    return consoleFetch<ConsoleAdminDetail>(`/admins/${adminId}`)
  },

  async createAdmin(payload: CreateAdminPayload): Promise<ConsoleAdminDetail> {
    return consoleFetch<ConsoleAdminDetail>('/admins', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async updateAdmin(adminId: number, payload: UpdateAdminPayload, version: number): Promise<ConsoleAdminDetail> {
    return consoleFetch<ConsoleAdminDetail>(`/admins/${adminId}`, {
      method: 'PATCH',
      headers: {
        'If-Match': `"${version}"`,
      },
      body: JSON.stringify({ ...payload, version }),
    })
  },

  async assignAdminRoles(adminId: number, payload: AssignAdminRolesPayload, version: number): Promise<ConsoleAdminDetail> {
    return consoleFetch<ConsoleAdminDetail>(`/admins/${adminId}/roles`, {
      method: 'PUT',
      headers: {
        'If-Match': `"${version}"`,
      },
      body: JSON.stringify({ ...payload, version }),
    })
  },

  async resetAdminPasskeys(adminId: number): Promise<{ ok: boolean; status: string; message: string }> {
    return consoleFetch<{ ok: boolean; status: string; message: string }>(`/admins/${adminId}/reset-passkeys`, {
      method: 'POST',
    })
  },

  async revokeAdminSessions(adminId: number): Promise<{ ok: boolean; status: string; revoked_count: number }> {
    return consoleFetch<{ ok: boolean; status: string; revoked_count: number }>(`/admins/${adminId}/sessions`, {
      method: 'DELETE',
    })
  },

  async deleteAdmin(adminId: number): Promise<{ ok: boolean; status: string; message: string }> {
    return consoleFetch<{ ok: boolean; status: string; message: string }>(`/admins/${adminId}`, {
      method: 'DELETE',
    })
  },

  // ── Audit Trail (Phase 4) ──
  async listAuditLogs(params: {
    cursor?: string
    limit?: number
    admin_id?: number
    action_type?: string
    target_user_id?: number
    target_account_id?: number
    outcome?: string
    from?: string
    to?: string
    search?: string
  } = {}): Promise<AuditLogsPage> {
    const sp = new URLSearchParams()
    if (params.cursor) sp.set('cursor', params.cursor)
    if (params.limit) sp.set('limit', String(params.limit))
    if (params.admin_id) sp.set('admin_id', String(params.admin_id))
    if (params.action_type) sp.set('action_type', params.action_type)
    if (params.target_user_id) sp.set('target_user_id', String(params.target_user_id))
    if (params.target_account_id) sp.set('target_account_id', String(params.target_account_id))
    if (params.outcome) sp.set('outcome', params.outcome)
    if (params.from) sp.set('from', params.from)
    if (params.to) sp.set('to', params.to)
    if (params.search) sp.set('search', params.search)

    const query = sp.toString() ? `?${sp.toString()}` : ''
    return consoleFetch<AuditLogsPage>(`/audit-logs${query}`)
  },

  async getAuditLog(id: number): Promise<AuditLogDetail> {
    return consoleFetch<AuditLogDetail>(`/audit-logs/${id}`)
  },

  async getAuditIntegrity(fromId?: number): Promise<AuditIntegrityResponse> {
    const query = fromId ? `?from_id=${fromId}` : ''
    return consoleFetch<AuditIntegrityResponse>(`/audit-logs/integrity${query}`)
  },

  async exportAuditLogs(payload: AuditExportPayload): Promise<{ blob?: Blob; data?: unknown; filename?: string }> {
    const csrf = getCsrfTokenFromCookie()
    const res = await fetch('/console-api/audit-logs/exports', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      if (res.status === 401 && res.headers.get('x-step-up') === 'required') {
        const err = new Error('Step-up authentication required.')
        ;(err as unknown as { stepUpRequired: boolean }).stepUpRequired = true
        throw err
      }
      const data = await res.json().catch(() => ({}))
      const msg = formatApiErrorDetail(data?.detail || data?.message || data?.error, `Export failed with HTTP ${res.status}`)
      throw new Error(msg)
    }

    if (payload.format === 'csv') {
      const blob = await res.blob()
      return { blob, filename: `platform-audit-${Date.now()}.csv` }
    } else {
      const data = await res.json()
      return { data }
    }
  },
}

export const consoleAuthApi = {
  login: consoleApi.login,
  logout: consoleApi.logout,
  stepUp: consoleApi.stepUp,
  getMe: consoleApi.me,
}

export const consoleUsersApi = {
  list: consoleApi.listUsers,
  get: consoleApi.getUser,
  getLookups: consoleApi.getUserLookups,
  create: consoleApi.createUser,
  update: consoleApi.updateUser,
  suspend: consoleApi.suspendUser,
  reinstate: consoleApi.reinstateUser,
  unlock: consoleApi.unlockUser,
  resetPassword: consoleApi.resetPassword,
  revokeSessions: consoleApi.revokeUserSessions,
  delete: consoleApi.softDeleteUser,
  restore: consoleApi.restoreUser,
  createPurgeRequest: consoleApi.createPurgeRequest,
  listPurgeRequests: consoleApi.listPurgeRequests,
  approvePurgeRequest: consoleApi.approvePurgeRequest,
  rejectPurgeRequest: consoleApi.rejectPurgeRequest,
  impersonate: consoleApi.impersonateUser,
  terminateImpersonation: consoleApi.terminateImpersonation,
  listActiveImpersonations: consoleApi.listActiveImpersonations,
  getRetentionPolicies: consoleApi.getRetentionPolicies,
}

export const consoleRolesApi = {
  getPermissions: consoleApi.listPermissions,
  list: consoleApi.listRoles,
  get: consoleApi.getRole,
  create: consoleApi.createRole,
  update: consoleApi.updateRole,
  delete: consoleApi.deleteRole,
  setPermissions: consoleApi.setRolePermissions,
}

export const consoleAdminsApi = {
  list: consoleApi.listAdmins,
  get: consoleApi.getAdmin,
  create: consoleApi.createAdmin,
  update: consoleApi.updateAdmin,
  delete: consoleApi.deleteAdmin,
  assignRoles: consoleApi.assignAdminRoles,
  resetPasskeys: consoleApi.resetAdminPasskeys,
  revokeSessions: consoleApi.revokeAdminSessions,
}

export const consoleAuditApi = {
  list: consoleApi.listAuditLogs,
  get: consoleApi.getAuditLog,
  getIntegrity: consoleApi.getAuditIntegrity,
  export: consoleApi.exportAuditLogs,
}

// ── Audit Types Export ──
export interface AuditLogItem {
  audit_id: number
  occurred_at: string
  admin_id: number | null
  admin_email: string
  session_id: number | null
  action_type: string
  target_type: string | null
  target_id: number | null
  target_account_id: number | null
  target_user_id: number | null
  reason: string | null
  outcome: 'success' | 'denied' | 'failed' | string
  request_id: string
  ip_address: string | null
  user_agent: string | null
  prev_hash: string | null
  row_hash: string
  has_diff: boolean
}

export interface AuditLogDetail {
  audit_id: number
  occurred_at: string
  admin_id: number | null
  admin_email: string
  session_id: number | null
  action_type: string
  target_type: string | null
  target_id: number | null
  target_account_id: number | null
  target_user_id: number | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  reason: string | null
  outcome: string
  request_id: string
  ip_address: string | null
  user_agent: string | null
  prev_hash: string | null
  row_hash: string
}

export interface AuditLogsPage {
  items: AuditLogItem[]
  next_cursor: string | null
  has_more: boolean
  total_count: number
}

export interface AuditIntegrityResponse {
  chain_intact: boolean
  total_verified: number
  broken_at_id: number | null
  error_detail: string | null
  last_verified_at: string
}

export interface AuditExportPayload {
  format: 'csv' | 'json'
  admin_id?: number
  action_type?: string
  target_user_id?: number
  target_account_id?: number
  outcome?: string
  from?: string
  to?: string
  limit?: number
}

// ── Billing Types Export ──
export interface PlatformBillingMetrics {
  total_accounts: number
  active_subscriptions: number
  locked_accounts: number
  total_revenue_rupees: number
  monthly_recurring_revenue: number
  annual_recurring_revenue: number
  plans_breakdown?: Record<string, number>
}

export interface PlatformAccountBillingItem {
  account_id: number
  company_name?: string
  account_name?: string
  admin_email?: string
  current_plan?: string
  plan_code?: string | null
  plan_name?: string | null
  status?: string
  account_status?: string
  subscription_status?: string
  current_period_end?: string | null
  valid_until?: string | null
  is_locked?: boolean
  max_users?: number | null
  max_companies?: number | null
  active_users?: number
  active_companies?: number
  extra_users?: number
  extra_companies?: number
}

export interface AssignPlanPayload {
  plan_code: string
  duration_years: number
  extra_users?: number
  extra_companies?: number
}

export interface CustomPlanPayload {
  name: string
  tagline?: string
  max_users?: number | null
  max_companies?: number | null
  max_devices?: number | null
  feature_keys: string[]
  yearly_price_paise: number
}

export interface OfflinePaymentPayload {
  account_id: number
  plan_code: string
  duration_years: number
  extra_users?: number
  extra_companies?: number
  reference: string
  method: string
  buyer_state_code?: string
}

export interface PlatformLeadItem {
  lead_id: number
  account_id: number | null
  company_name: string
  email: string
  phone: string | null
  requested_plan: string | null
  status: string
  created_at: string
  notes?: string | null
}

export interface PlatformWebhookEventItem {
  event_id: number
  gateway: string
  event_type: string
  status: string
  error_detail?: string | null
  created_at: string
}

export const consoleBillingApi = {
  async getMetrics(): Promise<PlatformBillingMetrics> {
    return consoleFetch<PlatformBillingMetrics>('/billing/metrics')
  },

  async getAccounts(): Promise<PlatformAccountBillingItem[]> {
    const res = await consoleFetch<{ accounts: PlatformAccountBillingItem[] }>('/billing/accounts')
    return res.accounts || []
  },

  async assignPlan(accountId: number, payload: AssignPlanPayload): Promise<{ success: boolean; message: string; current_period_end: string }> {
    return consoleFetch(`/billing/accounts/${accountId}/assign-plan`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async createCustomPlan(accountId: number, payload: CustomPlanPayload): Promise<{ success: boolean; plan_id: number; plan_code: string; amount_rupees: number }> {
    return consoleFetch(`/billing/accounts/${accountId}/custom-plan`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async lockAccount(accountId: number, reason?: string): Promise<{ success: boolean; message: string }> {
    return consoleFetch(`/billing/accounts/${accountId}/lock`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  async unlockAccount(accountId: number, reason?: string): Promise<{ success: boolean; message: string }> {
    return consoleFetch(`/billing/accounts/${accountId}/unlock`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  },

  async recordOfflinePayment(payload: OfflinePaymentPayload): Promise<{ success: boolean; message: string }> {
    return consoleFetch('/billing/offline-payment', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async getLeads(): Promise<PlatformLeadItem[]> {
    const res = await consoleFetch<{ leads: PlatformLeadItem[] } | PlatformLeadItem[]>('/billing/leads')
    return Array.isArray(res) ? res : (res.leads || [])
  },

  async getWebhooks(): Promise<PlatformWebhookEventItem[]> {
    const res = await consoleFetch<{ events: PlatformWebhookEventItem[] } | PlatformWebhookEventItem[]>('/billing/webhooks')
    return Array.isArray(res) ? res : (res.events || [])
  },
}

