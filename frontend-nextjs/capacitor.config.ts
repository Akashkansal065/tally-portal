import type { CapacitorConfig } from '@capacitor/cli';

// Support setting server URL via environment variable (e.g. CAPACITOR_SERVER_URL or NEXT_PUBLIC_APP_URL)
const serverUrl =
  process.env.CAPACITOR_SERVER_URL ||
  process.env.NEXT_PUBLIC_APP_URL ||
  'https://tally-portal-one.vercel.app';

// WebView relaxations are only for pointing the shell at a plain-HTTP LAN dev server.
// Production (https server URL) gets none of them. Force them on with CAPACITOR_DEV=true.
const isDevShell = serverUrl.startsWith('http://') || process.env.CAPACITOR_DEV === 'true';
const serverHost = new URL(serverUrl).hostname;

const config: CapacitorConfig = {
  appId: 'com.snehdistributors.mytally',
  appName: 'SnehDist.',
  webDir: 'public',
  server: {
    ...(serverUrl ? { url: serverUrl } : {}),
    cleartext: isDevShell,
    androidScheme: 'https',
    // Pages on these hosts get the native bridge (camera, GPS, tracking token), so list exact hosts only.
    // Never '*.vercel.app': anyone can deploy there.
    allowNavigation: [...new Set(
      isDevShell
        ? ['tally-portal-one.vercel.app', serverHost, 'localhost', '127.0.0.1']
        : ['tally-portal-one.vercel.app', serverHost]
    )],
  },
  android: {
    allowMixedContent: isDevShell,
    captureInput: true,
    // webContentsDebuggingEnabled is intentionally unset: Capacitor enables it for debug builds only
    backgroundColor: '#0f172a',
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: '#0f172a',
      showSpinner: true,
      spinnerColor: '#10b981',
    },
    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0f172a',
    },
  },
};

export default config;
