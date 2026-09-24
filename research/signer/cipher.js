// ChaCha-flavor stream cipher used to encrypt the X-Gnarly payload.
//
// This is *not* RFC 8439 ChaCha20. It uses the same quarter-round (ARX
// pattern with rotation amounts [16, 12, 8, 7]) and the same column-then-
// diagonal round structure, but:
//
//   1. The 4 sigma constants differ. Standard ChaCha uses
//      ["expand 32-byte k"] interpreted as 4 uint32s in little-endian:
//      [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]. webmssdk uses
//      [1196819126, 600974999, 3863347763, 1451689750] instead — pulled
//      out of an internal constant table at indices [9, 69, 51, 92].
//
//   2. The 12-word "key + nonce" portion is not split into 8 key words +
//      4 nonce words. All 12 words are random and embedded into the
//      ciphertext (see encode.js for the embedding scheme). Effectively
//      it's a fresh symmetric key per call, recovered by the decoder.
//
//   3. Round count is variable per-call: derived from the random key as
//      `((sumOfLowNibblesOfKeyWords) & 15) + 5`, so rounds ∈ [5, 20].
//      RFC ChaCha20 is fixed at 20 rounds.
//
//   4. The keystream block index is incremented after every 64-byte
//      block, exactly like standard ChaCha. The increment goes into
//      state[12] (no overflow handling needed for our payload sizes).
//
// Encryption and decryption are the same operation (XOR a stream),
// so we expose a single `chachaXor` helper.

// Sigma constants — see point (1) above.
export const SIGMA = [1196819126, 600974999, 3863347763, 1451689750];

const u32 = (x) => x >>> 0;
const rotl = (v, c) => u32((v << c) | (v >>> (32 - c)));

/**
 * One quarter round, in-place on the 16-word state. Standard ChaCha
 * arithmetic with rotation amounts 16, 12, 8, 7.
 */
function quarter(s, a, b, c, d) {
  s[a] = u32(s[a] + s[b]);
  s[d] = rotl(s[d] ^ s[a], 16);
  s[c] = u32(s[c] + s[d]);
  s[b] = rotl(s[b] ^ s[c], 12);
  s[a] = u32(s[a] + s[b]);
  s[d] = rotl(s[d] ^ s[a], 8);
  s[c] = u32(s[c] + s[d]);
  s[b] = rotl(s[b] ^ s[c], 7);
}

/**
 * Generate one 64-byte keystream block (returned as 16 uint32 words).
 * Runs `rounds` total quarter-round passes — alternating column-rounds
 * and diagonal-rounds. After the rounds, the working state is added to
 * the initial state (matching ChaCha's "feed-forward" step).
 */
export function chachaBlock(initial, rounds) {
  const s = initial.slice();
  let r = 0;
  while (r < rounds) {
    // Column round
    quarter(s, 0, 4, 8, 12);
    quarter(s, 1, 5, 9, 13);
    quarter(s, 2, 6, 10, 14);
    quarter(s, 3, 7, 11, 15);
    if (++r >= rounds) break;
    // Diagonal round
    quarter(s, 0, 5, 10, 15);
    quarter(s, 1, 6, 11, 12);
    quarter(s, 2, 7, 12, 13);
    quarter(s, 3, 4, 13, 14);
    r++;
  }
  for (let i = 0; i < 16; i++) s[i] = u32(s[i] + initial[i]);
  return s;
}

/**
 * XOR-encrypt (or decrypt — same op) `bytes` in place with a keystream
 * derived from `keyWords` (12 uint32s) and the SIGMA constants.
 *
 * The 16-word ChaCha state is laid out as [SIGMA[0..3], keyWords[0..11]],
 * with state[12] doubling as the block counter (so it gets bumped after
 * every 64 bytes consumed). This matches the layout we observed via
 * dynamic tracing of webmssdk_2.0.0.485 — see README §5 for the trace.
 */
export function chachaXor(bytes, keyWords, rounds) {
  if (keyWords.length !== 12) {
    throw new Error(`expected 12 key words, got ${keyWords.length}`);
  }
  const state = [...SIGMA, ...keyWords];
  for (let off = 0; off < bytes.length; off += 64) {
    const stream = chachaBlock(state, rounds);
    state[12] = u32(state[12] + 1);
    const lim = Math.min(64, bytes.length - off);
    for (let i = 0; i < lim; i++) {
      const word = stream[i >>> 2];
      const byte = (word >>> (8 * (i & 3))) & 0xff;
      bytes[off + i] ^= byte;
    }
  }
  return bytes;
}

/**
 * Compute the round count from the 12 key words. Each call to the
 * producer in webmssdk derives `rounds` from `(sumOfLowNibbles) & 15`
 * and then adds 5 — clamping it into [5, 20].
 *
 * This means rounds is observable from the encoded ciphertext (recover
 * the key, then reapply the formula), so the decoder doesn't need it
 * encoded alongside the data.
 */
export function deriveRounds(keyWords) {
  let r = 0;
  for (const w of keyWords) r = (r + (w & 15)) & 15;
  return r + 5;
}
