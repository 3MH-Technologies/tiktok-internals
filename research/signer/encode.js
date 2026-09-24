import { createHash, randomBytes } from "node:crypto";
import { encodeBase64 } from "./alphabet.js";
import { chachaXor, deriveRounds } from "./cipher.js";
import { encodePayload } from "./payload.js";

// Magic byte prepended to every X-Gnarly payload. Computed at runtime
// inside webmssdk as `((1 << 6) ^ (1 << 3) ^ 3) & 0xFF` = 75 = 'K' —
// hard-coded here for clarity. The decoded byte stream of every valid
// X-Gnarly we've ever seen begins with this byte.
export const MAGIC_BYTE = 75; // 'K'

const md5 = (s) => createHash("md5").update(s, "utf8").digest("hex");

/**
 * Build a fully-formed X-Gnarly URL parameter value.
 *
 * Inputs follow the producer call shape we recovered by tracing
 * webmssdk_2.0.0.485 dynamically (see README §5):
 *
 *   queryString  – the URL's `?...` portion *without* the leading `?`,
 *                  with msToken substituted in and X-Bogus / X-Gnarly
 *                  stripped. All other request params remain.
 *   body         – the request body. For GETs this is the empty string.
 *                  Critical: pass "" (not undefined) — TikTok rejects the
 *                  ffff... sentinel that webmssdk emits for nullish.
 *   userAgent    – navigator.userAgent at the moment of signing.
 *   counters     – the secsdk request counter object. The page bundle
 *                  passes its live tally; for off-page signing we just
 *                  approximate with small ints — TikTok does not appear
 *                  to validate the exact values, only the format.
 *   options
 *     .ubcode                – field 2 (default 4 for /api/post/...)
 *     .sdkVersion            – field 10 (default "1.0.0.368")
 *     .timestampMs           – override clock for deterministic tests
 *     .randomKey             – override randomBytes(48) for deterministic tests
 *
 * Returns the encoded X-Gnarly string (≈332 chars for ZTCA payload size).
 */
export function encode(queryString, body, userAgent, counters = {}, options = {}) {
  const ts = options.timestampMs ?? Date.now();
  const ubcode = options.ubcode ?? 4;
  const sdkVersion = options.sdkVersion ?? "1.0.0.368";

  // Field 14: high 16 bits are 0x0041 (= field 1 left-shifted by 16),
  // low 16 bits are random.
  const r14LowBytes = options.randomLow16 ?? randomBytes(2);
  const field14 = (65 << 16) | (r14LowBytes[0] << 8) | r14LowBytes[1];

  // Field 15: full uint32 random.
  const r15Bytes = options.random32 ?? randomBytes(4);
  const field15 =
    ((r15Bytes[0] << 24) |
      (r15Bytes[1] << 16) |
      (r15Bytes[2] << 8) |
      r15Bytes[3]) >>>
    0;

  const fields = {
    1: 65,
    2: ubcode,
    3: md5(queryString),
    4: md5(body),
    5: md5(userAgent),
    6: Math.floor(ts / 1000),
    7: 3181061566, // observed constant; likely build-time hash baked into the SDK
    8: ts % 0x80000000,
    9: "5.1.3-ZTCA",
    10: sdkVersion,
    11: 1,
    12:
      (counters.totalXHRRequests ?? 0) +
      (counters.totalFetchRequests ?? 0),
    13:
      (counters.interceptedXHRRequests ?? 0) +
      (counters.interceptedFetchRequests ?? 0),
    14: field14,
    15: field15,
  };

  // Serialize → 12-word random key → ChaCha-XOR encrypt.
  const plaintext = encodePayload(fields);
  const keyBytes = options.randomKey ?? randomBytes(48);
  const keyWords = new Array(12);
  for (let i = 0; i < 12; i++) {
    const o = i * 4;
    keyWords[i] =
      ((keyBytes[o] |
        (keyBytes[o + 1] << 8) |
        (keyBytes[o + 2] << 16) |
        (keyBytes[o + 3] << 24)) >>>
        0);
  }
  const rounds = deriveRounds(keyWords);

  const cipher = new Uint8Array(plaintext); // copy, will be XOR'd in place
  chachaXor(cipher, keyWords, rounds);

  // Embed the 48-byte key into the cipher at a position derived from a
  // running checksum over both keyBytes and the cipher itself. The
  // decoder recovers this position by brute-forcing keyStart and looking
  // for a valid TLV header — see decode.js.
  const xLen = cipher.length;
  const mod = xLen + 1;
  let sum = 0;
  for (const b of keyBytes) sum = (sum + b) % mod;
  for (const b of cipher) sum = (sum + b) % mod;
  const insertPos = sum;

  // [magic][cipher[0..insertPos]][keyBytes][cipher[insertPos..]]
  const out = new Uint8Array(1 + xLen + 48);
  out[0] = MAGIC_BYTE;
  out.set(cipher.subarray(0, insertPos), 1);
  out.set(keyBytes, 1 + insertPos);
  out.set(cipher.subarray(insertPos), 1 + insertPos + 48);

  return encodeBase64(out);
}
