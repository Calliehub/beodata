"""
Tests capturing scribal spelling differences in the Beowulf manuscript.

The Cotton Vitellius A.xv manuscript was copied by two scribes. These tests
encode the systematic orthographic preferences that distinguish them, as
discovered by running scribal_differences_exploration.py against the Brunetti
tokenization data.

All data comes from parsing raw asset files — no DuckDB, no internet,
no LLM training data.

Run with: poetry run pytest tests/test_scribal_differences.py -v
"""

import pytest

from explore_beowulf import parse_brunetti_file
from scribal_differences_exploration import (
    SCRIBE_BOUNDARY,
    compute_digram_shifts,
    find_all_transitions,
    find_lemma_variants,
    get_digram,
    get_variant_for_lemma,
    prepare_tokens,
    split_by_scribe,
    thorn_eth_ratio_by_line_range,
    thorn_eth_ratio_by_scribe,
    track_all_patterns,
)

# ─────────────────────────────────────────────────────────────
# Shared fixtures — parse data once per session
# ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def scribal_tokens():
    """All ScribalTokens, prepared once for the entire test session."""
    raw = parse_brunetti_file()
    return prepare_tokens(raw)


@pytest.fixture(scope="session")
def a_tokens(scribal_tokens):
    a, _ = split_by_scribe(scribal_tokens)
    return a


@pytest.fixture(scope="session")
def b_tokens(scribal_tokens):
    _, b = split_by_scribe(scribal_tokens)
    return b


@pytest.fixture(scope="session")
def lemma_variants(scribal_tokens):
    return find_lemma_variants(scribal_tokens)


@pytest.fixture(scope="session")
def digram_shifts(scribal_tokens):
    return compute_digram_shifts(scribal_tokens, top_n=50)


@pytest.fixture(scope="session")
def all_patterns(scribal_tokens):
    return track_all_patterns(scribal_tokens)


@pytest.fixture(scope="session")
def transitions(scribal_tokens):
    return find_all_transitions(scribal_tokens)


@pytest.fixture(scope="session")
def thorn_eth_ratios(scribal_tokens):
    return thorn_eth_ratio_by_scribe(scribal_tokens)


@pytest.fixture(scope="session")
def thorn_eth_curve(scribal_tokens):
    return thorn_eth_ratio_by_line_range(scribal_tokens)


# ═════════════════════════════════════════════════════════════
# TOKEN SPLIT: Basic sanity checks on the scribe boundary
# ═════════════════════════════════════════════════════════════


class TestTokenSplit:
    """Verify the scribe boundary splits tokens correctly."""

    def test_boundary_is_1939(self):
        assert SCRIBE_BOUNDARY == 1939

    def test_scribe_a_has_more_tokens(self, a_tokens, b_tokens):
        # Scribe A copied the first 1939 lines — the bigger chunk.
        assert len(a_tokens) > len(b_tokens), (
            f"Scribe A ({len(a_tokens)}) should have more tokens "
            f"than Scribe B ({len(b_tokens)})"
        )

    def test_total_token_count(self, a_tokens, b_tokens):
        total = len(a_tokens) + len(b_tokens)
        assert 16000 < total < 18000, f"Expected 16k–18k total tokens, got {total}"

    def test_a_tokens_all_before_boundary(self, a_tokens):
        assert all(t.line_id <= SCRIBE_BOUNDARY for t in a_tokens)

    def test_b_tokens_all_after_boundary(self, b_tokens):
        assert all(t.line_id > SCRIBE_BOUNDARY for t in b_tokens)


# ═════════════════════════════════════════════════════════════
# LEMMA VARIANTS: Systematic spelling differences
#
# The same lemma, two different scribes, different surface forms.
# This is the heart of scribal identification.
# ═════════════════════════════════════════════════════════════


