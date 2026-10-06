package com.snehdistributors.mytally;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.os.Build;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.content.ContextCompat;
import androidx.core.app.NotificationCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Headless Native Background Tracking Service
 *
 * Runs as an independent Android Foreground Service with START_STICKY and
 * onTaskRemoved auto-resurrection. It continues tracking 1-meter GPS movements
 * and posting them directly to the backend even if the app UI is closed or swiped away.
 */
public class NativeTrackingService extends Service {
    private static final String TAG = "NativeTrackingService";
    public static final String CHANNEL_ID = "mytally_shift_tracking_channel";
    public static final int NOTIFICATION_ID = 28352;
    public static final String PREFS_NAME = "mytally_native_tracking";

    private FusedLocationProviderClient fusedLocationClient;
    private LocationCallback locationCallback;
    private PowerManager.WakeLock wakeLock;
    private ExecutorService networkExecutor;

    private double lastLatitude = 0.0;
    private double lastLongitude = 0.0;
    private long lastPingTime = 0;
    private boolean isRequestingUpdates = false;

    // Phone GPS drifts 5-50 m while standing still, so smaller thresholds mostly record noise and load the server
    private static final float MIN_DISTANCE_METERS = 25.0f; // movement that counts as a real move
    private static final long BURST_DEBOUNCE_MS = 30 * 1000;  // at least 30s between pings, even while driving
    private static final long HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000; // 5 min periodic heartbeat

    /** Android 14+ refuses a location foreground service (and crashes the app) without location permission. */
    public static boolean hasLocationPermission(Context context) {
        return ContextCompat.checkSelfPermission(context, android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(context, android.Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    /** Starting while the app isn't on screen (after a reboot, or swiped away) also needs "Allow all the time". */
    public static boolean canStartInBackground(Context context) {
        if (!hasLocationPermission(context)) return false;
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.Q
                || ContextCompat.checkSelfPermission(context, android.Manifest.permission.ACCESS_BACKGROUND_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "Creating NativeTrackingService");
        networkExecutor = Executors.newSingleThreadExecutor();
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this);

        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager != null) {
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "MyTally:NativeTrackingWakeLock");
            wakeLock.setReferenceCounted(false);
        }

        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "NativeTrackingService onStartCommand");

        // Verify shift is still marked active in preferences
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        boolean isActive = prefs.getBoolean("is_shift_active", false);

        if (!isActive) {
            Log.d(TAG, "Shift is not active, stopping service.");
            stopSelf();
            return START_NOT_STICKY;
        }

        if (!hasLocationPermission(this)) {
            // Location was denied or revoked. Stop quietly; the app starts tracking again once it's allowed.
            Log.w(TAG, "Location permission not granted, not starting tracking.");
            stopSelf();
            return START_NOT_STICKY;
        }

