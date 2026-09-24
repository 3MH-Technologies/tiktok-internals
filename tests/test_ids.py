"""Offline tests for ID-list parsing — no network access."""

from tiktok_tools import ids


def test_from_text_dedupe_and_split():
    text = "7673909736131038495 7673909736131038495,7680721699171601694\n7680996287877008670"
    assert ids.from_text(text) == [
        "7673909736131038495",
        "7680721699171601694",
        "7680996287877008670",
    ]


def test_from_file(tmp_path):
    f = tmp_path / "ids.txt"
    f.write_text("7673909736131038495\n 7680721699171601694 ", encoding="utf-8")
    out = ids.from_file(str(f))
    assert out == ["7673909736131038495", "7680721699171601694"]


def test_collect_manual_empty_list_is_offline_safe():
    videos, source, note = ids.collect("someuser", manual="no-numbers-here")
    assert videos == []
    assert "فارغة" in note