class TestLemmaVariants:
    """Verify known lemma-level spelling splits between scribes."""

    def test_at_least_100_lemmas_with_exclusive_forms(self, lemma_variants):
        # With 312 lemmas showing exclusive forms (min 3 each half),
        # these are NOT random fluctuations — they're systematic habits.
        assert (
            len(lemma_variants) >= 100
        ), f"Expected 100+ lemmas with exclusive forms, got {len(lemma_variants)}"

    def test_self_sylf_split(self, lemma_variants):
        # Scribe A writes "self*", Scribe B writes "sylf*".
        v = get_variant_for_lemma(lemma_variants, "self")
        assert v is not None, "Expected lemma 'self' in variants"

        # A should have self-forms the B doesn't
        a_has_self = any("self" in f for f in v.a_forms)
        b_has_sylf = any("sylf" in f for f in v.b_forms)
        assert a_has_self, f"Expected Scribe A to use self-forms: {v.a_forms}"
        assert b_has_sylf, f"Expected Scribe B to use sylf-forms: {v.b_forms}"

    def test_scolde_sceolde_split(self, lemma_variants):
        # Scribe A: "scolde" exclusively. Scribe B: "sceolde" exclusively.
        # A perfect binary split — no exceptions whatsoever.
        v = get_variant_for_lemma(lemma_variants, "sculan")
        assert v is not None, "Expected lemma 'sculan' in variants"

        a_has_scolde = any("scolde" in f or "scolde" in f for f in v.a_forms)
        b_has_sceolde = any("sceolde" in f or "sceold" in f for f in v.b_forms)
        assert a_has_scolde, f"Expected Scribe A to use scolde: {v.a_forms}"
        assert b_has_sceolde, f"Expected Scribe B to use sceolde: {v.b_forms}"

    def test_gamol_gomel_split(self, lemma_variants):
        # Scribe B prefers "gom*" (rounded vowel) over "gam*".
        v = get_variant_for_lemma(lemma_variants, "gamol")
        assert v is not None, "Expected lemma 'gamol' in variants"

        # B should have gom-forms
        b_has_gom = any(f.startswith("gom") for f in v.b_forms)
        assert b_has_gom, f"Expected Scribe B to use gom- forms: {v.b_forms}"

    def test_heorot_hiorot_split(self, scribal_tokens):
        # The hall's name: Scribe A "Heorot", Scribe B "Hiorot".
        # The eo→io shift extends beyond just Beowulf's name.
        # Scribe B has only 2 attestations (below min_count=3 for
        # lemma_variants), so we check the raw tokens directly.
        heorot = [t for t in scribal_tokens if t.lemma == "Heorot"]
        a_forms = [t.text for t in heorot if t.scribe == "A"]
        b_forms = [t.text for t in heorot if t.scribe == "B"]

        assert (
            len(a_forms) >= 10
        ), f"Expected 10+ Heorot in Scribe A, got {len(a_forms)}"
        assert len(b_forms) >= 1, f"Expected Heorot in Scribe B, got {len(b_forms)}"

        a_has_eo = any("eo" in f.lower() for f in a_forms)
        b_has_io = any("io" in f.lower() for f in b_forms)
        assert a_has_eo, f"Expected Scribe A Heorot with 'eo': {a_forms}"
        assert b_has_io, f"Expected Scribe B Hiorot with 'io': {b_forms}"

    def test_beowulf_biowulf_split(self, lemma_variants):
        # The hero's own name: the flagship scribal marker.
        v = get_variant_for_lemma(lemma_variants, "Beowulf")
        assert v is not None, "Expected lemma 'Beowulf' in variants"

        # B should have io-forms that A doesn't
        b_io = any("io" in f.lower() for f in v.b_only)
        assert b_io, f"Expected Scribe B-only io forms: {v.b_only}"

    def test_siththan_wild_variation_in_a(self, lemma_variants):
        # siððan: Scribe A uses 6+ different spellings (syþðan, syðþan,
        # siþðan, siððan, seoþðan, seoððan, siþþan, siðþan...).
        # Scribe B normalizes everything to just "syððan".
        v = get_variant_for_lemma(lemma_variants, "siððan")
        assert v is not None, "Expected lemma 'siððan' in variants"

        # Scribe A should have many more unique spellings than B
        assert len(v.a_forms) > len(v.b_forms), (
            f"Expected Scribe A to have more siððan variants ({len(v.a_forms)}) "
            f"than Scribe B ({len(v.b_forms)})"
        )
        # Scribe A: at least 6 distinct spellings
        assert len(v.a_forms) >= 6, (
            f"Expected 6+ siððan spellings from Scribe A, got {len(v.a_forms)}: "
            f"{list(v.a_forms.keys())}"
        )

    def test_ecgtheow_split(self, lemma_variants):
        # Ecgþeow: Scribe A uses þ (thorn), Scribe B uses ð (eth).
        # Also the eo→io shift appears (Ecgðiow- in B).
        v = get_variant_for_lemma(lemma_variants, "Ecgþeow")
        if v is None:
            # Try alternate lemma form
            v = get_variant_for_lemma(lemma_variants, "Ecgþēow")
        assert v is not None, "Expected Ecgþeow lemma in variants"

        # A should have þ, B should have ð
        a_has_thorn = any("þ" in f for f in v.a_forms)
        b_has_eth = any("ð" in f for f in v.b_forms)
        assert a_has_thorn, f"Expected Scribe A Ecgþeow with þ: {v.a_forms}"
        assert b_has_eth, f"Expected Scribe B Ecgðeow with ð: {v.b_forms}"


