"use strict";
// The MyTally Bridge window. It only draws: every action is a call to the Python side (webview_app.Api),
// and everything shown is set as text, never as HTML.

const PATHS = {
  ok: "M20 6 9 17l-5-5",
  sync: "M21 12a9 9 0 0 0-15-6.7L3 8M3 3v5h5M3 12a9 9 0 0 0 15 6.7L21 16M21 21v-5h-5",
  warn: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  error: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM15 9l-6 6M9 9l6 6",
  idle: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z",
  paused: "M9 5v14M15 5v14",
  companies: "M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h2a2 2 0 0 1 2 2v10M2 21h20M8 7h4M8 11h4M8 15h4",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  settings: "M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M14 4v4M8 10v4M16 16v4",
  chevron: "m6 9 6 6 6-6",
};

function icon(name, cls) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "ic" + (cls ? " " + cls : ""));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", PATHS[name]);
  svg.appendChild(path);
  return svg;
}

// h("div", {class: "x", onclick: fn}, child, "text", [more])
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key === "value") el.value = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return el;
}

const $app = document.getElementById("app");
const $overlay = document.getElementById("overlay");
let api = null;
let boot = null;
let view = "";

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

// ---------------------------------------------------------------------------
// Confirm dialog
// ---------------------------------------------------------------------------
function confirmDialog(title, text, okLabel, danger) {
  return new Promise((resolve) => {
    const close = (answer) => { document.removeEventListener("keydown", onKey); $overlay.replaceChildren(); resolve(answer); };
    const onKey = (e) => { if (e.key === "Escape") close(false); };
    const okBtn = h("button", { class: "btn " + (danger ? "solid-danger" : "pri"), id: "dialog-ok", onclick: () => close(true) }, okLabel);
    $overlay.replaceChildren(h("div", { class: "scrim", onclick: (e) => { if (e.target === e.currentTarget) close(false); } },
      h("div", { class: "dialog", role: "alertdialog", "aria-modal": "true" },
        h("h1", null, title), h("p", null, text),
        h("div", { class: "acts" }, h("button", { class: "btn sec", id: "dialog-cancel", onclick: () => close(false) }, "Cancel"), okBtn))));
    document.addEventListener("keydown", onKey);
    okBtn.focus();
  });
}

// ---------------------------------------------------------------------------
// First run: welcome, then sign in with a code from the MyTally app, or with email and password
// ---------------------------------------------------------------------------
const F = { server: "", tally: "", email: "", password: "", company: "", autostart: false };
const pairing = { code: "", timer: null };
const setup = { screen: "", advanced: false, note: { text: "Looking for TallyPrime...", kind: "idle" }, msgEl: null, noteEl: null, mainBtn: null, mainLabel: "", detected: false };

function input(key, type) {
  return h("input", { class: "inp", id: "f-" + key, type: type || "text", value: F[key], autocomplete: "off", spellcheck: "false",
    oninput: (e) => { F[key] = e.target.value; } });
}
function field(label, key, help, type) {
  return h("div", { class: "field" }, h("label", { for: "f-" + key }, label), input(key, type), help ? h("small", null, help) : null);
}
function passwordField(help) {
  const box = input("password", "password");
  const toggle = h("button", { class: "btn sec", id: "f-password-show", type: "button", onclick: () => {
    box.type = box.type === "password" ? "text" : "password";
    toggle.textContent = box.type === "password" ? "Show" : "Hide";
  } }, "Show");
  return h("div", { class: "field" }, h("label", { for: "f-password" }, "Password"), h("div", { class: "row" }, box, toggle), help ? h("small", null, help) : null);
}
function checkbox(key, label) {
  return h("label", { class: "check" }, h("input", { type: "checkbox", id: "f-" + key, checked: F[key], onchange: (e) => { F[key] = e.target.checked; } }), label);
}
function tallyNote() {
  setup.noteEl = h("small", { class: "c-" + setup.note.kind }, setup.note.text);
  return setup.noteEl;
}
function say(text, kind) {
  if (!setup.msgEl) return;
  setup.msgEl.textContent = text || "";
  setup.msgEl.className = "msg c-" + (kind || "idle");
}
function busy(text) {
  if (!setup.mainBtn) return;
  setup.mainBtn.disabled = Boolean(text);
  setup.mainBtn.textContent = text || setup.mainLabel;
}
function mainButton(label, onclick) {
  setup.mainLabel = label;
  setup.mainBtn = h("button", { class: "btn pri lg", id: "setup-main", onclick }, label);
  return setup.mainBtn;
}
function advancedFields() {
  if (!setup.advanced) return null;
  const test = h("button", { class: "btn sec", id: "setup-test", onclick: async () => {
    test.disabled = true; test.textContent = "Testing...";
    say("Checking TallyPrime and the server...");
    const result = await api.test_connection(F);
    test.disabled = false; test.textContent = "Test connection";
    say(result.text, result.kind);
  } }, "Test connection");
  return [field("Server address", "server"), field("TallyPrime address", "tally", "TallyPrime's default is http://127.0.0.1:9000"), h("div", null, test)];
}
function footLinks(leftLabel, leftScreen) {
  return h("div", { class: "foot" },
    h("button", { class: "link", id: "setup-switch", onclick: () => showSetup(leftScreen) }, leftLabel),
    h("button", { class: "link", id: "setup-advanced", onclick: () => { setup.advanced = !setup.advanced; showSetup(setup.screen); } },
      setup.advanced ? "Hide advanced" : "Advanced"));
}

