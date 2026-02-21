"""Tests for Brunetti alignment with the 5-way token alignment."""

from pathlib import Path
from typing import List

import pytest

from sources.align_brunetti import (
    AlignRow,
    BrunettiToken,
    align_brunetti,
    parse_aligned,
    parse_brunetti_tokens,
    parse_mit_id,
)


class TestParseMitId:
    """Tests for the ID parser."""

    def test_simple(self) -> None:
        assert parse_mit_id("0001a1") == (1, "a", 1)

    def test_high_line(self) -> None:
        assert parse_mit_id("3182b2") == (3182, "b", 2)

    def test_multi_digit_offset(self) -> None:
        assert parse_mit_id("0307b4") == (307, "b", 4)


class TestParseBrunettiTokens:
    """Tests for Brunetti token parsing."""

    def test_basic_tokens(self, tmp_path: Path) -> None:
        txt = tmp_path / "bru.txt"
        txt.write_text(
            "00|001|1|0|0001|a|1|-||Hwæt|!|||hwæt|e||well|Hwæt\n"
            "00|001|0|0|0001|a|2|-||We|||np|we|p||we|Wē\n"
        )
        tokens = parse_brunetti_tokens(txt)
        assert len(tokens) == 2
        assert tokens[0].id_str == "0001a1"
        assert tokens[0].id_tuple == (1, "a", 1)
        assert tokens[0].text == "Hwæt!"
        assert tokens[1].id_str == "0001a2"
        assert tokens[1].text == "Wē"

    def test_space_in_with_length(self, tmp_path: Path) -> None:
        """Spaces in with_length should become underscores."""
        txt = tmp_path / "bru.txt"
        txt.write_text("00|002|0|0|0009|a|1|-||oð þæt||||oð þæt|c||until|oð þæt\n")
        tokens = parse_brunetti_tokens(txt)
        assert tokens[0].text == "oð_þæt"

    def test_pre_punc(self, tmp_path: Path) -> None:
        """Non-empty pre_punc should be prepended."""
        txt = tmp_path / "bru.txt"
        txt.write_text("00|002|0|0|0018|b|1|/|– |blæd|||ns|blæd|m||fame|blǣd\n")
        tokens = parse_brunetti_tokens(txt)
        assert tokens[0].text == "–_blǣd"

    def test_post_punc(self, tmp_path: Path) -> None:
        """Post punctuation should be appended."""
        txt = tmp_path / "bru.txt"
        txt.write_text(
            "00|001|0|0|0001|b|2|-||geardagum|,||dp|gear-dagas|m||days of yore|gēardagum\n"
        )
        tokens = parse_brunetti_tokens(txt)
        assert tokens[0].text == "gēardagum,"

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        txt = tmp_path / "bru.txt"
        txt.write_text(
            "00|001|1|0|0001|a|1|-||Hwæt|!|||hwæt|e||well|Hwæt\n"
            "\n"
            "00|001|0|0|0001|a|2|-||We|||np|we|p||we|Wē\n"
        )
        tokens = parse_brunetti_tokens(txt)
        assert len(tokens) == 2


class TestParseAligned:
    """Tests for aligned.txt parsing."""

    def test_basic(self, tmp_path: Path) -> None:
        txt = tmp_path / "aligned.txt"
        txt.write_text(
            "0001a1 0001a1 0001a1 0001a1 0001a1 Hwæt! Hwæt! Hwæt! HWÆT: Hwæt,\n"
            "0001a2 0001a2 0001a2 0001a2 0001a2 We We Wé WE wē\n"
        )
        rows = parse_aligned(txt)
        assert len(rows) == 2
        assert rows[0].ids == ["0001a1", "0001a1", "0001a1", "0001a1", "0001a1"]
        assert rows[0].texts == ["Hwæt!", "Hwæt!", "Hwæt!", "HWÆT:", "Hwæt,"]


# ── Alignment helpers ───────────────────────────────────────