# ═════════════════════════════════════════════════════════════
# DIGRAM SHIFTS: Character bigram frequency analysis
#
# The data-driven approach: count every two-character sequence
# in each half and look for the biggest skews. No fishing for
# patterns — the math finds them on its own.
# ═════════════════════════════════════════════════════════════


class TestDigramShifts:
    """Verify the character bigram frequency shifts between scribes."""

    def test_io_bigram_favors_scribe_b(self, digram_shifts):
        # The io bigram is massively more frequent in Scribe B's text.
        # This is the eo→io diphthong shift at the character level.
        io = get_digram(digram_shifts, "io")
        assert io is not None, "Expected 'io' bigram in shift data"
        assert io.b_rate_per_10k > io.a_rate_per_10k * 5, (
            f"Expected io to be 5x+ more frequent in B: "
            f"A={io.a_rate_per_10k}/10k, B={io.b_rate_per_10k}/10k"
        )

    def test_thorn_eth_bigram_favors_scribe_a(self, digram_shifts):
        # þð (thorn-eth) is Scribe A's mixed dental cluster.
        # ~38 occurrences in A, ~0 in B. Scribe B avoids it entirely.
        td = get_digram(digram_shifts, "þð")
        assert td is not None, "Expected 'þð' bigram in shift data"
        assert td.a_count >= 30, f"Expected 30+ þð in Scribe A, got {td.a_count}"
        assert td.b_count <= 2, f"Expected ~0 þð in Scribe B, got {td.b_count}"

    def test_double_eth_favors_scribe_b(self, digram_shifts):
        # ðð (double eth) is Scribe B's normalized replacement for
        # Scribe A's wild thorn/eth mixing. B uses it at 4x+ A's rate.
        dd = get_digram(digram_shifts, "ðð")
        assert dd is not None, "Expected 'ðð' bigram in shift data"
        assert dd.b_rate_per_10k > dd.a_rate_per_10k * 2, (
            f"Expected ðð to be 2x+ more frequent in B: "
            f"A={dd.a_rate_per_10k}/10k, B={dd.b_rate_per_10k}/10k"
        )


# ═════════════════════════════════════════════════════════════
# PATTERN TRACKING: Known scribal markers
#
# Classifier-based tracking of specific orthographic features
# across the full poem.
# ═════════════════════════════════════════════════════════════


class TestPatternTracking:
    """Verify the distribution of known scribal spelling patterns."""

    def test_eo_dominates_scribe_a(self, all_patterns):
        # Scribe A overwhelmingly uses "eo" diphthongs.
        eo_io = all_patterns["eo/io"]
        a_eo = eo_io["A"].get("eo", 0)
        a_io = eo_io["A"].get("io", 0)
        assert a_eo > a_io * 10, (
            f"Expected Scribe A to heavily prefer eo over io: " f"eo={a_eo}, io={a_io}"
        )

    def test_io_rises_in_scribe_b(self, all_patterns):
        # Scribe B has a dramatically higher io proportion.
        eo_io = all_patterns["eo/io"]
        b_eo = eo_io["B"].get("eo", 0)
        b_io = eo_io["B"].get("io", 0)
        # io should be a significant fraction — not necessarily dominant
        # (eo is still used for many words), but at least 10% of diphthongs
        assert b_io > b_eo * 0.1, (
            f"Expected significant io usage in Scribe B: " f"eo={b_eo}, io={b_io}"
        )

    def test_self_sylf_distribution(self, all_patterns):
        ss = all_patterns["self/sylf"]
        # Scribe A: self dominates
        assert ss["A"].get("self", 0) > ss["A"].get(
            "sylf", 0
        ), f"Expected Scribe A to prefer 'self': {ss['A']}"
        # Scribe B: sylf dominates
        assert ss["B"].get("sylf", 0) > ss["B"].get(
            "self", 0
        ), f"Expected Scribe B to prefer 'sylf': {ss['B']}"

    def test_scolde_sceolde_perfect_split(self, all_patterns):
        sc = all_patterns["scolde/sceolde"]
        # Scribe A: only scolde
        assert sc["A"].get("scolde", 0) > 0, f"Expected scolde in Scribe A: {sc['A']}"
        assert (
            sc["A"].get("sceolde", 0) == 0
        ), f"Expected no sceolde in Scribe A: {sc['A']}"
        # Scribe B: only sceolde
        assert sc["B"].get("sceolde", 0) > 0, f"Expected sceolde in Scribe B: {sc['B']}"
        assert (
            sc["B"].get("scolde", 0) == 0
        ), f"Expected no scolde in Scribe B: {sc['B']}"

    def test_siththan_scribe_b_normalizes(self, all_patterns):
        # Scribe B uses basically one spelling: syððan.
        si = all_patterns["siððan variants"]
        # B should have far fewer distinct spellings than A
        assert len(si["A"]) > len(si["B"]), (
            f"Expected Scribe A to have more siððan variants: "
            f"A has {len(si['A'])}, B has {len(si['B'])}"
        )
        # B should be almost entirely "syððan"
        b_total = sum(si["B"].values())
        b_syththan = si["B"].get("syððan", 0) + si["B"].get("Syððan", 0)
        assert b_syththan / b_total > 0.9, f"Expected Scribe B >90% syððan: {si['B']}"


