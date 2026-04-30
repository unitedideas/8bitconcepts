const { spawnSync } = require("child_process");

const BRAVE_APP_ID = "com.brave.Browser";
const LEASE_BIN = "/Users/shanecheek/.foundry/foundry-sync-state/bin/foundry-computer-use-lease";
let targetWindowName = "";

function appleString(value) {
  return `"${String(value)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\r?\n/g, "\\n")}"`;
}

function osa(script) {
  const proc = spawnSync("osascript", ["-"], {
    input: script,
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 12,
  });
  if (proc.status !== 0) {
    throw new Error((proc.stderr || proc.stdout || "osascript failed").trim());
  }
  return proc.stdout.trim();
}

function braveJS(js) {
  focusTargetWindow();
  const script = `
tell application id "${BRAVE_APP_ID}"
  activate
  if (count of windows) = 0 then make new window
  return execute active tab of front window javascript ${appleString(js)}
end tell
`;
  const out = osa(script);
  if (!out || out === "missing value") return null;
  try {
    return JSON.parse(out);
  } catch {
    return out;
  }
}

function setBraveUrl(url) {
  focusTargetWindow();
  osa(`
tell application id "${BRAVE_APP_ID}"
  activate
  if (count of windows) = 0 then make new window
  set URL of active tab of front window to ${appleString(url)}
end tell
`);
}

function openDedicatedWindow(url) {
  osa(`
tell application id "${BRAVE_APP_ID}"
  activate
  set w to make new window
  set URL of active tab of w to ${appleString(url)}
  set index of w to 1
end tell
`);
}

function markActiveWindow(marker) {
  targetWindowName = "";
  const script = `
tell application id "${BRAVE_APP_ID}"
  activate
  return execute active tab of front window javascript ${appleString(`window.name = ${JSON.stringify(marker)}; window.name`)}
end tell
`;
  const out = osa(script);
  if (out !== marker) {
    throw new Error(`could not mark Brave window as ${marker}: ${out}`);
  }
  targetWindowName = marker;
}

function closeFrontWindow() {
  focusTargetWindow();
  osa(`
tell application id "${BRAVE_APP_ID}"
  if (count of windows) > 0 then close front window
end tell
`);
}

function focusTargetWindow() {
  if (!targetWindowName) return false;
  const script = `
tell application id "${BRAVE_APP_ID}"
  repeat with wi from 1 to count of windows
    repeat with ti from 1 to count of tabs of window wi
      try
        set marker to execute tab ti of window wi javascript "window.name"
        if marker is ${appleString(targetWindowName)} then
          set active tab index of window wi to ti
          set index of window wi to 1
          activate
          return "ok"
        end if
      end try
    end repeat
  end repeat
end tell
return "not found"
`;
  return osa(script) === "ok";
}

function getClipboard() {
  return osa(`
try
  return the clipboard as text
on error
  return ""
end try
`);
}

function setClipboard(text) {
  osa(`set the clipboard to ${appleString(text)}`);
}

function pasteIntoFocusedElement() {
  focusTargetWindow();
  osa(`
tell application "System Events"
  keystroke "v" using command down
end tell
`);
}

function clickAXButton(name) {
  focusTargetWindow();
  const script = `
tell application id "${BRAVE_APP_ID}" to activate
delay 0.2
tell application "System Events"
  tell process "Brave Browser"
    set frontmost to true
    repeat with e in (entire contents of front window)
      try
        if (class of e as text) is "button" and (name of e as text) is ${appleString(name)} then
          click e
          return "ok"
        end if
      end try
    end repeat
  end tell
end tell
return "not found"
`;
  return osa(script) === "ok";
}

function frontWindowBounds() {
  focusTargetWindow();
  const out = osa(`
tell application id "${BRAVE_APP_ID}"
  return bounds of front window
end tell
`);
  const nums = out.split(",").map(part => Number(part.trim())).filter(Number.isFinite);
  if (nums.length !== 4) {
    throw new Error(`could not parse Brave bounds: ${out}`);
  }
  return { left: nums[0], top: nums[1], right: nums[2], bottom: nums[3], width: nums[2] - nums[0], height: nums[3] - nums[1] };
}

