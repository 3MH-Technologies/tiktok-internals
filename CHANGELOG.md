# Changelog

All notable changes to **tiktok-internals** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [1.0.0] — 2026-09-24

### Added
- Python package `tiktok_tools` (stdlib only): `http`, `ids`, `metadata`, `download`, `storage`, `collector`, `probe`, `sign`, `cli`.
- Command-line gateway `tiktok-tools` with five subcommands: `video`, `user`, `probe`, `sign`, `selftest`.
- **X-Gnarly** encoder (webmssdk `2.0.0.520` / payload `5.3.0`): 16-field TLV payload, custom-sigma ChaCha variant, key-embedding scheme, custom base64 alphabet — with a self-verification decoder.
- **X-Bogus** encoder: double-MD5 params/body, RC4+re-alphabeted UA hash, filter/scramble, final RC4, custom base64 (verified **bit-identical** to the Node reference for identical inputs).
- Offline unit tests (`tests/`) covering signatures, ID parsing, and videoData normalization.
- CI workflow (GitHub Actions): install + pytest across Python 3.10–3.13.
- Research bundle: Arabic deep-dive report `research/tiktok-api-internals.md`, Node clean-room signer references under `research/signer/`, JS collectors under `research/webmssdk-analysis/`.

### Verified live (2026-09-24)
- `oEmbed` + `embed/v2` data pipeline: metadata for `7673909736131038495` (598,500 views) and a 5.3 MB `ftyp`-valid MP4 download.
- Full-account sweep `user tiktok --ids …`: 3/3 videos collected with live stats.