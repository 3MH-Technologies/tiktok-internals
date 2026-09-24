# Research

Where the deep analysis lives — everything produced by **black-box probing and
dynamic tracing of TikTok's official CDN bundles**, with clean-room reference
implementations.

| Path | Contents |
|---|---|
| `tiktok-api-internals.md` | Full Arabic deep-dive: live API mapping, WAF/Orcas gate behaviour, signing chain, X-Gnarly/X-Bogus/msToken/XXTEA walkthroughs, public data pipeline. |
| `signer/` | Node clean-room reference encoder: `encode520.js` (X-Gnarly), `xbogus3.js` (X-Bogus), plus `cipher.js`, `payload.js`, `alphabet.js` primitives. |
| `webmssdk-analysis/` | JS collector scripts: `get-video.mjs`, `user-collect.mjs`, `extract-live.mjs`, `msToken-acquire.mjs`, `probe-local.mjs`. |

> ℹ️ The raw `webmssdk_*.js` bundles downloaded from TikTok's CDN for analysis
> are **not committed** to this repository (see `.gitignore`). They are
> third-party proprietary artifacts; only our own analysis and clean-room
> re-implementations are published here.

## Verifying the Node reference encoders

```bash
cd research/signer
node -e "import('./xgnarly2.js')"          # see exports in each file
node --input-type=module -e "
  import { generateXBogus } from './xbogus3.js';
  console.log(generateXBogus('https://www.tiktok.com/api/search/general/full/?keyword=test',
                             'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36',
                             1700000000));
"
# expected: DFtzs1rXVpR-pNbPq-XJ-xoHc/PB   (matches tests/test_sign.py::test_xbogus_reference_vector)
```

## Ethical boundary

These findings document publicly observable behaviour and Google-able results.
Use them for education, detection, and defense. Mass scraping and signature
forgery against TikTok violate its Terms of Service.