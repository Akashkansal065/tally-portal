package com.snehdistributors.mytally;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (bridge != null && bridge.getWebView() != null) {
            bridge.getWebView().setWebViewClient(new BridgeWebViewClient(bridge) {
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    Uri url = request.getUrl();
                    if (url == null) return false;

                    String scheme = url.getScheme();
                    if (scheme == null) return false;

                    if ("intent".equalsIgnoreCase(scheme)) {
                        try {
                            Intent intent = Intent.parseUri(url.toString(), Intent.URI_INTENT_SCHEME);
                            if (intent != null) {
                                view.getContext().startActivity(intent);
                                return true;
                            }
                        } catch (Exception e) {
                            try {
                                Intent intent = Intent.parseUri(url.toString(), Intent.URI_INTENT_SCHEME);
                                String fallbackUrl = intent != null ? intent.getStringExtra("browser_fallback_url") : null;
                                if (fallbackUrl != null) {
                                    view.loadUrl(fallbackUrl);
                                    return true;
                                }
                            } catch (Exception ignored) {}
                        }
                    } else if ("geo".equalsIgnoreCase(scheme) || "tel".equalsIgnoreCase(scheme) ||
                               "mailto".equalsIgnoreCase(scheme) || "sms".equalsIgnoreCase(scheme) ||
                               "whatsapp".equalsIgnoreCase(scheme)) {
                        try {
                            Intent intent = new Intent(Intent.ACTION_VIEW, url);
                            view.getContext().startActivity(intent);
                            return true;
                        } catch (Exception ignored) {}
                    }

                    return super.shouldOverrideUrlLoading(view, request);
                }
            });
        }
    }
}
