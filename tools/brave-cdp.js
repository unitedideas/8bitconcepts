#!/usr/bin/env node
const { spawn, spawnSync } = require("child_process");
const http = require("http");

const PORT = Number(process.env.SOCIAL_BRAVE_CDP_PORT || 9222);
const BRAVE_BIN = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser";

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function request(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port: PORT, method, path, timeout: 5000 }, res => {
      let data = "";
      res.setEncoding("utf8");
      res.on("data", chunk => { data += chunk; });
      res.on("end", () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`${method} ${path} returned ${res.statusCode}: ${data.slice(0, 300)}`));
          return;
        }
        resolve(data);
      });
    });
    req.on("timeout", () => {
      req.destroy(new Error(`${method} ${path} timed out`));
    });
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function json(method, path, body = null) {
  return JSON.parse(await request(method, path, body));
}

async function cdpReady() {
  try {
    await json("GET", "/json/version");
    return true;
  } catch {
    return false;
  }
}

async function ensureCdp(startUrl = "about:blank") {
  if (await cdpReady()) return;

  spawnSync("osascript", ["-e", 'tell application id "com.brave.Browser" to quit'], {
    encoding: "utf8",
    timeout: 10000,
  });
  for (let i = 0; i < 40; i += 1) {
    const stillRunning = spawnSync("pgrep", ["-x", "Brave Browser"], { encoding: "utf8" }).status === 0;
    if (!stillRunning) break;
    await sleep(250);
  }

  const child = spawn(BRAVE_BIN, [
    `--remote-debugging-port=${PORT}`,
    "--remote-allow-origins=*",
    "--no-first-run",
    startUrl,
  ], {
    detached: true,
    stdio: "ignore",
  });
  child.unref();

  for (let i = 0; i < 80; i += 1) {
    if (await cdpReady()) return;
    await sleep(250);
  }
  throw new Error("Brave CDP did not become ready");
}

function hostMatches(pageUrl, host) {
  if (!host) return true;
  try {
    const actual = new URL(pageUrl).hostname.toLowerCase();
    const wanted = String(host).toLowerCase();
    return actual === wanted || actual.endsWith(`.${wanted}`);
  } catch {
    return false;
  }
}

function wsSend(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ws.nextId++;
    const onMessage = event => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg.id !== id) return;
      ws.removeEventListener("message", onMessage);
      if (msg.error) reject(new Error(`${method}: ${JSON.stringify(msg.error)}`));
      else resolve(msg.result || {});
    };
    ws.addEventListener("message", onMessage);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function withPage(page, fn) {
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  ws.nextId = 1;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("CDP websocket timed out")), 5000);
    ws.addEventListener("open", () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
    ws.addEventListener("error", error => {
      clearTimeout(timer);
      reject(error.error || error);
    }, { once: true });
  });
  try {
    return await fn(ws);
  } finally {
    ws.close();
  }
}

async function evalOnPage(page, expression) {
  return withPage(page, async ws => {
    await wsSend(ws, "Runtime.enable");
    const result = await wsSend(ws, "Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text || "CDP evaluation failed");
    }
    const remote = result.result || {};
    if (remote.type === "undefined") return "";
    if (Object.prototype.hasOwnProperty.call(remote, "value")) return remote.value;
    return remote.description || "";
  });
}

async function pageInfo(page) {
  let marker = "";
  let hostname = "";
  try {
    marker = String(await evalOnPage(page, "window.name") || "");
  } catch {}
  try {
    hostname = String(await evalOnPage(page, "location.hostname") || "");
  } catch {}
  return { page, marker, hostname, url: page.url || "" };
}

async function pages() {
  return (await json("GET", "/json/list")).filter(page => page.type === "page" && page.webSocketDebuggerUrl);
}

async function findPage({ marker = "", namePrefix = "", host = "" } = {}) {
  const infos = [];
  for (const page of await pages()) {
    const info = await pageInfo(page);
    infos.push(info);
    if (marker && info.marker === marker) return info.page;
  }
  if (namePrefix) {
    const byMarker = infos.find(info => info.marker.startsWith(namePrefix) && hostMatches(info.url, host));
    if (byMarker) return byMarker.page;
  }
  if (host) {
    const byHost = infos.find(info => hostMatches(info.url, host));
    if (byHost) return byHost.page;
  }
  return null;
}

async function openPage(url, { marker = "", namePrefix = "", host = "" } = {}) {
  await ensureCdp(url);
  let page = await findPage({ marker, namePrefix, host });
  if (!page) {
    page = await json("PUT", `/json/new?${encodeURIComponent(url)}`);
  } else {
    await request("PUT", `/json/activate/${page.id}`);
    try {
      await request("PUT", `/json/navigate/${page.id}?${encodeURIComponent(url)}`);
    } catch (error) {
      if (!String(error.message || "").includes("Unknown command: navigate")) throw error;
      await evalOnPage(page, `location.href = ${JSON.stringify(url)}; location.href`);
    }
  }
  if (marker) {
    await waitForPage(page, 15000);
    await evalOnPage(page, `window.name = ${JSON.stringify(marker)}; window.name`);
  }
  return page;
}

async function waitForPage(page, timeoutMs = 15000) {
  const start = Date.now();
  let last = "";
  while (Date.now() - start < timeoutMs) {
    try {
      last = await evalOnPage(page, "document.readyState + ' ' + location.href");
      const ready = String(last).startsWith("interactive") || String(last).startsWith("complete");
      if (ready) return;
    } catch (error) {
      last = error.message;
    }
    await sleep(300);
  }
  throw new Error(`page did not load: ${last}`);
}

async function activePage() {
  await ensureCdp();
  const list = await pages();
  if (!list.length) return openPage("about:blank");
  return list[0];
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  if (cmd === "ensure") {
    await ensureCdp(args[0] || "about:blank");
    console.log("ok");
    return;
  }
  if (cmd === "open") {
    const [url, marker = "", namePrefix = "", host = ""] = args;
    if (!url) throw new Error("missing url");
    const page = await openPage(url, { marker, namePrefix, host });
    console.log(JSON.stringify({ ok: true, id: page.id, url: page.url }));
    return;
  }
  if (cmd === "eval") {
    const [expression, marker = "", namePrefix = "", host = ""] = args;
    if (!expression) throw new Error("missing expression");
    await ensureCdp();
    const page = (marker || namePrefix || host) ? await findPage({ marker, namePrefix, host }) : await activePage();
    if (!page) {
      console.log("missing value");
      return;
    }
    const value = await evalOnPage(page, expression);
    if (value === undefined || value === null) console.log("missing value");
    else if (typeof value === "string") console.log(value);
    else console.log(JSON.stringify(value));
    return;
  }
  throw new Error("usage: brave-cdp.js ensure [url] | open <url> [marker] [namePrefix] [host] | eval <js> [marker] [namePrefix] [host]");
}

main().catch(error => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
});
