package com.snehdistributors.mytally;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;

import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "NativeTracking")
public class NativeTrackingPlugin extends Plugin {
    private static final String TAG = "NativeTrackingPlugin";

    @PluginMethod
    public void startTracking(PluginCall call) {
        String token = call.getString("token");
        String apiBase = call.getString("apiBase");

        if (token == null || token.isEmpty()) {
            call.reject("Token is required to start native tracking");
            return;
        }

        if (!NativeTrackingService.hasLocationPermission(getContext())) {
            // Starting the service now would crash the app on Android 14+
            call.reject("Location permission is not granted", "LOCATION_PERMISSION");
            return;
        }

        try {
            Context context = getContext();
            SharedPreferences prefs = context.getSharedPreferences(NativeTrackingService.PREFS_NAME, Context.MODE_PRIVATE);
            prefs.edit()
                    .putString("token", token)
                    .putString("api_base", apiBase != null && !apiBase.isEmpty() ? apiBase : "https://tally-portal-one.vercel.app")
                    .putBoolean("is_shift_active", true)
                    .apply();

            Intent serviceIntent = new Intent(context, NativeTrackingService.class);
            ContextCompat.startForegroundService(context, serviceIntent);

            Log.i(TAG, "Native tracking started successfully via plugin.");
            JSObject ret = new JSObject();
            ret.put("success", true);
            ret.put("active", true);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "Failed to start native tracking service: " + e.getMessage());
            call.reject("Failed to start native tracking service: " + e.getMessage());
        }
    }

    @PluginMethod
    public void stopTracking(PluginCall call) {
        try {
            Context context = getContext();
            SharedPreferences prefs = context.getSharedPreferences(NativeTrackingService.PREFS_NAME, Context.MODE_PRIVATE);
            prefs.edit().putBoolean("is_shift_active", false).apply();

            Intent serviceIntent = new Intent(context, NativeTrackingService.class);
            context.stopService(serviceIntent);

            Log.i(TAG, "Native tracking stopped successfully via plugin.");
            JSObject ret = new JSObject();
            ret.put("success", true);
            ret.put("active", false);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "Failed to stop native tracking service: " + e.getMessage());
            call.reject("Failed to stop native tracking: " + e.getMessage());
        }
    }

    @PluginMethod
    public void isTrackingActive(PluginCall call) {
        Context context = getContext();
        SharedPreferences prefs = context.getSharedPreferences(NativeTrackingService.PREFS_NAME, Context.MODE_PRIVATE);
        boolean isActive = prefs.getBoolean("is_shift_active", false);

        JSObject ret = new JSObject();
        ret.put("active", isActive);
        call.resolve(ret);
    }

    @PluginMethod
    public void requestBatteryExemption(PluginCall call) {
        try {
            Context context = getContext();
            PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);

            if (pm != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                boolean isIgnoring = pm.isIgnoringBatteryOptimizations(context.getPackageName());
                if (!isIgnoring) {
                    Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + context.getPackageName()));
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(intent);

                    JSObject ret = new JSObject();
                    ret.put("prompted", true);
                    ret.put("isIgnoring", false);
                    call.resolve(ret);
                    return;
                }
            }

            JSObject ret = new JSObject();
            ret.put("prompted", false);
            ret.put("isIgnoring", true);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "Failed to request battery exemption: " + e.getMessage());
            call.reject("Failed to request battery exemption: " + e.getMessage());
        }
    }
}
