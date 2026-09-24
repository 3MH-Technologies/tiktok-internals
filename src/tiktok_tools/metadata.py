"""أداة البيانات الرسمية — وظيفتها: جلب بيانات فيديو TikTok من TikTok نفسه.

مساران رسميان لا يحتاجان توقيع X-Gnarly ولا متصفحاً:
  1. oEmbed   → عنوان + اسم الكاتب + صورة مصغرة (سريع، خفيف).
  2. embed/v2 → ملف JSON كامل (videoData): النص، الإحصائيات، المؤلف،
                الموسيقى، الهاشتاقات، وقائمة روابط CDN — فيتح منها رابط التشغيل.

لاحظ: ضغط 503 على embed/v2 شائع، لذلك نعيد المحاولة بنوم 6 ثوانٍ.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

from . import http

_VIDEO_ID_RE = re.compile(r"(\d{15,21})")


def extract_id(value: str) -> str:
    """خذ رابط الفيديو أو رقمه وأرجع المعرّف الرقمي فقط."""
    m = _VIDEO_ID_RE.search(value)
    if not m:
        raise ValueError("ما لقيت معرّف فيديو صالح في المدخل")
    return m.group(1)


def balanced_extract(html: str, marker: str) -> str | None:
    """اقتطع أول كائن JSON من نص HTML يبدأ بعد marker (مع احترام الأقواس والسلاسل)."""
    i = html.find(marker)
    if i == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    j = i
    while j < len(html):
        c = html[j]
        if esc:
            esc = False
        elif in_str:
            if c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return html[i : j + 1]
        j += 1
    return None


def oembed(video_id: str) -> dict | None:
    """وظيفة oEmbed: سلّم JSON الرسمي أو None. الفيديو الميت يعطي HTTP 400 -> None."""
    qs = urllib.parse.urlencode(
        {"url": f"https://www.tiktok.com/@_/video/{video_id}", "format": "json"}
    )
    status, body, _ = http.get(f"https://www.tiktok.com/oembed?{qs}",
                               headers={"Accept": "application/json"})
    if status != 200:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def embed_v2(video_id: str, retries: int = 4) -> dict | None:
    """وظيفة embed/v2: ارجع سجل videoData كاملاً أو None.

    يعيد المحاولة عند 503/429 (ضغط الخادم) مع نوم 6 ثوانٍ.
    الفيديو المحذوف/المقفول يرجع HTTP 400 -> None (لا يتعطل الجمع).
    """
    for attempt in range(1, retries + 1):
        status, body, _ = http.get(
            f"https://www.tiktok.com/embed/v2/{video_id}",
            headers={"Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"},
        )
        if status == 200:
            html = http.to_text(body)
            block = balanced_extract(html, '"videoData"')
            if not block:
                return None
            try:
                return json.loads("{" + block + "}")["videoData"]
            except (json.JSONDecodeError, KeyError):
                return None
        if status in (503, 429):
            time.sleep(6)
            continue
        return None
    return None


def normalize(vd: dict, video_id: str) -> dict:
    """صفّي سجل videoData الخام إلى شكل مرتب لأغراض الحفظ والملخص."""
    item = vd.get("itemInfos") or {}
    author = vd.get("authorInfos") or {}
    video = item.get("video") or {}
    return {
        "id": video_id,
        "text": item.get("text"),
        "createTime": item.get("createTime"),
        "videoMeta": video.get("videoMeta"),
        "stats": {
            "digg": item.get("diggCount"),
            "play": item.get("playCount"),
            "comment": item.get("commentCount"),
            "share": item.get("shareCount"),
        },
        "author": {
            "nickName": author.get("nickName"),
            "uniqueId": author.get("uniqueId"),
            "secUid": author.get("secUid"),
            "verified": author.get("verified"),
        },
        "authorStats": vd.get("authorStats"),
        "music": {
            "title": (vd.get("musicInfos") or {}).get("musicName"),
            "authorName": (vd.get("musicInfos") or {}).get("authorName"),
        },
        "hashtags": [
            {"name": c.get("challengeName"), "id": c.get("challengeId")}
            for c in (vd.get("challengeInfoList") or [])
        ],
        "cover": (item.get("covers") or [None])[0],
        "playUrl": (video.get("urls") or [None])[0],
    }


def fetch_complete(video_id: str) -> tuple[dict | None, dict | None]:
    """وظيفة مجمِّعة: oEmbed + embed/v2 معاً (نتيجة واحدة للنداءات البسيطة)."""
    return oembed(video_id), embed_v2(video_id)