# ═════════════════════════════════════════════════════════════
# TRANSITION MAPPING: Where does each pattern shift?
#
# The scribe boundary is traditionally at line 1939, but the
# spelling shifts don't all happen at the same line. They
# cluster in the 1800–2200 range with a spread > 10 lines.
# ═════════════════════════════════════════════════════════════


class TestTransitionMapping:
    """Verify that spelling transitions cluster near line 1939 but spread out."""

    def test_clean_transitions_cluster_near_boundary(self, transitions):
        # self/sylf and scolde/sceolde have clean binary splits and their
        # optimal transition points land right near the scribe boundary.
        # gamol/gomel is messier because Scribe A already uses some "gom"
        # forms, so its transition point is unreliable.
        for name in ["self/sylf", "scolde/sceolde"]:
            tr = transitions.get(name)
            if tr is not None:
                assert 1800 <= tr.transition_line <= 2100, (
                    f"{name} transition at line {tr.transition_line}, "
                    f"expected 1800–2100"
                )

    def test_transitions_are_not_all_at_same_line(self, transitions):
        # Even the clean transitions don't land on the exact same line.
        lines = [tr.transition_line for tr in transitions.values()]
        if len(lines) >= 2:
            spread = max(lines) - min(lines)
            assert (
                spread > 10
            ), f"Expected transition spread > 10 lines, got {spread}: {lines}"

    def test_self_sylf_transition_near_1939(self, transitions):
        # The self→sylf transition should be close to the scribe boundary.
        # Despite the single outlier "sylfa" at line 505 in Scribe A,
        # the optimal split point correctly identifies ~1944.
        tr = transitions.get("self/sylf")
        assert tr is not None, "Expected self/sylf transition"
        assert (
            1800 <= tr.transition_line <= 2100
        ), f"self/sylf transition at {tr.transition_line}, expected 1800–2100"

    def test_scolde_sceolde_transition(self, transitions):
        # Perfect binary split: all scolde ≤1798, all sceolde ≥2056.
        # Transition point lands right in the gap.
        tr = transitions.get("scolde/sceolde")
        assert tr is not None, "Expected scolde/sceolde transition"
        assert (
            1800 <= tr.transition_line <= 2100
        ), f"scolde/sceolde transition at {tr.transition_line}, expected 1800–2100"


# ═════════════════════════════════════════════════════════════
# THORN/ETH: The dental fricative ratio reversal
#
# Scribe A prefers þ (thorn), Scribe B prefers ð (eth).
# This shows up as a dramatic ratio reversal at the boundary.
# ═════════════════════════════════════════════════════════════


class TestThornEth:
    """Verify the þ/ð preference reversal between scribes."""

    def test_scribe_a_prefers_thorn(self, thorn_eth_ratios):
        a_ratio, _ = thorn_eth_ratios
        assert a_ratio > 0.5, f"Expected Scribe A þ/(þ+ð) > 0.5, got {a_ratio:.3f}"

    def test_scribe_b_prefers_eth(self, thorn_eth_ratios):
        _, b_ratio = thorn_eth_ratios
        assert b_ratio < 0.5, f"Expected Scribe B þ/(þ+ð) < 0.5, got {b_ratio:.3f}"

    def test_ratio_reversal_is_dramatic(self, thorn_eth_ratios):
        # The gap should be substantial — not a marginal preference.
        a_ratio, b_ratio = thorn_eth_ratios
        gap = a_ratio - b_ratio
        assert gap > 0.2, (
            f"Expected þ ratio gap > 0.2 between scribes: "
            f"A={a_ratio:.3f}, B={b_ratio:.3f}, gap={gap:.3f}"
        )

    def test_ratio_curve_shows_transition(self, thorn_eth_curve):
        # The sliding window curve should cross 0.5 near the boundary.
        # Find the window where it drops below 0.5 for the first time.
        crossings = [
            (start, ratio)
            for start, end, ratio, _, _ in thorn_eth_curve
            if start > 1000 and ratio < 0.5
        ]
        assert (
            len(crossings) > 0
        ), "Expected the thorn/eth ratio to drop below 0.5 somewhere after line 1000"
        first_crossing_line = crossings[0][0]
        assert 1600 <= first_crossing_line <= 2200, (
            f"Expected first ratio<0.5 crossing near boundary, "
            f"got line {first_crossing_line}"
        )
