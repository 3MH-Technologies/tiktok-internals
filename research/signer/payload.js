// Encode/decode the 16-field TLV payload that lives inside the
// X-Gnarly ciphertext. See README §3 for the field semantics.
//
// Wire format:
//
//   [count_u8] (number of fields, e.g. 16 for ZTCA)
//   For each field:
//     [key_u8]               (field index 0..15)
//     [len_u16_be]           (value length in bytes)
//     [value_bytes...]
//
// Length ≤ 4: value is a big-endian unsigned integer.
// Length > 4: value is a UTF-8 string.
//
// Fields are emitted in the order listed in `FIELD_ORDER` below — the
// key in front of each field is what gets parsed back, but the producer
// uses a fixed insertion order at write time. We mirror that order so
// the encoder is deterministic.

// Order in which fields are appended at encode time. Field 0 (the XOR
// header) is appended LAST because its value depends on all other ints.
export const FIELD_ORDER = [
  1, 2, 6, 7, 8, 9, 10, 11, 4, 5, 3, 12, 13, 14, 15, 0,
];

// Convert a non-negative integer into the smallest big-endian byte
// sequence that fits. 0 → 1 byte, 256 → 2 bytes, etc. Capped at 4 bytes
// (uint32). webmssdk treats anything ≤ 4 bytes as an integer at decode
// time, so even 0 needs a length byte ≥ 1.
function intToBytes(n) {
  if (n < 0 || !Number.isInteger(n)) throw new Error("non-int");
  if (n === 0) return Uint8Array.of(0);
  const out = [];
  while (n > 0) {
    out.unshift(n & 0xff);
    n = Math.floor(n / 256);
  }
  return Uint8Array.from(out);
}

/**
 * Serialize the payload object → flat Uint8Array. The XOR header (field
 * 0) is computed automatically from the integer fields and inserted
 * last; callers should NOT pre-compute or pass a "0" value.
 */
export function encodePayload(fields) {
  const present = [];
  for (const k of FIELD_ORDER) {
    if (k === 0) continue;
    if (fields[k] === undefined) continue;
    present.push(k);
  }

  // XOR header = XOR of all integer field values across the payload.
  // Strings (fields 9, 10, plus the MD5 hex strings 3, 4, 5) are skipped.
  let xorHeader = 0;
  for (const k of present) {
    const v = fields[k];
    if (typeof v === "number") xorHeader = (xorHeader ^ v) >>> 0;
  }

  // Field 0 last
  const order = [...present, 0];
  const fieldsWith0 = { ...fields, 0: xorHeader };

  // Estimate buffer size; final length is exact post-fill.
  const out = [fieldsWith0[0] !== undefined ? order.length : present.length];
  for (const k of order) {
    const v = fieldsWith0[k];
    let valueBytes;
    if (typeof v === "number") {
      valueBytes = intToBytes(v);
    } else if (typeof v === "string") {
      valueBytes = new TextEncoder().encode(v);
    } else {
      throw new Error(`unsupported field ${k} type: ${typeof v}`);
    }
    out.push(k & 0xff);
    const len = valueBytes.length;
    out.push((len >>> 8) & 0xff, len & 0xff);
    for (const b of valueBytes) out.push(b);
  }
  return Uint8Array.from(out);
}

/**
 * Parse a flat byte buffer back into a fields object. Mirrors webmssdk's
 * `len ≤ 4` int / `len > 4` string heuristic exactly.
 */
export function decodePayload(bytes) {
  const fields = {};
  if (bytes.length === 0) return fields;
  let p = 0;
  const count = bytes[p++];
  let parsed = 0;
  while (p + 3 <= bytes.length && parsed < count) {
    const key = bytes[p++];
    const len = (bytes[p] << 8) | bytes[p + 1];
    p += 2;
    if (p + len > bytes.length) break;
    const value = bytes.slice(p, p + len);
    p += len;
    if (len <= 4) {
      let n = 0;
      for (const b of value) n = (n << 8) | b;
      fields[key] = n >>> 0;
    } else {
      fields[key] = new TextDecoder().decode(value);
    }
    parsed++;
  }
  return fields;
}
