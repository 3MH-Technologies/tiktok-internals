"""أداة التنزيل — وظيفتها: سحب ملف الفيديو MP4 من CDN إلى القرص.

روابط CDN (v16m/v45/v58.tiktokcdn.com) تطلب Range وتخدمني بحالة 206
مع جسم `video/mp4`. ننزل على شكل شرائح حتى لا نعلق الذاكرة مع ملفات كبيرة.
"""
from __future__ import annotations

import ssl
import urllib.error
import urllib.request

from . import http

_CTX = ssl.create_default_context()


def download_video(play_url: str, dest: str, timeout: int = 120) -> tuple[bool, object]:
    """نزّل الفيديو من رابط التشغيل إلى المسار dest.

    ترجع: (نجح?, الحجم_بايت أو نص_الخطأ)
    """
    req = urllib.request.Request(
        play_url,
        headers={"User-Agent": http.UA, "Range": "bytes=0-"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            if r.status not in (200, 206):
                return False, f"HTTP {r.status}"
            total = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
            return True, total
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
        return False, str(e)[:120]