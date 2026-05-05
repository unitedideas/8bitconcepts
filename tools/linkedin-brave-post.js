#!/usr/bin/env node
/*
 * Background LinkedIn publisher using the authenticated Brave session.
 *
 * This is intentionally a one-shot publishing tool behind the sync-state
 * LinkedIn automation, not a generic browser automation loop.
 * The default path reads Brave's LinkedIn cookies and posts through LinkedIn's
 * authenticated Voyager HTTPS endpoints, so Brave never becomes the focused app.
 * The DOM helpers below are retained only as supervised emergency recovery code.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const zlib = require("zlib");
const { spawnSync } = require("child_process");
const {
  bodySnapshot,
  braveJS,
  clickAXButton,
  closeFrontWindow,
  getClipboard,
  nativeClickElement,
  nativeClickScreenPoint,
  nativeClickWindowRelative,
  normalize,
  openDedicatedWindow,
  pasteIntoFocusedElement,
  runWithLease,
  setBraveUrl,
  setClipboard,
  tryWaitFor,
  waitFor,
} = require("./social-brave-common");

const FEED_URL = "https://www.linkedin.com/feed/?shareActive=true";
const ACTIVITY_ALL_URL = "https://www.linkedin.com/in/shane-cheek-9173473b6/recent-activity/all/";
const DEFAULT_NAME = "Shane Cheek";
const DEFAULT_HEADLINE = "Software Engineer at 8BitConcepts";
const LINKEDIN_ALLOW_FILE = "/tmp/8bit-linkedin-browser-one-shot-allow";
const LINKEDIN_ONE_SHOT_TOKEN = "8bit-linkedin-supervised-manual-v2";
const COOKIE_SOURCES = [
  {
    name: "brave-default",
    db: `${os.homedir()}/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies`,
    safeStorageService: "Brave Safe Storage",
  },
  {
    name: "chrome-profile-3",
    db: `${os.homedir()}/Library/Application Support/Google/Chrome/Profile 3/Cookies`,
    safeStorageService: "Chrome Safe Storage",
  },
];

function verificationNeedles(text) {
  const normalized = normalize(text || "");
  const withoutUrls = normalized
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const chunks = withoutUrls
    .split(/(?<=[.!?])\s+|\n+/)
    .map(s => s.trim())
    .filter(s => s.length >= 36);
  const needles = [];
  for (const chunk of chunks) {
    const needle = chunk.slice(0, 90).trim();
    if (needle.length >= 36 && !needles.includes(needle)) needles.push(needle);
    if (needles.length >= 2) break;
  }
  if (!needles.length && withoutUrls.length >= 36) needles.push(withoutUrls.slice(0, 90));
  if (!needles.length) needles.push(normalized.slice(0, 90));
  return needles;
}

function livePostTextMatches(liveText, expectedText) {
  const live = normalize(liveText || "");
  return verificationNeedles(expectedText).some(needle => live.includes(needle));
}

function usage() {
  console.error("usage: node tools/linkedin-brave-post.js (--text <copy> | --text-file <path>) --allow-browser [--dry-run] [--recover-only] [--skip-lease] [--expected-name <name>] [--expected-headline <headline>]");
  process.exit(2);
}

function parseArgs(argv) {
  const args = {
    dryRun: false,
    recoverOnly: false,
    allowBrowser: false,
    expectedName: DEFAULT_NAME,
    expectedHeadline: DEFAULT_HEADLINE,
    skipLease: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--allow-browser") args.allowBrowser = true;
    else if (arg === "--recover-only") args.recoverOnly = true;
    else if (arg === "--skip-lease") args.skipLease = true;
    else if (arg === "--text") args.text = argv[++i];
    else if (arg === "--text-file") args.textFile = argv[++i];
    else if (arg === "--expected-name") args.expectedName = argv[++i];
    else if (arg === "--expected-headline") args.expectedHeadline = argv[++i];
    else usage();
  }
  if ((!args.text && !args.textFile) || (args.text && args.textFile) || !args.expectedName || !args.expectedHeadline) usage();
  const browserMode = args.recoverOnly || process.env.SOCIAL_LINKEDIN_FORCE_BROWSER === "1";
  if (browserMode) requireBrowserAllowance(args);
  return args;
}

function requireBrowserAllowance(args) {
  if (
    !args.allowBrowser ||
    process.env.SOCIAL_BRAVE_LINKEDIN_ONE_SHOT !== LINKEDIN_ONE_SHOT_TOKEN ||
    !fs.existsSync(LINKEDIN_ALLOW_FILE) ||
    fs.readFileSync(LINKEDIN_ALLOW_FILE, "utf8").trim() !== LINKEDIN_ONE_SHOT_TOKEN
  ) {
    console.error("LinkedIn browser recovery is disabled unless --allow-browser, SOCIAL_BRAVE_LINKEDIN_ONE_SHOT, and the one-shot allow-file content are all set by an explicit supervised run.");
    process.exit(3);
  }
}

function readText(args) {
  const text = args.textFile ? fs.readFileSync(args.textFile, "utf8") : args.text;
  return String(text || "").trim();
}

function extractMe(json) {
  const data = (json && json.data ? json.data : json) || {};
  const included = json && Array.isArray(json.included) ? json.included : [];
  let mini = data && data.miniProfile ? data.miniProfile : null;
  if (!mini && data && data["*miniProfile"]) {
    mini = included.find(item => item && item.entityUrn === data["*miniProfile"]);
  }
  if (!mini) {
    mini = included.find(item => item && (
      String(item.$type || "").includes("MiniProfile") ||
      (item.firstName && item.lastName && item.occupation)
    ));
  }
  mini = mini || {};
  const first = data.firstName || mini.firstName || "";
  const last = data.lastName || mini.lastName || "";
  const name = `${first} ${last}`.trim();
  return {
    name,
    headline: data.occupation || mini.occupation || "",
    objectUrn: data.objectUrn || "",
    plainId: data.plainId || "",
    publicIdentifier: mini.publicIdentifier || data.publicIdentifier || "",
  };
}

function ensureLinkedInBackgroundTab(args) {
  const marker = `8bit-linkedin-api-${process.pid}`;
  linkedinOpenDedicatedWindow("https://www.linkedin.com/feed/", { marker, namePrefix: "8bit-linkedin-", host: "www.linkedin.com" });
  return waitFor("LinkedIn background tab API readiness", () => {
    const snap = linkedinBodySnapshot(3000);
    const text = snap.text || "";
    return { ok: Boolean(snap.url && snap.url.includes("linkedin.com") && text.includes(args.expectedName)), snap };
  }, 15000);
}

function linkedinPageRequest(method, target, body = null, accept = "application/vnd.linkedin.normalized+json+2.1") {
  return linkedinJS(`(() => {
    const method = ${JSON.stringify(method)};
    const target = ${JSON.stringify(target)};
    const body = ${JSON.stringify(body)};
    const accept = ${JSON.stringify(accept)};
    const csrf = (document.cookie.match(/(?:^|; )JSESSIONID=([^;]+)/) || [])[1] || "";
    const xhr = new XMLHttpRequest();
    xhr.open(method, target, false);
    xhr.setRequestHeader("accept", accept);
    xhr.setRequestHeader("csrf-token", decodeURIComponent(csrf).replace(/^"|"$/g, ""));
    xhr.setRequestHeader("x-restli-protocol-version", "2.0.0");
    if (body !== null) xhr.setRequestHeader("content-type", "application/json; charset=UTF-8");
    xhr.send(body === null ? null : JSON.stringify(body));
    let json = null;
    try { json = xhr.responseText ? JSON.parse(xhr.responseText) : null; } catch {}
    return JSON.stringify({
      ok: xhr.status >= 200 && xhr.status < 300,
      status: xhr.status,
      responseURL: xhr.responseURL,
      json,
      text: json ? "" : String(xhr.responseText || "").slice(0, 12000)
    });
  })()`);
}

function verifyLinkedInPageIdentity(args) {
  const res = linkedinPageRequest("GET", "/voyager/api/me");
  if (!res || !res.ok) {
    throw new Error(`LinkedIn background tab identity request failed: ${JSON.stringify({ status: res && res.status, responseURL: res && res.responseURL, text: res && res.text ? res.text.slice(0, 300) : "" })}`);
  }
  const me = extractMe(res.json);
  if (me.name !== args.expectedName || me.headline !== args.expectedHeadline) {
    throw new Error(`LinkedIn background tab identity mismatch: expected ${args.expectedName} / ${args.expectedHeadline}, got ${me.name || "(missing name)"} / ${me.headline || "(missing headline)"}`);
  }
  return me;
}

function extractPostResult(json) {
  const status = json && json.data && json.data.status ? json.data.status : {};
  const urn = status.urn || json.urn || "";
  const updateV2 = status["*updateV2"] || "";
  const activityUrn = updateV2 && updateV2.includes("(") ? updateV2.split("(").pop().split(",")[0] : "";
  const url = status.toastCtaUrl || (activityUrn ? `https://www.linkedin.com/feed/update/${activityUrn}/` : (urn ? `https://www.linkedin.com/feed/update/${urn}/` : ""));
  return { urn, activityUrn, url, message: status.mainToastText || "" };
}

function postTextPayload(text) {
  return {
    visibleToConnectionsOnly: false,
    externalAudienceProviders: [],
    commentaryV2: { text, attributes: [] },
    origin: "FEED",
    allowedCommentersScope: "ALL",
    postState: "PUBLISHED",
    media: [],
  };
}

function sqliteQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function browserSafeStorageKey(source) {
  const proc = spawnSync("security", ["find-generic-password", "-w", "-s", source.safeStorageService], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
    timeout: 10000,
  });
  if (proc.status !== 0 || proc.error) {
    throw new Error((proc.stderr || (proc.error && proc.error.message) || "could not read Brave Safe Storage key").trim());
  }
  return crypto.pbkdf2Sync(proc.stdout.trim(), "saltysalt", 1003, 16, "sha1");
}

function decryptBraveCookie(host, encryptedHex, key) {
  const encrypted = Buffer.from(encryptedHex, "hex");
  if (!encrypted.subarray(0, 3).equals(Buffer.from("v10"))) {
    throw new Error(`unsupported Brave cookie encryption prefix for ${host}`);
  }
  const decipher = crypto.createDecipheriv("aes-128-cbc", key, Buffer.alloc(16, 0x20));
  let value = Buffer.concat([decipher.update(encrypted.subarray(3)), decipher.final()]);
  const hostDigest = crypto.createHash("sha256").update(host).digest();
  if (value.subarray(0, 32).equals(hostDigest)) value = value.subarray(32);
  return value.toString("utf8");
}

function readLinkedInCookies(source) {
  if (!fs.existsSync(source.db)) {
    throw new Error(`${source.name} cookie DB not found at ${source.db}`);
  }
  const hosts = [".www.linkedin.com", ".linkedin.com", "www.linkedin.com", "linkedin.com"];
  const sql = `select host_key,name,hex(encrypted_value) from cookies where host_key in (${hosts.map(sqliteQuote).join(",")});`;
  const proc = spawnSync("sqlite3", [source.db, sql], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
    timeout: 10000,
  });
  if (proc.status !== 0 || proc.error) {
    throw new Error((proc.stderr || (proc.error && proc.error.message) || "could not read Brave cookies").trim());
  }
  const key = browserSafeStorageKey(source);
  const cookies = {};
  for (const row of proc.stdout.trim().split(/\n/).filter(Boolean)) {
    const [host, name, encryptedHex] = row.split("|");
    if (!cookies[name]) cookies[name] = decryptBraveCookie(host, encryptedHex, key);
  }
  const missing = ["li_at", "JSESSIONID"].filter(name => !cookies[name]);
  if (missing.length) throw new Error(`missing ${source.name} LinkedIn cookies: ${missing.join(", ")}`);
  return cookies;
}

function linkedinDirectAuthForSource(source) {
  const cookies = readLinkedInCookies(source);
  const csrf = cookies.JSESSIONID.replace(/^"|"$/g, "");
  return {
    sourceName: source.name,
    headers: {
      "accept": "application/vnd.linkedin.normalized+json+2.1",
      "csrf-token": csrf,
      "referer": "https://www.linkedin.com/feed/",
      "x-restli-protocol-version": "2.0.0",
      "x-li-lang": "en_US",
      "x-li-track": JSON.stringify({ clientVersion: "1.13.14473", mpVersion: "1.13.14473", osName: "web", timezoneOffset: -7, timezone: "America/Los_Angeles" }),
      "user-agent": "Mozilla/5.0",
      // Cookie header values must stay raw; percent-encoding breaks LinkedIn's
      // session parsing and causes Voyager to 400 before identity verification.
      "cookie": Object.entries(cookies).map(([name, value]) => `${name}=${value}`).join("; "),
    },
  };
}

function linkedinDirectAuthCandidates() {
  const errors = [];
  const candidates = [];
  for (const source of COOKIE_SOURCES) {
    try {
      candidates.push(linkedinDirectAuthForSource(source));
    } catch (error) {
      errors.push(`${source.name}: ${error.message || String(error)}`);
    }
  }
  if (!candidates.length) throw new Error(`missing LinkedIn authenticated cookies in local browser stores: ${errors.join("; ")}`);
  return candidates;
}

async function linkedinDirectRequest(method, target, body = null, accept = "application/vnd.linkedin.normalized+json+2.1") {
  const candidates = linkedinDirectAuthCandidates();
  const attempts = [];
  for (const auth of candidates) {
    const headers = { ...auth.headers, accept };
    if (body !== null) headers["content-type"] = "application/json; charset=UTF-8";
    const res = await fetch(new URL(target, "https://www.linkedin.com").toString(), {
      method,
      headers,
      body: body === null ? undefined : JSON.stringify(body),
      redirect: "manual",
    });
    const text = await res.text();
    let json = null;
    try { json = text ? JSON.parse(text) : null; } catch {}
    const out = { ok: res.status >= 200 && res.status < 300, status: res.status, location: res.headers.get("location") || "", json, text: json ? "" : text.slice(0, 12000), responseURL: res.url, sourceName: auth.sourceName };
    if (out.ok || ![301, 302, 401, 403].includes(out.status)) return out;
    attempts.push(`${auth.sourceName}:${out.status}`);
  }
  const last = attempts[attempts.length - 1] || "no-attempt";
  return { ok: false, status: 0, location: "", json: null, text: `all LinkedIn cookie sources rejected (${attempts.join(", ") || last})`, responseURL: new URL(target, "https://www.linkedin.com").toString(), sourceName: "" };
}

async function verifyLivePostDirect(url, text) {
  const res = await linkedinDirectRequest("GET", url, null, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
  if (!res.ok) return false;
  return livePostTextMatches(res.text || JSON.stringify(res.json || ""), text);
}

async function postOrDryRunApi(args, text) {
  const meRes = await linkedinDirectRequest("GET", "/voyager/api/me");
  if (!meRes || !meRes.ok) {
    throw new Error(`LinkedIn direct identity request failed: ${JSON.stringify({ status: meRes && meRes.status, location: meRes && meRes.location, responseURL: meRes && meRes.responseURL, text: meRes && meRes.text ? meRes.text.slice(0, 300) : "" })}`);
  }
  const me = extractMe(meRes.json);
  if (me.name !== args.expectedName || me.headline !== args.expectedHeadline) {
    throw new Error(`LinkedIn direct identity mismatch: expected ${args.expectedName} / ${args.expectedHeadline}, got ${me.name || "(missing name)"} / ${me.headline || "(missing headline)"}`);
  }
  if (args.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, method: "linkedin_direct_cookie_voyager_api", identity: { name: me.name, headline: me.headline, plainId: me.plainId } }));
    return;
  }
  const created = await linkedinDirectRequest("POST", "/voyager/api/contentcreation/normShares", postTextPayload(text));
  if (!created || !created.ok) {
    throw new Error(`LinkedIn direct post request failed: ${JSON.stringify({ status: created && created.status, responseURL: created && created.responseURL, text: created && created.text ? created.text.slice(0, 500) : "" })}`);
  }
  const result = extractPostResult(created.json);
  const verified = Boolean(result.url) && await verifyLivePostDirect(result.url, text);
  if (!verified) throw new Error(`LinkedIn API post created but live URL verification failed for ${result.url || "(missing url)"}`);
  console.log(JSON.stringify({ ok: true, url: result.url, verified: true, method: "linkedin_direct_cookie_voyager_api", urn: result.urn, activityUrn: result.activityUrn }));
}

async function postOrDryRunApiWithFallback(args, text) {
  try {
    return await postOrDryRunApi(args, text);
  } catch (error) {
    const message = error && error.message ? error.message : String(error);
    if (message.includes("LinkedIn direct identity request failed")) {
      requireBrowserAllowance(args);
      console.error(`LinkedIn direct identity failed; falling back to page-context Voyager API: ${message}`);
      return postOrDryRunPageApi(args, text);
    }
    throw error;
  }
}

function postOrDryRunPageApi(args, text) {
  ensureLinkedInBackgroundTab(args);
  const me = verifyLinkedInPageIdentity(args);
  if (args.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, method: "linkedin_page_voyager_api", identity: { name: me.name, headline: me.headline, plainId: me.plainId } }));
    return;
  }
  const created = linkedinPageRequest("POST", "/voyager/api/contentcreation/normShares", postTextPayload(text));
  if (!created || !created.ok) {
    throw new Error(`LinkedIn page-context post request failed: ${JSON.stringify({ status: created && created.status, responseURL: created && created.responseURL, text: created && created.text ? created.text.slice(0, 500) : "" })}`);
  }
  const result = extractPostResult(created.json);
  let url = result.url || "";
  let verified = Boolean(url) && verifyLivePost(url, text);
  if (!verified) {
    const recovered = findPostUrlFromActivity(text);
    url = recovered.url || "";
    verified = Boolean(url) && verifyLivePost(url, text);
  }
  if (!verified) {
    throw new Error(`LinkedIn page-context post created but live URL verification failed for ${url || "(missing url)"}`);
  }
  console.log(JSON.stringify({ ok: true, url, verified: true, method: "linkedin_page_voyager_api", urn: result.urn, activityUrn: result.activityUrn }));
}

function postOrDryRunBrowser(args, text) {
  const composer = openComposer(args);
  insertCopy(text, composer.mode);
  return postOrDryRun(args.dryRun, text, composer.mode);
}

function linkedinJS(js) {
  return braveJS(js, { focus: false });
}

function linkedinSetBraveUrl(url) {
  return setBraveUrl(url, { focus: false });
}

function linkedinOpenDedicatedWindow(url, options = {}) {
  return openDedicatedWindow(url, { ...options, focus: false });
}

function linkedinBodySnapshot(maxChars = 3000) {
  return linkedinJS(`(() => {
    const text = document.body ? document.body.innerText : "";
    return JSON.stringify({ ok: true, url: location.href, title: document.title, text: text.slice(0, ${maxChars}) });
  })()`);
}

function visibleEditor() {
  return linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const editors = Array.from(root.querySelectorAll('[contenteditable="true"], .ql-editor, [role="textbox"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        const label = e.getAttribute("aria-label") || "";
        const placeholder = e.getAttribute("data-placeholder") || e.getAttribute("placeholder") || "";
        const editorLike = /text editor|creating content|what do you want|talk about/i.test(label + " " + placeholder)
          || String(e.className || "").includes("ql-editor");
        return r.width > 200 && r.height > 10 && editorLike && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no visible composer editor" });
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, text: el.innerText || "", rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`);
}

function verifyIdentity(expectedName, expectedHeadline) {
  const snap = linkedinBodySnapshot(4000);
  const text = snap.text || "";
  if (!text.includes(expectedName) || !text.includes(expectedHeadline)) {
    throw new Error(`LinkedIn identity mismatch at ${snap.url}: expected ${expectedName} / ${expectedHeadline}`);
  }
}

function openComposer(args) {
  const marker = `8bit-linkedin-${process.pid}`;
  linkedinOpenDedicatedWindow(FEED_URL, { marker, namePrefix: "8bit-linkedin-", host: "www.linkedin.com" });
  waitFor("LinkedIn feed load", () => {
    const snap = linkedinBodySnapshot();
    const text = snap.text || "";
    const identityOk = text.includes(args.expectedName) && text.includes(args.expectedHeadline);
    if (!identityOk) return { ok: false, snap };
    const editor = visibleEditor();
    const composerOk = text.includes("Start a post") || Boolean(editor && editor.ok);
    return { ok: composerOk, snap };
  }, 15000);
  verifyIdentity(args.expectedName, args.expectedHeadline);

  const shareUrlEditor = tryWaitFor("LinkedIn composer from shareActive", () => visibleEditor(), 4000);
  if (shareUrlEditor.ok) return { mode: "dom", ...shareUrlEditor };

  linkedinJS(`(() => { window.scrollTo(0, 0); return JSON.stringify({ ok: true, y: window.scrollY }); })()`);

  waitFor("LinkedIn Start a post visible", () => linkedinJS(`(() => {
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
      .filter(e => {
        const text = ((e.innerText || e.textContent || "").trim());
        const label = e.getAttribute("aria-label") || "";
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (text === "Start a post" || label === "Start a post" || text.includes("Start a post"));
      });
    return JSON.stringify({ ok: candidates.length > 0, count: candidates.length });
  })()`), 12000);

  const clicked = linkedinJS(`(() => {
    const interop = document.querySelector("#interop-outlet");
    if (interop) interop.style.pointerEvents = "none";
    const preferred = Array.from(document.querySelectorAll('button[aria-label], [role="button"][aria-label]'))
      .find(e => {
        const label = e.getAttribute("aria-label") || "";
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && label.includes("Start a post");
      });
    if (preferred) {
      preferred.click();
      preferred.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
      return JSON.stringify({ ok: true, selector: "aria-label", tag: preferred.tagName });
    }
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
      .filter(e => {
        const text = ((e.innerText || e.textContent || "").trim());
        const label = e.getAttribute("aria-label") || "";
        const a = e.closest('a');
        if (a && a.href && a.href.includes('/in/')) return false;
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (text === "Start a post" || label === "Start a post" || text.includes("Start a post"));
      });
    const exact = candidates.filter(e => ((e.innerText || e.textContent || "").trim() === "Start a post") || e.getAttribute("aria-label") === "Start a post");
    const el = (exact[0] || candidates.sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return (ar.width * ar.height) - (br.width * br.height);
    })[0]);
    if (!el) return JSON.stringify({ ok: false, reason: "Start a post not found" });
    const target = el.closest('button, [role="button"], a') || el;
    target.click();
    target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    return JSON.stringify({ ok: true, text: el.innerText || el.getAttribute("aria-label") || "", tag: target.tagName, role: target.getAttribute("role") });
  })()`);
  if (!clicked || !clicked.ok) {
    throw new Error(`LinkedIn Start a post click failed: ${JSON.stringify(clicked)}`);
  }
  const afterDomClick = tryWaitFor("LinkedIn composer after DOM Start a post", () => visibleEditor(), 5000);
  if (afterDomClick.ok) return { mode: "dom", ...afterDomClick };

  const nativeTarget = linkedinJS(`(() => {
    const interop = document.querySelector("#interop-outlet");
    if (interop) interop.style.pointerEvents = "none";
    const preferred = Array.from(document.querySelectorAll('button[aria-label], [role="button"][aria-label]'))
      .find(e => {
        const label = e.getAttribute("aria-label") || "";
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && label.includes("Start a post");
      });
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
      .filter(e => {
        const text = ((e.innerText || e.textContent || "").trim());
        const label = e.getAttribute("aria-label") || "";
        const a = e.closest('a');
        if (a && a.href && a.href.includes('/in/')) return false;
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (text === "Start a post" || label === "Start a post" || text.includes("Start a post"));
      });
    const exact = candidates.filter(e => ((e.innerText || e.textContent || "").trim() === "Start a post") || e.getAttribute("aria-label") === "Start a post");
    const el = preferred || exact.find(e => e.matches('button, [role="button"]')) || exact[0] || candidates[0];
    if (!el) return JSON.stringify({ ok: false, reason: "Start a post not found for native click" });
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, rect: { x: r.x, y: r.y, w: r.width, h: r.height }, innerHeight: window.innerHeight });
  })()`);
  if (nativeTarget && nativeTarget.ok) {
    nativeClickElement(nativeTarget.rect, nativeTarget.innerHeight);
    const afterNativeClick = tryWaitFor("LinkedIn composer after native Start a post", () => visibleEditor(), 7000);
    if (afterNativeClick.ok) return { mode: "dom", ...afterNativeClick };
  }

  throw new Error(`LinkedIn browser recovery could not open the composer: ${JSON.stringify({ clicked, nativeTarget })}`);
}

function focusAndClearEditor() {
  const focused = linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const editors = Array.from(root.querySelectorAll('[contenteditable="true"], .ql-editor, [role="textbox"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        const label = e.getAttribute("aria-label") || "";
        const placeholder = e.getAttribute("data-placeholder") || e.getAttribute("placeholder") || "";
        const editorLike = /text editor|creating content|what do you want|talk about/i.test(label + " " + placeholder)
          || String(e.className || "").includes("ql-editor");
        return r.width > 200 && r.height > 10 && editorLike && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no editor" });
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand("delete");
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward", data: null }));
    return JSON.stringify({ ok: true });
  })()`);
  if (!focused || !focused.ok) {
    throw new Error(`could not focus LinkedIn composer: ${JSON.stringify(focused)}`);
  }
}

function directInsertCopy(text) {
  const inserted = linkedinJS(`(() => {
    const text = ${JSON.stringify(text)};
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const editors = Array.from(root.querySelectorAll('[contenteditable="true"], .ql-editor, [role="textbox"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        const label = e.getAttribute("aria-label") || "";
        const placeholder = e.getAttribute("data-placeholder") || e.getAttribute("placeholder") || "";
        const editorLike = /text editor|creating content|what do you want|talk about/i.test(label + " " + placeholder)
          || String(e.className || "").includes("ql-editor");
        return r.width > 200 && r.height > 10 && editorLike && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no editor" });
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand("delete");
    const ok = document.execCommand("insertText", false, text);
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
    return JSON.stringify({ ok, text: el.innerText || el.textContent || "" });
  })()`);
  if (!inserted || !inserted.ok) {
    throw new Error(`LinkedIn direct composer insertion failed: ${JSON.stringify(inserted)}`);
  }
  return inserted;
}

function insertCopy(text, mode) {
  if (mode === "native") {
    throw new Error("LinkedIn background mode refused native paste/click fallback.");
  }
  focusAndClearEditor();
  const direct = waitFor("LinkedIn direct composer insertion", () => {
    directInsertCopy(text);
    const editor = visibleEditor();
    return { ok: editor.ok && normalize(editor.text) === normalize(text), editor };
  }, 4000);
  if (!direct.ok) {
    throw new Error(`LinkedIn direct composer insertion failed: ${JSON.stringify(direct)}`);
  }
}

function postButtonState() {
  return linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const buttons = Array.from(root.querySelectorAll('button, [role="button"]'))
      .filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
    const post = buttons.find(b => ((b.innerText || "").trim() === "Post") || b.getAttribute("aria-label") === "Post");
    if (!post) return JSON.stringify({ ok: false, reason: "Post button not found" });
    return JSON.stringify({ ok: true, disabled: post.disabled || post.getAttribute("aria-disabled") === "true" });
  })()`);
}

function closeDraft() {
  const close = linkedinJS(`(() => {
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) return JSON.stringify({ ok: true, alreadyClosed: true });
    const buttons = Array.from(dialog.querySelectorAll('button'))
      .filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
    const closeButton = buttons.find(b => /dismiss|close/i.test(b.getAttribute("aria-label") || ""))
      || buttons.find(b => (b.innerText || "").trim() === "Cancel");
    if (!closeButton) return JSON.stringify({ ok: false, reason: "close button not found" });
    closeButton.click();
    return JSON.stringify({ ok: true });
  })()`);
  if (!close || !close.ok) return close;

  tryWaitFor("LinkedIn discard dialog", () => linkedinJS(`(() => {
    const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
      .filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
    const discard = buttons.find(b => /^(discard|discard post)$/i.test(((b.innerText || b.textContent || "").trim())));
    if (!discard) return JSON.stringify({ ok: false, reason: "discard button not visible" });
    discard.click();
    return JSON.stringify({ ok: true });
  })()`), 3000);

  return waitFor("LinkedIn draft modal cleanup", () => {
    const editor = visibleEditor();
    return { ok: !editor.ok, editor };
  }, 9000);
}

function clickPost() {
  const clicked = linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const post = Array.from(root.querySelectorAll('button, [role="button"]'))
      .find(b => ((b.innerText || "").trim() === "Post") || b.getAttribute("aria-label") === "Post");
    if (!post || post.disabled || post.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    post.click();
    return JSON.stringify({ ok: true });
  })()`);
  if (!clicked || !clicked.ok) {
    return clickNativePost();
  }
  return clicked;
}

function postSuccessProbe() {
  return linkedinJS(`(() => {
    const toastRoots = Array.from(document.querySelectorAll('[role="alert"], [role="status"], .artdeco-toast-item, .artdeco-toast-item__content, .artdeco-toasts'));
    for (const root of toastRoots) {
      const t = ((root.innerText || root.textContent || "") || "").trim();
      if (!t || !/post/i.test(t)) continue;
      const link = Array.from(root.querySelectorAll('a'))
        .find(a => (a && a.href && a.href.includes('/feed/update/')));
      return JSON.stringify({ ok: true, url: link ? link.href : "", toast: t.slice(0, 240) });
    }
    return JSON.stringify({ ok: false, url: "" });
  })()`);
}

function postClickEffect() {
  const success = postSuccessProbe();
  if (success && success.ok) return success;
  const draft = linkedinJS(`(() => {
    const editor = Array.from(document.querySelectorAll('[contenteditable="true"]'))
      .find(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 200 || r.height < 40) return false;
        const style = getComputedStyle(e);
        return style.display !== "none" && style.visibility !== "hidden" && String(e.innerText || e.textContent || "").trim();
      });
    return JSON.stringify({ ok: true, open: Boolean(editor) });
  })()`);
  if (draft && draft.open) return { ok: false, reason: "draft still open" };
  const state = postButtonState();
  return { ok: !state || !state.ok || Boolean(state.disabled), state };
}

function openDraftState(text) {
  return linkedinJS(`(() => {
    const expected = ${JSON.stringify(normalize(text))};
    const editors = Array.from(document.querySelectorAll('[contenteditable="true"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 200 || r.height < 40) return false;
        const style = getComputedStyle(e);
        return style.display !== "none" && style.visibility !== "hidden";
      })
      .map(e => (e.innerText || e.textContent || ""))
      .filter(Boolean)
      .sort((a, b) => b.length - a.length);
    const got = String(editors[0] || "");
    const normalized = got.trim().toLowerCase().replace(/\\s+/g, " ");
    return JSON.stringify({
      ok: true,
      open: Boolean(got) && normalized.includes(expected.slice(0, 60)),
      text: got.slice(0, 180),
      url: location.href
    });
  })()`);
}

function frontWindowBounds() {
  const proc = spawnSync("osascript", ["-"], {
    input: `tell application id "com.brave.Browser"\n  activate\n  return bounds of front window\nend tell\n`,
    encoding: "utf8",
    maxBuffer: 1024 * 128,
    timeout: 10000,
  });
  if (proc.status !== 0 || proc.error) {
    throw new Error((proc.stderr || (proc.error && proc.error.message) || "could not read Brave bounds").trim());
  }
  const nums = proc.stdout.trim().split(",").map(v => Number(v.trim())).filter(Number.isFinite);
  if (nums.length !== 4) throw new Error(`could not parse Brave bounds: ${proc.stdout.trim()}`);
  return { left: nums[0], top: nums[1], right: nums[2], bottom: nums[3], width: nums[2] - nums[0], height: nums[3] - nums[1] };
}

function decodePngRgba(filePath) {
  const data = fs.readFileSync(filePath);
  if (!data.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    throw new Error("screen capture was not PNG");
  }
  let pos = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  let interlace = 0;
  const idat = [];
  while (pos < data.length) {
    const len = data.readUInt32BE(pos);
    const type = data.subarray(pos + 4, pos + 8).toString("ascii");
    const chunk = data.subarray(pos + 8, pos + 8 + len);
    pos += len + 12;
    if (type === "IHDR") {
      width = chunk.readUInt32BE(0);
      height = chunk.readUInt32BE(4);
      bitDepth = chunk[8];
      colorType = chunk[9];
      interlace = chunk[12];
    } else if (type === "IDAT") {
      idat.push(chunk);
    } else if (type === "IEND") {
      break;
    }
  }
  if (bitDepth !== 8 || colorType !== 6 || interlace !== 0) {
    throw new Error(`unsupported PNG format: bitDepth=${bitDepth} colorType=${colorType} interlace=${interlace}`);
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const bpp = 4;
  const stride = width * bpp;
  const pixels = Buffer.alloc(width * height * bpp);
  let offset = 0;
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[offset];
    offset += 1;
    const scan = raw.subarray(offset, offset + stride);
    offset += stride;
    const recon = Buffer.alloc(stride);
    for (let x = 0; x < stride; x += 1) {
      const a = x >= bpp ? recon[x - bpp] : 0;
      const b = prev[x];
      const c = x >= bpp ? prev[x - bpp] : 0;
      const v = scan[x];
      let r;
      if (filter === 0) r = v;
      else if (filter === 1) r = (v + a) & 255;
      else if (filter === 2) r = (v + b) & 255;
      else if (filter === 3) r = (v + Math.floor((a + b) / 2)) & 255;
      else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        const pr = pa <= pb && pa <= pc ? a : (pb <= pc ? b : c);
        r = (v + pr) & 255;
      } else {
        throw new Error(`unsupported PNG filter ${filter}`);
      }
      recon[x] = r;
    }
    recon.copy(pixels, y * stride);
    prev = recon;
  }
  return { width, height, pixels };
}

function findVisibleBluePostButton() {
  const bounds = frontWindowBounds();
  const capture = path.join(os.tmpdir(), `linkedin-post-${process.pid}-${Date.now()}.png`);
  const cap = spawnSync("screencapture", ["-x", capture], { encoding: "utf8", timeout: 10000 });
  if (cap.status !== 0 || cap.error) {
    throw new Error((cap.stderr || (cap.error && cap.error.message) || "screencapture failed").trim());
  }
  try {
    const { width, height, pixels } = decodePngRgba(capture);
    const scale = Math.round(width / 1728) || 2;
    const minX = Math.max(0, Math.floor(bounds.left * scale));
    const maxX = Math.min(width - 1, Math.ceil(bounds.right * scale));
    const minY = Math.max(0, Math.floor((bounds.top + 160) * scale));
    const maxY = Math.min(height - 1, Math.ceil((bounds.bottom - 80) * scale));
    const seen = new Uint8Array(width * height);
    const candidates = [];
    const isBlue = (x, y) => {
      if (x < minX || x > maxX || y < minY || y > maxY) return false;
      const o = (y * width + x) * 4;
      const r = pixels[o], g = pixels[o + 1], b = pixels[o + 2], a = pixels[o + 3];
      return a > 200 && r < 80 && g >= 80 && g <= 180 && b >= 135 && b > g + 20;
    };
    for (let y = minY; y <= maxY; y += 1) {
      for (let x = minX; x <= maxX; x += 1) {
        const idx = y * width + x;
        if (seen[idx] || !isBlue(x, y)) continue;
        const stack = [[x, y]];
        seen[idx] = 1;
        let count = 0, sumX = 0, sumY = 0, loX = x, hiX = x, loY = y, hiY = y;
        while (stack.length) {
          const [cx, cy] = stack.pop();
          count += 1;
          sumX += cx;
          sumY += cy;
          loX = Math.min(loX, cx); hiX = Math.max(hiX, cx);
          loY = Math.min(loY, cy); hiY = Math.max(hiY, cy);
          for (const [nx, ny] of [[cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]]) {
            const nidx = ny * width + nx;
            if (nx >= minX && nx <= maxX && ny >= minY && ny <= maxY && !seen[nidx] && isBlue(nx, ny)) {
              seen[nidx] = 1;
              stack.push([nx, ny]);
            }
          }
        }
        const w = hiX - loX + 1;
        const h = hiY - loY + 1;
        if (count >= 800 && w >= 70 && w <= 260 && h >= 28 && h <= 110) {
          candidates.push({ count, x: sumX / count / scale, y: sumY / count / scale, rect: { x: loX / scale, y: loY / scale, w: w / scale, h: h / scale } });
        }
      }
    }
    candidates.sort((a, b) => (b.y - a.y) || (b.count - a.count));
    const chosen = candidates[0];
    if (!chosen) throw new Error(`visible blue Post button not found in screenshot; bounds=${JSON.stringify(bounds)}`);
    return { ok: true, ...chosen, candidates: candidates.slice(0, 5) };
  } finally {
    try { fs.unlinkSync(capture); } catch {}
  }
}

function clickNativePost() {
  const target = linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const post = Array.from(root.querySelectorAll('button, [role="button"]'))
      .find(b => ((b.innerText || "").trim() === "Post") || b.getAttribute("aria-label") === "Post");
    if (!post || post.disabled || post.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    const r = post.getBoundingClientRect();
    if (!r || r.width <= 0 || r.height <= 0) return JSON.stringify({ ok: false });
    return JSON.stringify({
      ok: true,
      rect: { x: r.x, y: r.y, w: r.width, h: r.height },
      innerHeight: window.innerHeight,
      screen: {
        x: window.screenX + r.x + (r.width / 2),
        y: window.screenY + (window.outerHeight - window.innerHeight) + r.y + (r.height / 2),
        screenX: window.screenX,
        screenY: window.screenY,
        outerHeight: window.outerHeight,
        innerHeight: window.innerHeight
      }
    });
  })()`);
  const attempts = [];
  const domClick = linkedinJS(`(() => {
    const dialog = Array.from(document.querySelectorAll('[role="dialog"]'))
      .find(d => {
        const r = d.getBoundingClientRect();
        return r.width > 300 && r.height > 200 && getComputedStyle(d).display !== "none" && getComputedStyle(d).visibility !== "hidden";
      });
    const root = dialog || document;
    const post = Array.from(root.querySelectorAll('button, [role="button"]'))
      .find(b => ((b.innerText || "").trim() === "Post") || b.getAttribute("aria-label") === "Post");
    if (!post || post.disabled || post.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    post.click();
    post.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    return JSON.stringify({ ok: true });
  })()`);
  if (domClick && domClick.ok) {
    attempts.push("dom");
    const effect = tryWaitFor("LinkedIn post click effect after DOM click", postClickEffect, 4000);
    if (effect.ok) return { ok: true, method: "dom", effect };
  }
  if (clickAXButton("Post")) {
    attempts.push("accessibility");
    const effect = tryWaitFor("LinkedIn post click effect after accessibility click", postClickEffect, 4000);
    if (effect.ok) return { ok: true, method: "accessibility", effect };
  }
  if (target && target.ok && target.screen) {
    const clicked = nativeClickScreenPoint(target.screen.x, target.screen.y);
    attempts.push("screen-point");
    const effect = tryWaitFor("LinkedIn post click effect after screen-point click", postClickEffect, 5000);
    if (effect.ok) return { ok: true, method: "screen-point", clicked, effect };
  }
  if (target && target.ok) {
    nativeClickElement(target.rect, target.innerHeight);
    attempts.push("window-bounds");
    const effect = tryWaitFor("LinkedIn post click effect after window-bounds click", postClickEffect, 4000);
    if (effect.ok) return { ok: true, method: "window-bounds", effect };
  }
  const screenshotTarget = findVisibleBluePostButton();
  nativeClickScreenPoint(screenshotTarget.x, screenshotTarget.y);
  attempts.push("screenshot-blue-button");
  const effect = tryWaitFor("LinkedIn post click effect after screenshot-blue-button click", postClickEffect, 8000);
  if (effect.ok) return { ok: true, method: "screenshot-blue-button", clicked: { x: screenshotTarget.x, y: screenshotTarget.y }, effect };
  throw new Error(`LinkedIn post click did not affect composer: ${JSON.stringify({ attempts, target, domClick, screenshotTarget })}`);
}

function waitForPostSuccess() {
  return waitFor("LinkedIn post success", postSuccessProbe, 45000);
}

function findPostUrlFromActivity(text) {
  const marker = `8bit-linkedin-activity-${process.pid}`;
  linkedinOpenDedicatedWindow(ACTIVITY_ALL_URL, { marker, namePrefix: "8bit-linkedin-", host: "www.linkedin.com" });
  waitFor("LinkedIn activity cards", () => linkedinJS(`(() => {
    const cards = document.querySelectorAll('div.feed-shared-update-v2');
    const url = location.href || "";
    return JSON.stringify({ ok: url.includes("recent-activity") && cards.length > 0, cardCount: cards.length, url });
  })()`), 15000);

  const match = waitFor("LinkedIn activity exact text match", () => linkedinJS(`(() => {
    const normalize = (t) => String(t || '').trim().toLowerCase().replace(/\\s+/g, ' ');
    const needle = normalize(${JSON.stringify(text)}).slice(0, 110);
    const cards = Array.from(document.querySelectorAll('div.feed-shared-update-v2')).slice(0, 4);
    for (const card of cards) {
      const body = normalize(card.innerText || card.textContent || '');
      if (!body.includes(needle)) continue;
      const anchors = Array.from(card.querySelectorAll('a')).map(a => a && a.href ? a.href : '').filter(Boolean);
      const direct = anchors.find(h => h.includes('/feed/update/'));
      if (direct) return JSON.stringify({ ok: true, url: direct, method: 'activity_card_exact' });
      for (const href of anchors) {
        const m = href.match(/urn:li:activity:(\\d+)/);
        if (m && m[1]) return JSON.stringify({ ok: true, url: 'https://www.linkedin.com/feed/update/urn:li:activity:' + m[1] + '/', method: 'activity_card_exact' });
      }
      const post = anchors.find(h => h.includes('/posts/'));
      if (post) return JSON.stringify({ ok: true, url: post, method: 'activity_card_exact' });
      return JSON.stringify({ ok: false, reason: 'matching card had no permalink' });
    }
    return JSON.stringify({ ok: false, reason: 'no recent activity card matched exact text', checked: cards.length });
  })()`), 15000);

  if (match && match.ok && verifyLivePost(match.url, text)) return match;
  return { ok: false, url: "", method: "activity_card_exact", reason: match && match.reason ? match.reason : "no verified exact text match" };
}

function verifyLivePost(url, text) {
  linkedinSetBraveUrl(url);
  const result = tryWaitFor("LinkedIn live post verification", () => {
    const snap = linkedinBodySnapshot(12000);
    return { ok: livePostTextMatches(snap.text || "", text), url: snap.url };
  }, 6000);
  return Boolean(result.ok);
}

function closeNativeDraft() {
  return closeDraft();
}

function postOrDryRun(dryRun, text, mode) {
  if (mode === "native") {
    throw new Error("LinkedIn background mode refused native post fallback.");
  }
  const state = postButtonState();
  if (!state || !state.ok || state.disabled) {
    throw new Error(`Post button not ready: ${JSON.stringify(state)}`);
  }
  if (dryRun) {
    const cleanup = closeDraft();
    console.log(JSON.stringify({ ok: true, dryRun: true, cleaned: Boolean(cleanup && cleanup.ok) }));
    return;
  }
  clickPost();
  const result = tryWaitFor("LinkedIn post success", postSuccessProbe, 45000);
  let url = result.url;
  if (!url) {
    const draft = openDraftState(text);
    if (draft && draft.open) {
      throw new Error(`LinkedIn post did not submit; draft is still open at ${draft.url}`);
    }
    const recovered = findPostUrlFromActivity(text);
    url = recovered.url;
  }
  let verified = Boolean(url) && verifyLivePost(url, text);
  if (!verified) {
    const draft = openDraftState(text);
    if (draft && draft.open) {
      throw new Error(`LinkedIn live URL verification blocked because draft is still open at ${draft.url}`);
    }
    const recovered = findPostUrlFromActivity(text);
    url = recovered.url;
    verified = Boolean(url) && verifyLivePost(url, text);
  }
  if (!verified) {
    throw new Error(`LinkedIn live URL verification failed for ${url || "(missing url)"}`);
  }
  console.log(JSON.stringify({ ok: true, url, verified }));
}

function main() {
  const args = parseArgs(process.argv);
  const text = readText(args);
  if (!text) throw new Error("post text is empty");

  const run = () => {
    if (process.env.SOCIAL_LINKEDIN_FORCE_BROWSER === "1") {
      return Promise.resolve().then(() => postOrDryRunBrowser(args, text));
    }
    if (!args.recoverOnly) return postOrDryRunApiWithFallback(args, text);
    return Promise.resolve().then(() => {
      const recovered = findPostUrlFromActivity(text);
      const verified = Boolean(recovered.url) && verifyLivePost(recovered.url, text);
      if (!verified) {
        throw new Error(`LinkedIn recover-only verification failed for ${recovered.url || "(missing url)"}`);
      }
      console.log(JSON.stringify({ ok: true, url: recovered.url, verified, recovered: true, method: recovered.method || "" }));
    });
  };

  return runWithLease({
    owner: "8bit-linkedin-brave-post",
    reason: args.dryRun ? "dry-run LinkedIn background posting flow" : "publish LinkedIn post through background HTTPS",
    ttl: 900,
    skip: args.skipLease,
  }, run);
}

Promise.resolve()
  .then(() => main())
  .catch(error => {
    const cause = error && error.cause ? `\nCause: ${error.cause.code || error.cause.message || String(error.cause)}` : "";
    console.error(`${(error && error.stack) || (error && error.message) || String(error)}${cause}`);
    process.exit(1);
  });
