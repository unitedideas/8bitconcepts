#!/usr/bin/env node
/*
 * Supervised X publisher for the authenticated Brave session.
 *
 * This is for one-shot recovery or explicit live posting while API credentials
 * are unavailable. It verifies the active @8bitconcepts session, uses DOM
 * selectors only, verifies copied content before clicking Post, and returns the
 * live status URL after publication.
 */
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const {
  bodySnapshot,
  braveJS,
  cdpClickElement,
  cdpInputText,
  cdpPasteText,
  getClipboard,
  markActiveWindow,
  nativeClickElement,
  nudgeFocusedElement,
  normalize,
  openDedicatedWindow,
  pasteIntoFocusedElement,
  runWithLease,
  setBraveUrl,
  setClipboard,
  sleep,
  typeIntoFocusedElement,
  tryWaitFor,
  waitFor,
} = require("./social-brave-common");

const HOME_URL = "https://x.com/home";
const COMPOSE_URL = "https://x.com/compose/post";
const PROFILE_BASE = "https://x.com";
const DEFAULT_HANDLE = "8BitConcepts";
const BRAVE_COOKIE_DB = `${os.homedir()}/Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies`;
const BRAVE_SAFE_STORAGE_SERVICE = "Brave Safe Storage";

let xWebConfigCache = null;

function usage() {
  console.error("usage: node tools/x-brave-post.js (--text <copy> | --text-file <path> | --delete <statusUrlOrId>) [--expected-handle <handle>] [--dry-run] [--json] [--skip-lease]");
  process.exit(2);
}

function parseArgs(argv) {
  const args = {
    dryRun: false,
    expectedHandle: DEFAULT_HANDLE,
    json: false,
    skipLease: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--json") args.json = true;
    else if (arg === "--skip-lease") args.skipLease = true;
    else if (arg === "--text") args.text = argv[++i];
    else if (arg === "--text-file") args.textFile = argv[++i];
    else if (arg === "--delete") args.deleteTarget = argv[++i];
    else if (arg === "--expected-handle") args.expectedHandle = argv[++i];
    else usage();
  }
  if (args.deleteTarget) {
    if (args.text || args.textFile) usage();
    const match = String(args.deleteTarget).match(/(\d{6,})/);
    if (!match) usage();
    args.deleteId = match[1];
  } else {
    if (!args.text && !args.textFile) usage();
    if (args.text && args.textFile) usage();
  }
  args.expectedHandle = args.expectedHandle.replace(/^@/, "");
  return args;
}

function readText(args) {
  const text = args.textFile ? fs.readFileSync(args.textFile, "utf8") : args.text;
  return String(text || "").trim();
}

function sqliteQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function braveSafeStorageKey() {
  const proc = spawnSync("security", ["find-generic-password", "-w", "-s", BRAVE_SAFE_STORAGE_SERVICE], {
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

function readBraveCookies(host) {
  if (!fs.existsSync(BRAVE_COOKIE_DB)) {
    throw new Error(`Brave cookie DB not found at ${BRAVE_COOKIE_DB}`);
  }
  const proc = spawnSync("sqlite3", [BRAVE_COOKIE_DB, `select name,hex(encrypted_value) from cookies where host_key=${sqliteQuote(host)};`], {
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
    timeout: 10000,
  });
  if (proc.status !== 0 || proc.error) {
    throw new Error((proc.stderr || (proc.error && proc.error.message) || "could not read Brave cookies").trim());
  }
  const key = braveSafeStorageKey();
  const cookies = {};
  for (const row of proc.stdout.trim().split(/\n/).filter(Boolean)) {
    const [name, encryptedHex] = row.split("|");
    cookies[name] = decryptBraveCookie(host, encryptedHex, key);
  }
  return cookies;
}

function xCookieAuth() {
  const cookies = {
    ...readBraveCookies(".twitter.com"),
    ...readBraveCookies(".x.com"),
    ...readBraveCookies("x.com"),
  };
  for (const name of ["auth_token", "ct0", "twid"]) {
    if (!cookies[name]) throw new Error(`missing Brave X cookie: ${name}`);
  }
  const cookie = Object.entries(cookies)
    .map(([name, value]) => `${name}=${String(value).replace(/;/g, "%3B")}`)
    .join("; ");
  return { cookies, cookie };
}

function parseOperation(mainJs, operationName) {
  const escaped = operationName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = mainJs.match(new RegExp(`queryId:"([^"]+)",operationName:"${escaped}"[\\s\\S]*?metadata:\\{featureSwitches:\\[([^\\]]*)\\],fieldToggles:\\[([^\\]]*)\\]`));
  if (!match) throw new Error(`could not find X ${operationName} operation metadata`);
  const parseNames = value => Object.fromEntries([...value.matchAll(/"([^"]+)"/g)].map(item => [item[1], true]));
  return {
    queryId: match[1],
    features: parseNames(match[2]),
    fieldToggles: parseNames(match[3]),
  };
}

function parseOperationOptional(mainJs, operationName) {
  try {
    return parseOperation(mainJs, operationName);
  } catch (_) {
    return null;
  }
}

async function xWebConfig() {
  if (xWebConfigCache) return xWebConfigCache;
  const { cookie } = xCookieAuth();
  const home = await fetch(HOME_URL, {
    headers: {
      "cookie": cookie,
      "user-agent": "Mozilla/5.0",
    },
  });
  const html = await home.text();
  if (!home.ok || !html.includes("8BitConcepts")) {
    throw new Error(`X authenticated home fetch failed: status ${home.status}`);
  }
  const mainUrl = (html.match(/https:\/\/abs\.twimg\.com\/responsive-web\/client-web\/main\.[^"']+\.js/) || [])[0];
  if (!mainUrl) throw new Error("could not find X main JS bundle URL");
  const mainRes = await fetch(mainUrl, { headers: { "user-agent": "Mozilla/5.0" } });
  const mainJs = await mainRes.text();
  if (!mainRes.ok) throw new Error(`could not fetch X main JS bundle: status ${mainRes.status}`);
  const bearer = (mainJs.match(/AAAAAAAAAAAAA[A-Za-z0-9%_-]+/) || [])[0];
  if (!bearer) throw new Error("could not find X web bearer token");
  xWebConfigCache = {
    bearer,
    operations: {
      CreateTweet: parseOperation(mainJs, "CreateTweet"),
      DeleteTweet: parseOperation(mainJs, "DeleteTweet"),
      TweetResultByRestId: parseOperation(mainJs, "TweetResultByRestId"),
      UserByScreenName: parseOperation(mainJs, "UserByScreenName"),
      UserTweets: parseOperationOptional(mainJs, "UserTweets"),
    },
  };
  return xWebConfigCache;
}

async function xApiRequest(method, target, body = null) {
  const { cookies, cookie } = xCookieAuth();
  const config = await xWebConfig();
  const headers = {
    "authorization": `Bearer ${config.bearer}`,
    "cookie": cookie,
    "origin": "https://x.com",
    "referer": "https://x.com/home",
    "user-agent": "Mozilla/5.0",
    "x-csrf-token": cookies.ct0,
    "x-twitter-active-user": "yes",
    "x-twitter-auth-type": "OAuth2Session",
    "x-twitter-client-language": "en",
  };
  if (body !== null) headers["content-type"] = "application/json";
  const res = await fetch(new URL(target, "https://x.com").toString(), {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let json = null;
  try { json = text ? JSON.parse(text) : null; } catch {}
  return { ok: res.status >= 200 && res.status < 300, status: res.status, json, text: json ? "" : text.slice(0, 12000), responseURL: res.url };
}

async function verifyAccountDirect(expectedHandle) {
  const config = await xWebConfig();
  const op = config.operations.UserByScreenName;
  const query = new URLSearchParams({
    variables: JSON.stringify({ screen_name: expectedHandle, withSafetyModeUserFields: true }),
    features: JSON.stringify(op.features),
    fieldToggles: JSON.stringify(op.fieldToggles),
  });
  const res = await xApiRequest("GET", `/i/api/graphql/${op.queryId}/UserByScreenName?${query}`);
  const result = res.json && res.json.data && res.json.data.user && res.json.data.user.result;
  const screenName = result && result.core && result.core.screen_name;
  const name = result && result.core && result.core.name;
  if (!res.ok || !screenName || screenName.toLowerCase() !== expectedHandle.toLowerCase()) {
    throw new Error(`X direct identity mismatch: expected @${expectedHandle}, got @${screenName || "(missing)"} status ${res.status}`);
  }
  return { id: result.rest_id, screenName, name };
}

function createTweetPayload(text) {
  return {
    variables: {
      tweet_text: text,
      dark_request: false,
      media: { media_entities: [], possibly_sensitive: false },
      semantic_annotation_ids: [],
      disallowed_reply_options: null,
    },
    features: xWebConfigCache.operations.CreateTweet.features,
    queryId: xWebConfigCache.operations.CreateTweet.queryId,
  };
}

async function verifyTweetDirect(tweetId, text) {
  const config = await xWebConfig();
  const op = config.operations.TweetResultByRestId;
  const query = new URLSearchParams({
    variables: JSON.stringify({ tweetId, withCommunity: false, includePromotedContent: false, withVoice: false }),
    features: JSON.stringify(op.features),
    fieldToggles: JSON.stringify(op.fieldToggles),
  });
  const res = await xApiRequest("GET", `/i/api/graphql/${op.queryId}/TweetResultByRestId?${query}`);
  const result = res.json && res.json.data && res.json.data.tweetResult && res.json.data.tweetResult.result;
  const fullText = result && result.legacy && result.legacy.full_text;
  return Boolean(res.ok && fullText && normalize(fullText).includes(normalize(text).slice(0, 90)));
}

function collectTweets(value, tweets = []) {
  if (!value || typeof value !== "object") return tweets;
  if (value.legacy && value.legacy.full_text && value.rest_id) {
    tweets.push(value);
  }
  for (const child of Object.values(value)) {
    if (child && typeof child === "object") collectTweets(child, tweets);
  }
  return tweets;
}

async function findPostedTweetDirect(expectedHandle, text) {
  const account = await verifyAccountDirect(expectedHandle);
  const config = await xWebConfig();
  const op = config.operations.UserTweets;
  if (!op) throw new Error("could not find X UserTweets operation metadata");
  const query = new URLSearchParams({
    variables: JSON.stringify({ userId: account.id, count: 20, includePromotedContent: false, withQuickPromoteEligibilityTweetFields: true, withVoice: false }),
    features: JSON.stringify(op.features),
    fieldToggles: JSON.stringify(op.fieldToggles),
  });
  const res = await xApiRequest("GET", `/i/api/graphql/${op.queryId}/UserTweets?${query}`);
  if (!res.ok || !res.json) {
    throw new Error(`X direct timeline fetch failed: ${JSON.stringify({ status: res.status, errors: res.json && res.json.errors, text: res.text ? res.text.slice(0, 500) : "" })}`);
  }
  const target = normalize(text);
  const prefix = target.slice(0, 90);
  const tweet = collectTweets(res.json).find(item => {
    const fullText = normalize(item.legacy && item.legacy.full_text || "");
    return fullText === target || fullText.includes(prefix);
  });
  if (!tweet) throw new Error("X direct timeline did not contain the expected post text");
  return `${PROFILE_BASE}/${account.screenName}/status/${tweet.rest_id}`;
}

async function postOrDryRunDirect(args, text) {
  const account = await verifyAccountDirect(args.expectedHandle);
  if (args.dryRun) {
    const payload = { ok: true, dryRun: true, method: "x_direct_cookie_graphql_api", identity: account };
    console.log(JSON.stringify(payload));
    return;
  }
  await xWebConfig();
  try {
    const existingUrl = await findPostedTweetDirect(args.expectedHandle, text);
    if (args.json) console.log(JSON.stringify({ ok: true, url: existingUrl, verified: true, method: "x_direct_existing_recovery" }));
    else console.log(existingUrl);
    return;
  } catch (_) {}
  const op = xWebConfigCache.operations.CreateTweet;
  const created = await xApiRequest("POST", `/i/api/graphql/${op.queryId}/CreateTweet`, createTweetPayload(text));
  const tweet = created.json && created.json.data && created.json.data.create_tweet && created.json.data.create_tweet.tweet_results && created.json.data.create_tweet.tweet_results.result;
  const tweetId = tweet && tweet.rest_id;
  const fullText = tweet && tweet.legacy && tweet.legacy.full_text;
  if (created.ok && !tweetId) {
    // X returned 2xx without a usable tweet ID. Body may be empty, empty {}, or a JSON object that lacks data.create_tweet.tweet_results.result.
    // In any of these cases the post may have been silently created — verify through the authenticated timeline before any browser fallback.
    let recoveredUrl = null;
    for (let attempt = 0; attempt < 3 && !recoveredUrl; attempt++) {
      if (attempt > 0) sleep(15000);
      try { recoveredUrl = await findPostedTweetDirect(args.expectedHandle, text); } catch (_) {}
      if (!recoveredUrl) {
        try { recoveredUrl = findPostedTweet(args.expectedHandle, text); } catch (_) {}
      }
    }
    if (recoveredUrl) {
      if (args.json) console.log(JSON.stringify({ ok: true, url: recoveredUrl, verified: true, method: "x_direct_empty_200_recovery" }));
      else console.log(recoveredUrl);
      return;
    }
    throw new Error("EMPTY_200_NO_FALLBACK: X direct API returned empty 200; status likely created but unverifiable. Skipping browser fallback to prevent duplicate post.");
  }
  if (!created.ok || !tweetId || normalize(fullText || "") !== normalize(text)) {
    throw new Error(`X direct post request failed: ${JSON.stringify({ status: created.status, responseURL: created.responseURL, text: created.text ? created.text.slice(0, 500) : "", errors: created.json && created.json.errors })}`);
  }
  const verified = await verifyTweetDirect(tweetId, text);
  if (!verified) throw new Error(`X API post created but live status verification failed for ${tweetId}`);
  const url = `${PROFILE_BASE}/${account.screenName}/status/${tweetId}`;
  if (args.json) console.log(JSON.stringify({ ok: true, url, verified: true, method: "x_direct_cookie_graphql_api" }));
  else console.log(url);
}

async function deleteDirect(args) {
  const account = await verifyAccountDirect(args.expectedHandle);
  if (args.dryRun) {
    if (args.json) console.log(JSON.stringify({ ok: true, dryRun: true, method: "x_direct_delete", id: args.deleteId, identity: account }));
    else console.log(`would delete ${args.deleteId}`);
    return;
  }
  await xWebConfig();
  const op = xWebConfigCache.operations.DeleteTweet;
  const res = await xApiRequest("POST", `/i/api/graphql/${op.queryId}/DeleteTweet`, {
    variables: { tweet_id: args.deleteId, dark_request: false },
    queryId: op.queryId,
  });
  const success = res.json && res.json.data && res.json.data.delete_tweet && res.json.data.delete_tweet.tweet_results;
  if (!res.ok || !success) {
    throw new Error(`X DeleteTweet failed: ${JSON.stringify({ status: res.status, errors: res.json && res.json.errors, text: res.text ? res.text.slice(0, 500) : "" })}`);
  }
  if (args.json) console.log(JSON.stringify({ ok: true, deleted: args.deleteId, method: "x_direct_delete", identity: account }));
  else console.log(`deleted ${args.deleteId}`);
}

function profileHref() {
  return braveJS(`(() => {
    const host = location.hostname;
    const link = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
    return JSON.stringify({ ok: host.endsWith("x.com") && Boolean(link), host, href: link ? link.href : "", body: document.body ? document.body.innerText.slice(0, 1000) : "" });
  })()`);
}

function verifyAccount(expectedHandle) {
  const marker = `8bit-x-${process.pid}`;
  openDedicatedWindow(HOME_URL, { marker, namePrefix: "8bit-x-", host: "x.com" });
  waitFor("X home URL load", () => braveJS(`(() => JSON.stringify({ ok: location.hostname.endsWith("x.com"), host: location.hostname, href: location.href }))()`), 12000);
  const result = waitFor("X home/account load", () => {
    const info = profileHref();
    if (!info || !info.ok) return info;
    const path = new URL(info.href).pathname.replace(/^\//, "").replace(/\/$/, "");
    return { ok: path.toLowerCase() === expectedHandle.toLowerCase(), href: info.href, path };
  }, 25000);
  markActiveWindow(marker);
  return result;
}

function visibleEditor() {
  return braveJS(`(() => {
    const editors = Array.from(document.querySelectorAll('[data-testid="tweetTextarea_0"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 100 && r.height > 20 && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no visible tweet editor" });
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, text: el.innerText || "", innerHeight: window.innerHeight, rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`);
}

function openComposer() {
  setBraveUrl(COMPOSE_URL);
  const direct = tryWaitFor("X compose route editor", () => visibleEditor(), 14000);
  if (direct.ok) return direct;

  setBraveUrl(HOME_URL);
  waitFor("X home ready", () => {
    const snap = bodySnapshot();
    return { ok: (snap.text || "").includes("Home"), snap };
  }, 15000);
  const clicked = braveJS(`(() => {
    const selectors = [
      'a[href="/compose/post"]',
      'a[data-testid="SideNav_NewTweet_Button"]',
      '[data-testid="SideNav_NewTweet_Button"]',
      '[data-testid="tweetButtonInline"]'
    ];
    for (const selector of selectors) {
      const el = Array.from(document.querySelectorAll(selector)).find(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
      if (el) {
        el.click();
        return JSON.stringify({ ok: true, selector });
      }
    }
    return JSON.stringify({ ok: false, reason: "compose trigger not found" });
  })()`);
  if (!clicked || !clicked.ok) {
    throw new Error(`X compose open failed: ${JSON.stringify(clicked)}`);
  }
  return waitFor("X compose editor after trigger", () => visibleEditor(), 10000);
}

function focusAndClearEditor() {
  const focused = braveJS(`(() => {
    const editors = Array.from(document.querySelectorAll('[data-testid="tweetTextarea_0"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 100 && r.height > 20 && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
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
    throw new Error(`could not focus X composer: ${JSON.stringify(focused)}`);
  }
}

function directInsertCopy(text) {
  const inserted = braveJS(`(() => {
    const text = ${JSON.stringify(text)};
    const editors = Array.from(document.querySelectorAll('[data-testid="tweetTextarea_0"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 100 && r.height > 20 && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
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
    return JSON.stringify({ ok, text: el.innerText || "" });
  })()`);
  if (!inserted || !inserted.ok) {
    throw new Error(`X direct composer insertion failed: ${JSON.stringify(inserted)}`);
  }
  return inserted;
}

function editorTargetExpression({ clear = false } = {}) {
  return `(() => {
    const editors = Array.from(document.querySelectorAll('[data-testid="tweetTextarea_0"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 100 && r.height > 20 && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no editor" });
    el.focus();
    ${clear ? `
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    document.execCommand("delete");
    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContentBackward", data: null }));
    ` : ""}
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, text: el.innerText || "", rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`;
}

function cdpInsertCopy(text) {
  const attempts = [];
  let verified = { ok: false };
  for (const [method, fn] of [
    ["paste", () => cdpPasteText(editorTargetExpression({ clear: true }), text, { host: "x.com" })],
    ["input", () => cdpInputText(editorTargetExpression({ clear: true }), text, { host: "x.com" })],
  ]) {
    const inserted = fn();
    attempts.push({ method, inserted });
    if (!inserted || !inserted.ok) continue;
    verified = tryWaitFor(`X composer CDP ${method} content verification`, () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 9000);
    attempts[attempts.length - 1].verified = verified;
    if (verified.ok) break;
  }
  if (!verified.ok) {
    const direct = directInsertCopy(text);
    const directVerified = waitFor("X composer direct content verification after CDP miss", () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 9000);
    if (!directVerified.ok) {
      throw new Error(`X CDP/direct composer verification failed: ${JSON.stringify({ attempts, direct, directVerified })}`);
    }
  }
  const ready = tryWaitFor("X Post button after CDP insert", () => {
    const button = postButtonState();
    return { ok: Boolean(button && button.ok && !button.disabled), button, editor: visibleEditor() };
  }, 5000);
  if (!ready.ok) {
    throw new Error(`X CDP insert did not enable Post: ${JSON.stringify(ready)}`);
  }
}

function keyboardInsertCopy(text) {
  const editor = visibleEditor();
  if (!editor || !editor.ok) {
    throw new Error(`X composer editor disappeared before keyboard insert: ${JSON.stringify(editor)}`);
  }
  nativeClickElement(editor.rect, editor.innerHeight);
  typeIntoFocusedElement(text);
  return waitFor("X composer keyboard entry verification", () => {
    const current = visibleEditor();
    return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
  }, 12000);
}

function insertCopy(text) {
  if (process.env.SOCIAL_X_DOM_ONLY === "1") {
    cdpInsertCopy(text);
    return;
  }

  const cdpInserted = tryWaitFor("X composer CDP insert", () => {
    cdpInsertCopy(text);
    return { ok: true };
  }, 1000, 1000);
  if (cdpInserted.ok) return;

  const oldClipboard = getClipboard();
  try {
    focusAndClearEditor();
    const editor = visibleEditor();
    if (!editor || !editor.ok) {
      throw new Error(`X composer editor disappeared before paste: ${JSON.stringify(editor)}`);
    }
    nativeClickElement(editor.rect, editor.innerHeight);
    setClipboard(text);
    pasteIntoFocusedElement();
    const pasted = tryWaitFor("X composer clipboard paste verification", () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 4500);
    if (pasted.ok) {
      nudgeFocusedElement();
      waitFor("X composer content verification after keyboard nudge", () => {
        const current = visibleEditor();
        return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
      }, 3000);
      return;
    }

    directInsertCopy(text);
    waitFor("X composer content verification", () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 9000);
    nudgeFocusedElement();
    waitFor("X composer content verification after keyboard nudge", () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 3000);
    const ready = tryWaitFor("X Post button after direct insert", () => {
      const button = postButtonState();
      return { ok: Boolean(button && button.ok && !button.disabled), button, editor: visibleEditor() };
    }, 3000);
    if (!ready.ok) {
      focusAndClearEditor();
      keyboardInsertCopy(text);
    }
  } finally {
    setClipboard(oldClipboard);
  }
}

function postButtonState() {
  return braveJS(`(() => {
    const buttons = Array.from(document.querySelectorAll('button[data-testid="tweetButton"], button[data-testid="tweetButtonInline"]'))
      .filter(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      })
      .map(b => ({
        disabled: b.disabled || b.getAttribute("aria-disabled") === "true",
        testid: b.getAttribute("data-testid"),
        text: (b.innerText || b.textContent || "").trim()
      }));
    const button = buttons.find(b => !b.disabled) || buttons[0];
    if (!button) return JSON.stringify({ ok: false, reason: "Post button not found" });
    return JSON.stringify({ ok: true, disabled: button.disabled, testid: button.testid, text: button.text, buttons });
  })()`);
}

function closeDraft() {
  const close = braveJS(`(() => {
    const closeButton = Array.from(document.querySelectorAll('button[aria-label="Close"], button[aria-label="Discard"]'))
      .find(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
    if (!closeButton) return JSON.stringify({ ok: false, reason: "close/discard button not found" });
    closeButton.click();
    return JSON.stringify({ ok: true, label: closeButton.getAttribute("aria-label") || "" });
  })()`);
  if (!close || !close.ok) return close;

  tryWaitFor("X discard confirmation", () => braveJS(`(() => {
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

  return waitFor("X draft modal cleanup", () => {
    const editor = visibleEditor();
    return { ok: !editor.ok || normalize(editor.text || "") === "", editor };
  }, 9000);
}

function clickPost() {
  const expression = `(() => {
    const button = Array.from(document.querySelectorAll('button[data-testid="tweetButton"], button[data-testid="tweetButtonInline"]'))
      .find(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !b.disabled && b.getAttribute("aria-disabled") !== "true";
      });
    if (!button || button.disabled || button.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    const r = button.getBoundingClientRect();
    return JSON.stringify({ ok: true, testid: button.getAttribute("data-testid"), text: (button.innerText || button.textContent || "").trim(), rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`;
  const cdpClicked = tryWaitFor("X CDP post click", () => {
    const result = cdpClickElement(expression, { host: "x.com" });
    return { ok: Boolean(result && result.ok), result };
  }, 1000, 1000);
  if (cdpClicked.ok) return;

  const clicked = braveJS(`(() => {
    const button = Array.from(document.querySelectorAll('button[data-testid="tweetButton"], button[data-testid="tweetButtonInline"]'))
      .find(b => {
        const r = b.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && !b.disabled && b.getAttribute("aria-disabled") !== "true";
      });
    if (!button || button.disabled || button.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    button.click();
    return JSON.stringify({ ok: true, testid: button.getAttribute("data-testid") });
  })()`);
  if (!clicked || !clicked.ok) {
    throw new Error(`X post click failed: ${JSON.stringify({ cdpClicked, domClicked: clicked })}`);
  }
}

function findPostedTweet(expectedHandle, text) {
  const needles = [
    normalize(text).slice(0, 90),
    normalize(text.replace(/https?:\/\/\S+/g, "")).slice(0, 90),
    normalize(text.split(/\n+/).filter(line => !/^https?:\/\//.test(line.trim())).join(" ")).slice(0, 90),
  ].filter(Boolean);
  const fromCurrentPage = tryWaitFor("X current page live post verification", () => braveJS(`(() => {
    const normalize = s => String(s || "").trim().toLowerCase().replace(/\\s+/g, " ");
    const stripUrls = s => normalize(normalize(s).replace(/https?:\\/\\/\\s+/g, "https://").replace(/https?:\\/\\/\\S+/g, ""));
    const needles = ${JSON.stringify(needles)};
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const article = articles.find(a => {
      const text = a.innerText || "";
      const haystacks = [normalize(text), stripUrls(text)];
      return needles.some(needle => haystacks.some(haystack => haystack.includes(needle)));
    });
    if (!article) return JSON.stringify({ ok: false, reason: "matching tweet not visible", articles: articles.length });
    const links = Array.from(article.querySelectorAll('a[href*="/status/"]'))
      .map(a => a.href)
      .filter(Boolean);
    const url = links.find(h => /\\/status\\/\\d+/.test(h)) || "";
    return JSON.stringify({ ok: Boolean(url), url, articleText: (article.innerText || "").slice(0, 400) });
  })()`), 12000);
  if (fromCurrentPage && fromCurrentPage.ok && fromCurrentPage.url) return fromCurrentPage.url;

  const profileUrl = `${PROFILE_BASE}/${expectedHandle}`;
  setBraveUrl(profileUrl);
  return waitFor("X profile live post verification", () => braveJS(`(() => {
    const normalize = s => String(s || "").trim().toLowerCase().replace(/\\s+/g, " ");
    const stripUrls = s => normalize(normalize(s).replace(/https?:\\/\\/\\s+/g, "https://").replace(/https?:\\/\\/\\S+/g, ""));
    const needles = ${JSON.stringify(needles)};
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const article = articles.find(a => {
      const text = a.innerText || "";
      const haystacks = [normalize(text), stripUrls(text)];
      return needles.some(needle => haystacks.some(haystack => haystack.includes(needle)));
    });
    if (!article) return JSON.stringify({ ok: false, reason: "matching tweet not visible", articles: articles.length });
    const links = Array.from(article.querySelectorAll('a[href*="/status/"]'))
      .map(a => a.href)
      .filter(Boolean);
    const url = links.find(h => /\\/status\\/\\d+/.test(h)) || "";
    return JSON.stringify({ ok: Boolean(url), url, articleText: (article.innerText || "").slice(0, 400) });
  })()`), 30000).url;
}

function postOrDryRun(args, text) {
  const state = waitFor("X Post button enabled", () => {
    const button = postButtonState();
    return { ok: Boolean(button && button.ok && !button.disabled), button, editor: visibleEditor() };
  }, 25000);
  if (args.dryRun) {
    const cleanup = closeDraft();
    const payload = { ok: true, dryRun: true, cleaned: Boolean(cleanup && cleanup.ok) };
    console.log(JSON.stringify(payload));
    return;
  }

  clickPost();
  const url = findPostedTweet(args.expectedHandle, text);
  if (args.json) {
    console.log(JSON.stringify({ ok: true, url }));
  } else {
    console.log(url);
  }
}

function main() {
  const args = parseArgs(process.argv);
  if (args.deleteId) {
    return runWithLease({
      owner: "8bit-x-brave-post",
      reason: args.dryRun ? "dry-run X direct delete" : `delete X status ${args.deleteId} via direct authenticated X API`,
      ttl: 300,
      skip: args.skipLease,
    }, async () => deleteDirect(args));
  }
  const text = readText(args);
  if (!text) throw new Error("post text is empty");

  return runWithLease({
    owner: "8bit-x-brave-post",
    reason: args.dryRun ? "dry-run X direct posting flow" : "publish X post through direct authenticated X API",
    ttl: 900,
    skip: args.skipLease,
  }, async () => {
    if (process.env.SOCIAL_X_FORCE_BROWSER !== "1") {
      try {
        await postOrDryRunDirect(args, text);
        return;
      } catch (error) {
        const message = error && error.message ? error.message : String(error);
        if (/identity mismatch|missing Brave X cookie|authenticated home fetch failed/i.test(message)) {
          throw error;
        }
        if (/EMPTY_200_NO_FALLBACK/i.test(message)) {
          if (args.json) console.log(JSON.stringify({ ok: false, likely_posted: true, retry: false, method: "x_direct_empty_200_unverifiable", error: message }));
          else console.error(message);
          process.exitCode = 2;
          return;
        }
        if (/duplicate/i.test(message)) {
          verifyAccount(args.expectedHandle);
          const url = findPostedTweet(args.expectedHandle, text);
          if (args.json) console.log(JSON.stringify({ ok: true, url, verified: true, method: "x_direct_duplicate_recovery" }));
          else console.log(url);
          return;
        }
        console.error(`X direct API failed; falling back to browser CDP: ${message}`);
      }
    }
    verifyAccount(args.expectedHandle);
    openComposer();
    insertCopy(text);
    postOrDryRun(args, text);
  });
}

try {
  Promise.resolve(main()).catch(error => {
    console.error(error.message || String(error));
    process.exit(1);
  });
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
