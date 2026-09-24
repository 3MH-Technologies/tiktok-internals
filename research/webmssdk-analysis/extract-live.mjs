// Extract live video data from official embed/v2 SSR (browser-less, signed-free)
// Then verify the play URLs actually stream by downloading a few bytes.
import fs from "node:fs";
import path from "node:path";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36";
const ids = ["7676134473112489247", "7675779662903069983", "7675385273848450334", "7673909736131038495"];
const outDir = path.join(import.meta.dirname, "live-videos");
fs.mkdirSync(outDir, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getPage(id) {
  for (let a = 1; a <= 4; a++) {
    const res = await fetch(`https://www.tiktok.com/embed/v2/${id}`, {
      headers: { "user-agent": UA, accept: "text/html", "accept-language": "en-US,en;q=0.9" },
    });
    if (res.status === 200) return { status: res.status, html: await res.text() };
    if (res.status === 503 || res.status === 429) await sleep(7000);
    else { const t = await res.text().catch(() => ""); return { status: res.status, html: t }; }
  }
  return { status: 503, html: "" };
}

// balanced-extract from the marker to the closing brace
function balancedExtract(html, marker) {
  const i = html.indexOf(marker);
  if (i === -1) return null;
  let depth = 0, inStr = false, esc = false, j = i;
  for (; j < html.length; j++) {
    const c = html[j];
    if (esc) { esc = false; continue; }
    if (inStr) { if (c === "\\") esc = true; else if (c === '"') inStr = false; continue; }
    if (c === '"') inStr = true;
    else if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) break; }
  }
  return depth === 0 ? html.slice(i, j + 1) : null;
}

// repair JSON that was HTML-escaped by the server
function repairJson(raw) {
  return raw
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029")
    .replace(/\u00a0/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

const summary = [];
for (const id of ids) {
  const page = await getPage(id);
  const block = balancedExtract(page.html, '"videoData"');
  if (!block) { summary.push({ id, status: page.status, error: "no videoData block" }); continue; }
  let vd = null;
  const wrapped = "{" + block + "}";
  try { vd = JSON.parse(wrapped).videoData; } catch {
    try { vd = JSON.parse(repairJson(wrapped)).videoData; } catch {
      summary.push({ id, status: page.status, error: "json parse failed", head: block.slice(0, 400) });
      continue;
    }
  }
  // normalize
  const item = vd.itemInfos || {};
  const author = vd.authorInfos || {};
  const music = vd.musicInfos || {};
  const authorStats = vd.authorStats || {};
  const stats = ["diggCount", "shareCount", "playCount", "commentCount", "collectCount"]
    .reduce((a, k) => (item[k] !== undefined && (a[k] = item[k]), a), {});
  const play = (item.video && item.video.urls) ? item.video.urls.slice(0, 5) : [];
  fs.writeFileSync(path.join(outDir, `${id}.json`), JSON.stringify(vd, null, 2));
  const rec = {
    id: item.id, status: page.status,
    text: item.text, createTime: item.createTime,
    videoMeta: item.video && item.video.videoMeta,
    author: { nickname: author.nickName, uniqueId: author.uniqueId, secUid: author.secUid, verified: author.verified },
    authorStats,
    music: { title: music.musicName, authorName: music.authorName, playUrl: music.playUrl },
    stats,
    play1: play[0] ?? null,
    cover: (item.covers ?? [])[0] ?? null,
  };
  summary.push(rec);
}

// verify: GET first bytes of each play URL (follow redirects to CDN)
const verify = [];
for (const s of summary) {
  if (!s.play1) { verify.push({ id: s.id, error: "no play url" }); continue; }
  try {
    const r = await fetch(s.play1, {
      headers: { "user-agent": UA, range: "bytes=0-2048" },
      redirect: "follow", method: "GET",
    });
    const ab = await r.arrayBuffer().catch(() => new Uint8Array(0).buffer);
    const bytes = new Uint8Array(ab).slice(0, 16);
    const hexHead = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
    // MP4 starts with ftyp box typically
    verify.push({ id: s.id, status: r.status, bytes: ab.byteLength, ctype: r.headers.get("content-type"), cdn: r.url?.slice(0, 80), hexHead, looksLikeMp4: hexHead.includes("ftyp") });
  } catch (e) { verify.push({ id: s.id, error: String(e).slice(0, 80) }); }
}

console.log(JSON.stringify({ summary, verify }, null, 1));