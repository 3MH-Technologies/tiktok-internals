"""أداة HTTP الموحّدة — وظيفتها: تنفيذ كل الطلبات بنفس الهوية وبتحمّل الأعطال.

كل أداة أخرى في الحزمة تمر طلباتها من هنا حتى تضمن:
- User-Agent واحد (شكل متصفح Chrome)
- مهلة زمنية لا تعلق العملية للأبد
- إرجاع حالة HTTP والجسم والهيدرات حتى لو فشلت (لا استثناءات مفاجئة)
"""
from __future__ import annotations

import ssl
import urllib.error
import urllib.parse
import urllib.request

# الهوية الموحدة لجميع الطلبات (متصفح Chrome عادي)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_CTX = ssl.create_default_context()


def get(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
) -> tuple[int, bytes, dict]:
    """وظيفة GET واحدة لكل شيء.

    ترجع: (رمز_الحالة، الجسم_bytes، الهيدرات_dict)
    عند فشل الشبكة ترجع (0, نص_الخطأ, {}) — لا ترمي استثناء.
    """
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, str(e).encode("utf-8", "replace"), {}


def to_text(body: bytes) -> str:
    """حوّل الجسم إلى نص UTF-8 بأمان (أي رمز يتلف يُستبدل بدل التعليق)."""
    return body.decode("utf-8", "replace")