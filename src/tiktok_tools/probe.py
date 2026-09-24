"""أداة التشخيص — وظيفتها: فحص سريع لسلوك الجدران على رابط معيّن.

مفيدة للتمييز بين:
  - «الرابط انكسر»           (404/400 مع جسم منطقي)
  - «الواجهة تتحدى الـ IP»   (403 + "Just a moment…" من Cloudflare)
  - «الـ Orcas يسقط الطلب صامتاً» (200 لكن جسم فارغ — نقاط استجابة TikTok)
"""
from __future__ import annotations

import re

from . import http

_JUST_A_MOMENT = re.compile(r"Just a moment|challenge", re.I)


def probe(url: str) -> dict:
    """افحص رابطاً واحداً ورجع ما يراه عميلنا من ناحية الشبكة.

    الحقول: الحالة، الطول، نوع المحتوى، هل يشبه تحدّي Cloudflare، أول 150 حرفاً.
    """
    status, body, headers = http.get(url, headers={"Accept": "text/html, */*"})
    text = http.to_text(body)
    return {
        "url": url[:110],
        "status": status if status else "خطأ شبكة",
        "bytes": len(body),
        "content_type": headers.get("Content-Type") or headers.get("content-type") or "",
        "cloudflare_challenge": bool(_JUST_A_MOMENT.search(text[:500])) and status == 403,
        "x_ms_token": bool(headers.get("x-ms-token")),
        "orcas_drop": status == 200 and not body,
        "head": re.sub(r"\s+", " ", text[:150]),
    }


def probe_many(urls: list[str]) -> list[dict]:
    """افحص مجموعة روابط واحدة بعد الأخرى (تشخيص مقارن)."""
    return [probe(u) for u in urls]