// user-collect.mjs — automated full-account collector (no browser, no signature).
//
// Pipeline:
//   1. Fetch profile video IDs (primary: Urlebird mirror — no WAF; fallback: Jina reader)
//   2. For each ID: official oEmbed (metadata) + embed/v2 (full videoData)
//   3. Save per-video JSON + a summary CSV, optionally download the MP4s.
//
// Usage:
//   node user-collect.mjs USERNAME [--limit N] [--delay MS] [--download OUTDIR] [--maxdl K]
//
// Examples:
//   node user-collect.mjs tiktok --limit 8
//   node user-collect.mjs tiktok --limit 6 --download videos/tiktok --maxdl 3

import fs from "node:fs";
import path from "node:path";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const o = { user: null, limit: 12, delay: 1500, download: null, maxdl: 0, ids: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--") && !o.user) o.user = a;
    else if (a === "--limit") o.limit = Number(argv[i + 1]);
    else if (a === "--delay") o.delay = Number(argv[i + 1]);
    else if (a === "--download") o.download = argv[i + 1];
    else if (a === "--maxdl") o.maxdl = Number(argv[i + 1]);
    else if (a === "--ids" || a === "--list") o.ids = argv[i + 1];
  }
  return o;
}

function readIds(idsArg) {
  if (idsArg.startsWith("@")) {
    const raw = fs.readFileSync(idsArg.slice(1), "utf8");
    return [...new Set(raw.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
  }
  return [...new Set(idsArg.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
}

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

// ---- Step 1: profile -> video IDs (primary: Urlebird, fallback: Jina reader) ----
async function fetchIdsUrlebird(user) {
  const res = await fetch(`https://www.urlebird.com/user/${user}/`, {
    headers: { "user-agent": UA, accept: "text/html" },
  });
  if (res.status !== 200) return { ok: false, error: `HTTP ${res.status}` };
  const text = await res.text();
  const ids = [...new Set([...text.matchAll(/urlebird\.com\/video\/(?:[^"/]*?-)?(\d{15,21})\//g)].map((m) => m[1]))];
  return { ok: ids.length > 0, ids };
}

async function fetchIdsJina(user) {
  const res = await fetch(`https://r.jina.ai/https://www.tiktok.com/@${user}`, {
    headers: { "user-agent": UA, accept: "text/plain, text/markdown" },
  });
  if (res.status !== 200) return { ok: false, error: `HTTP ${res.status}` };
  const text = await res.text();
  const ids = [...new Set([...text.matchAll(/\/video\/(\d{15,21})/g)].map((m) => m[1]))];
  return { ok: ids.length > 0, ids };
}

// ---- Step 2a: official oEmbed (fast metadata) ----
async function fetchOembed(id) {
  try {
    const r = await fetch(`https://www.tiktok.com/oembed?url=https://www.tiktok.com/@_/video/${id}&format=json`, {
      headers: { "user-agent": UA, accept: "application/json" },
    });
    const j = await r.json().catch(() => null);
    return { ok: r.status === 200, status: r.status, json: j };
  } catch (e) {
    return { ok: false, error: String(e).slice(0, 60) };
  }
}

// ---- Step 2b: embed/v2 -> full videoData (with 503 retry) ----
async function fetchEmbedData(id) {
  for (let a = 1; a <= 4; a++) {
    const res = await fetch(`https://www.tiktok.com/embed/v2/${id}`, {
      headers: { "user-agent": UA, accept: "text/html", "accept-language": "en-US,en;q=0.9" },
    });
    if (res.status === 200) {
      const html = await res.text();
      const block = balancedExtract(html, '"videoData"');
      if (!block) return { ok: false, error: "no videoData block" };
      try {
        const vd = JSON.parse("{" + block + "}").videoData;
        return { ok: true, vd };
      } catch {
        try {
          const vd = JSON.parse("{" + block.replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029") + "}").videoData;
          return { ok: true, vd };
        } catch { return { ok: false, error: "json parse failed" }; }
      }
    }
    if (res.status === 503 || res.status === 429) { await sleep(6000); continue; }
    return { ok: false, error: `HTTP ${res.status}` };
  }
  return { ok: false, error: "rated (503 after retries)" };
}

function normalize(vd, id) {
  const item = vd.itemInfos || {};
  const author = vd.authorInfos || {};
  return {
    id,
    text: item.text,
    createTime: item.createTime,
    videoMeta: item.video?.videoMeta ?? null,
    stats: {
      digg: item.diggCount, play: item.playCount, comment: item.commentCount, share: item.shareCount,
    },
    author: { nickName: author.nickName, uniqueId: author.uniqueId, secUid: author.secUid, verified: author.verified },
    authorStats: vd.authorStats ?? null,
    music: { title: vd.musicInfos?.musicName, authorName: vd.musicInfos?.authorName },
    hashtags: (vd.challengeInfoList || []).map((c) => ({ name: c.challengeName, id: c.challengeId })),
    cover: (item.covers ?? [])[0] ?? null,
    playUrl: item.video?.urls?.[0] ?? null,
  };
}

// ---- optional download ----
async function downloadPlay(playUrl, dest) {
  const dl = await fetch(playUrl, { headers: { "user-agent": UA, range: "bytes=0-" }, redirect: "follow" });
  if (!dl.ok && dl.status !== 206) return { ok: false, status: dl.status };
  let got = 0;
  const ws = fs.createWriteStream(dest);
  for await (const chunk of dl.body) { ws.write(chunk); got += chunk.length; }
  ws.end();
  await new Promise((r) => ws.on("close", r));
  return { ok: true, bytes: got };
}

// ---- main ----
async function main() {
const args = parseArgs(process.argv.slice(2));
if (!args.user) {
  console.error("usage: node user-collect.mjs USERNAME [--limit N] [--delay MS] [--download DIR] [--maxdl K] [--ids 'id1,id2,...' | --ids @file.txt]");
  process.exitCode = 1;
  return;
}

let ids = [];
let source = "none";
if (args.ids) {
  ids = readIds(args.ids);
  source = "manual(--ids)";
  console.log(`== using manual ID list for @${args.user} ==`);
} else {
  console.log(`== fetching profile @${args.user} (Urlebird first, Jina fallback) ==`);
  for (const [name, fn] of [["Urlebird", fetchIdsUrlebird], ["Jina", fetchIdsJina]]) {
    const r = await fn(args.user);
    if (r.ok) { ids = r.ids; source = name; break; }
    console.log(`  ${name}: ${r.error ?? "no ids in page"}`);
  }
}
if (!ids.length) { console.error("no ids from any source"); process.exitCode = 3; return; }
ids = [...new Set(ids)].slice(0, args.limit);
console.log(`found ${ids.length} video ids (source: ${source}): ${ids.join(", ")}\n`);

const outRoot = path.join(import.meta.dirname, "accounts", args.user);
fs.mkdirSync(outRoot, { recursive: true });
if (args.download) fs.mkdirSync(args.download, { recursive: true });

const rows = [];
let downloads = 0;
for (let n = 0; n < ids.length; n++) {
  const id = ids[n];
  process.stdout.write(`[${n + 1}/${ids.length}] ${id} … `);
  const o = await fetchOembed(id);
  const e = await fetchEmbedData(id);
  if (!e.ok) { console.log(`embed FAILED (${e.error})`); continue; }
  const rec = normalize(e.vd, id);
  fs.writeFileSync(path.join(outRoot, `${id}.json`), JSON.stringify({ oEmbed: o.json, videoData: rec }, null, 2));
  rows.push([
    id, rec.createTime || "", (rec.text || "").replace(/[\n,]/g, " ").slice(0, 60),
    rec.stats.play ?? "", rec.stats.digg ?? "", rec.stats.comment ?? "",
    rec.videoMeta?.duration ?? "", rec.hashtags?.map((h) => h.name).join(";") ?? "",
    rec.author.uniqueId ?? "", rec.playUrl ? "yes" : "no",
  ]);
  let line = `ok (${rec.stats.play ?? "?"} views, ${(rec.hashtags || []).length} tags)`;
  if (args.download && args.maxdl && downloads < args.maxdl && rec.playUrl) {
    const dest = path.join(args.download, `${id}.mp4`);
    const d = await downloadPlay(rec.playUrl, dest);
    if (d.ok) { downloads++; line += ` · dl ${Math.round(d.bytes / 1e6)}MB`; }
  }
  console.log(line);
  await sleep(args.delay);
}

// CSV summary
const csvPath = path.join(import.meta.dirname, "accounts", `${args.user}.csv`);
const csv = ["id,createTime,text,playCount,diggCount,commentCount,durationSec,hashtags,uniqueId,playUrl"]
  .concat(rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")))
  .join("\n");
// UTF-8 BOM so Excel/PowerShell show Arabic + emoji correctly
fs.writeFileSync(csvPath, "\uFEFF" + csv, "utf8");
console.log(`\n== done: ${rows.length}/${ids.length} collected ==`);
console.log(`JSON dir : ${outRoot}`);
console.log(`CSV      : ${csvPath}`);
if (args.download) console.log(`Videos   : ${args.download} (${downloads} downloaded)`);
}

main();