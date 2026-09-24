"""أداة الجمع الشامل — وظيفتها: سحب حساب TikTok كاملاً (بيانات + فيديوهات).

تدير الأداتين السابقتين (ids ثم metadata/download/storage) في تسلسل واحد:
  1. جلب معرّفات الفيديوهات (تلقائي أو يدوي).
  2. لكل معرّف: oEmbed + embed/v2 (إعادة محاولة عند 503).
  3. حفظ JSON + إضافة صف CSV، وتنزيل MP4 اختياري بعدد أقصى.
  4. ترجع ملخصاً نهائياً أين نُزعت الملفات.

المخرجات تحت:  <هنا>/outputs/accounts/<user>/
"""
from __future__ import annotations

import os
import time

from . import download, ids, metadata, storage

_OUTPUTS = os.path.join(os.getcwd(), "outputs")


def collect_account(
    user: str,
    limit: int = 12,
    delay: float = 1.5,
    download_dir: str | None = None,
    maxdl: int = 0,
    manual: str | None = None,
) -> dict:
    """الوظيفة الرئيسية: اجمع حساباً كاملاً وارجع ملخص الإنجاز."""
    video_ids, source, note = ids.collect(user, manual)
    if not video_ids:
        print(f"✗ ما لقيت أي معرّف (كل المصادر فشلت: {note})")
        return {"ok": False, "reason": note}

    video_ids = video_ids[:limit]
    print(f"✔ وُجد {len(video_ids)} فيديو (المصدر: {source}): {', '.join(video_ids)}\n")

    out_root = os.path.join(_OUTPUTS, "accounts", user)
    os.makedirs(out_root, exist_ok=True)
    if download_dir:
        os.makedirs(download_dir, exist_ok=True)

    rows: list[list[object]] = []
    downloaded = 0
    for n, vid in enumerate(video_ids, 1):
        print(f"[{n}/{len(video_ids)}] {vid} … ", end="", flush=True)
        o = metadata.oembed(vid)
        vd = metadata.embed_v2(vid)
        if vd is None:
            print(f"فشل (المصدر الرسمي يرفض — محذوف أو مقفول)")
            continue
        rec = metadata.normalize(vd, vid)
        storage.save_json(out_root, vid, o, rec)

        tags = ";".join(h["name"] for h in rec["hashtags"] if h.get("name"))
        rows.append([
            vid,
            rec["createTime"] or "",
            (rec["text"] or "").replace("\n", " ")[:60],
            rec["stats"]["play"] or "",
            rec["stats"]["digg"] or "",
            rec["stats"]["comment"] or "",
            (rec["videoMeta"] or {}).get("duration") or "",
            tags,
            (rec["author"] or {}).get("uniqueId") or "",
            "yes" if rec["playUrl"] else "no",
        ])

        line = f"تم — {rec['stats']['play'] or '?'} مشاهدة، {len(rec['hashtags'])} هاشتاق"
        if download_dir and maxdl and downloaded < maxdl and rec.get("playUrl"):
            dest = os.path.join(download_dir, f"{vid}.mp4")
            ok, info = download.download_video(rec["playUrl"], dest)
            if ok:
                downloaded += 1
                line += f" · تحميل {round(int(info) / 1_000_000, 1)}MB"
        print(line)
        time.sleep(delay)

    csv_path = storage.write_csv(
        os.path.join(_OUTPUTS, "accounts", f"{user}.csv"), rows
    )
    summary = {
        "ok": True,
        "user": user,
        "collected": len(rows),
        "attempted": len(video_ids),
        "source": source,
        "json_dir": out_root,
        "csv": csv_path,
        "videos_dir": download_dir,
        "downloaded": downloaded,
    }
    print(f"\n== النهاية: {len(rows)}/{len(video_ids)} مجمعة ==")
    print(f"JSON  : {out_root}")
    print(f"CSV   : {csv_path}")
    if download_dir:
        print(f"فيديو : {download_dir} ({downloaded} منزّل)")
    return summary