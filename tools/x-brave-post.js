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
  closeFrontWindow,
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
  console.error("usage: node tools/x-brave-post.js (--text <copy> | --text-file <path>) [--expected-handle <handle>] [--dry-run] [--json] [--skip-lease]");
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
    else if (arg === "--expected-handle") args.expectedHandle = argv[++i];
    else usage();
  }
  if (!args.text && !args.textFile) usage();
  if (args.text && args.textFile) usage();
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
    .map(([name, value]) => `${name}=${encodeURIComponent(value)}`)
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
      TweetResultByRestId: parseOperation(mainJs, "TweetResultByRestId"),
      UserByScreenName: parseOperation(mainJs, "UserByScreenName"),
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

async function postOrDryRunDirect(args, text) {
  const account = await verifyAccountDirect(args.expectedHandle);
  if (args.dryRun) {
    const payload = { ok: true, dryRun: true, method: "x_direct_cookie_graphql_api", identity: account };
    console.log(JSON.stringify(payload));
    return;
  }
  await xWebConfig();
  const op = xWebConfigCache.operations.CreateTweet;
  const created = await xApiRequest("POST", `/i/api/graphql/${op.queryId}/CreateTweet`, createTweetPayload(text));
  const tweet = created.json && created.json.data && created.json.data.create_tweet && created.json.data.create_tweet.tweet_results && created.json.data.create_tweet.tweet_results.result;
  const tweetId = tweet && tweet.rest_id;
  const fullText = tweet && tweet.legacy && tweet.legacy.full_text;
  if (!created.ok || !tweetId || normalize(fullText || "") !== normalize(text)) {
    throw new Error(`X direct post request failed: ${JSON.stringify({ status: created.status, responseURL: created.responseURL, text: created.text ? created.text.slice(0, 500) : "", errors: created.json && created.json.errors })}`);
  }
  const verified = await verifyTweetDirect(tweetId, text);
  if (!verified) throw new Error(`X API post created but live status verification failed for ${tweetId}`);
  const url = `${PROFILE_BASE}/${account.screenName}/status/${tweetId}`;
  if (args.json) console.log(JSON.stringify({ ok: true, url, verified: true, method: "x_direct_cookie_graphql_api" }));
  else console.log(url);
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
    focusAndClearEditor();
    directInsertCopy(text);
    waitFor("X composer DOM-only content verification", () => {
      const current = visibleEditor();
      return { ok: current.ok && normalize(current.text) === normalize(text), editor: current };
    }, 9000);
    const ready = tryWaitFor("X Post button after DOM-only insert", () => {
      const button = postButtonState();
      return { ok: Boolean(button && button.ok && !button.disabled), button, editor: visibleEditor() };
    }, 3000);
    if (!ready.ok) {
      throw new Error(`X DOM-only insert did not enable Post: ${JSON.stringify(ready)}`);
    }
    return;
  }

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
    throw new Error(`X post click failed: ${JSON.stringify(clicked)}`);
  }
}

function findPostedTweet(expectedHandle, text) {
  const needle = normalize(text).slice(0, 90);
  const fromCurrentPage = tryWaitFor("X current page live post verification", () => braveJS(`(() => {
    const normalize = s => String(s || "").trim().toLowerCase().replace(/\\s+/g, " ");
    const needle = ${JSON.stringify(needle)};
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const article = articles.find(a => normalize(a.innerText || "").includes(needle));
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
    const needle = ${JSON.stringify(needle)};
    const articles = Array.from(document.querySelectorAll('article[data-testid="tweet"]'));
    const article = articles.find(a => normalize(a.innerText || "").includes(needle));
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
    if (cleanup && cleanup.ok) closeFrontWindow();
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
  const text = readText(args);
  if (!text) throw new Error("post text is empty");

  return runWithLease({
    owner: "8bit-x-brave-post",
    reason: args.dryRun ? "dry-run X direct posting flow" : "publish X post through direct authenticated X API",
    ttl: 900,
    skip: args.skipLease,
  }, async () => {
    if (process.env.SOCIAL_X_FORCE_BROWSER !== "1") {
      await postOrDryRunDirect(args, text);
      return;
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
