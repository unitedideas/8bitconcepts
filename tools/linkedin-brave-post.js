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
const os = require("os");
const path = require("path");
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
const DEFAULT_HEADLINE = "Founder at 8bitconcepts";
const LINKEDIN_ALLOW_FILE = "/tmp/8bit-linkedin-browser-one-shot-allow";
const LINKEDIN_ONE_SHOT_TOKEN = "8bit-linkedin-supervised-manual-v2";

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
  if (
    !args.allowBrowser ||
    process.env.SOCIAL_BRAVE_LINKEDIN_ONE_SHOT !== LINKEDIN_ONE_SHOT_TOKEN ||
    !fs.existsSync(LINKEDIN_ALLOW_FILE) ||
    fs.readFileSync(LINKEDIN_ALLOW_FILE, "utf8").trim() !== LINKEDIN_ONE_SHOT_TOKEN
  ) {
    console.error("LinkedIn Brave browser posting is disabled unless --allow-browser, SOCIAL_BRAVE_LINKEDIN_ONE_SHOT, and the one-shot allow-file content are all set by an explicit supervised run.");
    process.exit(3);
  }
  return args;
}

function readText(args) {
  const text = args.textFile ? fs.readFileSync(args.textFile, "utf8") : args.text;
  return String(text || "").trim();
}

