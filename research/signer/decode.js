import { decodeBase64 } from "./alphabet.js";
import { chachaXor, deriveRounds } from "./cipher.js";
import { decodePayload } from "./payload.js";
import { MAGIC_BYTE } from "./encode.js";

/**
 * Decode an X-Gnarly string into its 16-field payload object.
 *
 * Returns:
 *   { fields, keyStart, rounds, key }
 *
 * The keyStart and rounds are useful for cross-checking against an
 * encoder run — but for the common case of just inspecting the fields,
 * callers should ignore them.
 *
 * Throws if the input doesn't begin with the magic byte 'K' (= 75) or
 * if no plausible TLV layout is recoverable from any keyStart position.
 */
export function decode(xgnarly) {
  const buf = decodeBase64(xgnarly);
  if (buf.length === 0 || buf[0] !== MAGIC_BYTE) {
    throw new Error(`bad magic byte: expected ${MAGIC_BYTE} ('K'), got ${buf[0]}`);
  }

  const KEY_LEN = 48;
  const inner = buf.length - 1;
  if (inner < KEY_LEN + 4) throw new Error("payload too short");
  const cipherLen = inner - KEY_LEN;

  // Brute-force keyStart by trying every position [0, cipherLen]. For
  // each, peel out the candidate 48-byte key, reconstruct the cipher
  // (the bytes BEFORE the key + the bytes AFTER the key), decrypt, and
  // see if the resulting plaintext starts with a sane TLV header
  // (count_u8 in [10, 25], first key in [0, 30], first len in [1, 64]).
  //
  // Cost: at most cipherLen + 1 trial decryptions, but each is small —
  // a few hundred bytes of ChaCha at ≤20 rounds. Sub-millisecond.
  for (let keyStart = 0; keyStart <= cipherLen; keyStart++) {
    const keyBytes = buf.slice(1 + keyStart, 1 + keyStart + KEY_LEN);
    const cipher = new Uint8Array(cipherLen);
    cipher.set(buf.slice(1, 1 + keyStart), 0);
    cipher.set(buf.slice(1 + keyStart + KEY_LEN), keyStart);

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
    const plain = new Uint8Array(cipher);
    chachaXor(plain, keyWords, rounds);

    // Plausibility check on the leading TLV bytes.
    if (plain.length < 4) continue;
    const count = plain[0];
    if (count < 10 || count > 25) continue;
    const firstKey = plain[1];
    if (firstKey > 30) continue;
    const firstLen = (plain[2] << 8) | plain[3];
    if (firstLen === 0 || firstLen > 64) continue;

    const fields = decodePayload(plain);
    // Final sanity: expect field 9 to be a version string starting
    // with "5.".
    if (typeof fields[9] !== "string" || !/^5\./.test(fields[9])) continue;

    return { fields, keyStart, rounds, key: keyBytes };
  }
  throw new Error("could not recover plaintext at any keyStart position");
}
