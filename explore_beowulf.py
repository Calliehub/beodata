"""
---------------------------------------------------------------------------
Callie's Note: This file was written by Claude! (Opus 4.6) against v0.1.2
of the beodata project.

For the prompt that produced this file, see ./findings/explore_beowulf-0.1.2.md
---------------------------------------------------------------------------
Claude's work follows:

Exploratory analysis of the Beowulf text using beodata sources.

Run with: poetry run python -i explore_beowulf.py

Findings are captured as assertions in tests/test_explore_findings.py.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Tuple


def parse_brunetti_file() -> List[dict]:
    """Parse the raw Brunetti file into dicts without touching DuckDB."""
    from assets import get_asset_path

    COLS = [
        "fitt_id",
        "para_id",
        "para_first",
        "non_verse",
        "line_id",
        "half_line",
        "token_offset",
        "caesura_code",
        "pre_punc",
        "text",
        "post_punc",
        "syntax",
        "parse",
        "lemma",
        "pos",
        "inflection",
        "gloss",
        "with_length",
    ]
    tokens = []
    path = get_asset_path("brunetti-length.txt")
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            fields = line.split("|")
            if len(fields) < 18:
                continue
            row = {}
            for i, col in enumerate(COLS):
                row[col] = fields[i] if fields[i] else None
            tokens.append(row)
    return tokens


def parse_aligned_file() -> List[dict]:
    """Parse aligned_with_brunetti.txt into structured rows."""
    from assets import get_asset_path

    editions = ["mit", "mcmaster", "heorot", "ebeowulf", "perseus", "brunetti"]
    rows = []
    path = get_asset_path("aligned_with_brunetti.txt")
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(" ")
            if len(parts) != 12:
                continue
            row = {}
            for i, ed in enumerate(editions):
                row[f"{ed}_id"] = parts[i]
                row[f"{ed}_text"] = parts[i + 6]
            rows.append(row)
    return rows


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 1: The Two Scribes — Beowulf vs Biowulf
#
# The Cotton Vitellius A.xv manuscript was copied by two scribes.
# Their dialectal spelling preferences leave fingerprints in the
# text. The most visible: "eo" vs "io" in the hero's own name.
# ═══════════════════════════════════════════════════════════════


def analyze_scribal_hands(tokens: List[dict]) -> dict:
    """Track where the manuscript switches from Beowulf to Biowulf spelling."""
    beowulf_tokens = [t for t in tokens if t["lemma"] == "Beowulf"]

    # Classify each occurrence by its surface spelling
    eo_lines = []  # Lines where the text uses "eo" (Scribe A preference)
    io_lines = []  # Lines where the text uses "io" (Scribe B preference)

    for t in beowulf_tokens:
        line_num = int(t["line_id"])
        surface = t["text"] or ""
        if "io" in surface.lower():
            io_lines.append(line_num)
        elif "eo" in surface.lower():
            eo_lines.append(line_num)

    # Find the transition zone
    last_eo = max(eo_lines) if eo_lines else 0
    first_io = min(io_lines) if io_lines else 9999

    # There may be overlap — find the cleanest boundary
    # Where does Scribe B start consistently using "io"?
    transition_candidates = sorted(set(eo_lines + io_lines))

    return {
        "eo_count": len(eo_lines),
        "io_count": len(io_lines),
        "eo_range": (min(eo_lines), max(eo_lines)) if eo_lines else None,
        "io_range": (min(io_lines), max(io_lines)) if io_lines else None,
        "first_io_line": first_io,
        "last_eo_line": last_eo,
        "all_eo": sorted(eo_lines),
        "all_io": sorted(io_lines),
    }


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 2: Hapax Legomena
#
# Words appearing exactly once in the poem. OE poetry (especially
# Beowulf) is famous for its high rate of hapax legomena — unique
# compounds the poet may have invented on the spot.
# ═══════════════════════════════════════════════════════════════


def find_hapax_legomena(tokens: List[dict]) -> List[dict]:
    """Find lemmas that appear exactly once in the entire poem."""
    lemma_counts: Counter = Counter()
    lemma_to_token: Dict[str, dict] = {}

    for t in tokens:
        lemma = t["lemma"]
        if not lemma:
            continue
        lemma_counts[lemma] += 1
        if lemma not in lemma_to_token:
            lemma_to_token[lemma] = t

    hapaxes = []
    for lemma, count in lemma_counts.items():
        if count == 1:
            tok = lemma_to_token[lemma]
            hapaxes.append(
                {
                    "lemma": lemma,
                    "text": tok["text"],
                    "with_length": tok["with_length"],
                    "gloss": tok["gloss"],
                    "pos": tok["pos"],
                    "line_id": tok["line_id"],
                    "fitt_id": tok["fitt_id"],
                }
            )

    return sorted(hapaxes, key=lambda h: int(h["line_id"]))


def hapax_by_pos(hapaxes: List[dict]) -> Counter:
    """Which parts of speech are most likely to be hapax legomena?"""
    return Counter(h["pos"] for h in hapaxes if h["pos"])


def compound_hapaxes(hapaxes: List[dict]) -> List[dict]:
    """Hapax legomena that are compound words (contain a hyphen in the lemma)."""
    return [h for h in hapaxes if h["lemma"] and "-" in h["lemma"]]


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 3: Part-of-Speech Distribution
#
# What does the grammatical skeleton of Beowulf look like?
# How noun-heavy or verb-heavy is it compared to what you'd expect?
# ═══════════════════════════════════════════════════════════════

# Brunetti POS codes:
# m=masculine noun, f=feminine noun, n=neuter noun
# np=proper noun, v=verb, a=adjective, av=adverb
# p=pronoun, d=demonstrative, c=conjunction, pp=preposition
# nu=numeral, e=exclamation/interjection

POS_LABELS = {
    "m": "noun (masc)",
    "f": "noun (fem)",
    "n": "noun (neut)",
    "np": "proper noun",
    "v": "verb",
    "a": "adjective",
    "av": "adverb",
    "p": "pronoun",
    "d": "demonstrative",
    "c": "conjunction",
    "pp": "preposition",
    "nu": "numeral",
    "e": "interjection",
}


def pos_distribution(tokens: List[dict]) -> List[Tuple[str, str, int, float]]:
    """Count tokens by part of speech, return sorted (code, label, count, pct)."""
    counts = Counter(t["pos"] for t in tokens if t["pos"])
    total = sum(counts.values())
    results = []
    for code, count in counts.most_common():
        label = POS_LABELS.get(code, code)
        results.append((code, label, count, count / total * 100))
    return results


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 4: Cross-Edition Divergence
#
# Using the 6-way aligned text, find where editions disagree most.
# Not just punctuation — genuine textual variants where the
# editions read different *words*.
# ═══════════════════════════════════════════════════════════════


def edition_disagreements(aligned: List[dict]) -> dict:
    """Find rows where editions have genuinely different root words."""
    import re

    def normalize(text: str) -> str:
        """Strip punctuation and diacritics-ish chars for rough comparison."""
        text = text.lower()
        # Remove common OE punctuation variations
        text = re.sub(r"[.,;:!'·\[\](){}\"–—]", "", text)
        # Normalize some common spelling alternations
        text = text.replace("ð", "th").replace("þ", "th")
        text = text.replace("æ", "ae").replace("ǣ", "ae").replace("ā", "a")
        text = text.replace("ē", "e").replace("ī", "i").replace("ō", "o")
        text = text.replace("ū", "u").replace("ȳ", "y")
        return text.strip("_")

    editions = ["mit", "mcmaster", "heorot", "ebeowulf", "perseus", "brunetti"]
    divergent_rows = []

    for row in aligned:
        texts = []
        for ed in editions:
            t = row[f"{ed}_text"]
            if t != "@":
                texts.append(normalize(t))

        if len(texts) < 2:
            continue

        # Count unique normalized forms
        unique = set(texts)
        if len(unique) > 1:
            # Real divergence, not just punctuation/diacritic differences
            divergent_rows.append(
                {
                    "mit_id": row["mit_id"],
                    "texts": {ed: row[f"{ed}_text"] for ed in editions},
                    "unique_forms": len(unique),
                }
            )

    return {
        "total_rows": len(aligned),
        "divergent_count": len(divergent_rows),
        "divergent_pct": len(divergent_rows) / len(aligned) * 100,
        "worst": sorted(divergent_rows, key=lambda r: -r["unique_forms"])[:20],
    }


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 5: Vocabulary Density by Fitt
#
# Type-token ratio per fitt. Are some sections more repetitive
# (formulaic) and others more lexically inventive?
# ═══════════════════════════════════════════════════════════════


def vocabulary_density_by_fitt(tokens: List[dict]) -> List[dict]:
    """Compute type-token ratio (unique lemmas / total tokens) per fitt."""
    fitt_tokens: Dict[str, List[str]] = defaultdict(list)
    for t in tokens:
        if t["lemma"]:
            fitt_tokens[t["fitt_id"]].append(t["lemma"])

    results = []
    for fitt_id in sorted(fitt_tokens.keys()):
        lemmas = fitt_tokens[fitt_id]
        total = len(lemmas)
        unique = len(set(lemmas))
        results.append(
            {
                "fitt": int(fitt_id),
                "total_tokens": total,
                "unique_lemmas": unique,
                "ttr": unique / total if total else 0,
            }
        )

    return results


# ═══════════════════════════════════════════════════════════════
# ANALYSIS 6: Kennings and Compound Words
#
# OE poetry is famous for kennings — poetic compound metaphors.
# Brunetti marks compounds with hyphens in the lemma field.
# What semantic domains do they cluster in?
# ═══════════════════════════════════════════════════════════════


def analyze_compounds(tokens: List[dict]) -> dict:
    """Analyze compound words (hyphenated lemmas) in Beowulf."""
    compounds = [t for t in tokens if t["lemma"] and "-" in t["lemma"]]

    # Count unique compound lemmas
    lemma_counts = Counter(t["lemma"] for t in compounds)

    # What are the most common first elements? These reveal
    # the poet's favorite "building blocks" for compounds.
    first_elements = Counter()
    second_elements = Counter()
    for lemma in lemma_counts:
        parts = lemma.split("-")
        first_elements[parts[0]] += lemma_counts[lemma]
        second_elements[parts[-1]] += lemma_counts[lemma]

    # Group by gloss to find semantic clusters
    gloss_words = Counter()
    for t in compounds:
        if t["gloss"]:
            for word in t["gloss"].lower().split():
                gloss_words[word] += 1

    return {
        "total_compound_tokens": len(compounds),
        "unique_compounds": len(lemma_counts),
        "top_compounds": lemma_counts.most_common(20),
        "top_first_elements": first_elements.most_common(15),
        "top_second_elements": second_elements.most_common(15),
        "top_gloss_words": gloss_words.most_common(20),
    }


# ═══════════════════════════════════════════════════════════════
# MAIN: Run everything and print findings
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Loading Brunetti tokens...")
    tokens = parse_brunetti_file()
    print(f"  {len(tokens)} tokens\n")

    # --- Scribal hands ---
    print("=" * 60)
    print("ANALYSIS 1: The Two Scribes (Beowulf vs Biowulf)")
    print("=" * 60)
    hands = analyze_scribal_hands(tokens)
    print(
        f"  'Beowulf' (eo) spellings: {hands['eo_count']} "
        f"(lines {hands['eo_range'][0]}–{hands['eo_range'][1]})"
    )
    print(
        f"  'Biowulf' (io) spellings: {hands['io_count']} "
        f"(lines {hands['io_range'][0]}–{hands['io_range'][1]})"
    )
    print(
        f"  Last 'eo' at line {hands['last_eo_line']}, "
        f"first 'io' at line {hands['first_io_line']}"
    )
    # Show the transition zone in detail
    print("\n  Transition zone (lines 1900–2600):")
    for line in sorted(hands["all_eo"] + hands["all_io"]):
        if 1900 <= line <= 2600:
            spelling = "eo" if line in hands["all_eo"] else "io"
            print(f"    line {line}: {spelling}")

    # --- Hapax legomena ---
    print("\n" + "=" * 60)
    print("ANALYSIS 2: Hapax Legomena (words appearing exactly once)")
    print("=" * 60)
    hapaxes = find_hapax_legomena(tokens)
    print(f"  Total unique lemmas appearing only once: {len(hapaxes)}")
    total_lemmas = len(set(t["lemma"] for t in tokens if t["lemma"]))
    print(
        f"  Out of {total_lemmas} total unique lemmas "
        f"({len(hapaxes) / total_lemmas * 100:.1f}% are hapax)"
    )

    # POS breakdown of hapaxes
    hpos = hapax_by_pos(hapaxes)
    print("\n  Hapax legomena by part of speech:")
    for code, count in hpos.most_common():
        label = POS_LABELS.get(code, code)
        print(f"    {label:20s}: {count}")

    # Compound hapaxes — the poet's one-off inventions
    comp_hap = compound_hapaxes(hapaxes)
    print(f"\n  Compound hapaxes (hyphenated, appearing once): {len(comp_hap)}")
    print("  Sample compound hapaxes:")
    for h in comp_hap[:15]:
        print(f"    {h['lemma']:30s} '{h['gloss']}' (line {h['line_id']})")

    # --- POS distribution ---
    print("\n" + "=" * 60)
    print("ANALYSIS 3: Part-of-Speech Distribution")
    print("=" * 60)
    pos = pos_distribution(tokens)
    for code, label, count, pct in pos:
        print(f"  {label:20s}: {count:5d} ({pct:5.1f}%)")

    # --- Cross-edition divergence ---
    print("\n" + "=" * 60)
    print("ANALYSIS 4: Cross-Edition Divergence")
    print("=" * 60)
    print("  Loading aligned text...")
    aligned = parse_aligned_file()
    divs = edition_disagreements(aligned)
    print(f"  Total aligned rows: {divs['total_rows']}")
    print(
        f"  Rows with genuine divergence: {divs['divergent_count']} "
        f"({divs['divergent_pct']:.1f}%)"
    )
    print("\n  Most divergent rows (most unique readings):")
    for row in divs["worst"][:10]:
        print(f"    {row['mit_id']}: ", end="")
        texts = [f"{ed}={t}" for ed, t in row["texts"].items() if t != "@"]
        print(" | ".join(texts))

    # --- Vocabulary density by fitt ---
    print("\n" + "=" * 60)
    print("ANALYSIS 5: Vocabulary Density by Fitt (type-token ratio)")
    print("=" * 60)
    density = vocabulary_density_by_fitt(tokens)
    densest = sorted(density, key=lambda d: -d["ttr"])
    sparsest = sorted(density, key=lambda d: d["ttr"])
    print(f"  Most lexically dense (inventive) fitts:")
    for d in densest[:5]:
        print(
            f"    Fitt {d['fitt']:2d}: TTR={d['ttr']:.3f} "
            f"({d['unique_lemmas']}/{d['total_tokens']} tokens)"
        )
    print(f"  Most repetitive (formulaic) fitts:")
    for d in sparsest[:5]:
        print(
            f"    Fitt {d['fitt']:2d}: TTR={d['ttr']:.3f} "
            f"({d['unique_lemmas']}/{d['total_tokens']} tokens)"
        )

    # --- Compound words ---
    print("\n" + "=" * 60)
    print("ANALYSIS 6: Compound Words and Kennings")
    print("=" * 60)
    comps = analyze_compounds(tokens)
    print(f"  Total compound tokens: {comps['total_compound_tokens']}")
    print(f"  Unique compound lemmas: {comps['unique_compounds']}")
    print("\n  Most frequent compounds:")
    for lemma, count in comps["top_compounds"]:
        print(f"    {lemma:30s}: {count}")
    print("\n  Most productive first elements (compound prefixes):")
    for elem, count in comps["top_first_elements"]:
        print(f"    {elem:20s}: {count} occurrences")
    print("\n  Most productive second elements (compound suffixes):")
    for elem, count in comps["top_second_elements"]:
        print(f"    {elem:20s}: {count} occurrences")
    print("\n  Top semantic domains in compound glosses:")
    for word, count in comps["top_gloss_words"][:15]:
        print(f"    {word:20s}: {count}")
