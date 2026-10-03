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
    allowNavigation: [
      'tally-portal-one.vercel.app',
      '*.vercel.app',
      'localhost',
      '127.0.0.1',
    ],
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
