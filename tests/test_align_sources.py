"""Tests for 6-way source alignment (aligned-sources.txt)."""

from pathlib import Path
from typing import List

import pytest

from sources.align_sources import (
    Token,
    align_all,
    extract_brunetti_surface,
    parse_mit_id,
    read_txt_edition,
    tokenize_edition_line,
    tokenize_simple_edition,
)


class TestParseMitId:
    """Tests for the ID parser."""

    def test_simple(self) -> None:
        assert parse_mit_id("0001a1") == (1, "a", 1)

    def test_high_line(self) -> None:
        assert parse_mit_id("3182b2") == (3182, "b", 2)

    def test_multi_digit_offset(self) -> None:
        assert parse_mit_id("0307b4") == (307, "b", 4)

    def test_zero_offset(self) -> None:
        assert parse_mit_id("0389b0") == (389, "b", 0)


class TestTokenizeEditionLine:
    """Tests for the line tokenizer."""

    def test_simple_line(self) -> None:
        """Normal line with caesura produces a-half and b-half tokens."""
        tokens = tokenize_edition_line(1, "Hwæt! We Gardena     in geardagum,")
        assert len(tokens) == 5
        assert tokens[0] == Token("0001a1", "Hwæt!")
        assert tokens[1] == Token("0001a2", "We")
        assert tokens[2] == Token("0001a3", "Gardena")
        assert tokens[3] == Token("0001b1", "in")
        assert tokens[4] == Token("0001b2", "geardagum,")

    def test_at_only_half(self) -> None:
        """A half-line of only @ tokens shares the same ID."""
        tokens = tokenize_edition_line(389, 'Deniga leodum."     @ @ @ @')
        # a-half: 2 normal tokens; b-half: 4 @ tokens all at offset 0
        a_tokens = [t for t in tokens if t.id_str.startswith("0389a")]
        b_tokens = [t for t in tokens if t.id_str.startswith("0389b")]
        assert len(a_tokens) == 2
        assert a_tokens[0] == Token("0389a1", "Deniga")
        assert a_tokens[1] == Token("0389a2", 'leodum."')
        assert len(b_tokens) == 4
        assert all(t.id_str == "0389b0" for t in b_tokens)
        assert all(t.text == "@" for t in b_tokens)

    def test_underscore_join(self) -> None:
        """_ join token advances position by 1 + count('_')."""
        tokens = tokenize_edition_line(9, "oð_þæt him æghwylc     þara ymbsittendra")
        # oð_þæt: 1 underscore → offset=1, position advances to 2
        # him: offset=3, æghwylc: offset=4
        assert tokens[0] == Token("0009a1", "oð_þæt")
        assert tokens[1] == Token("0009a3", "him")
        assert tokens[2] == Token("0009a4", "æghwylc")
        assert tokens[3] == Token("0009b1", "þara")
        assert tokens[4] == Token("0009b2", "ymbsittendra")

    def test_mixed_at_and_real(self) -> None:
        """@ mixed with real words — @ inherits previous position."""
        tokens = tokenize_edition_line(62, "hyrde ic þæt @     wæs Onelan cwen,")
        a_tokens = [t for t in tokens if "a" in t.id_str[4]]
        # hyrde=1, ic=2, þæt=3, @=3 (shares with þæt)
        assert a_tokens[0] == Token("0062a1", "hyrde")
        assert a_tokens[1] == Token("0062a2", "ic")
        assert a_tokens[2] == Token("0062a3", "þæt")
        assert a_tokens[3] == Token("0062a3", "@")

    def test_leading_at(self) -> None:
        """@ at start of half gets offset 0."""
        tokens = tokenize_edition_line(432, "@ þes hearda heap,     Heorot fælsian.")
        assert tokens[0] == Token("0432a0", "@")
        assert tokens[1] == Token("0432a1", "þes")
        assert tokens[2] == Token("0432a2", "hearda")

    def test_no_caesura(self) -> None:
        """Line without 5-space caesura → all tokens in a-half."""
        tokens = tokenize_edition_line(999, "single half only")
        assert len(tokens) == 3
        assert all("a" in t.id_str[4] for t in tokens)

    def test_multiple_underscores(self) -> None:
        """Token with 2 underscores skips 3 positions total."""
        tokens = tokenize_edition_line(100, "a_b_c next     rest")
        # a_b_c: position 0→1, offset=1, then position += 2 → 3
        # next: position 3→4, offset=4
        assert tokens[0] == Token("0100a1", "a_b_c")
        assert tokens[1] == Token("0100a4", "next")