        // Build and display foreground notification
        Notification notification = buildForegroundNotification();
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
            } else {
                startForeground(NOTIFICATION_ID, notification);
            }
        } catch (Exception e) {
            // e.g. restarted in the background with only "While using the app" location access
            Log.w(TAG, "Could not start foreground tracking: " + e.getMessage());
            stopSelf();
            return START_NOT_STICKY;
        }

        // Start location updates
        startLocationUpdates();

        // START_STICKY instructs Android to recreate the service if memory pressure killed it
        return START_STICKY;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Shift Location Tracking",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Maintains continuous background movement tracking during active shift.");
            channel.setShowBadge(false);

            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildForegroundNotification() {
        Intent launchIntent = getPackageManager().getLaunchIntentForPackage(getPackageName());
        PendingIntent pendingIntent = null;
        if (launchIntent != null) {
            pendingIntent = PendingIntent.getActivity(
                    this,
                    0,
                    launchIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
        }

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("SnehDist. Active Shift")
                .setContentText("Continuous movement tracking is active.")
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .setContentIntent(pendingIntent)
                .build();
    }

    private void startLocationUpdates() {
        if (isRequestingUpdates) return;

        try {
            LocationRequest locationRequest;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                locationRequest = new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 30000)
                        .setMinUpdateDistanceMeters(MIN_DISTANCE_METERS)
                        .setMinUpdateIntervalMillis(15000)
                        .setMaxUpdateDelayMillis(60000)
                        .build();
            } else {
                locationRequest = LocationRequest.create()
                        .setPriority(LocationRequest.PRIORITY_HIGH_ACCURACY)
                        .setInterval(30000)
                        .setFastestInterval(15000)
                        .setSmallestDisplacement(MIN_DISTANCE_METERS);
            }

            locationCallback = new LocationCallback() {
                @Override
                public void onLocationResult(LocationResult locationResult) {
                    if (locationResult == null) return;
                    for (Location location : locationResult.getLocations()) {
                        handleLocationUpdate(location);
                    }
                }
            };

            fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper());
            isRequestingUpdates = true;
            Log.d(TAG, "Location updates requested successfully.");
        } catch (SecurityException se) {
            Log.e(TAG, "Location permission not granted: " + se.getMessage());
        } catch (Exception e) {
            Log.e(TAG, "Error starting location updates: " + e.getMessage());
        }
    }

    private void handleLocationUpdate(Location location) {
        if (location == null) return;

        long now = SystemClock.elapsedRealtime();
        double lat = location.getLatitude();
        double lng = location.getLongitude();
        float acc = location.hasAccuracy() ? location.getAccuracy() : 0.0f;

        // Calculate distance from previous checkpoint
        double dist = 0.0;
        if (lastLatitude != 0.0 || lastLongitude != 0.0) {
            dist = calculateHaversineDistance(lastLatitude, lastLongitude, lat, lng);
        } else {
            // First point
            dist = 0.0;
        }

        // At most one ping per BURST_DEBOUNCE_MS, whether or not the phone is moving
        if (lastPingTime != 0 && (now - lastPingTime) < BURST_DEBOUNCE_MS) {
            return;
        }

        // Must move >= MIN_DISTANCE_METERS OR 5 minutes elapsed (heartbeat)
        if (lastPingTime != 0 && dist < MIN_DISTANCE_METERS && (now - lastPingTime) < HEARTBEAT_INTERVAL_MS) {
            return;
        }

        // Valid displacement detected: update state and dispatch native HTTP post
        lastLatitude = lat;
        lastLongitude = lng;
        lastPingTime = now;

        Log.d(TAG, String.format("Movement detected: lat=%.6f, lng=%.6f, dist=%.1fm, acc=%.1fm", lat, lng, dist, acc));

        sendNativePing(lat, lng, acc);
    }

    private void sendNativePing(double lat, double lng, float accuracy) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String token = prefs.getString("token", "");
        String apiBase = prefs.getString("api_base", "https://tally-portal-one.vercel.app");

        if (token.isEmpty()) {
            Log.w(TAG, "No auth token in preferences, skipping ping.");
            return;
        }

        networkExecutor.execute(() -> {
            HttpURLConnection conn = null;
            try {
                if (wakeLock != null) {
                    wakeLock.acquire(10000); // 10s safety timeout
                }

                // Normalise API base URL
                String targetUrl = apiBase;
                if (!targetUrl.endsWith("/")) {
                    targetUrl += "/";
                }
                // Strip redundant trailing api if needed
                if (targetUrl.endsWith("/api/")) {
                    targetUrl = targetUrl.substring(0, targetUrl.length() - 5) + "/";
                }
                targetUrl += "attendance/ping-location";

                URL url = new URL(targetUrl);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(15000);
                conn.setDoOutput(true);

                JSONObject payload = new JSONObject();
                payload.put("latitude", lat);
                payload.put("longitude", lng);
                if (accuracy > 0) {
                    payload.put("accuracyMeters", accuracy);
                }

                byte[] postBytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(postBytes);
                    os.flush();
                }

                int statusCode = conn.getResponseCode();
                Log.d(TAG, "Native ping response status: " + statusCode);

                if (statusCode >= 200 && statusCode < 300) {
                    try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) {
                            sb.append(line);
                        }
                        JSONObject resp = new JSONObject(sb.toString());
                        if (resp.has("active") && !resp.getBoolean("active")) {
                            Log.i(TAG, "Server indicated shift is closed. Stopping native service.");
                            prefs.edit().putBoolean("is_shift_active", false).apply();
                            stopSelf();
                        }
                    }
                } else if (statusCode == 401) {
                    Log.w(TAG, "Auth token expired (401). Stopping native tracking.");
                    prefs.edit().putBoolean("is_shift_active", false).apply();
                    stopSelf();
                }
            } catch (Exception e) {
                Log.e(TAG, "Failed to send native ping: " + e.getMessage());
            } finally {
                if (conn != null) {
                    conn.disconnect();
                }
                if (wakeLock != null && wakeLock.isHeld()) {
                    try {
                        wakeLock.release();
                    } catch (Exception ignored) {}
                }
            }
        });
    }

    /**
     * Resurrects the service when the user swipes away the app from Recent Apps!
     */
    @Override
    public void onTaskRemoved(Intent rootIntent) {
        super.onTaskRemoved(rootIntent);
        Log.i(TAG, "User swiped away app from Recent Apps. Scheduling instant resurrection.");

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        boolean isActive = prefs.getBoolean("is_shift_active", false);

        if (isActive && canStartInBackground(this)) {
            Intent restartIntent = new Intent(getApplicationContext(), NativeTrackingService.class);
            restartIntent.setPackage(getPackageName());

            PendingIntent restartPendingIntent = PendingIntent.getService(
                    getApplicationContext(),
                    1001,
                    restartIntent,
                    PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_IMMUTABLE
            );

            AlarmManager alarmManager = (AlarmManager) getSystemService(Context.ALARM_SERVICE);
            if (alarmManager != null) {
                long restartTime = SystemClock.elapsedRealtime() + 1500; // 1.5 seconds later
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    alarmManager.setExactAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, restartTime, restartPendingIntent);
                } else {
                    alarmManager.set(AlarmManager.ELAPSED_REALTIME_WAKEUP, restartTime, restartPendingIntent);
                }
                Log.i(TAG, "Resurrection alarm scheduled for 1.5s in the future.");
            }
        }
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        Log.d(TAG, "Destroying NativeTrackingService");
        if (fusedLocationClient != null && locationCallback != null) {
            fusedLocationClient.removeLocationUpdates(locationCallback);
            isRequestingUpdates = false;
        }
        if (networkExecutor != null && !networkExecutor.isShutdown()) {
            networkExecutor.shutdown();
        }
        if (wakeLock != null && wakeLock.isHeld()) {
            try {
                wakeLock.release();
            } catch (Exception ignored) {}
        }
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private double calculateHaversineDistance(double lat1, double lon1, double lat2, double lon2) {
        final double R = 6371e3; // Earth radius in meters
        double phi1 = Math.toRadians(lat1);
        double phi2 = Math.toRadians(lat2);
        double deltaPhi = Math.toRadians(lat2 - lat1);
        double deltaLambda = Math.toRadians(lon2 - lon1);

        double a = Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
                Math.cos(phi1) * Math.cos(phi2) *
                Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }
}
