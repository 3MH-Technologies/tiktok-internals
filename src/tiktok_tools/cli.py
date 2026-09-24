"""Command-line gateway — one command per tool.

Usage:
    tiktok-tools video <url|id> [-o DIR] [--download PATH]
    tiktok-tools user  <username> [--limit N] [--delay SECS] [--download DIR] [--maxdl K] [--ids LIST|@FILE]
    tiktok-tools probe <url> [--multi url1,url2,...]
    tiktok-tools sign  xbogus <url> | gnarly [--query Q] [--body B] [--ua UA] | verify <token> [--query Q] [--body B] [--ua UA]
    tiktok-tools selftest
"""
from __future__ import annotations

import argparse
import sys

from tiktok_tools import collector, download as dl, metadata, probe as probe_mod, sign
from tiktok_tools import storage as storage_mod


def _ensure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def cmd_video(args: argparse.Namespace) -> int:
    """Single video: fetch official data + optional save/download."""
    video_id = metadata.extract_id(args.target)
    print(f"📎 video {video_id} ← official oEmbed + embed/v2 …")
    o = metadata.oembed(video_id)
    vd = metadata.embed_v2(video_id)
    if vd is None:
        print("✗ video unavailable (deleted/blocked/dead — HTTP 400 from the official source)")
        return 1
    rec = metadata.normalize(vd, video_id)
    st = rec["stats"]
    print(f"✔ title   : {(o or {}).get('title') or rec['text'] or '(no caption)'}")
    print(f"  views   : {st['play']:,}  |  likes: {st['digg']:,}  |  "
          f"comments: {st['comment']:,}  |  shares: {st['share']:,}")
    print(f"  author  : {rec['author']['uniqueId']} (@{rec['author']['nickName']})")
    if rec["hashtags"]:
        print(f"  hashtags: {', '.join(h['name'] for h in rec['hashtags'])}")
    print(f"  music   : {rec['music']['title']} — {rec['music']['authorName']}")
    if args.out_dir:
        path = storage_mod.save_json(args.out_dir, video_id, o, rec)
        print(f"  💾 saved : {path}")
    if args.download and rec["playUrl"]:
        ok, info = dl.download_video(rec["playUrl"], args.download)
        if ok:
            print(f"  ⬇ video  : {round(int(info) / 1_000_000, 1)}MB -> {args.download}")
        else:
            print(f"  ⬇ failed : {info}")
    elif args.download:
        print("  ⬇ no CDN URL present in this data")
    return 0


def cmd_user(args: argparse.Namespace) -> int:
    """Full account sweep."""
    summary = collector.collect_account(
        user=args.username,
        limit=args.limit,
        delay=args.delay,
        download_dir=args.download,
        maxdl=args.maxdl,
        manual=args.ids,
    )
    return 0 if summary.get("ok") else 1


def cmd_probe(args: argparse.Namespace) -> int:
    """Diagnose whether a URL is broken or the client is being challenged."""
    urls = [u for u in (args.target.split(",") if "," in args.target else [args.target]) if u]
    for p in probe_mod.probe_many(urls):
        print(f"== {p['url']}")
        print(f"   status: {p['status']} | size: {p['bytes']} B | type: {p['content_type']}")
        print(f"   cloudflare challenge: {'⚠ yes' if p['cloudflare_challenge'] else 'no'} | "
              f"orcas drop (empty 200): {'yes' if p['orcas_drop'] else 'no'} | "
              f"msToken issued: {'yes' if p['x_ms_token'] else 'no'}")
        print(f"   head: {p['head']}\n")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    """Signature toolbox: X-Bogus / X-Gnarly / verify."""
    if args.mode == "xbogus":
        print(sign.generate_xbogus(args.url, args.ua))
    elif args.mode == "gnarly":
        print(sign.encode_gnarly(query_string=args.query, body=args.body, user_agent=args.ua))
    elif args.mode == "verify":
        r = sign.verify_gnarly(args.token, args.query, args.body, args.ua)
        print("✔ signature is mathematically valid (fields match inputs)"
              if r["ok"] else "✗ signature mismatch")
        print(f"   cipher len: {r.get('xlen')} B | rounds: {r.get('rounds')} | "
              f"payload: {r.get('payloadVersion')} | sdk: {r.get('sdkVersion')}")
        print(f"   field3 == md5(query): {r.get('field3_matches_query_md5')}")
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    """Prove both signature engines behave exactly as the reference."""
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"
    url = "https://www.tiktok.com/api/search/general/full/?keyword=test"

    bogus = sign.generate_xbogus(url, ua, timestamp=1_700_000_000)
    print(f"X-Bogus (fixed ts): {bogus}  | length: {len(bogus)}")
    assert len(bogus) == 28, "expected 28-char X-Bogus"

    token = sign.encode_gnarly(url, "", ua)
    print(f"X-Gnarly: {token[:60]}…  | length: {len(token)}")
    v = sign.verify_gnarly(token, url, "", ua)
    print(f"self-check: {'✔ PASS' if v['ok'] else '✗ FAIL'} "
          f"(rounds={v.get('rounds')}, payload={v.get('payloadVersion')})")
    assert v["ok"], "X-Gnarly self-verification failed"
    print("\nAll self-checks passed ✅")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tiktok-tools",
        description="Python toolkit for TikTok internals — one tool per responsibility "
                    "(no browser, no dependencies).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("video", help="fetch official data for a single video")
    v.add_argument("target", help="video URL or numeric ID")
    v.add_argument("-o", "--out-dir", help="directory to save the JSON")
    v.add_argument("--download", help="path to save the MP4")
    v.set_defaults(fn=cmd_video)

    u = sub.add_parser("user", help="full account sweep (data + optional downloads)")
    u.add_argument("username", help="username without @")
    u.add_argument("--limit", type=int, default=12, help="max videos (default 12)")
    u.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    u.add_argument("--download", help="directory for MP4 downloads")
    u.add_argument("--maxdl", type=int, default=0, help="max downloads")
    u.add_argument("--ids", help="manual list 'a,b,c' or '@file.txt' (bypasses ID sources)")
    u.set_defaults(fn=cmd_user)

    pr = sub.add_parser("probe", help="diagnose gates on a URL")
    pr.add_argument("target", help="URL, or comma-separated URLs")
    pr.set_defaults(fn=cmd_probe)

    sg = sub.add_parser("sign", help="generate/verify X-Bogus and X-Gnarly")
    sg.add_argument("mode", choices=["xbogus", "gnarly", "verify"])
    sg.add_argument("url", nargs="?", default="", help="request URL (for xbogus)")
    sg.add_argument("--query", default="", help="query string (for gnarly)")
    sg.add_argument("--body", default="", help="request body (for gnarly)")
    sg.add_argument("--ua", default="", help="user-agent (for gnarly/xbogus)")
    sg.add_argument("--token", default="", help="signature to verify")
    sg.set_defaults(fn=cmd_sign)

    st = sub.add_parser("selftest", help="self-verify the signature engines")
    st.set_defaults(fn=cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8()
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as e:  # surface friendly errors without noisy tracebacks
        print(f"✗ error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())