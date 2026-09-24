"""أداة التوقيعات — وظيفتها: توليد توقيعات X-Gnarly و X-Bogus بنقاء بايثون (stdlib فقط).

نقل كامل للمراجع النظيفة من المجلد signer/ (JavaScript) إلى بايثون:

  X-Gnarly (webmssdk 2.0.0.520 / payload 5.3.0):
    payload TLV بـ 16 حقل ← تشفير ChaCha (أصفار مختلفة، عدد جولات مشتق من المفتاح)
    ← إخفاء المفتاح داخل النص بأسلوب الإدراج المحسوب ← Base64 بأبجدية مخصّصة.

  X-Bogus:
    MD5 مزدوج للمعاملات والجسم + تجزئة UA عبر RC4 ← ترتيب/خلط ← RC4 نهائي
    ← Base64 بأبجدية مخصّصة ثانية (دون حشو).

غرض التوقيعات هنا: التوثيق البحثي وإثبات الفهم للخوارزميات (راجع التقرير 5-6).
معظم مسارات الحصول على البيانات في هذه الحزمة لا تحتاج توقيعاً أصلاً.
"""
from __future__ import annotations

import hashlib
import os
import time

# ---------------------------------------------------------------------------
# 1) أبجدية X-Gnarly (مع الحشو '=') — من alphabet.js
# ---------------------------------------------------------------------------
GNARLY_ALPHABET = (
    "u09tbS3UvgDEe6r-ZVMXzLpsAohTn7mdINQlW412GqBjfYiyk8JORCF5/xKHwacP="
)
GNARLY_LUT = {ch: i for i, ch in enumerate(GNARLY_ALPHABET)}


def _b64_encode(data: bytes, alphabet: str, pad: bool) -> str:
    out: list[str] = []
    i, n = 0, len(data)
    while i + 3 <= n:
        v = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        out += [
            alphabet[(v >> 18) & 63],
            alphabet[(v >> 12) & 63],
            alphabet[(v >> 6) & 63],
            alphabet[v & 63],
        ]
        i += 3
    rem = n - i
    if rem == 1:
        v = data[i] << 16
        out += [alphabet[(v >> 18) & 63], alphabet[(v >> 12) & 63]]
        if pad:
            out += ["=", "="]
    elif rem == 2:
        v = (data[i] << 16) | (data[i + 1] << 8)
        out += [alphabet[(v >> 18) & 63], alphabet[(v >> 12) & 63], alphabet[(v >> 6) & 63]]
        if pad:
            out += ["="]
    return "".join(out)


def _b64_decode(s: str, lut: dict) -> bytes:
    end = len(s)
    while end > 0 and s[end - 1] == "=":
        end -= 1
    clean = s[:end]
    out = bytearray()
    i, n = 0, len(clean)
    while i + 4 <= n:
        v = (lut[clean[i]] << 18) | (lut[clean[i + 1]] << 12) | (
            lut[clean[i + 2]] << 6) | lut[clean[i + 3]]
        out.extend([(v >> 16) & 255, (v >> 8) & 255, v & 255])
        i += 4
    rem = n - i
    if rem == 2:
        v = (lut[clean[i]] << 6) | lut[clean[i + 1]]
        out.append((v >> 4) & 255)
    elif rem == 3:
        v = (lut[clean[i]] << 12) | (lut[clean[i + 1]] << 6) | lut[clean[i + 2]]
        out.extend([(v >> 10) & 255, (v >> 2) & 255])
    return bytes(out)


def gnarly_b64_encode(data: bytes) -> str:
    """كود Base64 أبجدية X-Gnarly (للختم النهائي للتوقيع)."""
    return _b64_encode(data, GNARLY_ALPHABET, pad=True)


def gnarly_b64_decode(s: str) -> bytes:
    """فك أبجدية X-Gnarly (للتحقق/فك التوقيع)."""
    return _b64_decode(s, GNARLY_LUT)

# ---------------------------------------------------------------------------
# 2) تشفير ChaCha بنكهة webmssdk — من cipher.js
# ---------------------------------------------------------------------------
_M32 = 0xFFFFFFFF
SIGMA = [1196819126, 600974999, 3863347763, 1451689750]