class TestExtractBrunettiSurface:
    """Tests for Brunetti surface text extraction."""

    def test_simple_a_half(self) -> None:
        text = extract_brunetti_surface("Hwæt! We Gardena    in geardagum,", "a", 1)
        assert text == "Hwæt!"

    def test_simple_b_half(self) -> None:
        text = extract_brunetti_surface("Hwæt! We Gardena    in geardagum,", "b", 2)
        assert text == "geardagum,"

    def test_third_word(self) -> None:
        text = extract_brunetti_surface("Hwæt! We Gardena    in geardagum,", "a", 3)
        assert text == "Gardena"

    def test_out_of_range(self) -> None:
        text = extract_brunetti_surface("Hwæt! We Gardena    in geardagum,", "a", 99)
        assert text == "@"

    def test_no_caesura(self) -> None:
        """If no caesura, b-half is empty → fallback to @."""
        text = extract_brunetti_surface("single half only", "b", 1)
        assert text == "@"

    def test_brackets_stripped(self) -> None:
        """Bracketed editorial text is removed before word extraction."""
        text = extract_brunetti_surface("[editorial] word1 word2    rest", "a", 1)
        assert text == "word1"


# ── Alignment helpers ───────────────────────────────────────


def _make_streams(*lines: str) -> List[List[Token]]:
    """Build 4 identical txt-edition streams from line strings.

    Each line string is tokenized sequentially starting at line 1.
    All 4 editions get the same tokens (they're positionally zipped).
    """
    tokens: List[Token] = []
    for i, line in enumerate(lines, start=1):
        tokens.extend(tokenize_edition_line(i, line))
    return [tokens] * 4


def _make_heorot_tokens(*lines: str) -> List[Token]:
    """Build Heorot tokens from plain text (no caesura, no @ or _ markers).

    Strips @, replaces _ joins with separate words, collapses caesura.
    """
    tokens: List[Token] = []
    for i, line in enumerate(lines, start=1):
        # Collapse 5-space caesura, drop @, expand _ joins
        clean = line.replace("     ", " ")
        words = []
        for w in clean.split():
            if w == "@":
                continue
            if "_" in w:
                words.extend(w.split("_"))
            else:
                words.append(w)
        line_str = str(i).zfill(4)
        for j, word in enumerate(words, start=1):
            tokens.append(Token(f"{line_str}a{j}", word))
    return tokens


def _parse_output(lines: List[str]) -> List[dict]:
    """Parse output lines into dicts with ids and texts."""
    results = []
    for line in lines:
        parts = line.split(" ")
        results.append({"ids": parts[:6], "texts": parts[6:]})
    return results


