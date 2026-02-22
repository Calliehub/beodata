"""
---------------------------------------------------------------------------
Callie's Note: This file was written by Claude! (Opus 4.6)
---------------------------------------------------------------------------
Claude's work follows:

Comprehensive analysis of scribal spelling differences in the Beowulf manuscript.

The Cotton Vitellius A.xv manuscript — our only copy of Beowulf — was written
by two scribes. The traditional boundary is line 1939 (folio 172v). By comparing
the surface forms (text) against normalized lemmas in the Brunetti tokenization,
we can systematically reveal every spelling preference that distinguishes them.

Scribe A is a wild orthographic improviser. Scribe B is a ruthless normalizer.

Run with: poetry run python -i scribal_differences_exploration.py

Findings are captured as assertions in tests/test_scribal_differences.py.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from explore_beowulf import parse_brunetti_file

# ═══════════════════════════════════════════════════════════════
# CONSTANTS & TYPES
# ═══════════════════════════════════════════════════════════════

SCRIBE_BOUNDARY = 1939  # lines <= 1939 = Scribe A, > 1939 = Scribe B


@dataclass
class ScribalToken:
    text: str
    lemma: str
    line_id: int
    pos: str
    parse: str
    scribe: str  # "A" or "B"


@dataclass
class LemmaVariant:
    lemma: str
    a_forms: Dict[str, int] = field(default_factory=dict)
    b_forms: Dict[str, int] = field(default_factory=dict)
    a_only: Set[str] = field(default_factory=set)
    b_only: Set[str] = field(default_factory=set)


@dataclass
class DigramShift:
    digram: str
    a_count: int
    b_count: int
    a_rate_per_10k: float
    b_rate_per_10k: float
    ratio: float  # b_rate / a_rate (>1 means B uses it more)


@dataclass
class PatternTransition:
    pattern_name: str
    a_form: str
    b_form: str
    transition_line: int
    last_a_form_line: int
    first_b_form_line: int
    overlap_lines: List[int] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# DATA PREPARATION
# ═══════════════════════════════════════════════════════════════


def prepare_tokens(raw_tokens: List[dict]) -> List[ScribalToken]:
    """Convert raw Brunetti dicts into ScribalTokens with scribe assignment."""
    result = []
    for t in raw_tokens:
        if not t["text"] or not t["line_id"]:
            continue
        line_id = int(t["line_id"])
        result.append(
            ScribalToken(
                text=t["text"],
                lemma=t["lemma"] or "",
                line_id=line_id,
                pos=t["pos"] or "",
                parse=t["parse"] or "",
                scribe="A" if line_id <= SCRIBE_BOUNDARY else "B",
            )
        )
    return result


def split_by_scribe(
    tokens: List[ScribalToken],
) -> Tuple[List[ScribalToken], List[ScribalToken]]:
    """Split tokens into Scribe A and Scribe B lists."""
    a = [t for t in tokens if t.scribe == "A"]
    b = [t for t in tokens if t.scribe == "B"]
    return a, b


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 1: Lemma-level spelling variants
#
# For each lemma appearing in BOTH halves (min 3 each), collect
# surface forms per scribe. Forms exclusive to one scribe reveal
# systematic spelling preferences.
# ═══════════════════════════════════════════════════════════════


def find_lemma_variants(
    tokens: List[ScribalToken], min_count: int = 3
) -> List[LemmaVariant]:
    """Find lemmas with different surface spellings between scribes."""
    a_forms: Dict[str, Counter] = defaultdict(Counter)
    b_forms: Dict[str, Counter] = defaultdict(Counter)

    for t in tokens:
        if not t.lemma:
            continue
        text_lower = t.text.lower()
        if t.scribe == "A":
            a_forms[t.lemma][text_lower] += 1
        else:
            b_forms[t.lemma][text_lower] += 1

    results = []
    for lemma in sorted(set(a_forms) & set(b_forms)):
        a_total = sum(a_forms[lemma].values())
        b_total = sum(b_forms[lemma].values())
        if a_total < min_count or b_total < min_count:
            continue

        a_set = set(a_forms[lemma])
        b_set = set(b_forms[lemma])
        a_only = a_set - b_set
        b_only = b_set - a_set

        if a_only or b_only:
            results.append(
                LemmaVariant(
                    lemma=lemma,
                    a_forms=dict(a_forms[lemma]),
                    b_forms=dict(b_forms[lemma]),
                    a_only=a_only,
                    b_only=b_only,
                )
            )

    return results


def get_variant_for_lemma(
    variants: List[LemmaVariant], lemma: str
) -> Optional[LemmaVariant]:
    """Find the LemmaVariant for a specific lemma, or None."""
    for v in variants:
        if v.lemma == lemma:
            return v
    return None


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 2: Character bigram frequency shifts
#
# Count all character bigrams in each half, normalize per 10k
# bigram slots. This finds eo/io, þð/ðð shifts without fishing.
# ═══════════════════════════════════════════════════════════════


def compute_digram_shifts(
    tokens: List[ScribalToken], top_n: int = 20
) -> List[DigramShift]:
    """Find character bigrams with the largest frequency ratio between scribes."""
    a_counts: Counter = Counter()
    b_counts: Counter = Counter()
    a_total = 0
    b_total = 0

    for t in tokens:
        text = t.text.lower()
        for i in range(len(text) - 1):
            bi = text[i : i + 2]
            if t.scribe == "A":
                a_counts[bi] += 1
                a_total += 1
            else:
                b_counts[bi] += 1
                b_total += 1

    # Get all bigrams that appear at least once in either half
    all_bigrams = set(a_counts) | set(b_counts)
    results = []
    for bi in all_bigrams:
        a_c = a_counts[bi]
        b_c = b_counts[bi]
        a_rate = a_c / a_total * 10000 if a_total else 0
        b_rate = b_c / b_total * 10000 if b_total else 0

        # Compute ratio (B/A), handling zero denominators
        if a_rate > 0 and b_rate > 0:
            ratio = max(b_rate / a_rate, a_rate / b_rate)
        elif a_rate > 0:
            ratio = float("inf")
        elif b_rate > 0:
            ratio = float("inf")
        else:
            ratio = 1.0

        # Only include bigrams with meaningful counts
        if a_c + b_c >= 5:
            results.append(
                DigramShift(
                    digram=bi,
                    a_count=a_c,
                    b_count=b_c,
                    a_rate_per_10k=round(a_rate, 2),
                    b_rate_per_10k=round(b_rate, 2),
                    ratio=round(ratio, 2),
                )
            )

    return sorted(results, key=lambda d: -d.ratio)[:top_n]


def get_digram(shifts: List[DigramShift], digram: str) -> Optional[DigramShift]:
    """Find a specific digram in the shift list."""
    for s in shifts:
        if s.digram == digram:
            return s
    return None


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 3: Specific pattern tracking
#
# Classifier functions for known scribal patterns. Each returns
# a variant label for a token, or None if not relevant.
# ═══════════════════════════════════════════════════════════════


def _classify_eo_io(t: ScribalToken) -> Optional[str]:
    """Classify eo vs io diphthong usage in any word."""
    text = t.text.lower()
    if "io" in text:
        return "io"
    if "eo" in text:
        return "eo"
    return None


def _classify_self_sylf(t: ScribalToken) -> Optional[str]:
    """Classify self vs sylf in lemma 'self'."""
    if t.lemma != "self":
        return None
    text = t.text.lower()
    if "sylf" in text:
        return "sylf"
    if "self" in text or "seolf" in text:
        return "self"
    return None


def _classify_scolde_sceolde(t: ScribalToken) -> Optional[str]:
    """Classify scolde vs sceolde in lemma 'sculan'."""
    if t.lemma != "sculan":
        return None
    text = t.text.lower()
    if "sceold" in text:
        return "sceolde"
    if "scold" in text:
        return "scolde"
    return None


def _classify_gamol(t: ScribalToken) -> Optional[str]:
    """Classify gam* vs gom* in lemma 'gamol'."""
    if t.lemma != "gamol":
        return None
    text = t.text.lower()
    if text.startswith("gom") or text.startswith("gum"):
        return "gom"
    if text.startswith("gam") or text.startswith("gem"):
        return "gam"
    return None


def _classify_siththan(t: ScribalToken) -> Optional[str]:
    """Classify the wild spelling diversity of siððan."""
    if t.lemma != "siððan":
        return None
    return t.text.lower()


PATTERNS: Dict[str, Callable[[ScribalToken], Optional[str]]] = {
    "eo/io": _classify_eo_io,
    "self/sylf": _classify_self_sylf,
    "scolde/sceolde": _classify_scolde_sceolde,
    "gamol/gomel": _classify_gamol,
    "siððan variants": _classify_siththan,
}


def track_pattern(
    tokens: List[ScribalToken],
    classifier: Callable[[ScribalToken], Optional[str]],
) -> Dict[str, Dict[str, int]]:
    """Track a pattern across both scribes. Returns {scribe: {variant: count}}."""
    result: Dict[str, Dict[str, int]] = {"A": {}, "B": {}}
    for t in tokens:
        label = classifier(t)
        if label is not None:
            result[t.scribe][label] = result[t.scribe].get(label, 0) + 1
    return result


def track_all_patterns(
    tokens: List[ScribalToken],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Track all registered patterns. Returns {pattern_name: {scribe: {variant: count}}}."""
    return {name: track_pattern(tokens, clf) for name, clf in PATTERNS.items()}


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 4: Transition zone mapping
#
# For binary patterns, find where the dominant form crosses 50%
# using a sliding window. Records the transition line and overlap.
# ═══════════════════════════════════════════════════════════════