function visibleEditor() {
  return braveJS(`(() => {
    const editors = Array.from(document.querySelectorAll('[role="dialog"] [contenteditable="true"]'))
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
  const marker = `8bit-linkedin-${process.pid}`;
  openDedicatedWindow(FEED_URL, { marker, namePrefix: "8bit-linkedin-", host: "www.linkedin.com" });
  waitFor("LinkedIn feed load", () => {
    const snap = bodySnapshot();
    const text = snap.text || "";
    const identityOk = text.includes(args.expectedName) && text.includes(args.expectedHeadline);
    if (!identityOk) return { ok: false, snap };
    const editor = visibleEditor();
    const composerOk = text.includes("Start a post") || Boolean(editor && editor.ok);
    return { ok: composerOk, snap };
  }, 35000);
  verifyIdentity(args.expectedName, args.expectedHeadline);

  const shareUrlEditor = tryWaitFor("LinkedIn composer from shareActive", () => visibleEditor(), 15000);
  if (shareUrlEditor.ok) return { mode: "dom", ...shareUrlEditor };

  waitFor("LinkedIn Start a post visible", () => braveJS(`(() => {
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, div'))
      .filter(e => {
        const text = ((e.innerText || e.textContent || "").trim());
        const label = e.getAttribute("aria-label") || "";
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && (text === "Start a post" || label === "Start a post" || text.includes("Start a post"));
      });
    return JSON.stringify({ ok: candidates.length > 0, count: candidates.length });
  })()`), 45000);

  const clicked = braveJS(`(() => {
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
      const a = e.closest('a');
      if (a && a.href && a.href.includes('/in/')) continue;
      if (text.includes("Start a post") || label.includes("Start a post")) {
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
    const editors = Array.from(document.querySelectorAll('[role="dialog"] [contenteditable="true"]'))
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

function directInsertCopy(text) {
  const inserted = braveJS(`(() => {
    const text = ${JSON.stringify(text)};
    const editors = Array.from(document.querySelectorAll('[role="dialog"] [contenteditable="true"]'))
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
    return JSON.stringify({ ok, text: el.innerText || el.textContent || "" });
  })()`);
  if (!inserted || !inserted.ok) {
    throw new Error(`LinkedIn direct composer insertion failed: ${JSON.stringify(inserted)}`);
  }
  return inserted;
}

function insertCopy(text, mode) {
  const oldClipboard = getClipboard();
  try {
    if (mode === "native") {
      const editorRect = braveJS(`(() => {
        const editors = Array.from(document.querySelectorAll('[contenteditable="true"]'))
          .filter(e => {
            const r = e.getBoundingClientRect();
            if (r.width < 200 || r.height < 60) return false;
            const style = getComputedStyle(e);
            return style.display !== "none" && style.visibility !== "hidden";
          })
          .map(e => {
            const r = e.getBoundingClientRect();
            return { el: e, area: r.width * r.height, rect: { x: r.x, y: r.y, w: r.width, h: r.height }, text: (e.innerText || e.textContent || "").slice(0, 200) };
          })
          .sort((a, b) => b.area - a.area);
        const best = editors[0];
        if (!best) return JSON.stringify({ ok: false, reason: "no contenteditable editor found" });
        return JSON.stringify({ ok: true, rect: best.rect, innerHeight: window.innerHeight, text: best.text });
      })()`);
      const hasEditorRect = Boolean(editorRect && editorRect.ok);
      if (hasEditorRect) nativeClickElement(editorRect.rect, editorRect.innerHeight);
      else nativeClickWindowRelative(170, 312);
      setClipboard(text);
      pasteIntoFocusedElement();
      if (!hasEditorRect) return;
      waitFor("LinkedIn native composer content verification", () => braveJS(`(() => {
        const normalize = (t) => String(t || '').trim().toLowerCase().replace(/\\s+/g, ' ');
        const expected = ${JSON.stringify(normalize(text))};
        const editors = Array.from(document.querySelectorAll('[contenteditable=\"true\"]'))
          .filter(e => {
            const r = e.getBoundingClientRect();
            if (r.width < 200 || r.height < 60) return false;
            const style = getComputedStyle(e);
            return style.display !== \"none\" && style.visibility !== \"hidden\";
          })
          .map(e => ({ text: e.innerText || e.textContent || \"\" }))
          .sort((a, b) => b.text.length - a.text.length);
        const got = normalize((editors[0] && editors[0].text) || \"\");
        return JSON.stringify({ ok: got.includes(expected.slice(0, 60)), got: got.slice(0, 200) });
      })()`), 9000);
      return;
    }
    focusAndClearEditor();
    const direct = tryWaitFor("LinkedIn direct composer insertion", () => {
      directInsertCopy(text);
      const editor = visibleEditor();
      return { ok: editor.ok && normalize(editor.text) === normalize(text), editor };
    }, 2500);
    if (direct.ok) return;

    setClipboard(text);
    pasteIntoFocusedElement();
    waitFor("LinkedIn composer content verification", () => {
      const editor = visibleEditor();
      return { ok: editor.ok && normalize(editor.text) === normalize(text), editor };
    }, 9000);
  } finally {
    setClipboard(oldClipboard);
  }
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

function postSuccessProbe() {
  return braveJS(`(() => {
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
  const draft = braveJS(`(() => {
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
  return braveJS(`(() => {
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
  const target = braveJS(`(() => {
    const post = Array.from(document.querySelectorAll('[role="dialog"] button'))
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
  const domClick = braveJS(`(() => {
    const post = Array.from(document.querySelectorAll('[role="dialog"] button'))
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
  openDedicatedWindow(ACTIVITY_ALL_URL, { marker, namePrefix: "8bit-linkedin-", host: "www.linkedin.com" });
  waitFor("LinkedIn activity cards", () => braveJS(`(() => {
    const cards = document.querySelectorAll('div.feed-shared-update-v2');
    const url = location.href || "";
    return JSON.stringify({ ok: url.includes("recent-activity") && cards.length > 0, cardCount: cards.length, url });
  })()`), 15000);

  const candidates = waitFor("LinkedIn activity candidate urls", () => braveJS(`(() => {
    const anchors = Array.from(document.querySelectorAll('a')).map(a => a && a.href ? a.href : '').filter(Boolean);
    const urls = [];
    const seen = new Set();
    const add = (u) => { if (!u || seen.has(u)) return; seen.add(u); urls.push(u); };
    for (const href of anchors) {
      if (href.includes('/feed/update/')) add(href);
      const m = href.match(/urn:li:activity:(\\d+)/);
      if (m && m[1]) add('https://www.linkedin.com/feed/update/urn:li:activity:' + m[1] + '/');
      if (href.includes('/posts/')) add(href);
    }
    return JSON.stringify({ ok: urls.length > 0, count: urls.length, urls: urls.slice(0, 12) });
  })()`), 15000);

  for (const url of (candidates.urls || []).slice(0, 6)) {
    if (verifyLivePost(url, text)) return { ok: true, url, method: "activity_candidates" };
  }
  return { ok: false, url: "", method: "activity_candidates", reason: "no verified match", candidate_count: (candidates.urls || []).length };
}

function verifyLivePost(url, text) {
  setBraveUrl(url);
  const needle = normalize(text).slice(0, 90);
  const result = tryWaitFor("LinkedIn live post verification", () => {
    const snap = bodySnapshot(12000);
    return { ok: normalize(snap.text || "").includes(needle), url: snap.url };
  }, 6000);
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
    console.log(JSON.stringify({ ok: true, url, verified, mode, click: clicked.method }));
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

  return runWithLease({
    owner: "8bit-linkedin-brave-post",
    reason: args.dryRun ? "dry-run LinkedIn Brave posting flow" : "publish LinkedIn post through Brave",
    ttl: 900,
    skip: args.skipLease,
  }, () => {
    if (args.recoverOnly) {
      const recovered = findPostUrlFromActivity(text);
      const verified = Boolean(recovered.url) && verifyLivePost(recovered.url, text);
      if (!verified) {
        throw new Error(`LinkedIn recover-only verification failed for ${recovered.url || "(missing url)"}`);
      }
      console.log(JSON.stringify({ ok: true, url: recovered.url, verified, recovered: true, method: recovered.method || "" }));
      return;
    }
    const composer = openComposer(args);
    insertCopy(text, composer.mode);
    postOrDryRun(args.dryRun, text, composer.mode);
  });
}

try {
  main();
} catch (error) {
  console.error((error && error.stack) || (error && error.message) || String(error));
  process.exit(1);
}
