"""Offline tests for the signature engine — no network access."""

from tiktok_tools import sign

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"
REF_URL = "https://www.tiktok.com/api/search/general/full/?keyword=test"


def test_xbogus_reference_vector():
    """Captured from the Node reference (research/signer/xbogus3.js) at ts=1700000000."""
    assert sign.generate_xbogus(REF_URL, UA, timestamp=1_700_000_000) == "DFtzs1rXVpR-pNbPq-XJ-xoHc/PB"


def test_xbogus_length():
    assert len(sign.generate_xbogus(REF_URL, UA)) == 28


def test_xbogus_deterministic_for_fixed_ts():
    a = sign.generate_xbogus(REF_URL, UA, timestamp=1_700_000_000)
    b = sign.generate_xbogus(REF_URL, UA, timestamp=1_700_000_000)
    assert a == b


def test_gnarly_length_and_magic_byte():
    token = sign.encode_gnarly(REF_URL, "", UA)
    assert len(token) == 316
    raw = sign.gnarly_b64_decode(token)
    assert raw and raw[0] == sign.MAGIC_BYTE  # 75 == 'K'


def test_gnarly_roundtrip_self_verify():
    token = sign.encode_gnarly(REF_URL, "x=1", UA)
    result = sign.verify_gnarly(token, REF_URL, "x=1", UA)
    assert result["ok"] is True
    assert result["payloadVersion"] == "5.3.0"
    assert result["sdkVersion"] == "2.0.0.520"


def test_gnarly_detects_tampered_query():
    token = sign.encode_gnarly(REF_URL, "", UA)
    result = sign.verify_gnarly(token, REF_URL + "&zz=1", "", UA)
    assert result["ok"] is False