def find_transition_line(
    tokens: List[ScribalToken],
    classifier: Callable[[ScribalToken], Optional[str]],
    a_form: str,
    b_form: str,
) -> Optional[PatternTransition]:
    """Find where form A gives way to form B using optimal split point.

    Tries every possible line split and picks the one that maximizes
    correct classification (a_form before split, b_form after). This is
    robust to isolated outliers like a single 'sylfa' at line 505.
    """
    # Collect (line, label) pairs
    labeled = []
    for t in tokens:
        label = classifier(t)
        if label == a_form or label == b_form:
            labeled.append((t.line_id, label))
    labeled.sort(key=lambda x: x[0])

    if not labeled:
        return None

    # Find last occurrence of a_form and first occurrence of b_form
    a_lines = [line for line, label in labeled if label == a_form]
    b_lines = [line for line, label in labeled if label == b_form]

    if not a_lines or not b_lines:
        return None

    last_a = max(a_lines)
    first_b = min(b_lines)

    # Optimal split: try each gap between consecutive labeled items
    # and find the split that maximizes correct classifications
    # (a_form items before split + b_form items after split).
    total_b = len(b_lines)
    best_line = (last_a + first_b) // 2
    best_score = -1

    a_before = 0
    b_before = 0
    for i in range(len(labeled)):
        line, label = labeled[i]
        if label == a_form:
            a_before += 1
        else:
            b_before += 1

        # Split after this item (before the next)
        b_after = total_b - b_before
        score = a_before + b_after
        if score > best_score:
            best_score = score
            if i + 1 < len(labeled):
                best_line = (labeled[i][0] + labeled[i + 1][0]) // 2
            else:
                best_line = labeled[i][0]

    transition_line = best_line

    # Overlap: lines where both forms appear in the transition zone
    overlap = sorted(
        set(a_lines) & set(range(first_b, last_a + 1))
        | set(b_lines) & set(range(first_b, last_a + 1))
    )

    return PatternTransition(
        pattern_name=f"{a_form}/{b_form}",
        a_form=a_form,
        b_form=b_form,
        transition_line=transition_line,
        last_a_form_line=last_a,
        first_b_form_line=first_b,
        overlap_lines=overlap,
    )


