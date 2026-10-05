package com.snehdistributors.mytally;

import android.content.Context;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Tells the web app whether this build includes a real Firebase setup (google-services.json at build time).
 * The push plugin crashes the app if asked to register without it, so the app checks here first.
 * The placeholder google-services.json (app id 1:000000000000:...) counts as no Firebase.
 */
@CapacitorPlugin(name = "PushSetup")
public class PushSetupPlugin extends Plugin {
    private static final String PLACEHOLDER_APP_ID_PREFIX = "1:000000000000:";

    @PluginMethod
    public void status(PluginCall call) {
        Context context = getContext();
        // The google-services Gradle plugin generates this resource; Firebase initialises only when it exists
        int resId = context.getResources().getIdentifier("google_app_id", "string", context.getPackageName());
        String appId = resId != 0 ? context.getString(resId) : "";
        JSObject ret = new JSObject();
        ret.put("firebase", !appId.isEmpty() && !appId.startsWith(PLACEHOLDER_APP_ID_PREFIX));
        call.resolve(ret);
    }
}
