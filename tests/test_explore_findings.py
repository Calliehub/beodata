"""
Tests capturing empirical findings from exploratory analysis of Beowulf.

Each test encodes a discovery made by running explore_beowulf.py against
the beodata sources. These serve as regression guards: if the underlying
data or parsing changes, these assertions will flag it.

All data comes from parsing raw asset files (brunetti-length.txt and
aligned_with_brunetti.txt) — no DuckDB, no internet, no LLM training data.

Run with: poetry run pytest tests/test_explore_findings.py -v
"""

import pytest

from explore_beowulf import (
    analyze_compounds,
    analyze_scribal_hands,
    compound_hapaxes,
    edition_disagreements,
    find_hapax_legomena,
    hapax_by_pos,
    parse_aligned_file,
    parse_brunetti_file,
    pos_distribution,
    vocabulary_density_by_fitt,
)

# ─────────────────────────────────────────────────────────────
# Shared fixtures — parse data files once per session
# ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def brunetti_tokens():
    """All Brunetti tokens, parsed once for the entire test session."""
    return parse_brunetti_file()


@pytest.fixture(scope="session")
def aligned_rows():
    """All 6-way aligned rows, parsed once for the entire test session."""
    return parse_aligned_file()


@pytest.fixture(scope="session")
def scribal_hands(brunetti_tokens):
    return analyze_scribal_hands(brunetti_tokens)


@pytest.fixture(scope="session")
def hapaxes(brunetti_tokens):
    return find_hapax_legomena(brunetti_tokens)


@pytest.fixture(scope="session")
def pos_dist(brunetti_tokens):
    return pos_distribution(brunetti_tokens)


@pytest.fixture(scope="session")
def density(brunetti_tokens):
    return vocabulary_density_by_fitt(brunetti_tokens)


@pytest.fixture(scope="session")
def compounds(brunetti_tokens):
    return analyze_compounds(brunetti_tokens)


@pytest.fixture(scope="session")
def divergence(aligned_rows):
    return edition_disagreements(aligned_rows)


# ═════════════════════════════════════════════════════════════
# ANALYSIS 1: The Two Scribes — Beowulf vs Biowulf
#
# The Cotton Vitellius A.xv manuscript was written by two scribes.
# Scribe A prefers "eo" (Beowulf), Scribe B prefers "io" (Biowulf).
# The transition happens around line 1939 in the manuscript, but
# the spelling shift in the hero's name shows up clearly in the
# Brunetti tokenization.
# ═════════════════════════════════════════════════════════════


class TestScribalHands:
    """Verify the eo/io spelling split that reveals two manuscript scribes."""

    def test_eo_spellings_dominate_first_half(self, scribal_hands):
        # Scribe A wrote the first ~1939 lines, using "Beowulf" (eo)
        # consistently. There should be many eo-spellings.
        assert (
            scribal_hands["eo_count"] >= 20
        ), "Expected at least 20 'eo' (Beowulf) spellings from Scribe A"

    def test_io_spellings_dominate_second_half(self, scribal_hands):
        # Scribe B took over and switched to "Biowulf" (io).
        assert (
            scribal_hands["io_count"] >= 10
        ), "Expected at least 10 'io' (Biowulf) spellings from Scribe B"

    def test_first_io_occurs_around_line_1987(self, scribal_hands):
        # The first "io" spelling appears at line 1987:
        #   'Hú lomp éow on láde, léofa Bíowulf,'
        # This is near the traditional scribe-switch point (~line 1939).
        first_io = scribal_hands["first_io_line"]
        assert 1900 <= first_io <= 2100, (
            f"First 'io' spelling at line {first_io}, "
            "expected near the scribe transition (~1939–2000)"
        )

    def test_last_eo_at_line_2510(self, scribal_hands):
        # The last "eo" spelling lingers at line 2510:
        #   'Béowulf maðelode béotwordum spræc'
        # This is deep in Scribe B's territory — a holdover or
        # editorial normalization, not a scribal error.
        last_eo = scribal_hands["last_eo_line"]
        assert last_eo == 2510, f"Expected last 'eo' at line 2510, got {last_eo}"

    def test_transition_zone_is_messy(self, scribal_hands):
        # The eo→io shift isn't a clean switch. There are "eo" outliers
        # (lines 2207, 2510) deep in "io" territory. Real manuscripts
        # are messy — scribes are human.
        eo_after_first_io = [
            line
            for line in scribal_hands["all_eo"]
            if line > scribal_hands["first_io_line"]
        ]
        assert len(eo_after_first_io) >= 2, (
            "Expected at least 2 'eo' outliers after the io transition — "
            "the transition zone is not a clean boundary"
        )

    def test_eo_outlier_at_2207(self, scribal_hands):
        # Line 2207: 'syððan Béowulfe braéde ríce'
        # An "eo" spelling deep in Scribe B's "io" territory.
        assert 2207 in scribal_hands["all_eo"], "Expected an 'eo' outlier at line 2207"


