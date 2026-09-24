"""Offline tests for metadata parsing/normalization — no network access."""

import json

import pytest

from tiktok_tools import metadata


def test_extract_id_from_url():
    url = "https://www.tiktok.com/@tiktok/video/7673909736131038495?lang=en"
    assert metadata.extract_id(url) == "7673909736131038495"


def test_extract_id_plain():
    assert metadata.extract_id("7673909736131038495") == "7673909736131038495"


def test_extract_id_invalid():
    with pytest.raises(ValueError):
        metadata.extract_id("not-a-video")


def test_balanced_extract_nested_json_with_braces_in_string():
    html = '{"a": 1, "b": {"c": "x}y", "d": 2}, "e": 3} tail'
    block = metadata.balanced_extract(html, '{"a"')
    parsed = json.loads(block)
    assert parsed["b"]["c"] == "x}y"
    assert parsed["e"] == 3


def test_balanced_extract_missing_marker():
    assert metadata.balanced_extract("<html></html>", '"videoData"') is None


def test_normalize_maps_all_sections():
    vd = {
        "itemInfos": {
            "text": "hello", "createTime": "1784334149",
            "diggCount": 5, "playCount": 10, "commentCount": 1, "shareCount": 2,
            "covers": ["cover-a"],
            "video": {"videoMeta": {"duration": 8, "ratio": 1}, "urls": ["https://cdn/x.mp4"]},
        },
        "authorInfos": {"nickName": "N", "uniqueId": "u", "secUid": "s", "verified": True},
        "authorStats": {"followerCount": 100},
        "musicInfos": {"musicName": "M", "authorName": "MA"},
        "challengeInfoList": [{"challengeName": "fyp", "challengeId": "229207"}],
    }
    rec = metadata.normalize(vd, "123")
    assert rec["stats"]["play"] == 10
    assert rec["hashtags"][0]["name"] == "fyp"
    assert rec["playUrl"] == "https://cdn/x.mp4"
    assert rec["author"]["secUid"] == "s"


def test_normalize_handles_empty_sections():
    rec = metadata.normalize({}, "1")
    assert rec["hashtags"] == []
    assert rec["playUrl"] is None