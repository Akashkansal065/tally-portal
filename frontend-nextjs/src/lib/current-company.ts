/**
 * The company this device is working in, for places outside React's reach: a confirm prompt, a share sheet.
 * AuthContext keeps it up to date. Someone with one company is never shown its name: there is nothing to mix up.
 */
let name = ''
let companies = 0
let id: number | null = null

export function setCurrentCompany(companyName: string, companyCount: number, companyId: number | null = null) {
  name = companyName
  companies = companyCount
  id = companyId
}

/** The query parameter a link carries to say which company it is for. */
export const COMPANY_PARAM = 'company'
const NOTICE_KEY = 'mytally_company_notice'

/**
 * An in-app path that also says which company it belongs to, for a link that will be opened later or by someone
 * else: /vouchers/12 becomes /vouchers/12?company=3. Opened in another company, the app switches first.
 */
export function linkInCompany(path: string, companyId: number | null = id): string {
  if (!companyId) return path
  const [base, hash = ''] = path.split('#')
  const joined = `${base}${base.includes('?') ? '&' : '?'}${COMPANY_PARAM}=${companyId}`
  return hash ? `${joined}#${hash}` : joined
}

/** Remember, across the reload a switch causes, that the next screen should say which company it is now in. */
export function noteCompanySwitch(companyName: string, forALink: boolean) {
  try { sessionStorage.setItem(NOTICE_KEY, JSON.stringify({ name: companyName, forALink })) } catch { /* no notice, the header still says */ }
}

/** The notice left by noteCompanySwitch, once. */
export function takeCompanySwitchNotice(): { name: string; forALink: boolean } | null {
  try {
    const raw = sessionStorage.getItem(NOTICE_KEY)
    if (!raw) return null
    sessionStorage.removeItem(NOTICE_KEY)
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/** The company's name when the person can open more than one, else ''. */
export function companyToName(): string {
  return companies > 1 ? name : ''
}

/** window.confirm that says which company the action is in, so a delete is never made in the wrong one. */
export function confirmInCompany(message: string): boolean {
  const company = companyToName()
  return window.confirm(company ? `${message}\n\nCompany: ${company}` : message)
}