function nativeClick(x, y) {
  focusTargetWindow();
  const source = `
import CoreGraphics
import Foundation
let p = CGPoint(x: ${Number(x).toFixed(1)}, y: ${Number(y).toFixed(1)})
CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
usleep(80_000)
CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
`;
  const proc = spawnSync("swift", ["-"], {
    input: source,
    encoding: "utf8",
    maxBuffer: 1024 * 1024,
  });
  if (proc.status !== 0) {
    throw new Error((proc.stderr || proc.stdout || "native click failed").trim());
  }
}

function nativeClickElement(rect, innerHeight) {
  const bounds = frontWindowBounds();
  const contentYOffset = Math.max(0, bounds.height - Number(innerHeight || 0));
  const x = bounds.left + rect.x + rect.w / 2;
  const y = bounds.top + contentYOffset + rect.y + rect.h / 2;
  nativeClick(x, y);
  return { x, y, contentYOffset, bounds };
}

function nativeClickWindowRelative(x, y) {
  const bounds = frontWindowBounds();
  nativeClick(bounds.left + Number(x), bounds.top + Number(y));
  return { x: bounds.left + Number(x), y: bounds.top + Number(y), bounds };
}

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function normalize(text) {
  return String(text).trim().toLowerCase().replace(/\s+/g, " ");
}

function waitFor(label, fn, timeoutMs = 12000, intervalMs = 500) {
  const start = Date.now();
  let last;
  while (Date.now() - start < timeoutMs) {
    try {
      last = fn();
      if (last && last.ok) return last;
    } catch (error) {
      last = { ok: false, error: error.message };
    }
    sleep(intervalMs);
  }
  throw new Error(`${label} failed: ${JSON.stringify(last)}`);
}

function tryWaitFor(label, fn, timeoutMs = 4000, intervalMs = 500) {
  try {
    return waitFor(label, fn, timeoutMs, intervalMs);
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

function bodySnapshot(maxChars = 3000) {
  return braveJS(`(() => {
    const text = document.body ? document.body.innerText : "";
    return JSON.stringify({ ok: true, url: location.href, title: document.title, text: text.slice(0, ${maxChars}) });
  })()`);
}

function visibleElementInfo(selector, predicate = "") {
  return braveJS(`(() => {
    const els = Array.from(document.querySelectorAll(${JSON.stringify(selector)}))
      .filter(e => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden" && getComputedStyle(e).display !== "none";
      })
      ${predicate ? `.filter(${predicate})` : ""};
    const el = els[0];
    if (!el) return JSON.stringify({ ok: false, reason: "not found", selector: ${JSON.stringify(selector)} });
    const r = el.getBoundingClientRect();
    return JSON.stringify({ ok: true, text: el.innerText || el.textContent || "", rect: { x: r.x, y: r.y, w: r.width, h: r.height } });
  })()`);
}

function acquireLease({ owner, reason, ttl = 900, skip = false }) {
  if (skip) return () => {};
  const proc = spawnSync("python3", [
    LEASE_BIN,
    "acquire",
    "--owner",
    owner,
    "--reason",
    reason,
    "--ttl",
    String(ttl),
    "--owner-pid",
    String(process.pid),
    "--json",
  ], { encoding: "utf8", maxBuffer: 1024 * 1024 });
  if (proc.status !== 0) {
    throw new Error((proc.stdout || proc.stderr || "computer-use lease acquire failed").trim());
  }
  let released = false;
  return () => {
    if (released) return;
    released = true;
    spawnSync("python3", [LEASE_BIN, "release", "--owner", owner, "--json"], {
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
    });
  };
}

function runWithLease(options, fn) {
  const release = acquireLease(options);
  let done = false;
  const cleanup = () => {
    if (!done) release();
  };
  process.once("exit", cleanup);
  process.once("SIGINT", () => {
    cleanup();
    process.exit(130);
  });
  process.once("SIGTERM", () => {
    cleanup();
    process.exit(143);
  });
  try {
    const result = fn();
    done = true;
    release();
    return result;
  } catch (error) {
    done = true;
    release();
    throw error;
  }
}

module.exports = {
  appleString,
  bodySnapshot,
  braveJS,
  clickAXButton,
  closeFrontWindow,
  getClipboard,
  nativeClickElement,
  nativeClickWindowRelative,
  markActiveWindow,
  normalize,
  pasteIntoFocusedElement,
  runWithLease,
  openDedicatedWindow,
  setBraveUrl,
  setClipboard,
  sleep,
  tryWaitFor,
  visibleElementInfo,
  waitFor,
};
