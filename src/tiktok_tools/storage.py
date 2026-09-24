"""أداة الحفظ — وظيفتها: تفريغ النتائج على القرص بشكل منظم.

- JSON لكل فيديو (oEmbed + videoData المرتب): سهل القراءة برمجياً.
- CSV ملخص (بتوقيع UTF-8-BOM): يفتح صح في Excel بالعربي والإيموجي.
"""
from __future__ import annotations

import csv
import json
import os


def save_json(out_dir: str, video_id: str, oembed: dict | None, record: dict | None) -> str:
    """احفظ ملف JSON واحد باسم <video_id>.json وارجع مساره."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{video_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"oEmbed": oembed, "videoData": record}, f, ensure_ascii=False, indent=2)
    return path


def write_csv(path: str, rows: list[list[object]]) -> str:
    """اكتب ملف ملخص CSV (ترويسة + صفوف) بترميز UTF-8-BOM، وارجع المسار."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    header = ["id", "createTime", "text", "playCount", "diggCount",
              "commentCount", "durationSec", "hashtags", "uniqueId", "playUrl"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)
    return path