const SCREENS = {
  welcome: () => [
    h("h1", null, "Connect TallyPrime to MyTally"),
    h("p", { class: "lead" }, boot.app.short + " runs on this PC and keeps your Tally companies in step with the MyTally app."),
    h("button", { class: "btn pri lg", id: "welcome-code", onclick: () => showSetup("code") }, "Connect with a code from the app"),
    h("button", { class: "btn sec lg", id: "welcome-signin", onclick: () => showSetup("signin") }, "Sign in with email and password"),
    h("div", { class: "aside" }, "New to MyTally? Create your account in the MyTally app first, then come back here. " +
      "Invited by your admin? You don't need " + boot.app.short + ". Accept the invitation in the app."),
  ],
  signin: () => [
    h("h1", null, "Sign in to link this PC"),
    h("p", { class: "lead" }, "Use an account that can manage the sync agent. Admins can by default."),
    field("Email", "email"),
    passwordField(),
    companyField(),
    checkbox("autostart", "Start with Windows"),
    mainButton("Sign in and start syncing", signIn),
    (setup.msgEl = h("div", { class: "msg" })),
    footLinks("Connect with a code instead", "code"),
    advancedFields(),
  ],
  code: () => [
    h("h1", null, "Connect with a code"),
    h("p", { class: "lead" }, pairing.code
      ? "Open the MyTally app on your phone or browser, go to Connect Tally and enter this code. This PC is signed in as soon as you do."
      : "You get a code to enter in the MyTally app, signed in as someone who can manage the sync agent. No password is typed on this PC."),
    pairing.code ? h("div", { class: "paircode", id: "pair-code", "aria-label": "Code " + pairing.code.split("").join(" ") }, pairing.code) : null,
    pairing.code ? null : companyField(),
    pairing.code ? null : checkbox("autostart", "Start with Windows"),
    mainButton(pairing.code ? "Get a new code" : "Get a code", startCode),
    (setup.msgEl = h("div", { class: "msg" })),
    footLinks("Sign in with email and password", "signin"),
    advancedFields(),
  ],
};

function companyField() {
  return h("div", { class: "field" }, h("label", { for: "f-company" }, "Company"),
    h("div", { class: "row" }, input("company"), h("button", { class: "btn sec", id: "setup-detect", onclick: detectTally }, "Detect")), tallyNote());
}

function showSetup(screen) {
  view = "setup";
  closeMenu();
  if (screen !== "code") stopCode();
  setup.screen = screen;
  setup.msgEl = setup.noteEl = setup.mainBtn = null;
  $app.replaceChildren(h("div", { class: "setup" }, h("div", { class: "card" }, SCREENS[screen]())));
  if (!setup.detected) { setup.detected = true; detectTally(); }
  const first = $app.querySelector("input.inp");
  if (first && screen !== "welcome") first.focus();
}

async function detectTally() {
  setNote("Looking for TallyPrime...", "idle");
  const found = await api.detect_tally(F.tally);
  if (found.company) {
    F.company = found.company;
    const box = document.getElementById("f-company");
    if (box) box.value = found.company;
  }
  setNote(found.text, found.kind);
}
function setNote(text, kind) {
  setup.note = { text, kind };
  if (setup.noteEl && setup.noteEl.isConnected) { setup.noteEl.textContent = text; setup.noteEl.className = "c-" + kind; }
}
function needServer() {
  if (F.server.trim()) return true;
  if (!setup.advanced) { setup.advanced = true; showSetup(setup.screen); }
  say("Enter the server address under Advanced.", "error");
  return false;
}

