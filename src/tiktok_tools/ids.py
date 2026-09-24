"""أداة جمع المعرّفات — وظيفتها: إيجاد أرقام فيديوهات حساب TikTok.

تسلسل المحاولة (أي واحد ينجح يكفي):
  1. Urlebird  — مرآة عامة بلا WAF خاصة بها، تعرض أول ~18 فيديو لكل حساب.
  2. Jina      — بروكسي قراءة خلف متصفح حقيقي يعبر الـ Slardar WAF ويعطينا ~12 معرّف.
  3. يدوي      — قائمة يمررها المستخدم (نص أو ملف) من أي مصدر خارجي.

النتيجة دائماً: (قائمة_ids_مرتبة_دون_تكرار, اسم_المصدر, ملاحظة)
"""
from __future__ import annotations

import re

from . import http

_ID_RE_URLEBIRD = re.compile(r"urlebird\.com/video/(?:[^\"/]*?-)?(\d{15,21})/")
_ID_RE_TIKTOK = re.compile(r"/video/(\d{15,21})")


def urlebird_ids(user: str) -> tuple[list[str] | None, str]:
    """اصفح مرآة Urlebird واستخرج معرّفات الفيديوهات الـ 15-21 رقماً."""
    status, body, _ = http.get(
        f"https://www.urlebird.com/user/{user}/", headers={"Accept": "text/html"}
    )
    if status != 200:
        return None, f"HTTP {status}"
    ids = sorted(set(_ID_RE_URLEBIRD.findall(http.to_text(body))))
    return (ids or None), ("ok" if ids else "صفحة بدون فيديوهات")


def jina_ids(user: str) -> tuple[list[str] | None, str]:
    """استخدم بروكسي Jina Reader لقراءة ملف البروفايل خلف الـ WAF كـ Markdown."""
    status, body, _ = http.get(
        f"https://r.jina.ai/https://www.tiktok.com/@{user}",
        headers={"Accept": "text/plain, text/markdown"},
        timeout=45,
    )
    if status != 200:
        return None, f"HTTP {status}"
    ids = sorted(set(_ID_RE_TIKTOK.findall(http.to_text(body))))
    return (ids or None), ("ok" if ids else "الصفحة رجعت بدون قائمة فيديوهات")


def from_text(text: str) -> list[str]:
    """افكك قائمة يدوية: أرقام مفصولة بفواصل/مسافات/أسطر، بدون تكرار."""
    return list(dict.fromkeys(re.findall(r"\d{15,21}", text)))


def from_file(path) -> list[str]:
    """اقرأ القائمة من ملف (سطر لكل رقم أو مفصولة بفواصل)."""
    with open(path, "r", encoding="utf-8") as f:
        return from_text(f.read())


def collect(user: str, manual: str | None = None) -> tuple[list[str], str, str]:
    """الوظيفة الرئيسية: اجلب معرّفات الحساب بأي مصدر متاح.

    ترجع: (ids, اسم_المصدر, ملاحظة)
    - manual بيدأب بحرف @ => مساره ملف؛ وإلا يعتبر قائمة نصية.
    """
    if manual:  # المصدر اليدوي أولاً لأنه الأقوى ولا يعتمد على جدران
        ids = from_file(manual[1:]) if manual.startswith("@") else from_text(manual)
        if ids:
            return ids, "يدوي(--ids)", "ok"
        return [], "يدوي(--ids)", "القائمة اليدوية فارغة"

    for name, fn in (("Urlebird", urlebird_ids), ("Jina", jina_ids)):
        ids, note = fn(user)
        if ids:
            return ids, name, note
        print(f"  ⚠ {name}: {note}")
    return [], "لا أحد", "كل المصادر فشلت"