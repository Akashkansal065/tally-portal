import type { CapacitorConfig } from '@capacitor/cli';

// Support setting server URL via environment variable (e.g. CAPACITOR_SERVER_URL or NEXT_PUBLIC_APP_URL)
const serverUrl =
  process.env.CAPACITOR_SERVER_URL ||
  process.env.NEXT_PUBLIC_APP_URL ||
  'https://tally-portal-one.vercel.app';

const config: CapacitorConfig = {
  appId: 'com.snehdistributors.mytally',
  appName: 'MyTally',
  webDir: 'public',
  server: {
    ...(serverUrl ? { url: serverUrl } : {}),
    cleartext: true,
    androidScheme: 'https',
    allowNavigation: ['*'],
  },
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: true,
    backgroundColor: '#0f172a',
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: '#0f172a',
      showSpinner: true,
      spinnerColor: '#10b981',
    },
  },
};

export default config;
