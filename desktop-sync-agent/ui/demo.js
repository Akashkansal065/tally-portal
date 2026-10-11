"use strict";
// Made-up data for looking at the window in a browser: index.html?demo, or ?demo=sync (idle, sync, ok, warn,
// error, paused, setup) and &theme=dark. Never loaded by the real app.
(function () {
  const params = new URLSearchParams(location.search);
  let kind = params.get("demo") || "idle";
  let codeChecks = 0;
  const HEALTH = {
    idle: { kind: "idle", title: "Up to date", detail: "Last synced 10 Oct 2026, 10:42:10 PM", action: "sync" },
    sync: { kind: "sync", title: "Syncing Sneh Distributors", detail: "This can take a while for a large company.", action: "sync" },
    ok: { kind: "ok", title: "Synced just now", detail: "Synced 42 Vouchers, 3 Ledgers", action: "sync" },
    warn: { kind: "warn", title: "Syncing, with something to check", detail: "Up-to-date | 'Shree Balaji Traders' is not open in Tally", action: "sync" },
    error: { kind: "error", title: "Can't reach TallyPrime", detail: "Open TallyPrime on this PC. Syncing resumes on its own once it is back.", action: "retry" },
    paused: { kind: "paused", title: "Syncing is paused", detail: "Changes will sync when you resume.", action: "resume" },
  };
  const logs = [
    { text: "22:41:58 [INFO] Starting background sync daemon (outbound: 5s, inbound: 60s)...", tag: "info" },
    { text: "22:42:03 [INFO] Synced 42 vouchers and 3 ledgers for 'Sneh Distributors'.", tag: "success" },
    { text: "22:42:04 [WARNING] 'Shree Balaji Traders' is not open in Tally", tag: "warning" },
    { text: "22:43:10 [ERROR] Push failed: the server did not answer in time", tag: "error" },
  ];
  const wait = (value, ms) => new Promise((resolve) => setTimeout(() => resolve(value), ms || 150));
  const settings = { tally_host: "localhost", tally_port: "9000", backend_url: "https://app.example.com", outbound_seconds: 5, inbound_seconds: 60,
    vouchers_per_range: 50, auto_discover_paths: true, force_full_sync: false, autostart: true, theme: params.get("theme") || "system", email: "accounts@snehdistributors.in" };
  window.pywebview = { api: {
    boot: () => wait({ app: { name: "MyTally Bridge", short: "Bridge", version: "2.0.0", pc: "ACCOUNTS-PC" }, signed_in: kind !== "setup", theme: settings.theme,
      setup: { server: "https://app.example.com", tally: "http://127.0.0.1:9000", email: "", company: "", autostart: true } }),
    state: (since) => wait({ health: HEALTH[kind] || HEALTH.idle, busy: kind === "sync", paused: kind === "paused", tally_ok: kind !== "error", cloud_ok: true, halted: false,
      syncing_name: kind === "sync" ? "Sneh Distributors" : null, logs: since ? [] : logs, seq: logs.length }, 20),
    sync_now: () => { kind = "sync"; setTimeout(() => { kind = "ok"; }, 2500); return wait({ ok: true }); },
    full_resync: () => { kind = "sync"; return wait({ ok: true }); },
    pause: () => { kind = "paused"; return wait({ ok: true }); },
    resume: () => { kind = "idle"; return wait({ ok: true }); },
    companies: () => wait({ device_mode: true, any_open: true,
      linked: [{ guid: "g1", name: "Sneh Distributors", note: "Syncing from this PC", kind: "ok" },
               { guid: "g2", name: "Shree Balaji Traders", note: "Closed in Tally. Open it there to sync it.", kind: "idle" }],
      unlinked: [{ guid: "g3", name: "Maa Durga Agencies", note: "Not synced from this PC", kind: "idle" }] }, 300),
    link_company: (guid, takeOver) => wait(takeOver ? { ok: true } : { ok: false, reason: "linked_to_another_device", message: "This company is synced from OFFICE-PC." }),
    unlink_company: () => wait({ ok: true }),
    settings: () => wait(Object.assign({}, settings)),
    save_settings: (v) => wait(isNaN(Number(v.outbound_seconds)) ? { ok: false, message: "The schedule and vouchers per request must be whole numbers." } : { ok: true, message: "Saved" }),
    set_theme: () => wait({ ok: true }),
    open_logs: () => wait({ ok: true, message: "" }),
    export_logs: () => wait({ ok: true, message: "Exported to the Desktop: MyTallyBridge_Logs_20261010_224500.zip" }),
    clear_logs: () => wait({ ok: true }),
    detect_tally: () => wait({ company: "Sneh Distributors", kind: "ok", text: "Found in TallyPrime: 'Sneh Distributors'." }, 400),
    test_connection: () => wait({ kind: "ok", text: "TallyPrime: connected (Sneh Distributors). Server: reachable." }, 500),
    sign_in: (v) => wait(v.password ? { ok: true } : { ok: false, message: "Sign-in failed: enter your password." }, 500),
    link_active: () => wait({ ok: true }),
    code_start: () => { codeChecks = 0; return wait({ ok: true, code: "K7QM-2XHP", minutes: 10 }, 400); },
    code_check: () => wait(++codeChecks < 4 ? { status: "pending" } : { status: "done", ok: true }, 100),
    hide: () => wait({ ok: true }),
    quit: () => wait({ ok: true }),
  } };
})();
