// Custom base64 alphabet used by webmssdk to encode the X-Gnarly payload.
//
// Note this is NOT standard RFC 4648 base64. The character at each 6-bit
// index has been permuted, so the same byte stream produces a different
// visible string than `Buffer.from(...).toString("base64")` would. The
// alphabet is constant across all webmssdk versions we've observed
// (1.0.0.211 → 2.0.0.485-ZTCA).
//
// Indices 0..63 map to one character each, plus the trailing `=` is the
// padding character (used the same way as standard base64).
export const ALPHABET =
  "u09tbS3UvgDEe6r-ZVMXzLpsAohTn7mdINQlW412GqBjfYiyk8JORCF5/xKHwacP=";

// Reverse lookup: char → 6-bit value. Built once at module load.
export const LUT = Object.fromEntries(
  [...ALPHABET].map((ch, i) => [ch, i]),
);

/**
 * Encode a byte buffer using the custom alphabet. Standard 4-byte-output
 * per 3-byte-input layout; the input is right-padded with zero bytes if
 * it isn't a multiple of 3, and the trailing `=` characters are appended
 * to mark how many bytes were padding.
 *
 * Identical wire format to standard base64, just with the alphabet swap.
 */
export function encodeBase64(bytes) {
  let out = "";
  let i = 0;
  for (; i + 3 <= bytes.length; i += 3) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    out +=
      ALPHABET[(n >>> 18) & 63] +
      ALPHABET[(n >>> 12) & 63] +
      ALPHABET[(n >>> 6) & 63] +
      ALPHABET[n & 63];
  }
  const rem = bytes.length - i;
  if (rem === 1) {
    const n = bytes[i] << 16;
    out += ALPHABET[(n >>> 18) & 63] + ALPHABET[(n >>> 12) & 63] + "==";
  } else if (rem === 2) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8);
    out +=
      ALPHABET[(n >>> 18) & 63] +
      ALPHABET[(n >>> 12) & 63] +
      ALPHABET[(n >>> 6) & 63] +
      "=";
  }
  return out;
}

/**
 * Decode a string produced by encodeBase64 back to a Uint8Array.
 *
 * Strips trailing `=` padding before parsing, so 0/1/2 padding chars are
 * handled symmetrically with the encode side.
 */
export function decodeBase64(str) {
  // Strip padding for cleaner accounting.
  let end = str.length;
  while (end > 0 && str[end - 1] === "=") end--;
  const clean = str.slice(0, end);

  const out = [];
  let i = 0;
  for (; i + 4 <= clean.length; i += 4) {
    const n =
      (LUT[clean[i]] << 18) |
      (LUT[clean[i + 1]] << 12) |
      (LUT[clean[i + 2]] << 6) |
      LUT[clean[i + 3]];
    out.push((n >>> 16) & 255, (n >>> 8) & 255, n & 255);
  }
  const rem = clean.length - i;
  if (rem === 2) {
    // 2 chars -> 1 byte
    const n = (LUT[clean[i]] << 6) | LUT[clean[i + 1]];
    out.push((n >>> 4) & 255);
  } else if (rem === 3) {
    // 3 chars -> 2 bytes
    const n =
      (LUT[clean[i]] << 12) | (LUT[clean[i + 1]] << 6) | LUT[clean[i + 2]];
    out.push((n >>> 10) & 255, (n >>> 2) & 255);
  }
  return Uint8Array.from(out);
}
