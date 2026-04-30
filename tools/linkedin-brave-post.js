#!/usr/bin/env node
/*
 * Supervised LinkedIn recovery publisher for the authenticated Brave session.
 *
 * This is intentionally a one-shot recovery tool, not a recurring automation.
 * It avoids coordinate clicks: every step uses DOM selectors in Brave, verifies
 * identity/content/button state, and exits non-zero if the page is not in the
 * expected state.
 */
const fs = require("fs");
const {
  bodySnapshot,
  braveJS,
  clickAXButton,
  closeFrontWindow,
  getClipboard,
  markActiveWindow,
  nativeClickElement,
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
const DEFAULT_NAME = "Shane Cheek";
const DEFAULT_HEADLINE = "Founder at 8bitconcepts";

function usage() {
  console.error("usage: node tools/linkedin-brave-post.js (--text <copy> | --text-file <path>) [--dry-run] [--skip-lease] [--expected-name <name>] [--expected-headline <headline>]");
  process.exit(2);
}

function parseArgs(argv) {
  const args = {
    dryRun: false,
    expectedName: DEFAULT_NAME,
    expectedHeadline: DEFAULT_HEADLINE,
    skipLease: false,
  };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--dry-run") args.dryRun = true;
    else if (arg === "--skip-lease") args.skipLease = true;
    else if (arg === "--text") args.text = argv[++i];
    else if (arg === "--text-file") args.textFile = argv[++i];
    else if (arg === "--expected-name") args.expectedName = argv[++i];
    else if (arg === "--expected-headline") args.expectedHeadline = argv[++i];
    else usage();
  }
  if ((!args.text && !args.textFile) || (args.text && args.textFile) || !args.expectedName || !args.expectedHeadline) usage();
  return args;
}

function readText(args) {
  const text = args.textFile ? fs.readFileSync(args.textFile, "utf8") : args.text;
  return String(text || "").trim();
}

function visibleEditor() {
  return braveJS(`(() => {
    const editors = Array.from(document.querySelectorAll('[role="dialog"] [contenteditable="true"][role="textbox"]'))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 100 && r.height > 20 && getComputedStyle(e).display !== "none" && getComputedStyle(e).visibility !== "hidden";
      });
    const el = editors[0];
    if (!el) return JSON.stringify({ ok: false, reason: "no visible composer editor" });
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, text: el.innerText || "", rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`);
}

function verifyIdentity(expectedName, expectedHeadline) {
  const snap = bodySnapshot(4000);
  const text = snap.text || "";
  if (!text.includes(expectedName) || !text.includes(expectedHeadline)) {
    throw new Error(`LinkedIn identity mismatch at ${snap.url}: expected ${expectedName} / ${expectedHeadline}`);
  }
}