def _bru(line_id: str, half: str, offset: int, text: str) -> str:
    """Build a minimal Brunetti pipe-delimited line for testing."""
    # Fields: fitt|para|pf|nv|line_id|half|offset|cc|pre_punc|text_col|post_punc
    #         |syntax|parse|lemma|pos|inflection|gloss|with_length
    # We only care about fields 4,5,6,8,10,17
    return f"00|001|0|0|{line_id}|{half}|{offset}|-||{text}||||x|y||z|{text}"


def _bru_full(
    line_id: str,
    half: str,
    offset: int,
    with_length: str,
    post_punc: str = "",
    pre_punc: str = "",
) -> str:
    """Build a Brunetti line with explicit pre/post punctuation."""
    return (
        f"00|001|0|0|{line_id}|{half}|{offset}|-|{pre_punc}|"
        f"text|{post_punc}|||x|y||z|{with_length}"
    )


def _aligned_row(mit_id: str, *texts: str) -> str:
    """Build an aligned.txt row. All 5 IDs set to mit_id, 5 texts required."""
    ids = " ".join([mit_id] * 5)
    return f"{ids} {' '.join(texts)}"


def _parse_output(lines: List[str]) -> List[dict]:
    """Parse output lines into dicts with ids and texts."""
    results = []
    for line in lines:
        parts = line.split(" ")
        results.append({"ids": parts[:6], "texts": parts[6:]})
    return results


