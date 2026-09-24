// probe-local.mjs — diagnose local-node access to ID sources
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function tryFetch(name, url, headers, parse) {
  try {
    const r = await fetch(url, { headers, redirect: "manual" });
    const t = await r.text();
    const res = { name, status: r.status, len: t.length, ct: r.headers.get("content-type"), head: t.slice(0, 80).replace(/\s+/g, " ") };
    if (parse) res.parsed = parse(t);
    return res;
  } catch (e) { return { name, error: String(e).slice(0, 80) }; }
}

const firefoxUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0";
const fullBrowserHeaders = {
  accept: "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "accept-language": "en-US,en;q=0.9",
  "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
  "sec-ch-ua-mobile": "?0",
  "sec-ch-ua-platform": '"Windows"',
  "sec-fetch-dest": "document",
  "sec-fetch-mode": "navigate",
  "sec-fetch-site": "none",
  "sec-fetch-user": "?1",
  "upgrade-insecure-requests": "1",
  "user-agent": UA,
};

const out = {};

// 1) urlebird local, chrome-ish full headers (charlidamelio)
out.urlebirdChrome = await tryFetch("urlebird-chrome", "https://www.urlebird.com/user/charlidamelio/", fullBrowserHeaders,
  (t) => [...new Set([...t.matchAll(/urlebird\.com\/video\/(?:[^"/]*?-)?(\d{15,21})\//g)].map((m) => m[1]))].slice(0, 5));

// 2) urlebird local, firefox UA
out.urlebirdFirefox = await tryFetch("urlebird-firefox", "https://www.urlebird.com/user/charlidamelio/",
  { "user-agent": firefoxUA, accept: "text/html,application/xhtml+xml" }, null);

// 3) jina retry for charli
out.jinaCharli = await tryFetch("jina-charli", "https://r.jina.ai/https://www.tiktok.com/@charlidamelio",
  { "user-agent": UA, accept: "text/plain, text/markdown" },
  (t) => ({ links: [...new Set([...t.matchAll(/\/video\/(\d{15,21})/g)].map((m) => m[1]))].slice(0, 8), hasSlardar: t.includes("slardar"), idLike: [...new Set([...t.matchAll(/(\d{19})/g)].map((m) => m[1]))].slice(0, 8) }));

// 4) wayback availability for charlidamelio
try {
  const av = await (await fetch("https://archive.org/wayback/available?url=www.tiktok.com/%40charlidamelio", { headers: { "user-agent": UA } })).json();
  const snap = av?.archived_snapshots?.closest;
  if (!snap) out.wayback = { none: true };
  else {
    const r = await fetch(snap.url, { headers: { "user-agent": UA, accept: "text/html" } });
    const t = await r.text();
    const itemIds = [...new Set([...t.matchAll(/"id":\s*"(\d{15,21})"(?:[^}]*?"desc")/g)].map((m) => m[1]))];
    const generic = [...new Set([...t.matchAll(/"id":"(\d{15,21})"/g)].map((m) => m[1]))];
    out.wayback = { snapshot: snap.url.slice(0, 80), tmp: snap.timestamp, status: r.status, len: t.length,
      hasItemList: t.includes("itemList"), hasUniversal: t.includes("__UNIVERSAL_DATA_FOR_REHYDRATION__"),
      itemIds: itemIds.slice(0, 10), genericIds: generic.slice(0, 10) };
  }
} catch (e) { out.wayback = { error: String(e).slice(0, 80) }; }

console.log(JSON.stringify(out, null, 2));