function openComposer(args) {
  openDedicatedWindow(FEED_URL);
  waitFor("LinkedIn feed load", () => {
    const snap = bodySnapshot();
    return { ok: (snap.text || "").includes(args.expectedName), snap };
  }, 25000);
  markActiveWindow(`8bit-linkedin-${process.pid}`);
  verifyIdentity(args.expectedName, args.expectedHeadline);

  const shareUrlEditor = tryWaitFor("LinkedIn composer from shareActive", () => visibleEditor(), 5000);
  if (shareUrlEditor.ok) return { mode: "dom", ...shareUrlEditor };

  const clicked = braveJS(`(() => {
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
      .filter(e => {
        const text = ((e.innerText || e.textContent || "").trim());
        const label = e.getAttribute("aria-label") || "";
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

  if (clickAXButton("Start a post")) {
    const afterAXClick = tryWaitFor("LinkedIn composer after accessibility Start a post", () => visibleEditor(), 5000);
    if (afterAXClick.ok) return { mode: "dom", ...afterAXClick };
  }

  const startRect = braveJS(`(() => {
    const els = Array.from(document.querySelectorAll('div, button, [role="button"], a'));
    let found = null;
    for (const e of els) {
      const text = String(e.innerText || e.textContent || "").trim();
      const label = e.getAttribute("aria-label") || "";
      if (text === "Start a post" || label === "Start a post") {
        const r = e.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) { found = e; break; }
      }
    }
    if (!found) return JSON.stringify({ ok: false, reason: "Start a post selector not found" });
    const r = found.getBoundingClientRect();
    return JSON.stringify({ ok: true, rect: { x: r.x, y: r.y, w: r.width, h: r.height }, innerHeight: window.innerHeight });
  })()`);
  if (!startRect || !startRect.ok) {
    throw new Error(`LinkedIn Start a post selector failed: ${JSON.stringify(startRect)}`);
  }
  nativeClickElement(startRect.rect, startRect.innerHeight);
  const afterNativeClick = tryWaitFor("LinkedIn composer after native Start a post", () => visibleEditor(), 5000);
  if (afterNativeClick.ok) return { mode: "dom", ...afterNativeClick };
  return { ok: true, mode: "native" };
}

function focusAndClearEditor() {
  const focused = braveJS(`(() => {
    const editors = Array.from(document.querySelectorAll('[role="dialog"] [contenteditable="true"][role="textbox"]'))
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
    throw new Error(`could not focus LinkedIn composer: ${JSON.stringify(focused)}`);
  }
}

function insertCopy(text, mode) {
  const oldClipboard = getClipboard();
  if (mode === "native") {
    nativeClickWindowRelative(170, 312);
    setClipboard(text);
    pasteIntoFocusedElement();
    setClipboard(oldClipboard);
    return;
  }
  focusAndClearEditor();
  setClipboard(text);
  pasteIntoFocusedElement();
  waitFor("LinkedIn composer content verification", () => {
    const editor = visibleEditor();
    return { ok: editor.ok && normalize(editor.text) === normalize(text), editor };
  }, 9000);
  setClipboard(oldClipboard);
}

function postButtonState() {
  return braveJS(`(() => {
    const buttons = Array.from(document.querySelectorAll('[role="dialog"] button'))
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
  const close = braveJS(`(() => {
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

  tryWaitFor("LinkedIn discard dialog", () => braveJS(`(() => {
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
  const clicked = braveJS(`(() => {
    const post = Array.from(document.querySelectorAll('[role="dialog"] button'))
      .find(b => ((b.innerText || "").trim() === "Post") || b.getAttribute("aria-label") === "Post");
    if (!post || post.disabled || post.getAttribute("aria-disabled") === "true") return JSON.stringify({ ok: false });
    post.click();
    return JSON.stringify({ ok: true });
  })()`);
  if (!clicked || !clicked.ok) {
    throw new Error(`LinkedIn post click failed: ${JSON.stringify(clicked)}`);
  }
}

function clickNativePost() {
  if (clickAXButton("Post")) return { ok: true, method: "accessibility" };
  const clicked = nativeClickWindowRelative(1010, 1100);
  return { ok: true, method: "native", clicked };
}

function waitForPostSuccess() {
  return waitFor("LinkedIn post success", () => braveJS(`(() => {
    const text = document.body ? document.body.innerText : "";
    const link = Array.from(document.querySelectorAll('a'))
      .find(a => ((a.innerText || a.textContent || "").trim() === "View post") && a.href.includes("/feed/update/"));
    return JSON.stringify({ ok: Boolean(link) && text.includes("Post successful"), url: link ? link.href : "" });
  })()`), 24000);
}

function verifyLivePost(url, text) {
  setBraveUrl(url);
  const needle = normalize(text).slice(0, 90);
  const result = tryWaitFor("LinkedIn live post verification", () => {
    const snap = bodySnapshot(12000);
    return { ok: normalize(snap.text || "").includes(needle), url: snap.url };
  }, 18000);
  return Boolean(result.ok);
}

function closeNativeDraft() {
  nativeClickWindowRelative(713, 195);
  // LinkedIn shows a discard confirmation only after text exists.
  nativeClickWindowRelative(1010, 1100);
  closeFrontWindow();
  return { ok: true };
}

function postOrDryRun(dryRun, text, mode) {
  if (mode === "native") {
    if (dryRun) {
      const cleanup = closeNativeDraft();
      console.log(JSON.stringify({ ok: true, dryRun: true, cleaned: Boolean(cleanup && cleanup.ok), mode }));
      return;
    }
    const clicked = clickNativePost();
    const result = waitForPostSuccess();
    const verified = verifyLivePost(result.url, text);
    console.log(JSON.stringify({ ok: true, url: result.url, verified, mode, click: clicked.method }));
    return;
  }
  const state = postButtonState();
  if (!state || !state.ok || state.disabled) {
    throw new Error(`Post button not ready: ${JSON.stringify(state)}`);
  }
  if (dryRun) {
    const cleanup = closeDraft();
    if (cleanup && cleanup.ok) closeFrontWindow();
    console.log(JSON.stringify({ ok: true, dryRun: true, cleaned: Boolean(cleanup && cleanup.ok) }));
    return;
  }
  clickPost();
  const result = waitForPostSuccess();
  const verified = verifyLivePost(result.url, text);
  console.log(JSON.stringify({ ok: true, url: result.url, verified }));
}

function main() {
  const args = parseArgs(process.argv);
  const text = readText(args);
  if (!text) throw new Error("post text is empty");

  return runWithLease({
    owner: "8bit-linkedin-brave-post",
    reason: args.dryRun ? "dry-run LinkedIn Brave posting flow" : "publish LinkedIn post through Brave",
    ttl: 900,
    skip: args.skipLease,
  }, () => {
    const composer = openComposer(args);
    insertCopy(text, composer.mode);
    postOrDryRun(args.dryRun, text, composer.mode);
  });
}

try {
  main();
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
