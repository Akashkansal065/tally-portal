package com.snehdistributors.mytally;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.util.Log;

import androidx.core.content.ContextCompat;

/**
 * Boot & Package Update Receiver
 *
 * Restarts NativeTrackingService automatically if the device is rebooted
 * or the app is updated while an active shift was in progress.
 */
public class BootReceiver extends BroadcastReceiver {
    private static final String TAG = "BootReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent != null ? intent.getAction() : null;
        Log.d(TAG, "BootReceiver triggered with action: " + action);

        if (Intent.ACTION_BOOT_COMPLETED.equals(action) ||
            Intent.ACTION_MY_PACKAGE_REPLACED.equals(action) ||
            "android.intent.action.QUICKBOOT_POWERON".equals(action)) {

            SharedPreferences prefs = context.getSharedPreferences(NativeTrackingService.PREFS_NAME, Context.MODE_PRIVATE);
            boolean isShiftActive = prefs.getBoolean("is_shift_active", false);

            if (isShiftActive) {
                Log.i(TAG, "Active shift found after reboot/update. Resuming NativeTrackingService.");
                Intent serviceIntent = new Intent(context, NativeTrackingService.class);
                try {
                    ContextCompat.startForegroundService(context, serviceIntent);
                } catch (Exception e) {
                    Log.e(TAG, "Failed to start NativeTrackingService on boot: " + e.getMessage());
                }
            } else {
                Log.d(TAG, "No active shift on reboot. Service not started.");
            }
        }
    }
}
