<div align="center">

# tiktok-internals

**A research-grade Python toolkit for TikTok internals: live public data pipelines, CDN media downloads, and clean-room X-Gnarly / X-Bogus signature implementations.**

[![CI](https://github.com/3MH-Technologies/tiktok-internals/actions/workflows/ci.yml/badge.svg)](https://github.com/3MH-Technologies/tiktok-internals/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

*Zero third-party dependencies · no browser required · verified against the live platform*

</div>

---

## Why this repository exists

This project documents and implements, from a **clean-room / black-box perspective**, how TikTok's public web surfaces behave — and what it takes to reproduce two of its client-side signature schemes byte-for-byte:

| Scheme | Bundle context | Output | Status |
|---|---|---|---|
| **X-Gnarly** | webmssdk `2.0.0.520` / `5.3.0` (verified live 2026-09-24) | 316-char custom-base64 blob | ✔ implemented + round-trip verified |
| **X-Bogus** | webmssdk (mobile web) | 28-char custom-base64 blob | ✔ implemented, **bit-identical** to reference |

Everything was produced by dynamic tracing and black-box probing of the **official CDN bundles** — not by extracting private keys or abusing internal services. The goal is security research and education.

> ⚠️ **Responsible use.** Mass/automated scraping of TikTok, forging platform signatures, and using automated accounts can violate **TikTok's Terms of Service**, platform abuse policies, and local law, and can result in permanent bans. This material is published for **education, security research, and defensive purposes only**. Do not operate at scale, do not bypass access controls you are not authorized to test.

## What's inside

```
tiktok-internals/
├── src/tiktok_tools/       Python package (stdlib only) — one tool per concern
├── tests/                  Unit tests — fully offline (no network in CI)
├── research/               The deep-dive: Arabic report + JS reference research
│   ├── tiktok-api-internals.md   Full Arabic analysis (API mappings, WAF/Orcas gate behaviour, algorithms)
│   ├── signer/             Node clean-room reference (encode520.js, xbogus3.js, cipher, payload, alphabet)
│   └── webmssdk-analysis/  JS collectors (get-video, user-collect, extract-live, msToken-acquire)
└── examples/               Sample live videoData JSON captured from TikTok
```

## The tools (one function each)

| Tool | Module | Responsibility |
|---|---|---|
| ⚙️ HTTP | `tiktok_tools/http.py` | Unified identity (Chrome UA), graceful failure, no surprise exceptions |
| 🔎 IDs | `tiktok_tools/ids.py` | Resolve an account's video IDs — Urlebird → Jina → manual `--ids` |
| 📊 Metadata | `tiktok_tools/metadata.py` | Official per-video data via `oEmbed` + `embed/v2` (503 retry with backoff) |
| ⬇️ Download | `tiktok_tools/download.py` | Stream MP4s from the signed CDN URLs (`Range` requests) |
| 💾 Storage | `tiktok_tools/storage.py` | Per-video JSON + summary CSV (UTF-8-BOM for Excel) |
| 🧠 Collector | `tiktok_tools/collector.py` | Orchestrates a full account sweep in one call |
| 🔬 Probe | `tiktok_tools/probe.py` | Tells "broken link" apart from "IP challenged" (Cloudflare / Orcas drops) |
| ✍️ Signatures | `tiktok_tools/sign.py` | X-Gnarly + X-Bogus generation **and** self-verification |

## Install

```bash
pip install -e .            # or: pip install .
# runtime needs nothing beyond Python 3.10+
```

## Quick start

```bash
# Prove the signature implementations are cryptographically sound (offline)
tiktok-tools selftest

# One video: official metadata + optional MP4 download
tiktok-tools video 7673909736131038495 -o out --download out/video.mp4

# Full account sweep (auto-ID discovery)
tiktok-tools user tiktok --limit 5 --download vids --maxdl 2

# Full account sweep with a manual ID list (most reliable — independent of third-party ID sources)
tiktok-tools user charlidamelio --ids "7141817229032574250,7421199605406158123"

# Diagnose why a URL behaves a certain way
tiktok-tools probe "https://www.tiktok.com/oembed?url=..."

# Signature toys
tiktok-tools sign xbogus "https://www.tiktok.com/api/search/general/full/?keyword=test"
```

## How the data pipeline works (no signature needed)

A large part of the TikTok web API requires the `X-Gnarly`/`X-Bogus` pair plus an `msToken`, and is still silently dropped by the **Orcas** risk engine for non-browser clients. Two official surfaces intentionally do **not** need signatures:

```
video ID ──► /oembed     ──► title, author, thumbnail
        └─► /embed/v2    ──► SSR videoData JSON (text, stats, author, music,
                              hashtags, signed CDN play URLs)
                              └─► GET play URL ──► 206 video/mp4 ──► save
```

Live-verified results (2026-09-24): `598,500` views on a reference video, `3/3` collected from a manual ID list, real `ftyp`-valid MP4s downloaded from `v16m/v45/v58.tiktokcdn.com`.

## Research highlights (see `research/tiktok-api-internals.md` — Arabic)

1. **Live API mapping** — which `/api/*` routes need signatures, which reply `"url doesn't match"` (missing signature), `2483` (login), `205001` (bad ID), and how Orcas silently drops signed-but-suspicious traffic (`tt_orcas_res:1`, empty body).
2. **WAF vs. risk engine** — Slardar challenges on the profile page; `player/v1`, `oEmbed`, and `embed/v2` stay open; `generate_204` msToken refresh flow; header signatures (`tt-ticket-guard-result`, `x-ms-token`, `x-tt-logid`).
3. **Signing chain** — X-Bogus is applied first, then X-Gnarly over the whole query string *including* X-Bogus; `ubcode` default, `strData` layout (magic `538969122`), key-embedding scheme.
4. **Signatures decoded** — X-Gnarly payload (16-field TLV, field 3 = MD5 of the query), ChaCha variant (custom sigma, rounds ∈ [5,20] derived from the key), custom base64 alphabet; X-Bogus steps (double-MD5, RC4+alphabet-shifted UA hash, filter/scramble, final RC4).
5. **msToken** — server-issued token mirrored in `set-cookie` + `x-ms-token`; `X-Mssdk-Info` = XXTEA (delta `0x9E3779B9`, rounds `6+52/n`).
6. **Honest limits** — public surfaces expose only the first ~12–18 videos of a profile; a full archive requires the signed API (`cursor` pagination) behind Orcas.

## Development / contributing

```bash
pip install -e .           # install with console script
python -m pytest -q        # all tests are offline
```

- **Style**: PEP 8, type hints, one public function per responsibility.
- **Testing**: `tests/` exercise pure logic only — no network calls, so CI is deterministic.
- **PRs**: please keep changes dependency-free unless the design truly needs it.

## Credits

**3MH TECHNOLOGIES** — researched, engineered, and verified everything in this repository.

- 🌐 Website: <https://3mh.pages.dev/>
- 💬 Telegram: <https://t.me/j49_c>

## License

MIT — see [LICENSE](LICENSE). The research report and analysis scripts are published for educational purposes; trademarked product names belong to their respective owners.