def _rotl(v: int, c: int) -> int:
    return ((v << c) | (v >> (32 - c))) & _M32


def _quarter(s: list[int], a: int, b: int, c: int, d: int) -> None:
    s[a] = (s[a] + s[b]) & _M32
    s[d] = _rotl(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & _M32
    s[b] = _rotl(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & _M32
    s[d] = _rotl(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & _M32
    s[b] = _rotl(s[b] ^ s[c], 7)


def chacha_block(initial: list[int], rounds: int) -> list[int]:
    """كتلة keystream واحدة بــ rounds زوج من جولات الأعمدة/الأقطار + تغذية أمامية."""
    s = list(initial)
    r = 0
    while r < rounds:
        _quarter(s, 0, 4, 8, 12)
        _quarter(s, 1, 5, 9, 13)
        _quarter(s, 2, 6, 10, 14)
        _quarter(s, 3, 7, 11, 15)
        r += 1
        if r >= rounds:
            break
        _quarter(s, 0, 5, 10, 15)
        _quarter(s, 1, 6, 11, 12)
        _quarter(s, 2, 7, 12, 13)
        _quarter(s, 3, 4, 13, 14)
        r += 1
    return [(s[i] + initial[i]) & _M32 for i in range(16)]


def chacha_xor(data: bytearray, key_words: list[int], rounds: int) -> bytearray:
    """خلط XOR لكامل الجسم بمجرى keystream (التشفير = الفك، نفس العملية)."""
    assert len(key_words) == 12, "12 كلمات مفتاح مطلوبة"
    state = SIGMA + list(key_words)
    off = 0
    while off < len(data):
        stream = chacha_block(state, rounds)
        state[12] = (state[12] + 1) & _M32
        lim = min(64, len(data) - off)
        for i in range(lim):
            word = stream[i >> 2]
            data[off + i] ^= (word >> (8 * (i & 3))) & 0xFF
        off += 64
    return data


def derive_rounds(key_words: list[int]) -> int:
    """عدد الجولات مشتق من مجموع الأنصاف الأدنى لكلمات المفتاح: [5, 20]."""
    r = 0
    for w in key_words:
        r = (r + (w & 15)) & 15
    return r + 5

# ---------------------------------------------------------------------------
# 3) حمولة TLV ذات الـ 16 حقلاً — من payload.js
# ---------------------------------------------------------------------------
FIELD_ORDER = [1, 2, 6, 7, 8, 9, 10, 11, 4, 5, 3, 12, 13, 14, 15, 0]


def _int_to_bytes(n: int) -> bytes:
    if n < 0:
        raise ValueError("int سالب غير مدعوم")
    if n == 0:
        return b"\x00"
    out = []
    while n > 0:
        out.insert(0, n & 0xFF)
        n >>= 8
    return bytes(out)


def encode_payload(fields: dict) -> bytes:
    """سلسّل الحقول إلى TLV؛ الحقل 0 (رأس XOR) يُحسب تلقائياً ويُدرج أخيراً."""
    present = [k for k in FIELD_ORDER if k != 0 and fields.get(k) is not None]
    xor_header = 0
    for k in present:
        if isinstance(fields[k], int):
            xor_header ^= fields[k]
    order = present + [0]
    fields0 = dict(fields)
    fields0[0] = xor_header
    out = bytearray([len(order)])
    for k in order:
        v = fields0[k]
        value = _int_to_bytes(v) if isinstance(v, int) else str(v).encode("utf-8")
        out.append(k & 0xFF)
        out.append((len(value) >> 8) & 0xFF)
        out.append(len(value) & 0xFF)
        out.extend(value)
    return bytes(out)


def decode_payload(data: bytes) -> dict:
    """اقرأ TLV إلى حقول (قيمة ≤4 بايت = عدد صحيح، غير ذلك = نص UTF-8)."""
    fields: dict = {}
    if not data:
        return fields
    p = 0
    count = data[0]
    p = 1
    parsed = 0
    while p + 3 <= len(data) and parsed < count:
        key = data[p]
        length = (data[p + 1] << 8) | data[p + 2]
        p += 3
        if p + length > len(data):
            break
        value = bytes(data[p : p + length])
        p += length
        if length <= 4:
            n = 0
            for b in value:
                n = (n << 8) | b
            fields[key] = n & _M32
        else:
            fields[key] = value.decode("utf-8", "replace")
        parsed += 1
    return fields

# ---------------------------------------------------------------------------
# 4) التوقيع الرئيسي: X-Gnarly — من encode520.js
# ---------------------------------------------------------------------------
MAGIC_BYTE = 75  # 'K'


def _md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def encode_gnarly(
    query_string: str = "",
    body: str = "",
    user_agent: str = "",
    counters: dict | None = None,
    *,
    timestamp_ms: int | None = None,
    ubcode: int = 4,
    sdk_version: str = "2.0.0.520",
    payload_version: str = "5.3.0",
) -> str:
    """ولّد توقيع X-Gnarly للمدخلات المعطاة (كل استدعاء يستخدم مفاتيح عشوائية).

    ترجع: سلسلة Base64 (أبجدية مخصّصة) تبدأ بفكّها بالبايت 75 ('K').
    """
    counters = counters or {}
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)

    r14 = os.urandom(2)
    field14 = (65 << 16) | (r14[0] << 8) | r14[1]
    r15 = os.urandom(4)
    field15 = ((r15[0] << 24) | (r15[1] << 16) | (r15[2] << 8) | r15[3]) & _M32

    fields = {
        1: 65,
        2: ubcode,
        3: _md5_hex(query_string),
        4: _md5_hex(body),
        5: _md5_hex(user_agent),
        6: ts // 1000,
        7: 3181061566,
        8: ts % 0x80000000,
        9: payload_version,
        10: sdk_version,
        11: 1,
        12: counters.get("totalXHRRequests", 0) + counters.get("totalFetchRequests", 0),
        13: counters.get("interceptedXHRRequests", 0) + counters.get("interceptedFetchRequests", 0),
        14: field14,
        15: field15,
    }

    plaintext = bytearray(encode_payload(fields))
    key_bytes = os.urandom(48)
    key_words = [
        (key_bytes[o] | (key_bytes[o + 1] << 8) | (key_bytes[o + 2] << 16) | (key_bytes[o + 3] << 24)) & _M32
        for o in range(0, 48, 4)
    ]
    rounds = derive_rounds(key_words)

    cipher = bytearray(plaintext)
    chacha_xor(cipher, key_words, rounds)

    xlen = len(cipher)
    mod = xlen + 1
    s = 0
    for b in key_bytes:
        s = (s + b) % mod
    for b in cipher:
        s = (s + b) % mod
    insert_pos = s

    out = bytearray(1 + xlen + 48)
    out[0] = MAGIC_BYTE
    out[1 : 1 + insert_pos] = cipher[:insert_pos]
    out[1 + insert_pos : 1 + insert_pos + 48] = key_bytes
    out[1 + insert_pos + 48 :] = cipher[insert_pos:]
    return gnarly_b64_encode(bytes(out))


def verify_gnarly(encoded: str, query_string: str = "", body: str = "", user_agent: str = "") -> dict:
    """وظيفة التحقق: افتح التوقيع واسترجع المفتاح وفك التشفير وقارن الحقول.

    تُستخدم كفحص ذاتي لإثبات أن المولّد ينتج ختماً صحيحاً رياضياً:
      - البايت الأول 'K' (75) بعد الفك.
      - استرجاع موضع المفتاح من مجموع البايتات (نفس حساب المولّد).
      - مشتقة الجولات ثم الفك — ومطابقة الحقول 3/4/5 لقيم MD5 للمدخلات.
    """
    raw = gnarly_b64_decode(encoded)
    if not raw or raw[0] != MAGIC_BYTE:
        return {"ok": False, "reason": "بايت السحر غير متطابق (ليس X-Gnarly)"}
    xlen = len(raw) - 1 - 48
    mod = xlen + 1
    s = 0
    for b in raw[1:]:
        s = (s + b) % mod
    pos = s
    key = raw[1 + pos : 1 + pos + 48]
    cipher = raw[1 : 1 + pos] + raw[1 + pos + 48 :]
    key_words = [
        (key[o] | (key[o + 1] << 8) | (key[o + 2] << 16) | (key[o + 3] << 24)) & _M32
        for o in range(0, 48, 4)
    ]
    rounds = derive_rounds(key_words)
    data = bytearray(cipher)
    chacha_xor(data, key_words, rounds)
    fields = decode_payload(bytes(data))
    return {
        "ok": (
            fields.get(3) == _md5_hex(query_string)
            and fields.get(4) == _md5_hex(body)
            and fields.get(5) == _md5_hex(user_agent)
        ),
        "xlen": xlen,
        "rounds": rounds,
        "payloadVersion": fields.get(9),
        "sdkVersion": fields.get(10),
        "field3_matches_query_md5": fields.get(3) == _md5_hex(query_string),
    }

# ---------------------------------------------------------------------------
# 5) التوقيع الثانوي: X-Bogus — من xbogus3.js
# ---------------------------------------------------------------------------
BOGUS_ALPHABET = "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe"
_BOGUS_MAGIC = 536919696
_RC4_UA_KEY = [0, 1, 14]
_RC4_FINAL_KEY = [255]


def _rc4(data: list[int] | bytes, key: list[int]) -> list[int]:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out = []
    i = j = 0
    for k in range(len(data)):
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append((data[k] if isinstance(data, bytes) else data[k]) ^ s[(s[i] + s[j]) % 256])
    return out


def _double_md5(data: str) -> str:
    first = hashlib.md5(data.encode("utf-8")).hexdigest()
    return hashlib.md5(first.encode("utf-8")).hexdigest()


def _bogus_b64(data: list[int]) -> str:
    return _b64_encode(bytes(data), BOGUS_ALPHABET, pad=False)


def _user_agent_hash(ua: str) -> str:
    enc = _rc4(ua.encode("utf-8"), _RC4_UA_KEY)
    return hashlib.md5(_bogus_b64(enc).encode("utf-8")).hexdigest()


def _build_data(timestamp: int, params_hash: str, body_hash: str, ua_hash: str) -> list[int]:
    ts = timestamp & _M32
    data = [
        ts & 0xFF, (ts >> 8) & 0xFF, (ts >> 16) & 0xFF, (ts >> 24) & 0xFF,
        _BOGUS_MAGIC & 0xFF, (_BOGUS_MAGIC >> 8) & 0xFF,
        (_BOGUS_MAGIC >> 16) & 0xFF, (_BOGUS_MAGIC >> 24) & 0xFF,
        0, 1, 14, 0,
    ]
    for h in (params_hash, body_hash, ua_hash):
        data += [int(h[-4:-2], 16), int(h[-2:], 16)]
    data += [ts & 0xFF, (ts >> 8) & 0xFF, (ts >> 16) & 0xFF, (ts >> 24) & 0xFF]
    checksum = 0
    for b in data:
        checksum ^= b
    data.append(checksum)
    return data


def _filter_bytes(data: list[int]) -> list[int]:
    return [data[i] for i in (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 1, 3, 5, 7, 9, 11, 13, 15, 17) if i < len(data)]


def _scramble_bytes(data: list[int]) -> list[int]:
    if not data:
        return data
    result = [0] * len(data)
    mid = len(data) // 2
    j = 0
    for i in range(mid):
        result[j] = data[i]
        j += 1
        if i + mid < len(data):
            result[j] = data[i + mid]
            j += 1
    if len(data) % 2 != 0:
        result[-1] = data[-1]
    return result


def generate_xbogus(url: str, user_agent: str, timestamp: int | None = None) -> str:
    """ولّد توقيع X-Bogus (28 رمزاً) — حتمي لثابت الزمن، عكس X-Gnarly."""
    ts = timestamp if timestamp is not None else int(time.time())
    params_hash = _double_md5(url)
    body_hash = _double_md5("")
    ua_hash = _user_agent_hash(user_agent)
    data = _build_data(ts, params_hash, body_hash, ua_hash)
    filtered = _filter_bytes(data)
    scrambled = _scramble_bytes(filtered)
    encrypted = _rc4(scrambled, _RC4_FINAL_KEY)
    prefixed = [2, 255] + encrypted
    return _bogus_b64(prefixed)