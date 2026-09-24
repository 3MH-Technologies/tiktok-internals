// msToken acquisition attempt via multiple paths
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
let jar = {};
function store(res) {
  const sc = res.headers.getSetCookie ? res.headers.getSetCookie() : [];
  for (const line of sc) { const m = line.match(/([^=;,\s]+)=([^;]*)/); if (m) jar[m[1]] = m[2]; }
  return sc.length;
}
const cj = () => Object.entries(jar).map(([k, v]) => `${k}=${v}`).join("; ");
async function get(url, opts = {}) {
  const headers = { "user-agent": UA, accept: opts.accept || "application/json, text/html, */*", referer: opts.referer || "https://www.tiktok.com/" };
  if (Object.keys(jar).length) headers.cookie = cj();
  const res = await fetch(url, { headers, method: opts.method || "GET", body: opts.body, redirect: "manual" });
  store(res);
  const text = await res.text();
  return { status: res.status, len: text.length, head: text.slice(0, 70) };
}

const common = "aid=1988&app_language=en&app_name=tiktok_web&browser_language=en&browser_name=Mozilla&browser_online=true&browser_platform=Win32&channel=tiktok_web&cookie_enabled=true&device_platform=web_pc&focus_state=true&history_len=2&is_fullscreen=false&is_page_visible=true&language=en&os=windows&priority_region=&referer=&region=US&screen_height=900&screen_width=1600&tz_name=America/New_York&webcast_language=en";

const steps = [];
steps.push(["challenge detail", await get("https://www.tiktok.com/api/challenge/detail/?challengeName=fyp&" + common)]);
steps.push(["discover/full", await get("https://www.tiktok.com/api/discover/full/?count=5&" + common)]);
steps.push(["feed/list", await get("https://www.tiktok.com/api/feed/list/?count=5&" + common)]);
steps.push(["user/detail +msToken=", await get("https://www.tiktok.com/api/user/detail/?uniqueId=tiktok&" + common + "&msToken=")]);
steps.push(["search general", await get("https://www.tiktok.com/api/search/general/full/?keyword=test&count=5&" + common)]);
steps.push(["post/item_list +msToken=", await get("https://www.tiktok.com/api/post/item_list/?secUid=MS4wLjABAAAAv7iSuuXCJ9bGx1p0c9q9l2xAlHF2lXAl8yYVq0qf4&count=5&cursor=0&" + common + "&msToken=")]);

const msBody = JSON.stringify({
  magic: 538969122, version: 1, dataType: 8,
  strData: "fWOdJTQR3/jwmZqBBsPO6tdNEc1jX7YTwPg0Z8CT+j3HScLFbj2Zm1XQ7/lqgSutntVKLJWaY3Hc/+vc0h+So9N1t6EqiImu5jKyUa+S4NPy6cNP0x9CUQQgb4+RRihCgsn4QyV8jivEFOsj3N5zFQbzXRyOV+9aG5B5EAnwpn8C70llsWq0zJz1VjN6y2KZiB",
  tspFromClient: Date.now(), ulr: 0
});
try {
  const r = await fetch("https://mssdk.bytedance.com/web/common", {
    method: "POST",
    headers: { "content-type": "application/json", "user-agent": UA, "referer": "https://www.tiktok.com/", ...(Object.keys(jar).length ? { cookie: cj() } : {}) },
    body: msBody,
  });
  store(r);
  const t = await r.text();
  steps.push(["mssdk/web/common POST", { status: r.status, len: t.length, head: t.slice(0, 120) }]);
} catch (e) {
  steps.push(["mssdk/web/common POST", { error: String(e).slice(0, 100) }]);
}

console.log(JSON.stringify({ jarKeys: Object.keys(jar), msTokenLen: (jar.msToken || "").length, msTokenHead: (jar.msToken || "").slice(0, 40), steps }, null, 1));