async function signIn() {
  if (!needServer()) return;
  busy("Signing in...");
  let result = await api.sign_in(F);
  if (!result.ok && result.reason === "linked_to_another_device") {
    if (await confirmDialog("Move sync to this PC?", result.message + "\n\nThe other PC will stop syncing this company.", "Move it here")) {
      result = await api.link_active(true);
    } else {
      result = { ok: false, message: "Not linked: the company is still synced from the other PC." };
    }
  }
  if (result.ok) return enterMain();
  busy(null);
  say(result.message, "error");
}

// The code is shown until it is entered in the app, it runs out, or the person leaves the screen
function stopCode() {
  clearInterval(pairing.timer);
  pairing.timer = null;
  pairing.code = "";
}

async function startCode() {
  if (!needServer()) return;
  stopCode();
  busy("Getting a code...");
  const result = await api.code_start(F);
  if (setup.screen !== "code" || view !== "setup") return;
  if (!result.ok) { busy(null); return say(result.message, "error"); }
  pairing.code = result.code;
  showSetup("code");
  say("Waiting for the code to be entered in the app. It is valid for " + result.minutes + " minutes.");
  pairing.timer = setInterval(checkCode, 3000);
}

async function checkCode() {
  if (pairing.checking) return;
  pairing.checking = true;
  let result;
  try { result = await api.code_check(F); } catch (err) { result = { status: "pending" }; }
  pairing.checking = false;
  if (result.status === "pending" || setup.screen !== "code" || view !== "setup") return;
  stopCode();
  if (result.status === "error") {
    showSetup("code");
    return say(result.message, "error");
  }
  // Signed in. The company is linked as after an email sign-in; if it could not be, the Companies page shows why.
  if (!result.ok && result.reason === "linked_to_another_device" &&
      await confirmDialog("Move sync to this PC?", result.message + "\n\nThe other PC will stop syncing this company.", "Move it here")) {
    await api.link_active(true);
  }
  enterMain();
}

function enterMain() {
  F.password = "";
  stopCode();
  boot.signed_in = true;
  boot.setup.email = F.email;
  showMain("companies");
}

// ---------------------------------------------------------------------------
// Signed in: rail, health bar, pages
// ---------------------------------------------------------------------------
const M = { page: "", seq: 0, logs: [], state: null, key: "", els: {}, menu: null, companies: null };
const ACTION_LABEL = { resume: "Resume", retry: "Retry", signin: "Sign in again", sync: "Sync now" };

function showMain(page) {
  view = "main";
  const e = (M.els = {});
  e.nav = {};
  const navButton = (name, label) => (e.nav[name] = h("button", { class: "nav", id: "nav-" + name, onclick: () => showPage(name) }, icon(name), label,
    name === "activity" ? (e.flag = h("span", { class: "flag", hidden: true })) : null));
  e.badge = h("span", { class: "badge k-idle" });
  e.title = h("div", { class: "ti" }, "Starting...");
  e.detail = h("div", { class: "su" });
  e.mainBtn = h("button", { class: "btn pri", id: "health-main", onclick: mainAction }, "Sync now");
  e.split = h("div", { class: "split" }, e.mainBtn,
    h("button", { class: "btn pri", id: "health-more", "aria-label": "More actions", onclick: (ev) => { ev.stopPropagation(); toggleMenu(); } }, icon("chevron")));
  e.bar = h("div", { class: "bar" }, h("b"));
  e.tDot = h("span", { class: "dot" }); e.tText = h("span", null, "TallyPrime");
  e.cDot = h("span", { class: "dot" }); e.cText = h("span", null, "Server");
  e.page = h("div", { class: "page" });
  $app.replaceChildren(h("div", { class: "shell" },
    h("nav", { class: "rail" },
      h("div", { class: "brand" }, h("img", { src: "../assets/icon.png", alt: "" }), boot.app.short),
      navButton("companies", "Companies"), navButton("activity", "Activity"), navButton("settings", "Settings"),
      h("div", { class: "foot" }, boot.app.pc, h("br"), "Version " + boot.app.version)),
    h("div", { class: "main" },
      h("div", { class: "health" },
        h("div", { class: "top" }, e.badge, h("div", { class: "txt" }, e.title, e.detail), e.split),
        e.bar,
        h("div", { class: "chips" }, h("span", { class: "chip" }, e.tDot, e.tText), h("span", { class: "chip" }, e.cDot, e.cText))),
      e.page)));
  M.key = "";
  showPage(page);
  poll();
}

