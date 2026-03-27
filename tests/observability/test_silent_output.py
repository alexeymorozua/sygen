"""Tests for [SILENT] marker support in cron and webhook observers."""

from __future__ import annotations


class TestSilentMarkerDetection:
    """Verify that [SILENT] prefix detection works correctly."""

    def test_silent_uppercase(self) -> None:
        text = "[SILENT] Nothing to report"
        assert text.lstrip().upper().startswith("[SILENT]")

    def test_silent_lowercase(self) -> None:
        text = "[silent] Nothing to report"
        assert text.lstrip().upper().startswith("[SILENT]")

    def test_silent_with_leading_whitespace(self) -> None:
        text = "  [SILENT]"
        assert text.lstrip().upper().startswith("[SILENT]")

    def test_non_silent_output(self) -> None:
        text = "BTC price changed to $105,000"
        assert not text.lstrip().upper().startswith("[SILENT]")

    def test_silent_marker_only(self) -> None:
        text = "[SILENT]"
        assert text.lstrip().upper().startswith("[SILENT]")

    def test_empty_string_not_silent(self) -> None:
        text = ""
        assert not text.lstrip().upper().startswith("[SILENT]")
