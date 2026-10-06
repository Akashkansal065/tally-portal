To find the exact reason the app is crashing on your real Android device, follow these steps:

---

### Step 1: Connect Your Phone & Enable USB Debugging

1. Connect your Android phone to your Mac via a USB cable.
2. On your phone:
   - Go to **Settings** > **About Phone**.
   - Tap **Build Number** 7 times until it says *"You are now a developer"*.
   - Go to **Settings** > **System** > **Developer Options** and turn **ON**:
     - **USB Debugging**
     - *(Optional on Xiaomi/Oppo/Vivo)* **Install via USB** and **USB debugging (Security settings)**.
3. When prompted on your phone screen (*"Allow USB debugging?"*), check **Always allow** and tap **Allow**.
4. In your Mac terminal, verify the connection:
   ```bash
   adb devices
   ```
   *(You should see your device serial number listed as `device`).*

---

### Step 2: Capture the Crash Log (Instant Stack Trace)

Run this one-liner in your Mac terminal:

```bash
adb logcat -c && adb logcat | grep -E "AndroidRuntime|FATAL EXCEPTION|com.snehdistributors.mytally|Capacitor"
```

1. Keep this command running in your terminal.
2. Open the app on your phone.
3. As soon as the app crashes, the terminal will print the exact **FATAL EXCEPTION** and stack trace with the line of code that triggered it!

> **Alternative (capture all errors to a file):**
> ```bash
> adb logcat *:E > crash_log.txt
> ```
> *(Open the app on phone, let it crash, press `Ctrl+C` in terminal, then inspect `crash_log.txt` or paste the error here).*

---

### Step 3: Debug WebView / JavaScript Crashes (White Screen)

If the app doesn't immediately close but gets stuck on a **white screen** or **spins indefinitely**, it's usually a web/JavaScript runtime exception:

1. Build & install the **Debug APK** (Capacitor enables remote Chrome DevTools by default in debug builds):
   ```bash
   cd frontend-nextjs
   npm run build:apk
   adb install -r android/app/build/outputs/apk/debug/app-debug.apk
   ```
2. Open **Google Chrome** on your Mac and navigate to:
   ```text
   chrome://inspect/#devices
   ```
3. You will see your phone and **`SnehDist. (com.snehdistributors.mytally)`**.
4. Click **inspect** to open Chrome DevTools:
   - Switch to the **Console** tab to see unhandled JavaScript errors, React crashes, or broken imports.
   - Switch to the **Network** tab to see any failing API calls (CORS, SSL, 404, or 500 errors).

---

### Top 3 Common Causes in This Project

1. **Conflict with previous Debug installation:**
   If you had the Debug APK installed previously and then installed the Release APK, Android will encounter a keystore/signature conflict.
   - **Fix:** Long-press and **uninstall the app completely** from your phone, then reinstall the new APK fresh:
     ```bash
     adb install -r android/app/build/outputs/apk/release/app-release.apk
     ```

2. **Android 14 Foreground Service / Location Permission (`NativeTrackingService`):**
   On Android 14+, starting a foreground service of type `location` before the user grants runtime Location or Notification permissions throws a `SecurityException`.

3. **HTTP vs HTTPS (`usesCleartextTraffic`):**
   In the release build, `usesCleartextTraffic` is set to `false`. If the app or any plugin tries to call an plain HTTP URL (`http://...`) instead of HTTPS, Android blocks the connection and throws an exception.