class TestAlignAll:
    """Tests for the full alignment pipeline."""

    def test_simple_1to1(self) -> None:
        """Each aligned row matches one Heorot and Brunetti token."""
        ed_lines = ("Hwæt! We     Gardena",)
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", "Hwæt!"),
            Token("0001a2", "We"),
            Token("0001b1", "Gardena"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        parsed = _parse_output(output)

        assert len(output) == 3
        # Heorot column (index 2)
        assert parsed[0]["texts"][2] == "Hwæt!"
        assert parsed[1]["texts"][2] == "We"
        assert parsed[2]["texts"][2] == "Gardena"
        # Brunetti column (index 5)
        assert parsed[0]["ids"][5] == "0001a1"
        assert parsed[0]["texts"][5] == "Hwæt!"
        assert parsed[1]["texts"][5] == "We"
        assert parsed[2]["texts"][5] == "Gardena"

    def test_join_row(self) -> None:
        """A _ join row collects multiple Heorot and Brunetti tokens."""
        ed_lines = ("mægen_Hreðmanna.     Na",)
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", "mægenhrēð"),
            Token("0001a2", "manna."),
            Token("0001b1", "Nā"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        parsed = _parse_output(output)

        # Heorot should collect the 2 expanded words joined with _
        assert parsed[0]["texts"][2] == "mægen_Hreðmanna."
        assert parsed[1]["texts"][2] == "Na"
        # Brunetti
        assert parsed[0]["texts"][5] == "mægenhrēð_manna."
        assert parsed[1]["texts"][5] == "Nā"

    def test_gap_no_brunetti(self) -> None:
        """@ gap with no Brunetti/Heorot match → '@' in output."""
        ed_lines = ("word     @ @",)
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", "word"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        parsed = _parse_output(output)

        assert parsed[0]["texts"][2] == "word"  # Heorot
        assert parsed[0]["texts"][5] == "word"  # Brunetti
        # @ tokens — Heorot has no words left, Brunetti has none either
        assert parsed[1]["texts"][2] == "@"
        assert parsed[1]["texts"][5] == "@"
        assert parsed[2]["texts"][2] == "@"
        assert parsed[2]["texts"][5] == "@"

    def test_gap_brunetti_has_tokens(self) -> None:
        """@ gaps where Brunetti has real tokens (like ms. lacunae filled)."""
        ed_lines = ('leodum."     @ @', "@ @     word")
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", 'leodum."'),
            Token("0002a1", "Wedera"),
            Token("0002a2", "lēodum"),
            Token("0002b1", "word"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        parsed = _parse_output(output)

        # Line 1a: normal match
        assert parsed[0]["texts"][2] == 'leodum."'  # Heorot
        assert parsed[0]["texts"][5] == 'leodum."'  # Brunetti
        # Line 1b: @ gaps
        assert parsed[1]["texts"][2] == "@"
        assert parsed[1]["texts"][5] == "@"
        assert parsed[2]["texts"][2] == "@"
        assert parsed[2]["texts"][5] == "@"
        # Line 2a: @ gaps in txt editions, but Brunetti has tokens
        # Heorot only has "word" for line 2, cursor doesn't advance on @
        assert parsed[3]["texts"][5] == "Wedera"
        assert parsed[4]["texts"][5] == "lēodum"
        # Line 2b: normal
        assert parsed[5]["texts"][2] == "word"  # Heorot
        assert parsed[5]["texts"][5] == "word"  # Brunetti

    def test_output_has_12_columns(self) -> None:
        """Each output line has exactly 12 space-separated columns."""
        ed_lines = ("Hwæt!     We",)
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", "Hwæt!"),
            Token("0001b1", "Wē"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        for line in output:
            parts = line.split(" ")
            assert len(parts) == 12

    def test_last_row_sentinel(self) -> None:
        """The last aligned row should still collect its Brunetti token."""
        ed_lines = ("lofgeornost.     end",)
        streams = _make_streams(*ed_lines)
        heo_tokens = _make_heorot_tokens(*ed_lines)
        bru_tokens = [
            Token("0001a1", "lofgeornost."),
            Token("0001b1", "end"),
        ]
        output = align_all(streams, heo_tokens, bru_tokens)
        parsed = _parse_output(output)

        assert parsed[-1]["texts"][2] == "end"  # Heorot
        assert parsed[-1]["texts"][5] == "end"  # Brunetti

    def test_token_count_mismatch_raises(self) -> None:
        """Mismatched edition token counts should raise AssertionError."""
        streams = [
            [Token("0001a1", "Hwæt!")],
            [Token("0001a1", "Hwæt!"), Token("0001a2", "We")],
            [Token("0001a1", "Hwæt!")],
            [Token("0001a1", "Hwæt!")],
        ]
        with pytest.raises(AssertionError, match="Token count mismatch"):
            align_all(streams, [], [])


class TestReadTxtEdition:
    """Tests for direct txt-file asset reading."""

    def test_reads_mit_txt(self) -> None:
        """Should read mit.txt and return lines with 'line' and 'oe' keys."""
        lines = read_txt_edition("mit.txt")
        assert len(lines) >= 3180
        assert lines[0]["line"] == 1
        assert "Hwæt" in lines[0]["oe"]

    def test_preserves_caesura(self) -> None:
        """The 5-space caesura should survive the read."""
        lines = read_txt_edition("mit.txt")
        assert "     " in lines[0]["oe"]

    def test_all_four_txt_editions_same_token_count(self) -> None:
        """All 4 text-file editions must produce exactly 17,302 tokens."""
        for asset in [
            "mit.txt",
            "mcmaster.txt",
            "ebeowulf.txt",
            "perseus.txt",
        ]:
            lines = read_txt_edition(asset)
            stream = tokenize_simple_edition(lines)
            assert len(stream) == 17302, f"{asset} produced {len(stream)} tokens"