# ═════════════════════════════════════════════════════════════
# ANALYSIS 2: Hapax Legomena
#
# Words appearing exactly once in the poem. Beowulf is famous
# for its extraordinary hapax rate — over half its vocabulary
# appears only once, many of them compounds the poet invented
# on the spot (or preserved from an oral tradition we've lost).
# ═════════════════════════════════════════════════════════════


class TestHapaxLegomena:
    """Verify the remarkable hapax legomena rate in Beowulf."""

    def test_hapax_count_around_1700(self, hapaxes, brunetti_tokens):
        # ~1696 lemmas appear exactly once, out of ~3263 unique lemmas.
        # That's roughly 52% — over half the vocabulary is hapax.
        total_lemmas = len(set(t["lemma"] for t in brunetti_tokens if t["lemma"]))
        hapax_pct = len(hapaxes) / total_lemmas * 100
        assert (
            45 < hapax_pct < 60
        ), f"Hapax rate {hapax_pct:.1f}% outside expected range 45–60%"

    def test_compound_hapaxes_are_abundant(self, hapaxes):
        # The poet's one-off compound inventions: words like
        # "brego-stol" (princely seat), "heaðo-lác" (battle-play),
        # that appear nowhere else in the OE corpus.
        comp_hap = compound_hapaxes(hapaxes)
        assert (
            len(comp_hap) > 700
        ), f"Expected 700+ compound hapaxes, got {len(comp_hap)}"

    def test_nouns_dominate_hapaxes(self, hapaxes):
        # Nouns (m + f + n) should be the largest hapax POS group.
        # This makes sense: nouns are the open class most amenable
        # to on-the-fly compounding (shield-warrior, wave-traveler, etc.)
        hpos = hapax_by_pos(hapaxes)
        noun_hapaxes = hpos.get("m", 0) + hpos.get("f", 0) + hpos.get("n", 0)
        verb_hapaxes = hpos.get("v", 0)
        assert noun_hapaxes > verb_hapaxes, (
            f"Expected nouns ({noun_hapaxes}) to outnumber verbs "
            f"({verb_hapaxes}) among hapaxes"
        )

    def test_masculine_nouns_lead_hapax_pos(self, hapaxes):
        # Masculine nouns are the single largest POS category
        # among hapaxes — the poet's compound-formation engine
        # overwhelmingly produces masculine nouns.
        hpos = hapax_by_pos(hapaxes)
        m_count = hpos.get("m", 0)
        # m should be the most frequent or close to it
        assert m_count == max(hpos.values()), (
            f"Expected masculine nouns to lead hapax POS, "
            f"but got {m_count} vs max {max(hpos.values())}"
        )


# ═════════════════════════════════════════════════════════════
# ANALYSIS 3: Part-of-Speech Distribution
#
# The grammatical skeleton of Beowulf: what kinds of words
# does the poet reach for most often?
# ═════════════════════════════════════════════════════════════


