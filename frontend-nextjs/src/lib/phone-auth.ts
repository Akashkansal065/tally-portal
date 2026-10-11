import { API_BASE } from '@/lib/utils'

/**
 * Sign-in with a mobile number. Firebase Authentication sends the OTP and confirms it in the browser; what
 * comes back is an ID token, which the server checks and exchanges for a MyTally session (/auth/phone/login).
 * Firebase is only the OTP: nobody stays signed in to it, and it is loaded only when someone asks for a code.
 *
 * Offered when the Firebase web app is configured here (NEXT_PUBLIC_FIREBASE_*) and the server has
 * PHONE_SIGNIN_ENABLED on.
 */

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
    || (process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ? `${process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID}.firebaseapp.com` : ''),
}

const configured = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId && firebaseConfig.appId)

/** Whether to show mobile number sign-in: set up in this build and switched on at the server. */
export async function phoneSignInOffered(): Promise<boolean> {
  if (!configured) return false
  try {
    const res = await fetch(`${API_BASE}/auth/phone/status`, { cache: 'no-store' })
    return res.ok && (await res.json()).enabled === true
  } catch {
    return false
  }
}

type Auth = import('firebase/auth').Auth
type RecaptchaVerifier = import('firebase/auth').RecaptchaVerifier
type ConfirmationResult = import('firebase/auth').ConfirmationResult

let authPromise: Promise<Auth> | null = null
let verifier: RecaptchaVerifier | null = null
let confirmation: ConfirmationResult | null = null

function firebaseAuth(): Promise<Auth> {
  if (!authPromise) {
    authPromise = (async () => {
      const [{ initializeApp, getApps }, { getAuth, setPersistence, inMemoryPersistence }] =
        await Promise.all([import('firebase/app'), import('firebase/auth')])
      const auth = getAuth(getApps()[0] ?? initializeApp(firebaseConfig))
      // The Firebase sign-in is thrown away once the server has answered, so it is never written to this device
      await setPersistence(auth, inMemoryPersistence)
      auth.useDeviceLanguage()
      return auth
    })().catch((err) => { authPromise = null; throw err })
  }
  return authPromise
}

function clearVerifier() {
  try { verifier?.clear() } catch { /* already gone with its element */ }
  verifier = null
}

/** What to tell the person when Firebase refuses to send or confirm a code. */
function otpError(err: unknown): Error {
  const code = (err as { code?: string })?.code || ''
  const messages: Record<string, string> = {
    'auth/invalid-phone-number': 'That mobile number does not look right. Check it and try again.',
    'auth/missing-phone-number': 'Enter your mobile number.',
    'auth/too-many-requests': 'Too many codes were asked for from this device. Wait a while and try again.',
    'auth/quota-exceeded': 'No more codes can be sent right now. Try again later, or sign in with email and password.',
    'auth/captcha-check-failed': 'The security check did not pass. Reload the page and try again.',
    'auth/invalid-app-credential': 'The security check did not pass. Reload the page and try again.',
    'auth/invalid-verification-code': 'That code is not right. Check the SMS and try again.',
    'auth/missing-verification-code': 'Enter the code from the SMS.',
    'auth/code-expired': 'That code has expired. Ask for a new one.',
    'auth/network-request-failed': 'No connection. Check your internet and try again.',
    'auth/operation-not-allowed': 'Sign-in with a mobile number is not switched on for this app yet.',
    'auth/billing-not-enabled': 'SMS codes are not switched on for this app yet. Sign in with email and password.',
    'auth/unauthorized-domain': 'This website is not allowed to send codes yet. Sign in with email and password.',
  }
  // Firebase uses the same code when the Phone provider is on but SMS to this country is not allowed
  // (Authentication > Settings > SMS region policy); only its message tells the two apart
  if (code === 'auth/operation-not-allowed' && /region/i.test((err as { message?: string })?.message || '')) {
    return new Error('SMS codes cannot be sent to numbers from this country yet.')
  }
  if (!messages[code]) console.error('[phone-auth]', err)
  return new Error(messages[code] || 'The code could not be sent. Try again, or sign in with email and password.')
}

/**
 * Send an OTP to a number in international form (+919900000001). `anchor` is an empty element on the page
 * that the invisible security check attaches to.
 */
export async function sendOtp(phone: string, anchor: HTMLElement): Promise<void> {
  confirmation = null
  try {
    const auth = await firebaseAuth()
    const { RecaptchaVerifier, signInWithPhoneNumber } = await import('firebase/auth')
    // A security check is good for one code: a fresh one each time, in a fresh element
    clearVerifier()
    const holder = document.createElement('div')
    anchor.replaceChildren(holder)
    verifier = new RecaptchaVerifier(auth, holder, { size: 'invisible' })
    confirmation = await signInWithPhoneNumber(auth, phone, verifier)
  } catch (err) {
    clearVerifier()
    throw otpError(err)
  }
}

/** Confirm the OTP. Returns the Firebase ID token to send to /auth/phone/login or /auth/phone/register. */
export async function confirmOtp(code: string): Promise<string> {
  if (!confirmation) throw new Error('Ask for a new code.')
  try {
    const { user } = await confirmation.confirm(code.trim())
    return await user.getIdToken()
  } catch (err) {
    throw otpError(err)
  }
}

/** Drop the Firebase sign-in and the pending code: called once the server has answered, or on going back. */
export async function forgetOtp(): Promise<void> {
  confirmation = null
  clearVerifier()
  if (!authPromise) return
  try {
    const auth = await authPromise
    const { signOut } = await import('firebase/auth')
    await signOut(auth)
  } catch { /* nothing was signed in */ }
}