function showPage(name) {
  M.page = name;
  for (const [key, button] of Object.entries(M.els.nav)) {
    if (key === name) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  }
  ({ companies: companiesPage, activity: activityPage, settings: settingsPage })[name]();
}

async function mainAction() {
  const action = M.state ? M.state.health.action : "sync";
  if (action === "signin") return showSetup("signin");
  if (action === "resume") await api.resume(); else await api.sync_now();
  poll();
}

function closeMenu() {
  if (M.menu) { M.menu.remove(); M.menu = null; }
}
function toggleMenu() {
  if (M.menu) return closeMenu();
  const paused = M.state && M.state.paused;
  const item = (id, label, run) => h("button", { id, onclick: () => { closeMenu(); run(); } }, label);
  M.menu = h("div", { class: "menu", role: "menu" },
    item("menu-full", "Full re-sync...", async () => {
      if (await confirmDialog("Run a full re-sync?", "Every record of every linked company is checked again, not just what changed. " +
        "This can take a long time for a large company.\n\nNothing is deleted.", "Run full re-sync")) { await api.full_resync(); poll(); }
    }),
    item("menu-pause", paused ? "Resume syncing" : "Pause syncing", async () => { await (paused ? api.resume() : api.pause()); poll(); }),
    h("hr"),
    item("menu-hide", "Hide to tray", () => api.hide()));
  M.els.split.appendChild(M.menu);
}
document.addEventListener("click", closeMenu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

async function poll() {
  if (view !== "main") return;
  let state;
  try { state = await api.state(M.seq); } catch (err) { return; }
  if (view !== "main") return;
  M.seq = state.seq;
  if (state.logs.length) {
    M.logs.push(...state.logs);
    if (M.logs.length > 1000) M.logs.splice(0, M.logs.length - 1000);
    if (M.page === "activity") appendLog(state.logs);
  }
  M.state = state;
  const key = JSON.stringify([state.health, state.busy, state.tally_ok, state.cloud_ok, state.halted]);
  if (key !== M.key) { M.key = key; drawHealth(state); }
  markSyncing(state.syncing_name);
}

function drawHealth(state) {
  const e = M.els, health = state.health;
  e.badge.className = "badge k-" + health.kind;
  e.badge.replaceChildren(icon(health.kind, health.kind === "sync" ? "spin" : ""));
  e.title.textContent = health.title;
  e.detail.textContent = health.detail;
  e.mainBtn.disabled = state.busy;
  e.mainBtn.replaceChildren(...(state.busy ? [icon("sync", "spin"), "Syncing"] : [ACTION_LABEL[health.action] || "Sync now"]));
  e.bar.classList.toggle("on", state.busy);
  e.tDot.className = "dot " + (state.tally_ok ? "ok" : "error");
  e.tText.textContent = state.tally_ok ? "TallyPrime connected" : "TallyPrime not running";
  e.cDot.className = "dot " + (state.cloud_ok && !state.halted ? "ok" : "error");
  e.cText.textContent = state.halted ? "Signed out" : (state.cloud_ok ? "Server connected" : "Server offline");
  const flagged = health.kind === "warn" || health.kind === "error";
  e.flag.hidden = !flagged;
  e.flag.className = "flag dot " + (flagged ? health.kind : "");
}

// -- Companies ---------------------------------------------------------------
function companiesPage() {
  const list = h("div", { id: "companies-list" });
  const msg = h("div", { class: "msg", id: "companies-msg" });
  M.companies = { list, msg, notes: [] };
  M.els.page.replaceChildren(
    h("div", { class: "page-head" }, h("h1", null, "Companies"), h("button", { class: "btn sec", id: "companies-refresh", onclick: loadCompanies }, "Refresh")),
    h("div", { class: "muted" }, "Open a company in TallyPrime to link it. A company is synced from one PC at a time."),
    list, msg);
  loadCompanies();
}
function companiesSay(text, kind) {
  if (M.page !== "companies") return;
  M.companies.msg.textContent = text || "";
  M.companies.msg.className = "msg c-" + (kind || "idle");
}
async function loadCompanies() {
  companiesSay("Checking TallyPrime...");
  const data = await api.companies();
  if (M.page !== "companies") return;
  const c = M.companies;
  c.notes = [];
  const row = (company, label, cls, run) => {
    const note = h("div", { class: "nt c-" + company.kind }, company.note);
    if (label === "Unlink") c.notes.push({ name: company.name, el: note, text: company.note, kind: company.kind });
    return h("div", { class: "co" }, h("div", { class: "who" }, h("div", { class: "nm" }, company.name), note),
      h("button", { class: "btn sm " + cls, onclick: () => run(company) }, label));
  };
  const parts = [];
  if (data.linked.length) parts.push(h("div", { class: "sub" }, "Linked to this PC"), h("div", { class: "card list" }, data.linked.map((x) => row(x, "Unlink", "danger", unlinkCompany))));
  if (data.unlinked.length) parts.push(h("div", { class: "sub" }, "Open in Tally, not linked"), h("div", { class: "card list" }, data.unlinked.map((x) => row(x, "Link", "sec", (company) => linkCompany(company, false)))));
  if (data.device_mode && !parts.length) parts.push(h("div", { class: "card empty" }, "No companies yet. Open one in TallyPrime, then press Refresh."));
  c.list.replaceChildren(...parts);
  if (!data.device_mode) companiesSay("This PC is not signed in as a sync device yet. Sign in again from Settings to manage companies here.", "warn");
  else companiesSay(data.any_open ? "" : "No company is open in TallyPrime.");
  markSyncing(M.state ? M.state.syncing_name : null);
}
function markSyncing(name) {
  if (M.page !== "companies" || !M.companies) return;
  for (const note of M.companies.notes) {
    const syncing = Boolean(name) && note.name === name;
    note.el.textContent = syncing ? "Syncing now..." : note.text;
    note.el.className = "nt c-" + (syncing ? "sync" : note.kind);
  }
}
async function linkCompany(company, takeOver) {
  companiesSay("Linking '" + company.name + "'...");
  const result = await api.link_company(company.guid, takeOver);
  if (result.ok) return loadCompanies();
  if (result.reason === "linked_to_another_device" && !takeOver &&
      await confirmDialog("Move sync to this PC?", result.message + "\n\nThe other PC will stop syncing this company.", "Move it here")) {
    return linkCompany(company, true);
  }
  companiesSay(result.message, "error");
}
async function unlinkCompany(company) {
  if (!await confirmDialog("Stop syncing this company?", "'" + company.name + "' will no longer be synced from this PC. Its data in the app stays.", "Unlink", true)) return;
  const result = await api.unlink_company(company.guid);
  if (result.ok) return loadCompanies();
  companiesSay("Could not unlink. Check the connection and try again.", "error");
}

// -- Activity ----------------------------------------------------------------
function activityPage() {
  const log = h("div", { class: "card log", id: "activity-log", tabindex: "0" });
  M.els.log = log;
  M.els.page.replaceChildren(
    h("div", { class: "page-head" }, h("h1", null, "Activity"),
      h("button", { class: "btn sec", id: "activity-clear", onclick: async () => { await api.clear_logs(); M.logs = []; log.replaceChildren(); } }, "Clear")),
    h("div", { class: "muted" }, "Everything the agent has done since it started. Support may ask for this."),
    log);
  appendLog(M.logs, true);
}
function appendLog(lines, toEnd) {
  const log = M.els.log;
  if (!log || !log.isConnected) return;
  const atEnd = toEnd || log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  log.append(...lines.map((line) => h("div", { class: line.tag }, line.text)));
  while (log.childElementCount > 1000) log.firstElementChild.remove();
  if (atEnd) log.scrollTop = log.scrollHeight;
}

// -- Settings ----------------------------------------------------------------
async function settingsPage() {
  const page = M.els.page;
  page.replaceChildren(h("div", { class: "page-head" }, h("h1", null, "Settings")));
  const v = await api.settings();
  if (M.page !== "settings") return;
  const text = (key, attrs) => h("input", Object.assign({ class: "inp", id: "s-" + key, value: String(v[key]), autocomplete: "off", spellcheck: "false",
    oninput: (e) => { v[key] = e.target.value; } }, attrs || {}));
  const toggle = (key, label) => {
    const button = h("button", { class: "tog", id: "s-" + key, role: "switch", "aria-checked": String(Boolean(v[key])), "aria-label": label,
      onclick: () => { v[key] = !v[key]; button.setAttribute("aria-checked", String(v[key])); } });
    return h("div", { class: "line" }, button, label);
  };
  const group = (title, hint, ...kids) => h("div", { class: "card group" }, h("h2", null, title), hint ? h("div", { class: "note" }, hint) : null, kids);
  const feedback = h("span", { class: "msg", id: "settings-msg" });
  const tell = (message, kind) => { feedback.textContent = message; feedback.className = "msg c-" + kind; };
  const themes = h("div", { class: "seg", role: "group", "aria-label": "Theme" }, ["system", "light", "dark"].map((name) =>
    h("button", { id: "s-theme-" + name, "aria-pressed": String(v.theme === name), onclick: async (e) => {
      v.theme = name; applyTheme(name);
      for (const b of themes.children) b.setAttribute("aria-pressed", String(b === e.currentTarget));
      await api.set_theme(name);
    } }, name[0].toUpperCase() + name.slice(1))));
  const save = h("button", { class: "btn pri", id: "settings-save", onclick: async () => {
    save.disabled = true;
    const result = await api.save_settings(v);
    save.disabled = false;
    tell(result.message, result.ok ? "ok" : "error");
    if (result.ok) setTimeout(() => { if (feedback.textContent === "Saved") feedback.textContent = ""; }, 3000);
  } }, "Save");

  page.replaceChildren(
    h("div", { class: "page-head" }, h("h1", null, "Settings"), feedback, save),
    group("Connection", null,
      h("div", { class: "field" }, h("label", { for: "s-tally_host" }, "TallyPrime computer and port"),
        h("div", { class: "row" }, text("tally_host"), text("tally_port", { class: "inp port", inputmode: "numeric" })),
        h("small", null, "Use localhost when TallyPrime runs on this PC. Its default port is 9000.")),
      h("div", { class: "field" }, h("label", { for: "s-backend_url" }, "Server address"), text("backend_url"))),
    group("Schedule", "How often " + boot.app.short + " looks for changes, in seconds.",
      h("div", { class: "line" }, text("outbound_seconds", { inputmode: "numeric" }), "Send changes made in the app to Tally"),
      h("div", { class: "line" }, text("inbound_seconds", { inputmode: "numeric" }), "Check Tally for new and changed records")),
    group("This PC", null, toggle("autostart", "Start with Windows"), h("div", { class: "line" }, "Theme", themes)),
    group("Account", null, h("div", { class: "line" }, "Signed in as " + (v.email || "a saved sign-in")),
      h("div", null, h("button", { class: "btn sec", id: "settings-relogin", onclick: () => { F.email = v.email || F.email; showSetup("signin"); } }, "Sign in as someone else"))),
    group("Support", "Support may ask for the log files. Export puts them in one zip file on the Desktop.",
      h("div", { class: "row" },
        h("button", { class: "btn sec", id: "settings-open-logs", onclick: async () => { const r = await api.open_logs(); if (!r.ok) tell(r.message, "warn"); } }, "Open logs folder"),
        h("button", { class: "btn sec", id: "settings-export-logs", onclick: async () => { const r = await api.export_logs(); tell(r.message, r.ok ? "ok" : "error"); } }, "Export logs"))),
    group("Advanced", "Change these only if support asks you to.",
      h("div", { class: "line" }, text("vouchers_per_range", { inputmode: "numeric" }), "Vouchers sent per request in a full re-sync. Lower it if one times out."),
      toggle("auto_discover_paths", "Find the TallyPrime program and data folders automatically"),
      toggle("force_full_sync", "Re-check every record on each sync (slower)")),
    group("Quit " + boot.app.short, "Syncing stops until " + boot.app.short + " is opened again. Closing the window only hides it to the tray.",
      h("div", null, h("button", { class: "btn danger", id: "settings-quit", onclick: async () => {
        if (await confirmDialog("Quit " + boot.app.short + "?", "Syncing stops until it is opened again.", "Quit", true)) api.quit();
      } }, "Quit " + boot.app.short))));
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function start() {
  api = window.pywebview.api;
  boot = await api.boot();
  applyTheme(boot.theme);
  Object.assign(F, boot.setup);
  if (boot.signed_in) showMain("companies"); else showSetup(boot.setup.email ? "signin" : "welcome");
  setInterval(poll, 1000);
}

if (new URLSearchParams(location.search).has("demo")) {
  // Design preview in a browser, with made-up data: open index.html?demo
  const demo = document.createElement("script");
  demo.src = "demo.js";
  demo.onload = start;
  document.head.appendChild(demo);
} else if (window.pywebview && window.pywebview.api) {
  start();
} else {
  window.addEventListener("pywebviewready", start, { once: true });
}