class TestPOSDistribution:
    """Verify the grammatical profile of the poem."""

    def test_verbs_are_most_frequent(self, pos_dist):
        # Verbs (code "v") should be the most frequent POS.
        # ~20% of all tokens — Beowulf is a poem of *action*.
        top_code = pos_dist[0][0]
        assert top_code == "v", f"Expected verbs to be #1 POS, got '{top_code}'"

    def test_verb_frequency_around_20_percent(self, pos_dist):
        # Verbs should be roughly 20% of all tokens.
        verb_entry = next(e for e in pos_dist if e[0] == "v")
        verb_pct = verb_entry[3]
        assert (
            15 < verb_pct < 25
        ), f"Verb frequency {verb_pct:.1f}% outside expected 15–25%"

    def test_masculine_nouns_are_second(self, pos_dist):
        # Masculine nouns (code "m") should be the second most frequent.
        # ~16% of tokens — the poem names its warriors, swords, halls.
        second_code = pos_dist[1][0]
        assert (
            second_code == "m"
        ), f"Expected masc nouns to be #2 POS, got '{second_code}'"

    def test_relative_pronoun_r_exists(self, pos_dist):
        # The Brunetti POS tag "r" = relative pronoun "þe".
        # About 117 occurrences. This is an unusual tag not in the
        # standard POS label set — it tracks the relative particle.
        r_entry = [e for e in pos_dist if e[0] == "r"]
        assert len(r_entry) == 1, "Expected POS code 'r' in distribution"
        assert (
            r_entry[0][2] > 100
        ), f"Expected 100+ relative pronoun tokens, got {r_entry[0][2]}"


# ═════════════════════════════════════════════════════════════
# ANALYSIS 4: Cross-Edition Divergence
#
# Six editions of Beowulf don't always agree. After normalizing
# punctuation, diacritics, and common OE spelling alternations
# (ð/þ, æ), about 46% of aligned rows still show genuine
# textual variation. Editors disagree a *lot*.
# ═════════════════════════════════════════════════════════════


class TestCrossEditionDivergence:
    """Verify the high rate of editorial disagreement across 6 editions."""

    def test_aligned_row_count(self, divergence):
        # The aligned file has 17,302 token rows.
        assert divergence["total_rows"] == 17302

    def test_divergence_rate_above_40_percent(self, divergence):
        # Even after normalizing diacritics, case, and ð/þ,
        # over 40% of rows show genuine textual differences.
        # This is astonishingly high — Beowulf is one manuscript,
        # but editors read it very differently.
        assert (
            divergence["divergent_pct"] > 40
        ), f"Expected >40% divergence, got {divergence['divergent_pct']:.1f}%"

    def test_divergence_rate_below_55_percent(self, divergence):
        # But not *too* high — most tokens are common OE words
        # that all editors agree on.
        assert (
            divergence["divergent_pct"] < 55
        ), f"Expected <55% divergence, got {divergence['divergent_pct']:.1f}%"


# ═════════════════════════════════════════════════════════════
# ANALYSIS 5: Vocabulary Density by Fitt
#
# Type-token ratio (unique lemmas / total tokens) varies by fitt.
# High TTR = the poet is reaching for novel vocabulary.
# Low TTR = formulaic, repetitive language (as in set speeches).
# ═════════════════════════════════════════════════════════════


class TestVocabularyDensity:
    """Verify vocabulary density variation across fitts."""

    def test_ttr_range_spans_0_55_to_0_77(self, density):
        # TTR ranges from about 0.553 (most formulaic) to 0.764 (most inventive).
        # That's a meaningful spread — some fitts are 40% more lexically
        # dense than others.
        ttrs = [d["ttr"] for d in density]
        assert min(ttrs) < 0.60, f"Expected min TTR < 0.60, got {min(ttrs):.3f}"
        assert max(ttrs) > 0.70, f"Expected max TTR > 0.70, got {max(ttrs):.3f}"

    def test_fitt_40_is_most_inventive(self, density):
        # Fitt 40 has the highest TTR (~0.764). This fitt covers
        # the dragon's hoard description — rich, unique vocabulary
        # for treasure, ancient weapons, and the curse on the gold.
        densest = max(density, key=lambda d: d["ttr"])
        assert (
            densest["fitt"] == 40
        ), f"Expected fitt 40 to be most inventive, got fitt {densest['fitt']}"

    def test_fitt_35_is_most_formulaic(self, density):
        # Fitt 35 has the lowest TTR (~0.553). This fitt contains
        # a retelling of past events — the kind of passage where
        # oral-formulaic diction dominates.
        sparsest = min(density, key=lambda d: d["ttr"])
        assert (
            sparsest["fitt"] == 35
        ), f"Expected fitt 35 to be most formulaic, got fitt {sparsest['fitt']}"

    def test_all_fitts_represented(self, density):
        # Brunetti numbers fitts 0–43 but skips fitt 30 (43 total).
        # Heorot.dk skips fitt 24 instead — different editorial traditions
        # disagree on where to place the fitt boundary.
        fitt_numbers = {d["fitt"] for d in density}
        assert len(fitt_numbers) == 43, f"Expected 43 fitts, got {len(fitt_numbers)}"
        assert (
            30 not in fitt_numbers
        ), "Fitt 30 should be absent in Brunetti's numbering"


