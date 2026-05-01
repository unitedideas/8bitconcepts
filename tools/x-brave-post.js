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
  tryWaitFor,
  waitFor,
} = require("./social-brave-common");

const HOME_URL = "https://x.com/home";
const COMPOSE_URL = "https://x.com/compose/post";
const PROFILE_BASE = "https://x.com";
const DEFAULT_HANDLE = "8BitConcepts";

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

function profileHref() {
  return braveJS(`(() => {
    const link = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
    return JSON.stringify({ ok: Boolean(link), href: link ? link.href : "", body: document.body ? document.body.innerText.slice(0, 1000) : "" });
  })()`);
}

function verifyAccount(expectedHandle) {
  const marker = `8bit-x-${process.pid}`;
  openDedicatedWindow(HOME_URL, { marker, namePrefix: "8bit-x-", host: "x.com" });
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

function insertCopy(text) {
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
    reason: args.dryRun ? "dry-run X Brave posting flow" : "publish X post through Brave",
    ttl: 900,
    skip: args.skipLease,
  }, () => {
    verifyAccount(args.expectedHandle);
    openComposer();
    insertCopy(text);
    postOrDryRun(args, text);
  });
}

try {
  main();
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
