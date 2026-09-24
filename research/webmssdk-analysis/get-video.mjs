// get-video.mjs — official public pipeline, no signature, no browser.
// Usage:
//   node get-video.mjs https://www.tiktok.com/@USER/video/ITEMID [--download out.mp4]
//   node get-video.mjs ITEMID
import fs from "node:fs";
import path from "node:path";

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const out = { id: null, download: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const m = a.match(/\/video\/(\d{15,21})/);
    if (m) out.id = m[1];
    else if (/^\d{15,21}$/.test(a) && !out.id) out.id = a;
    else if (a === "--download") out.download = argv[i + 1];
  }
  return out;
}

// balanced-extract from a marker to its closing brace
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

async function embedFetch(id) {
  for (let a = 1; a <= 4; a++) {
    const res = await fetch(`https://www.tiktok.com/embed/v2/${id}`, {
      headers: { "user-agent": UA, accept: "text/html", "accept-language": "en-US,en;q=0.9" },
    });
    if (res.status === 200) return { html: await res.text() };
    if (res.status === 503 || res.status === 429) await sleep(6000);
    else return { error: `HTTP ${res.status}` };
  }
  return { error: "rate limited (503) after retries" };
}

async function oembed(id) {
  try {
    const r = await fetch(`https://www.tiktok.com/oembed?url=https://www.tiktok.com/@tiktok/video/${id}&format=json`, {
      headers: { "user-agent": UA, accept: "application/json" },
    });
    return { status: r.status, json: await r.json().catch(() => null) };
  } catch (e) {
    return { error: String(e).slice(0, 80) };
  }
}

const args = parseArgs(process.argv.slice(2));
if (!args.id) {
  console.error("usage: node get-video.mjs <videoURL|ID> [--download out.mp4]");
  process.exit(1);
}
const id = args.id;

// 1) oEmbed metadata (official, fast)
const o = await oembed(id);
console.log("== oEmbed ==", o.status);
if (o.json) console.log("-", o.json.title, "\n-", o.json.author_name, `(@${o.json.author_unique_id})\n- thumb:`, (o.json.thumbnail_url || "").slice(0, 90));

// 2) embed/v2 full videoData
const e = await embedFetch(id);
if (e.error) {
  console.error("embed/v2:", e.error);
  process.exit(2);
}
const block = balancedExtract(e.html, '"videoData"');
if (!block) {
  console.error("no videoData block (video unavailable/regional?)");
  process.exit(3);
}
let vd = null;
try { vd = JSON.parse("{" + block + "}").videoData; }
catch {
  try { vd = JSON.parse("{" + block.replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029") + "}").videoData; }
  catch { console.error("videoData parse failed"); process.exit(4); }
}

const item = vd.itemInfos || {};
const author = vd.authorInfos || {};
const music = vd.musicInfos || {};
const playUrl = item.video?.urls?.[0] ?? null;

const record = {
  id, text: item.text, createTime: item.createTime,
  videoMeta: item.video?.videoMeta,
  stats: ["diggCount", "playCount", "commentCount", "shareCount"].reduce((a, k) => ((item[k] !== undefined) && (a[k] = item[k]), a), {}),
  author: { nickName: author.nickName, uniqueId: author.uniqueId, secUid: author.secUid, verified: author.verified },
  authorStats: vd.authorStats,
  music: { title: music.musicName, authorName: music.authorName },
  hashtags: (vd.challengeInfoList || []).map((c) => ({ name: c.challengeName, id: c.challengeId })),
  cover: (item.covers || [])[0],
  playUrl,
};
fs.writeFileSync(`${id}.json`, JSON.stringify(record, null, 2));
console.log("\n== videoData ==", JSON.stringify({ text: record.text, videoMeta: record.videoMeta, stats: record.stats, hashtags: record.hashtags, author: record.author.nickName }, null, 1));
console.log("playUrl:", (playUrl || "NONE").slice(0, 120) + (playUrl ? "…" : ""));
console.log("saved:", `${id}.json`);

// 3) optional download (resume-safe streaming)
if (args.download && playUrl) {
  console.log("\n-- downloading", args.download, "--");
  const dl = await fetch(playUrl, {
    headers: { "user-agent": UA, range: "bytes=0-" },
    redirect: "follow",
  });
  const dest = path.resolve(args.download);
  if (!dl.ok && dl.status !== 206) { console.error("download failed:", dl.status); process.exit(5); }
  const total = Number(dl.headers.get("content-length") || 0);
  let got = 0;
  const ws = fs.createWriteStream(dest);
  for await (const chunk of dl.body) { ws.write(chunk); got += chunk.length; }
  ws.end();
  await new Promise((r) => ws.on("close", r));
  console.log(`saved ${Math.round(got / 1e6)} MB -> ${dest}`);
  const head = fs.readFileSync(dest).subarray(0, 12).toString("hex");
  console.log("mp4 magic check:", head.includes("ftyp") || head.includes("66747970") ? "OK (ftyp)" : head);
}