class TestAlignBrunetti:
    """Tests for the alignment algorithm."""

    def test_simple_1to1(self, tmp_path: Path) -> None:
        """Each aligned row matches one Brunetti token."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru_full("0001", "a", 1, "Hwæt", post_punc="!")
            + "\n"
            + _bru_full("0001", "a", 2, "Wē")
            + "\n"
            + _bru_full("0001", "a", 3, "Gār-Dena")
            + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row("0001a1", "Hwæt!", "Hwæt!", "Hwæt!", "HWÆT:", "Hwæt,")
            + "\n"
            + _aligned_row("0001a2", "We", "We", "Wé", "WE", "wē")
            + "\n"
            + _aligned_row(
                "0001a3", "Gardena", "Gardena", "Gárdena", "GAR-DENA", "Gār-Dena"
            )
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        assert len(output) == 3
        assert parsed[0]["ids"][5] == "0001a1"
        assert parsed[0]["texts"][5] == "Hwæt!"
        assert parsed[1]["ids"][5] == "0001a2"
        assert parsed[1]["texts"][5] == "Wē"
        assert parsed[2]["ids"][5] == "0001a3"
        assert parsed[2]["texts"][5] == "Gār-Dena"

    def test_join_row(self, tmp_path: Path) -> None:
        """A _ join row collects multiple Brunetti tokens."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru_full("0445", "a", 1, "mægenhrēð")
            + "\n"
            + _bru_full("0445", "a", 2, "manna", post_punc=".")
            + "\n"
            + _bru_full("0445", "b", 1, "Nā")
            + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row(
                "0445a1",
                "mægen_Hreðmanna.",
                "mægen_Hreðmanna.",
                "mægenhréð_manna.",
                "mægenhreð_manna.",
                "mægenhrēð_manna.",
            )
            + "\n"
            + _aligned_row("0445b1", "Na", "Na", "Ná", "Na", "Nā")
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        assert parsed[0]["ids"][5] == "0445a1"
        assert parsed[0]["texts"][5] == "mægenhrēð_manna."
        assert parsed[1]["ids"][5] == "0445b1"
        assert parsed[1]["texts"][5] == "Nā"

    def test_gap_brunetti_missing(self, tmp_path: Path) -> None:
        """Brunetti has no tokens for a range → @."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru_full("0389", "a", 2, "lēodum", post_punc=".'")
            + "\n"
            + _bru_full("0390", "b", 1, "word")
            + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        # Last row of 389a, then 389b gap rows, then 390b
        align_path.write_text(
            _aligned_row(
                "0389a2", "leodum.", "leodum.", "leodum.", "leodum.", "lēodum."
            )
            + "\n"
            + _aligned_row("0389b1", "@", "@", "@", "@", "[þā")
            + "\n"
            + _aligned_row("0390b1", "word", "word", "Word", "Word", "word")
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        assert parsed[0]["texts"][5] == "lēodum.'"
        assert parsed[1]["texts"][5] == "@"
        assert parsed[1]["ids"][5] == "0389b1"  # fallback to mit_id
        assert parsed[2]["texts"][5] == "word"

    def test_gap_brunetti_has_tokens(self, tmp_path: Path) -> None:
        """Brunetti has tokens where other editions have @ (like 390a)."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru_full("0389", "a", 2, "lēodum", post_punc=".'")
            + "\n"
            + _bru_full("0390", "a", 1, "Wedera")
            + "\n"
            + _bru_full("0390", "a", 2, "lēodum")
            + "\n"
            + _bru_full("0390", "b", 1, "word")
            + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row(
                "0389a2", "leodum.", "leodum.", "leodum.", "leodum.", "lēodum."
            )
            + "\n"
            # 389b gap — mit stuck on same ID
            + _aligned_row("0389b1", "@", "@", "@", "@", "[þā")
            + "\n"
            + _aligned_row("0389b1", "@", "@", "@", "@", "wið")
            + "\n"
            # 390a gap — mit advances but still @
            + _aligned_row("0390a1", "@", "@", "@", "@", "Wulfgār")
            + "\n"
            + _aligned_row("0390a1", "@", "@", "@", "@", "ēode,]")
            + "\n"
            + _aligned_row("0390b1", "word", "word", "Word", "Word", "word")
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        # 389a2: normal match
        assert parsed[0]["texts"][5] == "lēodum.'"

        # 389b1 gap rows: Brunetti has nothing here
        assert parsed[1]["texts"][5] == "@"
        assert parsed[2]["texts"][5] == "@"

        # 390a rows: Brunetti has Wedera and lēodum
        assert parsed[3]["texts"][5] == "Wedera"
        assert parsed[3]["ids"][5] == "0390a1"
        assert parsed[4]["texts"][5] == "lēodum"
        assert parsed[4]["ids"][5] == "0390a2"

        # 390b: normal
        assert parsed[5]["texts"][5] == "word"

    def test_space_token_single_row(self, tmp_path: Path) -> None:
        """A single Brunetti token with internal space on a join row."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru("0009", "a", 1, "oð þæt") + "\n" + _bru("0009", "a", 2, "him") + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row("0009a1", "oðþæt", "oðþæt", "oð_þæt", "oð_þæt", "oð_þæt")
            + "\n"
            + _aligned_row("0009a2", "him", "him", "him", "him", "him")
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        assert parsed[0]["texts"][5] == "oð_þæt"
        assert parsed[1]["texts"][5] == "him"

    def test_output_has_12_columns(self, tmp_path: Path) -> None:
        """Each output line has exactly 12 space-separated columns."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(_bru_full("0001", "a", 1, "Hwæt", post_punc="!") + "\n")
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row("0001a1", "Hwæt!", "Hwæt!", "Hwæt!", "HWÆT:", "Hwæt,") + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)

        parts = output[0].split(" ")
        assert len(parts) == 12

    def test_last_row_sentinel(self, tmp_path: Path) -> None:
        """The last aligned row should still collect its Brunetti token."""
        bru_path = tmp_path / "bru.txt"
        bru_path.write_text(
            _bru_full("3182", "b", 2, "lofgeornost", post_punc=".") + "\n"
        )
        align_path = tmp_path / "aligned.txt"
        align_path.write_text(
            _aligned_row(
                "3182b2",
                "lofgeornost.",
                "lofgeornost.",
                "lofgeornost.",
                "lofgeornost.",
                "lofgeornost.",
            )
            + "\n"
        )

        tokens = parse_brunetti_tokens(bru_path)
        rows = parse_aligned(align_path)
        output = align_brunetti(rows, tokens)
        parsed = _parse_output(output)

        assert parsed[0]["texts"][5] == "lofgeornost."