# ═════════════════════════════════════════════════════════════
# ANALYSIS 6: Compound Words and Kennings
#
# The Beowulf-poet's compound words are the poem's most famous
# stylistic feature. Words like "hron-ráde" (whale-road = sea),
# "bán-hús" (bone-house = body), "beado-léoma" (battle-light = sword)
# are tiny poems within the poem.
# ═════════════════════════════════════════════════════════════


class TestCompoundWords:
    """Verify the compound word / kenning analysis."""

    def test_unique_compounds_above_1000(self, compounds):
        # The poet uses well over 1000 distinct compound lemmas.
        assert (
            compounds["unique_compounds"] > 1000
        ), f"Expected 1000+ unique compounds, got {compounds['unique_compounds']}"

    def test_war_vocabulary_dominates_first_elements(self, compounds):
        # The top compound prefixes are overwhelmingly war-related:
        # guð- (war), hilde- (battle), heaþo- (war), wæl- (slaughter).
        # The poet compounded battle words like a death-metal lyricist.
        top_firsts = [elem for elem, _ in compounds["top_first_elements"][:10]]
        war_prefixes = {"guð", "hilde", "heaþo", "wæl", "here"}
        found = war_prefixes.intersection(top_firsts)
        assert (
            len(found) >= 3
        ), f"Expected at least 3 war prefixes in top 10, found {found}"

    def test_gud_is_most_productive_prefix(self, compounds):
        # guð- (war/battle) is the single most productive first element.
        # The poet reaches for "guð-" more than any other compound prefix.
        top_first = compounds["top_first_elements"][0][0]
        assert (
            top_first == "guð"
        ), f"Expected 'guð' as #1 compound prefix, got '{top_first}'"

    def test_total_compound_tokens_above_1400(self, compounds):
        # Compound words appear over 1500 times in the poem (~1516).
        # That's roughly 1 in 11 tokens being a compound — concentrated
        # poetic density that sets Beowulf apart from prose texts.
        assert (
            compounds["total_compound_tokens"] > 1400
        ), f"Expected 1400+ compound tokens, got {compounds['total_compound_tokens']}"


# ═════════════════════════════════════════════════════════════
# DATA INTEGRITY: Basic sanity checks on the source data
# ═════════════════════════════════════════════════════════════


class TestDataIntegrity:
    """Sanity checks on the parsed source data."""

    def test_brunetti_token_count(self, brunetti_tokens):
        # Brunetti has ~17,244 tokens (give or take a few for blank lines).
        assert 17000 < len(brunetti_tokens) < 18000

    def test_aligned_row_count(self, aligned_rows):
        # The 6-way aligned file has exactly 17,302 rows.
        assert len(aligned_rows) == 17302

    def test_every_brunetti_token_has_line_id(self, brunetti_tokens):
        # Every token should have a line_id — it's the backbone of alignment.
        missing = [t for t in brunetti_tokens if not t["line_id"]]
        assert len(missing) == 0, f"{len(missing)} tokens missing line_id"

    def test_lemma_coverage(self, brunetti_tokens):
        # The vast majority of tokens should have a lemma assigned.
        # A few punctuation-only tokens may lack one.
        with_lemma = sum(1 for t in brunetti_tokens if t["lemma"])
        coverage = with_lemma / len(brunetti_tokens) * 100
        assert coverage > 95, f"Lemma coverage {coverage:.1f}% below expected 95%"
