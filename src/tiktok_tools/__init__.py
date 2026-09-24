# tiktok_tools — مجموعة أدوات TikTok بالبايثون (بدون متصفح، بدون مكتبات خارجية)
#
# كل ملف = أداة بوظيفة محددة:
#   http.py       ⚙️  طلبات HTTP موحّدة (هوية + احتمالية تحمل الأخطاء)
#   ids.py        🔎  جمع معرّفات فيديوهات الحساب (Urlebird / Jina / يدوي)
#   metadata.py   📊  بيانات الفيديو الرسمية (oEmbed + embed/v2)
#   download.py   ⬇️  تنزيل الفيديو MP4 من CDN
#   storage.py    💾  حفظ النتائج (JSON لكل فيديو + CSV ملخص)
#   collector.py  🧠  مدير الجمع: حساب كامل في خطوة واحدة
#   probe.py      🔬  تشخيص سلوك الجدران (WAF / Orcas / CDN)
#   sign.py       ✍️  توقيعات X-Gnarly و X-Bogus (نقل كامل من JS)

from . import http, ids, metadata, download, storage, collector, probe, sign

__all__ = ["http", "ids", "metadata", "download", "storage", "collector", "probe", "sign"]
__version__ = "1.0.0"