def find_all_transitions(
    tokens: List[ScribalToken],
) -> Dict[str, PatternTransition]:
    """Find transition lines for all binary patterns."""
    transitions = {}

    configs = [
        ("self/sylf", _classify_self_sylf, "self", "sylf"),
        ("scolde/sceolde", _classify_scolde_sceolde, "scolde", "sceolde"),
        ("gamol/gomel", _classify_gamol, "gam", "gom"),
    ]

    for name, clf, a_form, b_form in configs:
        t = find_transition_line(tokens, clf, a_form, b_form)
        if t:
            t.pattern_name = name
            transitions[name] = t

    return transitions


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 5: Thorn/eth ratio curve
#
# Per-character þ/(þ+ð) ratio in sliding windows across the poem.
# Scribe A ratio > 0.5 (prefers þ), Scribe B ratio < 0.5 (prefers ð).
# ═══════════════════════════════════════════════════════════════


def thorn_eth_ratio_by_line_range(
    tokens: List[ScribalToken], window: int = 200, step: int = 50
) -> List[Tuple[int, int, float, int, int]]:
    """Compute þ/(þ+ð) ratio in sliding windows.

    Returns list of (start_line, end_line, ratio, thorn_count, eth_count).
    """
    # Build line -> (thorn_count, eth_count) mapping
    line_chars: Dict[int, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for t in tokens:
        text = t.text
        thorn = text.count("þ") + text.count("Þ")
        eth = text.count("ð") + text.count("Ð")
        if thorn or eth:
            old_t, old_e = line_chars[t.line_id]
            line_chars[t.line_id] = (old_t + thorn, old_e + eth)

    all_lines = sorted(line_chars.keys())
    if not all_lines:
        return []

    min_line = all_lines[0]
    max_line = all_lines[-1]

    results = []
    start = min_line
    while start + window <= max_line:
        end = start + window
        total_thorn = 0
        total_eth = 0
        for line in all_lines:
            if start <= line < end:
                t, e = line_chars[line]
                total_thorn += t
                total_eth += e
        total = total_thorn + total_eth
        ratio = total_thorn / total if total > 0 else 0.5
        results.append((start, end, ratio, total_thorn, total_eth))
        start += step

    return results


def thorn_eth_ratio_by_scribe(
    tokens: List[ScribalToken],
) -> Tuple[float, float]:
    """Compute overall þ/(þ+ð) ratio for each scribe. Returns (a_ratio, b_ratio)."""
    a_thorn = a_eth = b_thorn = b_eth = 0
    for t in tokens:
        text = t.text
        thorn = text.count("þ") + text.count("Þ")
        eth = text.count("ð") + text.count("Ð")
        if t.scribe == "A":
            a_thorn += thorn
            a_eth += eth
        else:
            b_thorn += thorn
            b_eth += eth

    a_total = a_thorn + a_eth
    b_total = b_thorn + b_eth
    a_ratio = a_thorn / a_total if a_total else 0.5
    b_ratio = b_thorn / b_total if b_total else 0.5
    return a_ratio, b_ratio


# ═══════════════════════════════════════════════════════════════
# MAIN: Run everything and print findings
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading Brunetti tokens...")
    raw = parse_brunetti_file()
    tokens = prepare_tokens(raw)
    a_tokens, b_tokens = split_by_scribe(tokens)
    print(f"  {len(tokens)} tokens total")
    print(f"  Scribe A (lines 1–{SCRIBE_BOUNDARY}): {len(a_tokens)} tokens")
    print(f"  Scribe B (lines {SCRIBE_BOUNDARY + 1}–end): {len(b_tokens)} tokens")

    # --- Analysis 1: Lemma-level spelling variants ---
    print("\n" + "=" * 65)
    print("ANALYSIS 1: Lemma-level Spelling Variants")
    print("=" * 65)
    variants = find_lemma_variants(tokens)
    print(f"  Lemmas with exclusive forms (min 3 each half): {len(variants)}")
    print("\n  Noteworthy variants:")
    for lemma_name in ["self", "sculan", "gamol", "Heorot", "Beowulf", "siððan"]:
        v = get_variant_for_lemma(variants, lemma_name)
        if v:
            print(f"\n  {v.lemma}:")
            print(f"    Scribe A forms: {dict(v.a_forms)}")
            print(f"    Scribe B forms: {dict(v.b_forms)}")
            if v.a_only:
                print(f"    A-only: {v.a_only}")
            if v.b_only:
                print(f"    B-only: {v.b_only}")

    # --- Analysis 2: Character bigram shifts ---
    print("\n" + "=" * 65)
    print("ANALYSIS 2: Character Bigram Frequency Shifts")
    print("=" * 65)
    shifts = compute_digram_shifts(tokens, top_n=30)
    print(
        f"\n  {'Bigram':<8} {'A count':>8} {'B count':>8} {'A/10k':>8} {'B/10k':>8} {'Ratio':>8}"
    )
    print("  " + "-" * 50)
    for s in shifts[:15]:
        favors = "← A" if s.a_rate_per_10k > s.b_rate_per_10k else "B →"
        print(
            f"  {s.digram:<8} {s.a_count:>8} {s.b_count:>8} "
            f"{s.a_rate_per_10k:>8.1f} {s.b_rate_per_10k:>8.1f} "
            f"{s.ratio:>7.1f}x {favors}"
        )

    # --- Analysis 3: Pattern tracking ---
    print("\n" + "=" * 65)
    print("ANALYSIS 3: Specific Pattern Tracking")
    print("=" * 65)
    all_patterns = track_all_patterns(tokens)
    for name, data in all_patterns.items():
        print(f"\n  {name}:")
        print(f"    Scribe A: {data['A']}")
        print(f"    Scribe B: {data['B']}")

    # --- Analysis 4: Transition zone mapping ---
    print("\n" + "=" * 65)
    print("ANALYSIS 4: Transition Zone Mapping")
    print("=" * 65)
    transitions = find_all_transitions(tokens)
    for name, tr in transitions.items():
        print(f"\n  {name}:")
        print(f"    Transition line: ~{tr.transition_line}")
        print(f"    Last '{tr.a_form}' at line {tr.last_a_form_line}")
        print(f"    First '{tr.b_form}' at line {tr.first_b_form_line}")
        if tr.overlap_lines:
            print(f"    Overlap lines: {tr.overlap_lines}")

    transition_lines = [tr.transition_line for tr in transitions.values()]
    if transition_lines:
        spread = max(transition_lines) - min(transition_lines)
        print(f"\n  All transition lines: {transition_lines}")
        print(f"  Spread: {spread} lines")
        print(f"  Range: {min(transition_lines)}–{max(transition_lines)}")

    # --- Analysis 5: Thorn/eth ratio ---
    print("\n" + "=" * 65)
    print("ANALYSIS 5: Thorn/Eth Ratio (þ vs ð)")
    print("=" * 65)
    a_ratio, b_ratio = thorn_eth_ratio_by_scribe(tokens)
    print(
        f"  Scribe A þ/(þ+ð) ratio: {a_ratio:.3f} (prefers {'þ' if a_ratio > 0.5 else 'ð'})"
    )
    print(
        f"  Scribe B þ/(þ+ð) ratio: {b_ratio:.3f} (prefers {'þ' if b_ratio > 0.5 else 'ð'})"
    )

    print("\n  Sliding window (200 lines, step 50):")
    curve = thorn_eth_ratio_by_line_range(tokens)
    for start, end, ratio, thorn, eth in curve:
        bar = "█" * int(ratio * 40)
        marker = " ◄ BOUNDARY" if start <= SCRIBE_BOUNDARY < end else ""
        print(f"    {start:4d}–{end:4d}: {ratio:.3f} {bar}{marker}")

    print("\n  Done. Data available for interactive exploration:")
    print("    tokens, a_tokens, b_tokens, variants, shifts,")
    print("    all_patterns, transitions, curve")
